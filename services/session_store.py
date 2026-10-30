"""Durable local interview records and complete text exports."""
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import orjson

from core.config import EXPORTS_PATH


def validate_session_id(session_id: str) -> str:
    if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        raise ValueError("Invalid session ID")
    return session_id


def sanitize_record(value):
    """Credentials belong in provider configuration, never in saved records."""
    if isinstance(value, dict):
        return {key: sanitize_record(item) for key, item in value.items()
                if re.sub(r"[^a-z]", "", key.lower()) not in {
                    "key", "apikey", "apikeys", "deepgramkey", "deepgramapikey",
                    "token", "accesstoken", "authorization", "password", "secret"}}
    if isinstance(value, list):
        return [sanitize_record(item) for item in value]
    return value


def session_path(session_id: str) -> Path:
    root = EXPORTS_PATH.resolve()
    path = root / "sessions" / f"{validate_session_id(session_id)}.json"
    if not path.resolve().is_relative_to(root):
        raise ValueError("Session path must stay inside exports")
    return path


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_session(record: dict) -> Path:
    path = session_path(record["session_id"])
    _atomic_write(path, orjson.dumps(sanitize_record(record), option=orjson.OPT_INDENT_2))
    return path


def load_session(session_id: str) -> dict:
    record = orjson.loads(session_path(session_id).read_bytes())
    if not isinstance(record, dict) or record.get("session_id") != session_id:
        raise ValueError("Invalid saved session record")
    return sanitize_record(record)


def list_sessions() -> list[dict]:
    records = []
    for path in (EXPORTS_PATH / "sessions").glob("*.json"):
        try:
            record = load_session(path.stem)
        except (OSError, ValueError):
            continue
        onboarding = record.get("onboarding") or {}
        records.append({"session_id": record["session_id"], "started_at": record.get("started_at"),
                        "ended_at": record.get("ended_at"), "status": record.get("status"),
                        "candidate_name": onboarding.get("name", ""), "target_role": onboarding.get("role", ""),
                        "event_count": len(record.get("events", [])), "has_summary": bool(record.get("summary")),
                        "context": {"mode": onboarding.get('mode', 'call' if onboarding.get('session_mode') == 'regular' else 'interview'),
                            "role": onboarding.get('role', ''), "company": onboarding.get('company', '')},
                        "path": str(session_path(record['session_id']))})
    return sorted(records, key=lambda record: record.get("started_at") or "", reverse=True)


def export_session(record: dict, directory: Path | None = None) -> Path:
    record = sanitize_record(record)
    validate_session_id(record["session_id"])
    context = record.get("context") or {}
    persistent = context.get("persistent") or record.get("onboarding") or {}
    lines = [f"Interview transcript — {record.get('started_at') or datetime.now().isoformat()}",
             f"Session: {record['session_id']}",
             f"Candidate: {persistent.get('candidate_name', persistent.get('name', ''))} | Role: {persistent.get('target_role', persistent.get('role', ''))}",
             f"Status: {record.get('status', 'active')} | Ended: {record.get('ended_at') or 'Not ended'}", "=" * 60]
    metadata = {key: value for key, value in record.items() if key not in ("events", "summary")}
    lines.extend(["SESSION CONTEXT AND CONFIGURATION", orjson.dumps(metadata, option=orjson.OPT_INDENT_2).decode(), "=" * 60])
    for number, event in enumerate(record.get("events", []), 1):
        event_type = event.get("type", "transcript")
        label = event.get("speaker", "interviewer").upper() if event_type == "transcript" else {
            "question": "TYPED QUESTION", "answer": "AI ANSWER", "vision": "VISION", "gap": "CAPTURE GAP"}.get(event_type, event_type.upper())
        details = ""
        if event.get("provider"):
            details += f" ({event['provider']})"
        if event.get("success") is False:
            details += " [FAILED]"
        lines.append(f"[{event.get('timestamp', '')}] [T{number}] {label}: {event.get('text', '')}{details}")
        if event.get("question"):
            lines.append(f"Question: {event['question']}")
    if record.get("summary"):
        lines.extend(["=" * 60, "SUMMARY", str(record["summary"])])
    path = (directory or EXPORTS_PATH) / f"interview_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex}.txt"
    _atomic_write(path, "\n".join(lines).encode("utf-8"))
    return path.resolve()
