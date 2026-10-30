from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import config_api
from api.session_manager import session_manager
from services import session_store


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(session_store, "EXPORTS_PATH", tmp_path / "exports")
    monkeypatch.setattr(config_api, "EXPORTS_PATH", tmp_path / "exports")
    return session_store


@pytest.fixture
def client(store):
    app = FastAPI()
    app.include_router(config_api.router)
    return TestClient(app)


def record(session_id="session-1"):
    return {"session_id": session_id, "started_at": "2026-10-30T11:00:00", "status": "completed",
            "context": {"persistent": {"candidate_name": "Ada"}},
            "providers": {"primary": {"provider": "Test", "model": "test-model", "apiKey": "never-save"}},
            "events": [{"type": "transcript", "speaker": "interviewer", "timestamp": "t", "text": str(i)} for i in range(601)]}


def test_complete_record_export_and_collision(store):
    data = record()
    data["events"] += [{"type": "question", "text": "typed input"},
                       {"type": "answer", "text": "AI suggestion", "question": "typed input", "provider": "Test"},
                       {"type": "vision", "text": "screen analysis", "success": False},
                       {"type": "gap", "text": "audio disconnected"}]
    data["summary"] = "Decision [T1]"
    path = store.save_session(data)
    assert "never-save" not in path.read_text(encoding="utf-8")
    saved = store.load_session(data["session_id"])
    assert len(saved["events"]) == 605
    first, second = store.export_session(saved), store.export_session(saved)
    assert first != second
    text = first.read_text(encoding="utf-8")
    for snippet in ("INTERVIEWER: 0", "INTERVIEWER: 600", "TYPED QUESTION: typed input",
                    "AI ANSWER: AI suggestion", "VISION: screen analysis [FAILED]",
                    "CAPTURE GAP: audio disconnected", "Decision [T1]"):
        assert snippet in text
    assert store.list_sessions()[0]["event_count"] == 605


@pytest.mark.parametrize("session_id", ["../escape", "a/b", "a\\b", "C:outside", ".", "", "a" * 129])
def test_reject_unsafe_session_ids(store, session_id):
    with pytest.raises(ValueError):
        store.save_session(record(session_id))


def test_atomic_write_failure_preserves_record(store, monkeypatch):
    data = record()
    path = store.save_session(data)
    original = path.read_bytes()
    data["summary"] = "Should not replace saved data"
    def fail_replace(*args):
        raise OSError("Disk unavailable")
    monkeypatch.setattr(store.os, "replace", fail_replace)
    with pytest.raises(OSError):
        store.save_session(data)
    assert path.read_bytes() == original
    assert not list(path.parent.glob("*.tmp"))


def test_saved_session_read_export_finalize_retry(client, store):
    store.save_session(record())
    assert client.get("/api/sessions").json()[0]["session_id"] == "session-1"
    assert len(client.get("/api/sessions/session-1").json()["events"]) == 601
    result = client.post("/api/export-transcript", json={"session_id": "session-1"})
    assert result.status_code == 200
    assert result.json()["turns"] == 601
    retry = client.post("/api/finalize-session", json={"session_id": "session-1"})
    assert retry.status_code == 200
    assert retry.json()["success"] is True


def test_finalize_failure_keeps_active_session(client):
    session = SimpleNamespace(session_id="save-failure", finalize=AsyncMock(side_effect=OSError("Disk full")))
    session_manager.active_sessions[session.session_id] = session
    try:
        result = client.post("/api/finalize-session", json={"session_id": session.session_id})
        assert result.status_code == 503
        assert session_manager.active_sessions[session.session_id] is session
    finally:
        session_manager.active_sessions.pop(session.session_id)


def test_summary_failure_preserves_raw_session(client, store, tmp_path, monkeypatch):
    path = store.save_session(record())
    original = path.read_bytes()
    provider_path = tmp_path / "providers.json"
    provider_path.write_text('[{"name":"Test","baseURL":"https://example.invalid","apiKey":"test-real-key","models":["test-model"]}]')
    monkeypatch.setattr(config_api, "AI_PROVIDERS_PATH", provider_path)
    completion = AsyncMock(side_effect=RuntimeError("Provider rejected request"))
    manager = SimpleNamespace(client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion))), close=AsyncMock())
    monkeypatch.setattr(config_api, "LLMManager", lambda **kwargs: manager)
    result = client.post("/api/sessions/session-1/summary")
    assert result.status_code == 503
    assert path.read_bytes() == original
    completion.assert_awaited_once()
    assert "T601" in completion.call_args.kwargs["messages"][1]["content"]
    assert "test-real-key" not in completion.call_args.kwargs["messages"][1]["content"]
    manager.close.assert_awaited_once()


def test_summary_uses_usable_selected_fallback_once(client, store, tmp_path, monkeypatch):
    data = record()
    data["providers"]["secondary"] = {"provider": "Backup", "model": "backup-model"}
    store.save_session(data)
    provider_path = tmp_path / "providers.json"
    provider_path.write_text('[{"name":"Test","apiKey":"","models":["test-model"]},{"name":"Backup","baseURL":"https://example.invalid","apiKey":"test-real-key","models":["backup-model"]}]')
    monkeypatch.setattr(config_api, "AI_PROVIDERS_PATH", provider_path)
    completion = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Unknowns: No actions recorded [T1]."))]))
    manager = SimpleNamespace(client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion))), close=AsyncMock())
    monkeypatch.setattr(config_api, "LLMManager", lambda **kwargs: manager)
    result = client.post("/api/sessions/session-1/summary")
    assert result.status_code == 200
    assert store.load_session("session-1")["summary"] == result.json()["summary"]
    assert completion.call_args.kwargs["model"] == "backup-model"
    completion.assert_awaited_once()
