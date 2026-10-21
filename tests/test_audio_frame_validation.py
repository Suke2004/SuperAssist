"""Boundary tests for the Phase 5 binary audio transport hardening."""

import pytest

from api.session_manager import InterviewSession


@pytest.mark.asyncio
async def test_binary_audio_rejects_invalid_headers_and_sizes():
    session = InterviewSession("audio-validation")

    class StubSTT:
        def __init__(self):
            self.sent = []

        async def send_audio(self, payload):
            self.sent.append(payload)

    stt = StubSTT()
    session.stt_manager = stt

    await session.handle_binary_audio(b"\x03\x00\x00\x00")
    await session.handle_binary_audio(b"\x01\x02\x00\x00")
    await session.handle_binary_audio(b"\x01\x00\x00")
    await session.handle_binary_audio(b"\x01\x00" + (b"\x00" * (64 * 1024)))

    assert stt.sent == []


@pytest.mark.asyncio
async def test_binary_audio_accepts_valid_linear16_frame():
    session = InterviewSession("audio-valid")

    class StubSTT:
        def __init__(self):
            self.sent = []

        async def send_audio(self, payload):
            self.sent.append(payload)

    stt = StubSTT()
    session.stt_manager = stt

    await session.handle_binary_audio(b"\x02\x00\x12\x34\x56\x78")

    assert stt.sent == [b"\x12\x34\x56\x78"]
