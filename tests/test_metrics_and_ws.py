"""Tests for metrics, WS origin check, and delayed session cleanup."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.metrics import Metrics, app_metrics
from api.session_manager import InterviewSession, SessionManager
from api.websocket import _origin_host_is_local


class TestMetrics:
    def test_snapshot_has_known_counters(self):
        snap = Metrics().snapshot()
        for name in ("questions_answered", "fallbacks_used", "key_rotations"):
            assert name in snap["counters"]

    def test_inc_unknown_counter_on_the_fly(self):
        m = Metrics()
        m.inc("brand_new_counter", 3)
        assert m.snapshot()["counters"]["brand_new_counter"] == 3

    def test_provider_errors_are_attributed(self):
        m = Metrics()
        m.provider_error("Groq")
        m.provider_error("Groq")
        m.provider_error("Cerebras")
        snap = m.snapshot()
        assert snap["provider_errors"]["Groq"] == 2
        assert snap["provider_errors"]["Cerebras"] == 1

    def test_latency_percentiles(self):
        m = Metrics()
        for value in [10, 20, 30, 40, 100]:
            m.record_answer_latency(value)
        lat = m.snapshot()["answer_latency_ms"]
        assert lat["count"] == 5
        assert lat["p50"] == 30
        assert lat["max"] == 100

    def test_never_raises_on_bad_input(self):
        m = Metrics()
        m.record_answer_latency("not-a-number")
        m.record_answer_latency(-5)
        m.provider_error(None)
        assert m.snapshot()["answer_latency_ms"]["count"] == 0

    def test_global_singleton_records(self):
        before = app_metrics.snapshot()["counters"]["ws_disconnects"]
        app_metrics.inc("ws_disconnects")
        after = app_metrics.snapshot()["counters"]["ws_disconnects"]
        assert after == before + 1


class FakeHeadersWebSocket:
    """Minimal duck-type of fastapi WebSocket for the origin check."""

    def __init__(self, headers):
        self.headers = headers


class TestOriginCheck:
    def test_same_origin_allowed(self):
        ws = FakeHeadersWebSocket({"origin": "http://127.0.0.1:8002", "host": "127.0.0.1:8002"})
        assert _origin_host_is_local(ws) is True

    def test_missing_origin_allowed(self):
        # Non-browser clients (pywebview builds, tests) send no Origin
        ws = FakeHeadersWebSocket({"host": "127.0.0.1:8002"})
        assert _origin_host_is_local(ws) is True

    def test_foreign_origin_rejected(self):
        ws = FakeHeadersWebSocket({"origin": "https://evil.example.com", "host": "127.0.0.1:8002"})
        assert _origin_host_is_local(ws) is False

    def test_localhost_vs_127_rejected(self):
        # A webpage on localhost attacking the 127.0.0.1-bound server
        ws = FakeHeadersWebSocket({"origin": "http://localhost:8002", "host": "127.0.0.1:8002"})
        assert _origin_host_is_local(ws) is False

    def test_malformed_origin_rejected(self):
        ws = FakeHeadersWebSocket({"origin": "::::not-a-url", "host": "127.0.0.1:8002"})
        assert _origin_host_is_local(ws) is False


class TestDelayedCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_fires_after_grace(self):
        sm = SessionManager()
        session = sm.create_session()
        sm.schedule_delayed_cleanup(session.session_id, 0.05)

        await asyncio.sleep(0.15)
        assert session.session_id not in sm.active_sessions

    @pytest.mark.asyncio
    async def test_cleanup_cancelled_on_resume(self):
        sm = SessionManager()
        session = sm.create_session()
        sm.schedule_delayed_cleanup(session.session_id, 0.05)

        # Client reconnects — the resume path cancels the pending cleanup
        session.cancel_delayed_cleanup()
        await asyncio.sleep(0.15)
        assert session.session_id in sm.active_sessions

    @pytest.mark.asyncio
    async def test_reschedule_cancels_previous_task(self):
        sm = SessionManager()
        session = sm.create_session()
        sm.schedule_delayed_cleanup(session.session_id, 10)   # long
        sm.schedule_delayed_cleanup(session.session_id, 0.05)  # replaces it
        await asyncio.sleep(0.15)
        assert session.session_id not in sm.active_sessions


def test_stale_socket_disconnect_does_not_clear_new_socket():
    session = InterviewSession("socket-race")
    stale_socket = object()
    current_socket = object()
    session.websocket = current_socket

    assert session.clear_websocket(stale_socket) is False
    assert session.websocket is current_socket
    assert session.clear_websocket(current_socket) is True
    assert session.websocket is None


@pytest.mark.asyncio
async def test_session_sends_are_serialized_per_socket():
    class BlockingWebSocket:
        client_state = SimpleNamespace(name="CONNECTED")

        def __init__(self):
            self.entered = asyncio.Event()
            self.release = asyncio.Event()
            self.active = 0
            self.max_active = 0
            self.messages = []

        async def send_text(self, message):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.entered.set()
            await self.release.wait()
            self.messages.append(json.loads(message)["type"])
            self.active -= 1

    session = InterviewSession("send-lock")
    websocket = BlockingWebSocket()
    session.websocket = websocket

    first = asyncio.create_task(session._send_json("first", {}))
    await websocket.entered.wait()
    second = asyncio.create_task(session._send_json("second", {}))
    await asyncio.sleep(0)
    assert websocket.max_active == 1

    websocket.release.set()
    await asyncio.gather(first, second)
    assert websocket.max_active == 1
    assert websocket.messages == ["first", "second"]


@pytest.mark.asyncio
async def test_answer_processing_is_single_flight_per_session():
    class BlockingLLM:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.questions = []

        async def get_ai_answer(self, question, stream_callback, generate_full_answers=None):
            self.questions.append(question)
            if len(self.questions) == 1:
                self.started.set()
                await self.release.wait()
            return f"answer: {question}", {"success": True}

    session = InterviewSession("answer-lock")
    websocket = MagicMock()
    websocket.client_state.name = "CONNECTED"
    websocket.send_text = AsyncMock()
    session.websocket = websocket
    llm = BlockingLLM()
    session.llm_manager = llm
    session.transcript_buffer = "first question"

    first = asyncio.create_task(session._process_aggregated_transcript())
    await llm.started.wait()
    session.transcript_buffer = "second question"
    second = asyncio.create_task(session._process_aggregated_transcript())
    await asyncio.sleep(0)
    assert llm.questions == ["first question"]

    llm.release.set()
    await asyncio.gather(first, second)
    assert llm.questions == ["first question", "second question"]


@pytest.mark.asyncio
async def test_interview_start_runs_one_provider_health_preflight(monkeypatch):
    class StubLLM:
        def __init__(self):
            self.shared_context = object()
            self.presets = {"primary": {}}
            self.perform_health_checks = AsyncMock(return_value={"primary": True})

        def load_configuration(self, **kwargs):
            return True

        def initialize_candidate_context(self, onboarding_context):
            pass

        def get_current_preset_info(self):
            return {"key": "primary"}

    class StubSTT:
        def __init__(self, *args, **kwargs):
            pass

        async def start(self):
            pass

    llm = StubLLM()
    monkeypatch.setattr("api.session_manager.MultiLLMManager", lambda: llm)
    monkeypatch.setattr("api.session_manager.DeepgramManager", StubSTT)
    monkeypatch.setattr("api.session_manager.VisionService.set_context_manager", lambda self, context: None)
    monkeypatch.setattr("api.session_manager.VisionService.load_vision_providers", lambda self, **kwargs: None)
    appearance = MagicMock(return_value=True)
    monkeypatch.setattr('window_manager.window_manager.enable_proctoring_stealth_mode', appearance)

    session = InterviewSession("health-check")
    websocket = MagicMock()
    websocket.client_state.name = "CONNECTED"
    websocket.send_text = AsyncMock()
    session.websocket = websocket
    await session.handle_start_interview({
        "aiProvider": {"provider": "P", "model": "m"},
        "onboardingData": {},
    })

    await session._health_task
    assert llm.perform_health_checks.await_count == 1
    appearance.assert_called_once_with(click_through=False)


@pytest.mark.asyncio
async def test_session_cleanup_closes_llm_and_stt_resources():
    session = InterviewSession("cleanup-resources")
    session.llm_manager = MagicMock()
    session.llm_manager.close = AsyncMock()
    session.stt_manager = MagicMock()
    session.stt_manager.finish = AsyncMock()

    await session.cleanup()

    session.stt_manager.finish.assert_awaited_once()
    session.llm_manager.close.assert_awaited_once()
