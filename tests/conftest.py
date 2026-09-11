"""Test bootstrap: make first-party packages importable without running main()."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# core.config requires DEEPGRAM_API_KEY. Tests never talk to Deepgram, so
# point it at an obviously-fake value instead of requiring a real .env.
os.environ.setdefault("DEEPGRAM_API_KEY", "test-placeholder-key")
