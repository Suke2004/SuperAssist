"""Typed questions and manual answering reuse the live interview pipeline."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.session_manager import InterviewSession, TRANSCRIPT_BUFFER_MAX_CHARS
from core.prompts import get_interview_answer_prompt, get_quick_response_prompt
from services.context_manager import PersistentContextManager


@pytest.fixture
def session():
    session = InterviewSession("controls-test")
    session.is_active = True
    session.websocket = object()
    session._send_json = AsyncMock(return_value=True)

    async def answer(question, callback, generate_full_answers=None):
        await callback("Answer", "content")
        return "Answer", {"success": True}

    session.llm_manager = MagicMock()
    session.llm_manager.get_ai_answer = AsyncMock(side_effect=answer)
    session.llm_manager.close = AsyncMock()
    return session


async def finish_answers(session):
    await asyncio.gather(*list(session._answer_tasks))


@pytest.mark.asyncio
async def test_manual_mode_keeps_transcription_and_waits_for_answer_request(session):
    await session.handle_set_auto_answer({"enabled": False})
    await session.on_transcript({"transcript": "Explain two sum?", "is_final": True})
    assert session.silence_timer is None
    assert session.transcript_buffer == "Explain two sum?"
    session.llm_manager.get_ai_answer.assert_not_awaited()
    session._send_json.assert_any_await("transcript_update", {"transcript": "Explain two sum?", "is_final": True, "speaker_role": "interviewer"})
    session._send_json.assert_any_await("auto_answer_status", {"enabled": False})

    await session.handle_request_answer({})
    await finish_answers(session)
    assert session.transcript_buffer == ""
    assert session.llm_manager.get_ai_answer.await_args.args[0] == "Explain two sum?"
    session._send_json.assert_any_await("ai_answer_chunk", {"chunk": "Answer", "chunk_type": "content"})


@pytest.mark.asyncio
async def test_manual_mode_records_candidate_as_context_not_pending_question(session):
    await session.handle_set_auto_answer({"enabled": False})
    session.hint_timeline.append((time.time(), True))
    await session.on_transcript({"transcript": "I used a hash map.", "is_final": True})
    assert session.transcript_buffer == ""
    session.llm_manager.process_candidate_response.assert_called_once_with("I used a hash map.")
    assert session.transcript_log[-1]["speaker"] == "candidate"
    session._send_json.assert_any_await("transcript_update", {"transcript": "I used a hash map.", "is_final": True, "speaker_role": "candidate"})


@pytest.mark.asyncio
async def test_typed_question_streams_without_consuming_pending_transcript(session):
    session.transcript_buffer = "Pending interviewer question?"
    await session.handle_ask_question({"question": "  What is a heap?  "})
    await finish_answers(session)
    assert session.llm_manager.get_ai_answer.await_args.args[0] == "What is a heap?"
    assert session.transcript_buffer == "Pending interviewer question?"
    session._send_json.assert_any_await("ai_processing_started", {"question": "What is a heap?", "mode": "full"})
    session._send_json.assert_any_await("ai_answer_complete", {"answer": "Answer", "success": True})


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"question": " "}, {"question": 3}, {"question": "x" * 4001}, []])
async def test_invalid_typed_question_never_reaches_engine(session, payload):
    await session.handle_ask_question(payload)
    assert session._send_json.await_args.args[0] == "error"
    assert not session._answer_tasks
    session.llm_manager.get_ai_answer.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", ["false", 0, None])
async def test_auto_answer_requires_boolean(session, enabled):
    await session.handle_set_auto_answer({"enabled": enabled})
    assert session.auto_answer_enabled is True
    assert session._send_json.await_args.args[0] == "error"


@pytest.mark.asyncio
async def test_enabling_auto_answer_processes_buffer_once(session):
    await session.handle_set_auto_answer({"enabled": False})
    await session.on_transcript({"transcript": "Explain a heap?", "is_final": True})
    await session.handle_set_auto_answer({"enabled": True})
    await finish_answers(session)
    session.llm_manager.get_ai_answer.assert_awaited_once()
    assert session.transcript_buffer == ""


@pytest.mark.asyncio
async def test_disabling_auto_answer_preserves_a_queued_automatic_question(session):
    session.transcript_buffer = "Explain a heap?"
    await session.handle_set_auto_answer({"enabled": True})
    await session.handle_set_auto_answer({"enabled": False})
    await finish_answers(session)
    session.llm_manager.get_ai_answer.assert_not_awaited()
    assert session.transcript_buffer == "Explain a heap?"


@pytest.mark.asyncio
async def test_automatic_answer_uses_existing_silence_timer(session):
    await session.on_transcript({"transcript": "Explain a heap?", "is_final": True, "speech_final": True})
    await asyncio.wait_for(session.silence_timer, 2)
    session.llm_manager.get_ai_answer.assert_awaited_once()
    assert session.silence_timer is None


@pytest.mark.asyncio
async def test_pause_and_imperfect_english_are_combined_before_answering(session):
    await session.on_transcript({'transcript': 'You explain cache?', 'is_final': True,
                                 'speech_final': False, 'last_word_end': 2.0})
    timer = session.silence_timer
    await asyncio.sleep(0.8)  # Previously answered this incomplete fragment after 400ms.
    session.llm_manager.get_ai_answer.assert_not_awaited()
    await session.on_transcript({'transcript': 'when many user coming', 'is_final': False,
                                 'last_word_end': 3.0})
    await asyncio.gather(timer, return_exceptions=True)
    assert timer.cancelled() and session.silence_timer is None
    await session.on_transcript({'type': 'utterance_end', 'last_word_end': 2.0})
    assert session.silence_timer is None
    await session.on_transcript({'transcript': 'when many user coming how keep database fresh',
        'is_final': True, 'speech_final': True, 'last_word_end': 5.0})
    await asyncio.wait_for(session.silence_timer, 2)
    session.llm_manager.get_ai_answer.assert_awaited_once()
    assert session.llm_manager.get_ai_answer.await_args.args[0] == (
        'You explain cache? when many user coming how keep database fresh')


@pytest.mark.asyncio
async def test_speech_start_cancels_endpoint_and_old_boundary(session):
    await session.on_transcript({'transcript': 'Design an API', 'is_final': True,
                                 'speech_final': True, 'last_word_end': 2.0})
    timer = session.silence_timer
    await session.on_transcript({'type': 'speech_started', 'timestamp': 2.5})
    await asyncio.gather(timer, return_exceptions=True)
    await session.on_transcript({'type': 'utterance_end', 'last_word_end': 2.0})
    assert session.silence_timer is None
    session.llm_manager.get_ai_answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_utterance_end_processes_finalized_segments_once(session):
    await session.on_transcript({'transcript': 'How this work', 'is_final': True})
    await session.on_transcript({'type': 'utterance_end', 'last_word_end': 2.0})
    await asyncio.wait_for(session.silence_timer, 2)
    await session.on_transcript({'type': 'utterance_end', 'last_word_end': 2.0})
    assert session.silence_timer is None
    session.llm_manager.get_ai_answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_microphone_events_do_not_cancel_interviewer_question(session):
    session.state['process_all_speakers'] = False
    await session._system_transcript({'transcript': 'Explain caching', 'is_final': True,
                                      'speech_final': True})
    timer = session.silence_timer
    await session._microphone_transcript({'type': 'speech_started', 'timestamp': 0.0})
    assert session.silence_timer is timer and not timer.cancelled()
    await asyncio.wait_for(timer, 2)
    session.llm_manager.get_ai_answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_continued_speech_cancels_queued_answer_but_keeps_started_stream(session):
    await session._answer_lock.acquire()
    await session.on_transcript({'transcript': 'Explain cache', 'is_final': True, 'speech_final': True})
    queued = session.silence_timer
    await asyncio.sleep(.4)
    await session.on_transcript({'transcript': 'when updates happen', 'is_final': False})
    await asyncio.gather(queued, return_exceptions=True)
    session._answer_lock.release()
    assert queued.cancelled() and session.transcript_buffer == 'Explain cache'
    session.llm_manager.get_ai_answer.assert_not_awaited()

    entered, release = asyncio.Event(), asyncio.Event()
    async def answer(*args, **kwargs):
        entered.set()
        await release.wait()
        return 'Answer', {'success': True}
    session.llm_manager.get_ai_answer.side_effect = answer
    await session.on_transcript({'type': 'utterance_end', 'last_word_end': 5.0})
    active = session.silence_timer
    await asyncio.wait_for(entered.wait(), 2)
    assert session.silence_timer is None
    await session.on_transcript({'type': 'speech_started', 'timestamp': 6.0})
    assert not active.cancelled()
    release.set()
    await asyncio.wait_for(active, 2)


@pytest.mark.asyncio
async def test_disabling_auto_answer_cancels_pending_timer_without_losing_transcript(session):
    await session.on_transcript({"transcript": "Explain a heap?", "is_final": True})
    timer = session.silence_timer
    await session.handle_set_auto_answer({"enabled": False})
    await asyncio.gather(timer, return_exceptions=True)
    assert timer.cancelled()
    assert session.transcript_buffer == "Explain a heap?"
    session.llm_manager.get_ai_answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_buffer_is_bounded(session):
    await session.handle_set_auto_answer({"enabled": False})
    await session.on_transcript({"transcript": "x" * 5000, "is_final": True})
    assert len(session.transcript_buffer) == TRANSCRIPT_BUFFER_MAX_CHARS


@pytest.mark.asyncio
async def test_question_requires_active_unpaused_session(session):
    session.is_active = False
    await session.handle_ask_question({"question": "What is a heap?"})
    assert session._send_json.await_args.args[0] == "error"
    session.is_active = True
    session.state["is_universally_muted"] = True
    await session.handle_ask_question({"question": "What is a heap?"})
    assert session._send_json.await_args.args[0] == "error"
    session.llm_manager.get_ai_answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_cleanup_cancels_queued_typed_answer(session):
    entered = asyncio.Event()

    async def wait_for_answer(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    session.llm_manager.get_ai_answer.side_effect = wait_for_answer
    await session.handle_ask_question({"question": "Explain a heap?"})
    await asyncio.wait_for(entered.wait(), 2)
    tasks = list(session._answer_tasks)
    await session.cleanup()
    assert all(task.cancelled() for task in tasks)
    assert not session._answer_tasks
    session.llm_manager.close.assert_awaited_once()


def test_custom_preferences_reach_full_and_quick_prompts():
    context = PersistentContextManager()
    context.initialize_persistent_context({"instructions": "Use concise examples from backend engineering."})
    for builder in (get_interview_answer_prompt, get_quick_response_prompt):
        assert "Use concise examples from backend engineering." in builder("What is a heap?", context)


@pytest.mark.asyncio
async def test_provider_metadata_exposes_key_presence_without_secrets(tmp_path, monkeypatch):
    from api import config_api

    path = tmp_path / "ai_providers.json"
    path.write_text(json.dumps([
        {"name": "Groq", "apiKeys": ["YOUR_GROQ_KEY", "real-key"]},
        {"name": "OpenRouter", "apiKey": "YOUR_OPENROUTER_KEY"},
        {"name": "Cerebras", "apiKey": "real-key", "defaultVisionSecondary": True},
    ]), encoding="utf-8")
    monkeypatch.setattr(config_api, "AI_PROVIDERS_PATH", path)
    providers = await config_api.get_ai_providers()
    assert [provider["hasUsableKey"] for provider in providers] == [True, False, True]
    assert providers[-1]["defaultVisionSecondary"] is False
    assert "real-key" not in json.dumps(providers)
