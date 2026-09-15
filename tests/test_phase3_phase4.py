"""Tests for Phase 3 and Phase 4 enhancements:
1. Deepgram ring buffer resilience during disconnects.
2. STT connection health events emission and session manager forwarding.
3. Safe concurrent cleanup of sessions.
4. Atomic metrics persistence to disk and reload.
5. Window manager unified settings.
"""

import asyncio
import json
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.stt_service import DeepgramManager
from api.session_manager import InterviewSession, SessionManager
from api.metrics import Metrics
from core.config import settings
import window_manager


@pytest.mark.asyncio
async def test_stt_ring_buffer_accumulates_and_flushes():
    """Verify that when disconnected, audio accumulates in ring buffer, and flushes on send when connected."""
    callback = AsyncMock()
    mgr = DeepgramManager(transcript_callback=callback)
    
    # Initially disconnected
    mgr.is_connected = False
    mgr.dg_connection = None
    
    chunk1 = b"audio_chunk_1"
    chunk2 = b"audio_chunk_2"
    
    await mgr.send_audio(chunk1)
    await mgr.send_audio(chunk2)
    
    assert len(mgr.audio_ring_buffer) == 2
    assert list(mgr.audio_ring_buffer) == [chunk1, chunk2]
    
    # Now simulate connection restored
    mock_dg = AsyncMock()
    mgr.dg_connection = mock_dg
    mgr.is_connected = True
    
    chunk3 = b"audio_chunk_3"
    await mgr.send_audio(chunk3)
    
    # Ring buffer should be flushed, and chunk3 sent
    assert len(mgr.audio_ring_buffer) == 0
    assert mock_dg.send.call_count == 3
    sent_chunks = [call.args[0] for call in mock_dg.send.call_args_list]
    assert sent_chunks == [chunk1, chunk2, chunk3]


@pytest.mark.asyncio
async def test_stt_status_events_emission():
    """Verify STT status changes emit events to callback."""
    emitted_events = []
    
    async def fake_callback(data):
        emitted_events.append(data)
        
    mgr = DeepgramManager(transcript_callback=fake_callback)
    mock_dg = AsyncMock()
    mgr.dg_connection = mock_dg
    
    # on_open emits connected
    await mgr.on_open()
    assert len(emitted_events) >= 1
    assert emitted_events[-1]["type"] == "stt_status"
    assert emitted_events[-1]["status"] == "connected"
    
    # on_error emits reconnecting
    await mgr.on_error(error="socket drop")
    assert emitted_events[-1]["type"] == "stt_status"
    assert emitted_events[-1]["status"] == "reconnecting"
    
    # Cleanup task if created
    if mgr._reconnect_task and not mgr._reconnect_task.done():
        mgr._reconnect_task.cancel()


@pytest.mark.asyncio
async def test_session_on_transcript_forwards_stt_status():
    """Verify InterviewSession forwards stt_status message to client WebSocket."""
    session = InterviewSession("test-stt-status-session")
    mock_ws = AsyncMock()
    mock_ws.client_state.name = "CONNECTED"
    session.websocket = mock_ws
    
    status_event = {
        "type": "stt_status",
        "status": "reconnecting",
        "detail": "Network blip"
    }
    await session.on_transcript(status_event)
    
    assert mock_ws.send_text.call_count == 1
    sent_data = json.loads(mock_ws.send_text.call_args[0][0])
    assert sent_data["type"] == "stt_status"
    assert sent_data["payload"]["status"] == "reconnecting"


@pytest.mark.asyncio
async def test_stale_session_cleanup_concurrency_safe():
    """Verify _cleanup_stale_sessions does not raise RuntimeError if dictionary is modified during iteration."""
    sm = SessionManager()
    
    # Create multiple sessions
    s1 = InterviewSession("s1")
    s2 = InterviewSession("s2")
    s1.last_activity_time = 0  # old
    s2.last_activity_time = 0  # old
    
    sm.active_sessions["s1"] = s1
    sm.active_sessions["s2"] = s2
    
    await sm._cleanup_stale_sessions()
    assert "s1" not in sm.active_sessions
    assert "s2" not in sm.active_sessions


def test_metrics_save_and_load(tmp_path):
    """Verify atomic disk persistence and loading of metrics."""
    metrics_file = str(tmp_path / "test_metrics.json")
    
    m1 = Metrics()
    m1.inc("questions_answered", 5)
    m1.inc("fallbacks_used", 2)
    m1.save_to_disk(metrics_file)
    
    assert os.path.exists(metrics_file)
    with open(metrics_file, "r") as f:
        data = json.load(f)
    assert data["counters"]["questions_answered"] == 5
    assert data["counters"]["fallbacks_used"] == 2
    
    # Load into fresh metrics instance
    m2 = Metrics()
    m2.load_from_disk(metrics_file)
    snapshot = m2.snapshot()
    assert snapshot["counters"]["questions_answered"] == 5
    assert snapshot["counters"]["fallbacks_used"] == 2


def test_window_manager_settings_unified():
    """Verify window_manager uses values defined in core.config.settings."""
    assert window_manager.SCROLL_AMOUNT_PX == max(1, int(settings.SCROLL_SPEED_PX))
    assert window_manager.SCROLL_INTERVAL_MS == max(10, int(settings.SCROLL_INTERVAL_MS))
    assert window_manager.SCREEN_SHARE_SCAN_INTERVAL_S == max(0.2, float(settings.SCREEN_SHARE_SCAN_INTERVAL_S))
