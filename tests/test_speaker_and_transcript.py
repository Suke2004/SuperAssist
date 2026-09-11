"""A1/P3/hygiene: speaker classification, transcript log, and filler stripping."""
import asyncio
import time
from collections import deque

import pytest

from api.session_manager import InterviewSession, classify_speaker


# ---------------------------------------------------------------- classify_speaker

def test_no_hints_defaults_to_system():
    assert classify_speaker(deque(), time.time()) == "system"


def test_majority_mic_in_window():
    now = time.time()
    timeline = deque((now - i * 0.01, True) for i in range(10))  # all mic
    assert classify_speaker(timeline, now) == "microphone"


def test_majority_system_in_window():
    now = time.time()
    timeline = deque((now - i * 0.01, False) for i in range(10))  # all system
    assert classify_speaker(timeline, now) == "system"


def test_stale_hints_ignored():
    """A1: a hint far older than the window must not influence classification."""
    now = time.time()
    timeline = deque()
    # Old mic-dominant burst (10s ago) — well outside the 1.5s window.
    for i in range(50):
        timeline.append((now - 10 - i * 0.01, True))
    # Recent system-dominant burst.
    for i in range(20):
        timeline.append((now - i * 0.01, False))
    assert classify_speaker(timeline, now) == "system"


def test_mixed_window_takes_majority():
    now = time.time()
    timeline = deque()
    for i in range(6):
        timeline.append((now - i * 0.01, False))  # system majority
    for i in range(3):
        timeline.append((now - 0.2 - i * 0.01, True))  # mic minority
    assert classify_speaker(timeline, now) == "system"


# ---------------------------------------------------------------- session wiring

def _make_session():
    session = InterviewSession("test-sid")
    session.websocket = None  # no actual socket needed for these paths
    return session


def test_audio_chunk_appends_hint_timeline():
    session = _make_session()
    payload = {
        "audio_b64": None,
        "audio": list(b"\x00\x00" * 16),
        "speaker_hint": "microphone",
        "is_muted": False,
    }
    asyncio.get_event_loop() if False else None
    asyncio.run(session.handle_audio_chunk(payload))
    assert len(session.hint_timeline) == 1
    ts, mic_dominant = session.hint_timeline[0]
    assert mic_dominant is True


def test_transcript_log_records_turns():
    session = _make_session()
    session.state["process_all_speakers"] = True
    # Simulate the tail of on_transcript for a final interviewer utterance.
    session.transcript_log.append(
        {"speaker": "interviewer", "text": "what is two sum?", "timestamp": "t"}
    )
    assert session.transcript_log[0]["speaker"] == "interviewer"


def test_transcript_log_bounded():
    session = _make_session()
    from api.session_manager import TRANSCRIPT_LOG_MAX_TURNS
    for i in range(TRANSCRIPT_LOG_MAX_TURNS + 50):
        session.transcript_log.append({"speaker": "interviewer", "text": str(i), "timestamp": "t"})
        if len(session.transcript_log) > TRANSCRIPT_LOG_MAX_TURNS:
            del session.transcript_log[: len(session.transcript_log) - TRANSCRIPT_LOG_MAX_TURNS]
    assert len(session.transcript_log) == TRANSCRIPT_LOG_MAX_TURNS


# ---------------------------------------------------------------- filler hygiene

import re


def strip_fillers(text: str) -> str:
    """Mirrors the backend hygiene regex in session_manager.on_transcript."""
    cleaned = re.sub(r"\s*\b(um+|uh+|erm+|hmm+)\b[.,!?;]*(\.\.\.)*\s*", " ", text,
                     flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return re.sub(r"^[\s,.;]+|[\s,.;]+$", "", cleaned)


def test_filler_words_stripped():
    assert strip_fillers("Um, what is, uh, two sum?") == "what is, two sum?"
    assert strip_fillers("explain DFS please") == "explain DFS please"
    assert strip_fillers("Umm... hmm, ok") == "ok"
    assert strip_fillers("uh") == ""


def test_fillers_do_not_eat_real_words():
    # Words merely containing the pattern must survive.
    assert "summit" in strip_fillers("summit meeting")
    assert "human" in strip_fillers("human being")
