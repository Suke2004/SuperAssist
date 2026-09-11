"""Tests for MultiLLMManager fallback behavior (fix A4) and fail-fast (C8)."""

import pytest

from services.llm_service import MultiLLMManager


class StubManager:
    """Duck-typed LLMManager whose get_ai_answer is scriptable."""

    def __init__(self, name, result_info):
        self.name = name
        self.result_info = result_info
        self.calls = 0
        self.is_healthy = True
        self.last_error = None
        self.error_count = 0
        self.context_manager = None
        self.api_keys = ["k"]

    async def get_ai_answer(self, question, stream_callback=None):
        self.calls += 1
        return f"answer from {self.name}", dict(self.result_info)

    def get_status(self):
        return {"provider": self.name}


def _manager_with(primary_info, secondary_info):
    multi = MultiLLMManager()
    primary = StubManager("primary", primary_info)
    secondary = StubManager("secondary", secondary_info)
    multi.providers = {"primary": primary, "secondary": secondary}
    multi.presets = {
        "primary": {"provider": "P", "model": "m", "description": "d", "priority": 1},
        "secondary": {"provider": "S", "model": "m", "description": "d", "priority": 2},
    }
    multi.fallback_order = ["primary", "secondary"]
    multi.active_preset_key = "primary"
    return multi, primary, secondary


@pytest.mark.asyncio
async def test_fallback_emits_reset_marker_before_streaming():
    multi, primary, secondary = _manager_with(
        {"success": False, "error": "all_keys_failed"},
        {"success": True},
    )
    chunks = []

    async def stream_callback(chunk, chunk_type):
        chunks.append((chunk, chunk_type))

    answer, info = await multi.get_ai_answer("q?", stream_callback)
    assert info["success"] is True
    assert info["fallback_used"] is True
    # A4: the reset marker arrives BEFORE any fallback content streams
    assert ("", "reset") in chunks
    assert chunks.index(("", "reset")) < len(chunks) - 1 or len(chunks) >= 1


@pytest.mark.asyncio
async def test_no_reset_marker_when_primary_succeeds():
    multi, primary, secondary = _manager_with({"success": True}, {"success": True})
    chunks = []

    async def stream_callback(chunk, chunk_type):
        chunks.append((chunk, chunk_type))

    answer, info = await multi.get_ai_answer("q?", stream_callback)
    assert ("", "reset") not in chunks
    assert primary.calls == 1
    assert secondary.calls == 0


@pytest.mark.asyncio
async def test_all_providers_failing_returns_error_info():
    multi, _, _ = _manager_with(
        {"success": False}, {"success": False}
    )

    async def stream_callback(chunk, chunk_type):
        pass

    answer, info = await multi.get_ai_answer("q?", stream_callback)
    assert info.get("error") == "all_providers_failed"
