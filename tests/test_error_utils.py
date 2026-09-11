"""Tests for core.error_utils retryable-error classification (fix C8)."""

from core.error_utils import describe_error, is_retryable_error


class FakeStatusError(Exception):
    def __init__(self, status_code, message=""):
        super().__init__(message or f"status {status_code}")
        self.status_code = status_code


class TestRetryableStatuses:
    def test_auth_errors_are_retryable(self):
        # Another key may be valid, so rotation makes sense
        assert is_retryable_error(FakeStatusError(401)) is True
        assert is_retryable_error(FakeStatusError(403)) is True

    def test_rate_limit_is_retryable(self):
        assert is_retryable_error(FakeStatusError(429)) is True

    def test_server_errors_are_retryable(self):
        assert is_retryable_error(FakeStatusError(500)) is True
        assert is_retryable_error(FakeStatusError(503)) is True

    def test_client_errors_fail_fast(self):
        # The exact bug: "prompt too long" burned the whole key pool
        assert is_retryable_error(FakeStatusError(400)) is False
        assert is_retryable_error(FakeStatusError(404)) is False
        assert is_retryable_error(FakeStatusError(413)) is False
        assert is_retryable_error(FakeStatusError(422)) is False

    def test_unknown_4xx_fails_fast(self):
        assert is_retryable_error(FakeStatusError(418)) is False


class TestNoStatusErrors:
    def test_timeout_by_name(self):
        class APITimeoutError(Exception):
            pass

        assert is_retryable_error(APITimeoutError("timed out")) is True

    def test_connection_by_text(self):
        assert is_retryable_error(Exception("connection reset by peer")) is True

    def test_rate_limit_by_text_without_status(self):
        assert is_retryable_error(Exception("rate limit exceeded")) is True

    def test_unknown_error_fails_fast(self):
        # Default is fail-fast with the real error, not silent key burning
        assert is_retryable_error(Exception("something weird")) is False

    def test_none_is_not_retryable(self):
        assert is_retryable_error(None) is False


def test_describe_error_truncates():
    long = "x" * 500
    assert len(describe_error(Exception(long))) <= 200
