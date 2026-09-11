"""Tests for the Deepgram reconnect singleflight guard (fix A1)."""

import asyncio

import pytest

from services.stt_service import DeepgramManager


class FlakyStartManager(DeepgramManager):
    """DeepgramManager whose _connect_once succeeds after N failures."""

    def __init__(self, failures_before_success):
        # Bypass real __init__ (no Deepgram client needed for the guard logic)
        self.transcript_callback = None
        self.dg_connection = None
        self.is_connected = False
        self.stop_event = asyncio.Event()
        self.user_languages = []
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_base_delay = 0.01
        self._reconnect_task = None
        self._initial_connect_max_attempts = 3
        self.deepgram = None
        self.failures_before_success = failures_before_success
        self.connect_calls = 0

    async def _connect_once(self):
        self.connect_calls += 1
        if self.connect_calls <= self.failures_before_success:
            raise ConnectionError("simulated failure")
        self.is_connected = True


@pytest.mark.asyncio
async def test_initial_connect_retries_then_succeeds():
    mgr = FlakyStartManager(failures_before_success=1)
    await mgr.start()  # A2: retry succeeded instead of silently dying
    assert mgr.is_connected is True
    assert mgr.connect_calls == 2


@pytest.mark.asyncio
async def test_initial_connect_raises_after_budget_exhausted():
    mgr = FlakyStartManager(failures_before_success=99)
    with pytest.raises(RuntimeError):
        await mgr.start()
    assert mgr.is_connected is False
    assert mgr.connect_calls == mgr._initial_connect_max_attempts


@pytest.mark.asyncio
async def test_reconnect_singleflight_prevents_double_loop():
    """on_error + on_close firing together must produce ONE connect sequence."""
    mgr = FlakyStartManager(failures_before_success=1)

    # Kick off two reconnects concurrently (what on_error and on_close do)
    task1 = asyncio.create_task(mgr._reconnect())
    task2 = asyncio.create_task(mgr._reconnect())
    await asyncio.gather(task1, task2)

    # Round 1 calls start(), which retries once internally: one failed
    # _connect_once + one successful one. Without the singleflight guard the
    # second loop would run another round and add a third call.
    assert mgr.connect_calls == 2
    assert mgr.is_connected is True


@pytest.mark.asyncio
async def test_reconnect_stops_after_max_attempts():
    mgr = FlakyStartManager(failures_before_success=99)
    mgr._max_reconnect_attempts = 2
    await mgr._reconnect()
    # 2 rounds x start()'s internal budget of 3 connect attempts each
    assert mgr.connect_calls == 6
    assert mgr._reconnect_task is None  # guard released
