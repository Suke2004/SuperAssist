"""Capture isolation, bounded recovery and loss reporting without cloud requests."""
import asyncio
import time
from array import array
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.session_manager import InterviewSession
from services.native_audio import NativeLoopback, mono_pcm
from services.stt_service import DeepgramManager
from deepgram import LiveTranscriptionEvents


def test_loopback_downmix_preserves_pcm_and_does_not_overflow():
    stereo = array('h', [32767, 32767, -32768, -32768, 1000, -1000]).tobytes()
    assert array('h', mono_pcm(stereo, 2)).tolist() == [32767, -32768, 0]
    assert mono_pcm(stereo, 1) == stereo


@pytest.mark.asyncio
async def test_capture_queue_is_bounded_and_stopped_capture_discards_callbacks():
    capture = NativeLoopback(AsyncMock(), AsyncMock())
    for i in range(105):
        capture._enqueue(bytes([i]))
    assert capture.queue.qsize() == 100
    assert capture.dropped == 5
    assert capture.queue.get_nowait() == b'\x05'
    capture.paused = True
    capture._enqueue(b'private')
    assert capture.queue.qsize() == 99
    await capture.finish()
    capture._enqueue(b'late')
    assert capture.queue.empty()


@pytest.mark.asyncio
async def test_native_capture_retries_device_open_and_reports_failure(monkeypatch):
    capture = NativeLoopback(AsyncMock(), AsyncMock())
    capture.stream = MagicMock()
    capture.stream.is_active.return_value = False
    capture._close = MagicMock()
    capture.open = AsyncMock(side_effect=OSError('device removed'))
    monkeypatch.setattr('services.native_audio.asyncio.sleep', AsyncMock())
    await capture._consume()
    assert capture.open.await_count == 3
    capture.on_status.assert_any_await('failed', 'device removed')


@pytest.mark.asyncio
async def test_native_audio_routes_microphone_separately_and_drops_browser_system_mix():
    session = InterviewSession('native-routing')
    session.audio_capture_mode = 'native'
    session.stt_manager = MagicMock(send_audio=AsyncMock())
    session.mic_stt_manager = MagicMock(send_audio=AsyncMock())
    await session.handle_binary_audio(b'\x01\x00\x01\x02')
    await session.handle_binary_audio(b'\x02\x00\x03\x04')
    session.mic_stt_manager.send_audio.assert_awaited_once_with(b'\x01\x02')
    session.stt_manager.send_audio.assert_not_awaited()
    session.is_active = True
    await session._send_native_audio(b'\x05\x06')
    session.stt_manager.send_audio.assert_awaited_once_with(b'\x05\x06')
    session.state['is_universally_muted'] = True
    await session._send_native_audio(b'\x07\x08')
    assert session.stt_manager.send_audio.await_count == 1


@pytest.mark.asyncio
async def test_explicit_native_speaker_overrides_recent_microphone_dominance():
    session = InterviewSession('native-speaker')
    session.hint_timeline.append((time.time(), True))
    session.auto_answer_enabled = False
    session._send_json = AsyncMock()
    await session._system_transcript({'transcript': 'Explain caching?', 'is_final': True})
    assert session.transcript_log[-1]['speaker'] == 'interviewer'
    session._send_json.assert_any_await('transcript_update', {
        'transcript': 'Explain caching?', 'is_final': True, 'speaker_role': 'interviewer', 'source': 'system'})


@pytest.mark.asyncio
async def test_failed_send_keeps_fifo_and_starts_recovery_once():
    manager = DeepgramManager(AsyncMock())
    manager._reconnect = AsyncMock()
    connection = AsyncMock()
    connection.send.side_effect = [ConnectionError('offline'), None, None]
    manager.dg_connection = connection
    manager.is_connected = True
    await manager.send_audio(b'first')
    await manager.send_audio(b'second')
    assert list(manager.audio_ring_buffer) == [b'first', b'second']
    await asyncio.sleep(0)
    manager._reconnect.assert_awaited_once()
    await manager.on_open()
    assert [call.args[0] for call in connection.send.await_args_list] == [b'first', b'first', b'second']
    assert not manager.audio_ring_buffer


