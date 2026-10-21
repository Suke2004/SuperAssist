"""Concurrency bounds for the vision request manager."""

import asyncio

import pytest

from services.vision_service import VisionManager


@pytest.mark.asyncio
async def test_vision_manager_limits_concurrent_requests():
    manager = VisionManager.__new__(VisionManager)
    manager._request_semaphore = asyncio.Semaphore(2)
    active = 0
    maximum = 0

    async def fake_request(prompt, screenshots, languages=None):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        await asyncio.sleep(0.01)
        active -= 1
        return "ok", {"success": True}

    manager._analyze_screenshots = fake_request
    results = await asyncio.gather(*[
        manager.analyze_screenshots("prompt", ["image"])
        for _ in range(5)
    ])

    assert maximum == 2
    assert len(results) == 5
