"""Lightweight in-memory metrics for SuperAssist.

Design goals:
- Zero dependencies, zero I/O: counters live in a plain dict behind a lock.
- Never raises from the hot path: every method swallows unexpected input so a
  metrics problem can never take down an interview.
- No secrets: keys, transcripts and prompts are never recorded — only counts
  and latency percentiles.
"""

import threading
import time
from collections import deque
from typing import Dict, Optional

APP_VERSION = "1.1.0"

# Known counters are pre-seeded so a snapshot always exposes the full shape,
# even before anything happens. Dynamic keys (per-provider errors) are added
# on demand.
_KNOWN_COUNTERS = (
    "sessions_created",
    "ws_disconnects",
    "ws_origins_rejected",
    "questions_answered",
    "answers_streamed",
    "fallbacks_used",
    "key_rotations",
    "vision_requests",
    "deepgram_reconnects",
    "deepgram_connect_failures",
    "delayed_cleanups",
    "transcripts_exported",
    "answer_mode_hints",
    "answer_mode_full",
    "hint_answers",
    "stt_language_changes",
)

_START_MONOTONIC = time.monotonic()


class Metrics:
    """Thread-safe counters plus a rolling answer-latency window."""

    def __init__(self, latency_window: int = 200):
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {name: 0 for name in _KNOWN_COUNTERS}
        self._provider_errors: Dict[str, int] = {}
        self._latencies_ms = deque(maxlen=latency_window)

    # --- recording -----------------------------------------------------

    def inc(self, name: str, amount: int = 1) -> None:
        """Increment a counter. Unknown names are created on the fly."""
        try:
            with self._lock:
                self._counters[name] = self._counters.get(name, 0) + amount
        except Exception:
            pass

    def provider_error(self, provider_name: str) -> None:
        """Record a failed request attributed to a specific provider."""
        try:
            key = str(provider_name) or "unknown"
            with self._lock:
                self._provider_errors[key] = self._provider_errors.get(key, 0) + 1
        except Exception:
            pass

    def record_answer_latency(self, latency_ms: float) -> None:
        """Record one end-to-end answer latency (question → final answer)."""
        try:
            value = float(latency_ms)
            if value >= 0:
                with self._lock:
                    self._latencies_ms.append(value)
        except Exception:
            pass

    # --- reporting -----------------------------------------------------

    @staticmethod
    def _percentile(sorted_values, pct: float) -> Optional[float]:
        if not sorted_values:
            return None
        index = min(len(sorted_values) - 1, max(0, int(round(pct * (len(sorted_values) - 1)))))
        return sorted_values[index]

    def snapshot(self) -> dict:
        """Return a JSON-safe snapshot of all metrics."""
        with self._lock:
            counters = dict(self._counters)
            provider_errors = dict(self._provider_errors)
            latencies = list(self._latencies_ms)
        latencies.sort()
        return {
            "version": APP_VERSION,
            "uptime_s": round(time.monotonic() - _START_MONOTONIC, 1),
            "counters": counters,
            "provider_errors": provider_errors,
            "answer_latency_ms": {
                "count": len(latencies),
                "p50": self._percentile(latencies, 0.50),
                "p95": self._percentile(latencies, 0.95),
                "max": latencies[-1] if latencies else None,
            },
        }


# Single shared instance — imported by services, api and tests.
app_metrics = Metrics()
