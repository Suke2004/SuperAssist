"""Tests for metrics, WS origin check, and delayed session cleanup."""

import asyncio

import pytest

from api.metrics import Metrics, app_metrics
from api.session_manager import SessionManager
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
