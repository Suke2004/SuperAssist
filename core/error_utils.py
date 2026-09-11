"""Shared helpers for classifying provider errors.

Kept dependency-light and importable without an OpenAI client so unit tests
can exercise the classification with plain exception objects.
"""

from typing import Any

# HTTP statuses where rotating to the next API key can genuinely help:
# auth/permission failures (another key may be valid) and rate limits/5xx
# (another key has its own quota). 4xx client errors like 400/404/413/422
# would fail identically on every key, so retrying only adds latency.
_RETRYABLE_STATUSES = frozenset({401, 403, 407, 408, 409, 429})
_RETRYABLE_STATUS_FLOOR = 500

# Statuses that indicate the REQUEST ITSELF is bad (payload too large,
# invalid model, malformed input). Retrying another key cannot fix these.
_NON_RETRYABLE_STATUSES = frozenset({400, 404, 413, 422})


def _status_code(error: Any) -> int:
    """Best-effort extraction of an HTTP status code from an exception."""
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    # httpx/requests style: error.response.status_code
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status
    return 0


def _error_text(error: Any) -> str:
    """Lowercased combined string representation of an exception."""
    parts = [str(error), type(error).__name__]
    message = getattr(error, "message", None)
    if message:
        parts.append(str(message))
    return " ".join(parts).lower()


def is_retryable_error(error: Any) -> bool:
    """Return True when rotating to the next API key could plausibly help.

    Retryable: timeouts, connection errors, auth/quota (401/403/429),
    and 5xx server errors.
    Not retryable: 4xx request errors (bad prompt, unknown model, payload
    too large) — the same request would fail on every key, so fail fast
    and surface the real error to the user.
    """
    if error is None:
        return False

    # Cancellation should never be retried by the key loop.
    try:
        import asyncio

        if isinstance(error, asyncio.CancelledError):
            return False
    except Exception:
        pass

    status = _status_code(error)
    if status:
        if status in _NON_RETRYABLE_STATUSES:
            return False
        if status in _RETRYABLE_STATUSES or status >= _RETRYABLE_STATUS_FLOOR:
            return True
        # Unknown 4xx (e.g. 418) — treat as a request problem, fail fast.
        if 400 <= status < 500:
            return False

    # No HTTP status: decide from the exception type/name/text.
    name = type(error).__name__.lower()
    text = _error_text(error)

    # Timeout / connection problems are transient by nature.
    if "timeout" in name or "timedout" in name.replace("_", ""):
        return True
    if "connect" in name or "network" in name or "apiconnection" in name.replace("_", ""):
        return True
    if "timed out" in text or "timeout" in text:
        return True
    if "connection" in text or "temporarily" in text or "unreachable" in text:
        return True

    # Rate-limit / quota errors that sometimes arrive without a parsed status.
    if "rate limit" in text or "quota" in text or "429" in text:
        return True
    # Auth errors without a status are still worth a retry on another key.
    if "unauthorized" in text or "invalid api key" in text or "401" in text:
        return True

    # Default: treat unknown errors as non-retryable so we fail fast with
    # the real error instead of silently burning the whole key pool.
    return False


def describe_error(error: Any, limit: int = 200) -> str:
    """Compact, user-safe description of an exception for error payloads."""
    text = f"{type(error).__name__}: {error}" if error is not None else "unknown error"
    return text[:limit]
