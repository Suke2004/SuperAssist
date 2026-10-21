"""Focused tests for project-root configuration persistence."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError


@pytest.fixture()
def config_api_module():
    import api.config_api as config_api

    return config_api


@pytest.mark.asyncio
async def test_provider_save_is_atomic_utf8_and_uses_configured_path(
    config_api_module, tmp_path, monkeypatch
):
    target = tmp_path / "project" / "ai_providers.json"
    target.parent.mkdir()
    monkeypatch.setattr(config_api_module, "AI_PROVIDERS_PATH", target)

    replace_calls = []
    real_replace = config_api_module.os.replace

    def recording_replace(source, destination):
        replace_calls.append((Path(source), Path(destination)))
        assert Path(source).exists()
        real_replace(source, destination)

    monkeypatch.setattr(config_api_module.os, "replace", recording_replace)

    providers = [{"name": "测试 provider", "apiKey": "clé-é"}]
    result = await config_api_module.save_ai_providers(
        config_api_module.SaveProvidersRequest(providers=providers)
    )

    assert result["success"] is True
    assert json.loads(target.read_text(encoding="utf-8")) == providers
    assert len(replace_calls) == 1
    source, destination = replace_calls[0]
    assert source.parent == target.parent
    assert source != target
    assert destination == target
    assert not list(target.parent.glob(".ai_providers.json.*.tmp"))


def test_provider_payload_requires_a_list_of_objects(config_api_module):
    with pytest.raises(ValidationError):
        config_api_module.SaveProvidersRequest(providers={"name": "not-a-list"})

    with pytest.raises(ValidationError):
        config_api_module.SaveProvidersRequest(providers=["not-an-object"])


def test_default_metrics_path_is_project_root(monkeypatch, tmp_path):
    from api.metrics import Metrics

    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr("core.config.PROJECT_ROOT", project_root)

    metrics = Metrics()
    metrics.inc("questions_answered", 1)
    metrics.save_to_disk()

    assert (project_root / "metrics.json").exists()


@pytest.mark.asyncio
async def test_provider_read_uses_project_path_when_cwd_differs(
    config_api_module, tmp_path, monkeypatch
):
    project_config = tmp_path / "project" / "ai_providers.json"
    project_example = tmp_path / "project" / "ai_providers.example.json"
    project_config.parent.mkdir()
    project_example.write_text(
        json.dumps([{"name": "from-project"}]), encoding="utf-8"
    )
    monkeypatch.setattr(config_api_module, "AI_PROVIDERS_PATH", project_config)
    monkeypatch.setattr(config_api_module, "AI_PROVIDERS_EXAMPLE_PATH", project_example)

    unrelated_cwd = tmp_path / "unrelated-cwd"
    unrelated_cwd.mkdir()
    (unrelated_cwd / "ai_providers.json").write_text(
        json.dumps([{"name": "wrong-cwd"}]), encoding="utf-8"
    )
    monkeypatch.chdir(unrelated_cwd)

    providers = await config_api_module.get_ai_providers_full()

    assert providers == [{"name": "from-project"}]
    assert project_config.exists()


@pytest.mark.asyncio
async def test_save_deepgram_key_refreshes_imported_settings(
    config_api_module, tmp_path, monkeypatch
):
    from core import config as core_config
    from core.env_utils import EnvManager

    original_settings = core_config.settings.model_dump()
    env_path = tmp_path / ".env"
    env_path.write_text('DEEPGRAM_API_KEY="old-key"\n', encoding="utf-8")
    monkeypatch.setattr(core_config, "ENV_PATH", env_path)
    monkeypatch.setattr(
        config_api_module, "ENV_PATH", env_path
    )
    monkeypatch.setattr(config_api_module, "env_manager", EnvManager(str(env_path)))
    core_config.settings.DEEPGRAM_API_KEY = "old-key"

    try:
        result = await config_api_module.save_deepgram_key(
            config_api_module.SaveKeyRequest(key="new-key")
        )

        assert result["success"] is True
        assert 'DEEPGRAM_API_KEY="new-key"' in env_path.read_text(encoding="utf-8")
        assert core_config.settings.DEEPGRAM_API_KEY == "new-key"
    finally:
        object.__getattribute__(core_config.settings, "__dict__").update(
            original_settings
        )