@pytest.mark.asyncio
async def test_buffer_duration_and_expiry_do_not_depend_on_frame_size():
    manager = DeepgramManager(AsyncMock(), sample_rate=44100)
    for i in range(6):
        await manager.send_audio(bytes([i]) * 88200)
    assert sum(map(len, manager.audio_ring_buffer)) == 4 * 88200
    assert manager.audio_ring_buffer[0][0] == 2
    manager._last_audio_at = time.monotonic() - 5
    manager.dg_connection = AsyncMock()
    await manager.on_open()
    manager.dg_connection.send.assert_not_awaited()
    assert not manager.audio_ring_buffer


@pytest.mark.asyncio
async def test_cleanup_closes_other_resources_when_one_audio_device_fails():
    session = InterviewSession('cleanup')
    session.native_audio = MagicMock(finish=AsyncMock(side_effect=OSError('removed')))
    microphone = session.mic_stt_manager = MagicMock(finish=AsyncMock())
    session.stt_manager = MagicMock(finish=AsyncMock())
    session.llm_manager = MagicMock(close=AsyncMock())
    await session.cleanup()
    microphone.finish.assert_awaited_once()
    session.stt_manager.finish.assert_awaited_once()
    session.llm_manager.close.assert_awaited_once()
    assert session.native_audio is None and not session.is_active


@pytest.mark.asyncio
async def test_late_close_from_replaced_connection_cannot_disconnect_the_new_one():
    manager = DeepgramManager(AsyncMock())
    manager._reconnect = AsyncMock()
    first = MagicMock(start=AsyncMock(return_value=True), finish=AsyncMock())
    second = MagicMock(start=AsyncMock(return_value=True), finish=AsyncMock())
    manager.deepgram = MagicMock()
    manager.deepgram.listen.asynclive.v.side_effect = [first, second]
    await manager._connect_once()
    await manager._connect_once()
    old_close = next(call.args[1] for call in first.on.call_args_list if call.args[0] == LiveTranscriptionEvents.Close)
    await old_close()
    assert manager.is_connected and manager.dg_connection is second
    manager._reconnect.assert_not_awaited()
    first.finish.assert_awaited_once()
    assert second.start.await_args.args[0].sample_rate == 48000


@pytest.mark.asyncio
async def test_transcription_sdk_false_start_is_a_real_failure():
    manager = DeepgramManager(AsyncMock())
    manager.deepgram = MagicMock()
    manager.deepgram.listen.asynclive.v.return_value = MagicMock(start=AsyncMock(return_value=False))
    with pytest.raises(ConnectionError):
        await manager._connect_once()
    assert not manager.is_connected


@pytest.mark.asyncio
async def test_native_silence_reaches_stt_without_capturing_paused_audio(monkeypatch):
    capture = NativeLoopback(AsyncMock(), AsyncMock())
    capture.sample_rate = 44100
    capture.stream = MagicMock()

    async def timeout(*args, **kwargs):
        args[0].close()
        capture.stopped = True
        raise asyncio.TimeoutError

    monkeypatch.setattr('services.native_audio.asyncio.wait_for', timeout)
    await capture._consume()
    capture.on_audio.assert_awaited_once_with(bytes(44100))
    capture.on_status.assert_awaited_once_with('waiting', '')
    capture.stopped = False
    capture.paused = True
    capture.on_audio.reset_mock()
    await capture._consume()
    capture.on_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_output_starts_without_a_microphone_transcription_connection(monkeypatch):
    session = InterviewSession('system-only')
    session.audio_capture_mode = 'native'
    session.microphone_available = False
    manager = MagicMock(start=AsyncMock(), send_audio=AsyncMock())
    factory = MagicMock(return_value=manager)
    capture = MagicMock(open=AsyncMock(), sample_rate=48000)
    monkeypatch.setattr('api.session_manager.DeepgramManager', factory)
    monkeypatch.setattr('services.native_audio.NativeLoopback', MagicMock(return_value=capture))
    monkeypatch.setattr('services.portable_audio.PortableCapture', MagicMock(return_value=capture))
    monkeypatch.setattr('api.session_manager.MultiLLMManager', MagicMock())
    monkeypatch.setattr('api.session_manager.VisionService.set_context_manager', MagicMock())
    monkeypatch.setattr('api.session_manager.VisionService.load_vision_providers', MagicMock())
    await session.initialize_managers({}, None, None, None, {})
    assert session.is_active and session.stt_manager is manager and session.mic_stt_manager is None
    factory.assert_called_once()
    manager.start.assert_awaited_once()
    await session._send_native_audio(b'\x01\x02')
    manager.send_audio.assert_awaited_once_with(b'\x01\x02')


