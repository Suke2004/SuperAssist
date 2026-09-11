"""P3: transcript export endpoint test."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    import os
    os.environ.setdefault("DEEPGRAM_API_KEY", "test-key-for-import")
    from main import app
    with TestClient(app) as c:
        yield c


def test_export_transcript_unknown_session(client):
    resp = client.post("/api/export-transcript", json={"session_id": "does-not-exist"})
    assert resp.status_code == 404


def test_export_transcript_empty_log(client):
    from api.session_manager import session_manager
    session = session_manager.create_session()
    try:
        resp = client.post("/api/export-transcript", json={"session_id": session.session_id})
        assert resp.status_code == 400
        assert "No transcript" in resp.json()["detail"]
    finally:
        session_manager.remove_session(session.session_id)


def test_export_transcript_writes_file(client, tmp_path, monkeypatch):
    from api.session_manager import session_manager
    session = session_manager.create_session()
    session.transcript_log = [
        {"speaker": "interviewer", "text": "what is two sum?", "timestamp": "2026-09-11T10:00:00"},
        {"speaker": "candidate", "text": "hash map approach", "timestamp": "2026-09-11T10:00:05"},
    ]
    # Redirect exports into tmp_path so the test never writes to the repo root.
    monkeypatch.chdir(tmp_path)
    try:
        resp = client.post("/api/export-transcript", json={"session_id": session.session_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["turns"] == 2
        content = open(data["path"], encoding="utf-8").read()
        assert "INTERVIEWER: what is two sum?" in content
        assert "CANDIDATE: hash map approach" in content
    finally:
        session_manager.remove_session(session.session_id)
