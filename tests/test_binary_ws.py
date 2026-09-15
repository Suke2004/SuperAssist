"""Unit tests for Phase 2: Binary WebSocket audio transport and token compaction."""

import pytest
from fastapi.testclient import TestClient
from main import app
from core.config import APP_SESSION_TOKEN
from core.prompts import _compact_text, build_unlimited_candidate_profile, MAX_RESUME_CHARS, MAX_JD_CHARS
from api.session_manager import session_manager


@pytest.fixture
def client():
    return TestClient(app, headers={"X-App-Token": APP_SESSION_TOKEN})


class TestBinaryWebSocketAudio:
    def test_binary_audio_frame_dispatch(self, client):
        """Binary frame with speaker_hint=mic (0x01) and unmuted (0x00) is routed to session."""
        with client.websocket_connect("/ws") as ws:
            # First message received is session_created
            created_msg = ws.receive_json()
            assert created_msg["type"] == "session_created"
            session_id = created_msg["payload"]["session_id"]
            session = session_manager.get_session(session_id)
            assert session is not None

            # Construct binary frame: 2 bytes header + 4 bytes PCM (0x01 = mic, 0x00 = unmuted)
            binary_frame = bytes([0x01, 0x00, 0x12, 0x34, 0x56, 0x78])
            ws.send_bytes(binary_frame)

            # Let loop process
            import time
            time.sleep(0.05)

            # Check hint timeline recorded mic speech
            assert len(session.hint_timeline) > 0
            ts, is_mic = session.hint_timeline[-1]
            assert is_mic is True
            assert session.state["is_muted"] is False

    def test_binary_audio_frame_muted(self, client):
        """Binary frame with muted flag (0x01) updates mute state and drops mic chunk."""
        with client.websocket_connect("/ws") as ws:
            created_msg = ws.receive_json()
            session_id = created_msg["payload"]["session_id"]
            session = session_manager.get_session(session_id)

            # Byte 0 = system (0x02), Byte 1 = muted (0x01)
            binary_frame = bytes([0x02, 0x01, 0x10, 0x20])
            ws.send_bytes(binary_frame)

            import time
            time.sleep(0.05)

            assert len(session.hint_timeline) > 0
            ts, is_mic = session.hint_timeline[-1]
            assert is_mic is False
            assert session.state["is_muted"] is True

    def test_legacy_json_audio_chunk_still_supported(self, client):
        """Legacy JSON audio_chunk messages continue to work seamlessly."""
        with client.websocket_connect("/ws") as ws:
            created_msg = ws.receive_json()
            session_id = created_msg["payload"]["session_id"]
            session = session_manager.get_session(session_id)

            ws.send_json({
                "type": "audio_chunk",
                "payload": {
                    "audio_b64": "EjRWeA==",
                    "is_muted": False,
                    "speaker_hint": "microphone"
                }
            })

            import time
            time.sleep(0.05)

            assert len(session.hint_timeline) > 0
            ts, is_mic = session.hint_timeline[-1]
            assert is_mic is True


class TestTokenCompaction:
    def test_compact_text_short(self):
        """Short text below cap is preserved unchanged."""
        short_text = "Experienced Python & C++ backend engineer with 5 years experience."
        assert _compact_text(short_text, 100) == short_text

    def test_compact_text_exceeds_limit(self):
        """Text exceeding limit is cleanly truncated at boundary with notice."""
        long_text = "Word " * 1000  # 5000 chars
        compacted = _compact_text(long_text, 500)
        assert len(compacted) < 600
        assert "compacted for token hygiene" in compacted

    def test_candidate_profile_compaction(self):
        """Huge resume and JD are bounded in build_unlimited_candidate_profile."""
        context = {
            "candidate_name": "Alice",
            "target_company": "Google",
            "target_role": "L5 Software Engineer",
            "selected_languages": ["Python", "Go"],
            "complete_resume": "Resume project experience: " * 500,  # ~13,500 chars
            "complete_job_description": "Job requirements and specs: " * 500,  # ~14,000 chars
        }
        profile = build_unlimited_candidate_profile(context, include_personal_details=True)
        assert "Candidate Name: Alice" in profile
        assert "Target Company: Google" in profile
        assert "compacted for token hygiene" in profile
        # Whole profile should be safely bounded around 6000-7000 chars (~1500 tokens), not 30,000 chars!
        assert len(profile) < 8000