@pytest.mark.asyncio
async def test_native_playback_status_reports_signal_without_changing_pcm():
    capture = NativeLoopback(AsyncMock(), AsyncMock())
    capture.stream = MagicMock()
    capture.channels = 1
    capture.name = 'Headphones'
    pcm = array('h', [100, -100, 0]).tobytes()
    capture.queue.put_nowait(pcm)

    async def stop_after_audio(data):
        capture.stopped = True

    capture.on_audio.side_effect = stop_after_audio
    await capture._consume()
    capture.on_audio.assert_awaited_once_with(pcm)
    capture.on_status.assert_awaited_once_with('receiving', 'Headphones')


@pytest.mark.asyncio
async def test_stt_uses_balanced_keyterms_and_speech_events_without_blind_replacement():
    manager = DeepgramManager(AsyncMock(), user_languages=['SQL', 'Python'])
    connection = MagicMock(start=AsyncMock(return_value=True))
    manager.deepgram = MagicMock()
    manager.deepgram.listen.asynclive.v.return_value = connection
    await manager._connect_once()
    options = connection.start.await_args.args[0]
    assert options.model == 'nova-3' and options.replace is None
    assert options.keyterm[0] == 'SQL'
    assert {'PostgreSQL', 'distributed systems', 'two sum', 'Python'} <= set(options.keyterm)
    assert len(options.keyterm) == len({term.casefold() for term in options.keyterm}) <= 75
    events = {call.args[0] for call in connection.on.call_args_list}
    assert {LiveTranscriptionEvents.SpeechStarted, LiveTranscriptionEvents.UtteranceEnd} <= events
    assert options.endpointing == 1000 and options.utterance_end_ms == '1500'


@pytest.mark.asyncio
async def test_stt_preserves_raw_words_confidence_and_empty_endpoint():
    callback = AsyncMock()
    manager = DeepgramManager(callback)
    alternative = SimpleNamespace(transcript='to sum up my project', confidence=0.72,
                                  words=[SimpleNamespace(end=3.5)])
    result = SimpleNamespace(channel=SimpleNamespace(alternatives=[alternative]),
                             is_final=True, speech_final=False)
    await manager.on_message(result=result)
    callback.assert_awaited_with({'speaker': 0, 'transcript': 'to sum up my project',
        'is_final': True, 'speech_final': False, 'confidence': 0.72, 'last_word_end': 3.5})
    alternative.transcript = ''
    result.speech_final = True
    await manager.on_message(result=result)
    assert callback.await_args.args[0]['type'] == 'utterance_end'
    await manager.on_speech_started(speech_started=SimpleNamespace(timestamp=4.2))
    callback.assert_awaited_with({'type': 'speech_started', 'timestamp': 4.2})
    await manager.on_utterance_end(utterance_end=SimpleNamespace(last_word_end=5.1))
    callback.assert_awaited_with({'type': 'utterance_end', 'last_word_end': 5.1})
