"""Tests for core.key_utils placeholder filtering and key-pool resolution."""

from core.key_utils import is_placeholder_key, resolve_provider_keys, usable_keys


def test_blank_and_none_are_placeholders():
    assert is_placeholder_key(None) is True
    assert is_placeholder_key("") is True
    assert is_placeholder_key("   ") is True
    assert is_placeholder_key(123) is True


def test_template_values_are_placeholders():
    assert is_placeholder_key("YOUR_GROQ_API_KEY_1") is True
    assert is_placeholder_key("YOUR-API-KEY") is True
    assert is_placeholder_key("CHANGEME") is True
    assert is_placeholder_key("PLACEHOLDER") is True


def test_real_keys_pass():
    assert is_placeholder_key("gsk_realkey123") is False
    assert is_placeholder_key("sk-abc123") is False


def test_usable_keys_filters_and_strips():
    pool = ["  real-key ", "YOUR_X", "", "another-key"]
    assert usable_keys(pool) == ["real-key", "another-key"]


def test_usable_keys_rejects_non_sequence():
    assert usable_keys(None) == []
    assert usable_keys("not-a-list") == []
    assert usable_keys({"a": 1}) == []


def test_resolve_provider_prefers_api_keys_array():
    config = {"apiKey": "single", "apiKeys": ["k1", "k2"]}
    assert resolve_provider_keys(config) == ["k1", "k2"]


def test_resolve_provider_falls_back_to_single_key():
    # The regression case: example ships placeholder apiKeys + real apiKey
    config = {"apiKey": "real-key", "apiKeys": ["YOUR_GROQ_API_KEY_1"]}
    assert resolve_provider_keys(config) == ["real-key"]


def test_resolve_provider_empty_when_neither_set():
    assert resolve_provider_keys({}) == []
    assert resolve_provider_keys("nope") == []
