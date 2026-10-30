import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api.session_manager import InterviewSession, session_manager
from core.config import APP_SESSION_TOKEN
from services.context_manager import PersistentContextManager
from services.stt_service import DeepgramManager


@pytest.fixture(autouse=True)
def isolated_records(tmp_path, monkeypatch):
    monkeypatch.setattr('services.session_store.EXPORTS_PATH', tmp_path)


@pytest.mark.asyncio
async def test_finalize_preserves_last_speech_and_answers():
    session = session_manager.create_session()
    session.auto_answer_enabled = False
    session._send_json = AsyncMock(return_value=True)
    async def flush():
        await session.on_transcript({'transcript': 'Final statement', 'is_final': True, 'speaker_role': 'interviewer'})
    session.stt_manager = SimpleNamespace(flush=flush, finish=AsyncMock())
    await session._record_event('answer', 'Earlier answer', question='Earlier question', success=True)
    result = await session.finalize()
    assert result['record']['status'] == 'completed'
    assert [event['text'] for event in result['record']['events']] == ['Earlier answer', 'Final statement']
    assert session.session_id not in session_manager.active_sessions


@pytest.mark.asyncio
async def test_failed_finalize_stops_resources_and_is_retryable(monkeypatch):
    session = session_manager.create_session()
    session.stt_manager = SimpleNamespace(finish=AsyncMock())
    await session._record_event('transcript', 'Keep this', speaker='interviewer')
    from services.session_store import save_session
    monkeypatch.setattr('api.session_manager.save_session', lambda record: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):
        await session.finalize()
    assert not session.is_active
    assert session_manager.active_sessions[session.session_id] is session
    assert session.get_record()['events'][0]['text'] == 'Keep this'
    session.stt_manager.finish.assert_awaited()
    monkeypatch.setattr('api.session_manager.save_session', save_session)
    assert (await session.finalize())['success']


@pytest.mark.asyncio
async def test_canceled_checkpoint_cannot_overwrite_later_record(monkeypatch):
    session = InterviewSession('write-order')
    entered, release = threading.Event(), threading.Event()
    from services.session_store import save_session, load_session
    def blocked_save(record):
        if record['status'] == 'ready':
            entered.set()
            assert release.wait(2)
        return save_session(record)
    monkeypatch.setattr('api.session_manager.save_session', blocked_save)
    first = asyncio.create_task(session._checkpoint())
    assert await asyncio.to_thread(entered.wait, 1)
    first.cancel()
    session.status = 'completed'
    second = asyncio.create_task(session._checkpoint())
    await asyncio.sleep(0)
    assert not second.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await first
    await second
    assert load_session(session.session_id)['status'] == 'completed'


@pytest.mark.asyncio
async def test_vision_context_and_error_status_are_session_owned():
    first, second = InterviewSession('first'), InterviewSession('second')
    first_context, second_context = PersistentContextManager(), PersistentContextManager()
    first.vision_service.set_context_manager(first_context)
    second.vision_service.set_context_manager(second_context)
    assert first.vision_service.context_manager is first_context
    assert second.vision_service.context_manager is second_context
    first._send_json = AsyncMock(return_value=True)
    first.vision_service.analyze_coding_problem = AsyncMock(return_value=('Failure', {'error': 'invalid_screenshot'}))
    await first.handle_vision_analysis({'screenshots': ['invalid'], 'visionConfig': {'provider': 'P', 'model': 'M'}})
    payload = first._send_json.await_args.args[1]
    assert payload['success'] is False
    assert first.events[-1]['success'] is False


@pytest.mark.asyncio
async def test_language_reconnect_uses_new_language():
    manager = DeepgramManager(AsyncMock())
    languages = []
    async def connect():
        languages.append(manager.language)
    manager._connect_once = connect
    await manager.set_language('multi')
    assert manager.language == 'multi' and languages == ['multi']


@pytest.mark.asyncio
async def test_session_language_updates_both_sources():
    session = InterviewSession('language')
    session.stt_manager = SimpleNamespace(set_language=AsyncMock())
    session.mic_stt_manager = SimpleNamespace(set_language=AsyncMock())
    session._send_json = AsyncMock()
    await session.handle_config_update({'sttLanguage': 'multi'})
    session.stt_manager.set_language.assert_awaited_once_with('multi')
    session.mic_stt_manager.set_language.assert_awaited_once_with('multi')
    assert session.stt_language == 'multi'


def test_websocket_requires_token_even_without_origin():
    from main import app
    from starlette.websockets import WebSocketDisconnect
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/ws'):
                pass
        with client.websocket_connect('/ws', subprotocols=['superassist', APP_SESSION_TOKEN]) as websocket:
            assert websocket.accepted_subprotocol == 'superassist'
            assert websocket.receive_json()['type'] == 'session_created'


@pytest.mark.parametrize('origin', ['http://testserver:8019', 'https://testserver', 'http://testserver.evil', 'null'])
def test_api_and_websocket_reject_other_origins(origin):
    from main import app
    from starlette.websockets import WebSocketDisconnect
    with TestClient(app, headers={'X-App-Token': APP_SESSION_TOKEN}) as client:
        assert client.get('/api/sessions', headers={'Origin': origin}).status_code == 403
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/ws', headers={'Origin': origin}):
                pass
