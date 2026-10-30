# 🤝 Contributing to VeyraCue

First off — **thank you** for wanting to contribute! Every bug report, feature idea, and pull request makes VeyraCue better for everyone.

---

## 🚀 Quick Start

```bash
# 1. Fork & clone
git clone https://github.com/YOUR_USERNAME/SuperAssist.git
cd SuperAssist

# 2. Automated launch (recommended):
# On Windows:
run.bat
# On macOS / Linux:
chmod +x run.sh
./run.sh

# Development setup after installing uv:
uv sync --locked --managed-python --python 3.12
uv run --managed-python --python 3.12 -m pytest -q
# The app creates .env from .env.example if missing; configure your local keys.
uv run --managed-python --python 3.12 main.py
```

---

## 📋 How to Contribute

### 🐛 Found a Bug?

1. **Search existing issues** first to avoid duplicates
2. Open a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Terminal/console output (if applicable)
   - Your OS/CPU architecture, uv version, and managed Python version

### 💡 Have a Feature Idea?

1. Open an issue with the **`feature request`** label
2. Describe:
   - The use case — what problem does it solve?
   - Your proposed solution
   - Any alternatives you've considered

### 🔧 Want to Submit a PR?

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** — keep commits focused and atomic
4. **Test** your changes locally
5. **Push** and open a Pull Request:
   ```bash
   git push origin feature/your-feature-name
   ```

---

## 📁 Project Structure

```
SuperAssist/
├── main.py                 # App entry point — FastAPI server + pywebview
├── window_manager.py       # Cross-platform stealth (Win32 & Cocoa), hotkeys, transparency
├── api/                    # FastAPI route handlers & WebSocket streaming
├── core/                   # Prompts, config, and business logic
├── services/               # LLM failover, Deepgram STT, vision processing
├── web/                    # Frontend — HTML/CSS/JS served by pywebview
├── .env                    # Environment variables (secrets — not committed)
├── ai_providers.json       # AI provider config (secrets — not committed)
├── run.bat                 # Automated setup & launch script (Windows)
├── run.sh                  # Automated setup & launch script (macOS / Linux)
├── silent_run.vbs          # Invisible launch for Windows
├── silent_run.sh           # Quiet background launch for macOS / Linux
├── VeyraCue.applescript    # Source for a terminal-free macOS app launcher
├── build_macos_launcher.sh # Build the app bundle with microphone permission metadata
├── pyproject.toml          # Runtime and development dependencies
├── .python-version        # Managed Python minor version
└── uv.lock                 # Universal locked package versions and hashes
```

---

## 🎯 Areas We Need Help With

| Area | Description | Status |
|:-----|:------------|:-------|
| 🍎 **macOS Support** | Cocoa/AppKit capture protection, Dock hiding, floating levels | ✅ Completed |
| 🐧 **Linux Support** | Port stealth APIs to X11/Wayland equivalents | 🚧 Open |
| 🌐 **More AI Providers** | Add support for new LLM providers (Anthropic, Mistral, etc.) | 🚧 Open |
| 🎨 **UI/UX** | Improve themes, animations, glanceable components | 🚧 Open |
| 📝 **Documentation** | Setup guides, tutorials, video walkthroughs | 🚧 Open |
| 🧪 **Testing** | Unit & integration tests, mock audio tests, pytest test suite | ✅ 85 tests passing |

---

## 📐 Code Style

- **Python**: Follow PEP 8 conventions
- **JavaScript**: Use vanilla JS (no frameworks in the frontend)
- **CSS**: Vanilla CSS — no Tailwind or preprocessors
- **Naming**: Descriptive variable/function names, snake_case for Python, camelCase for JS
- **Comments**: Explain *why*, not *what* — code should be self-documenting

---

## ⚠️ Important Notes

- **Never commit secrets** — `.env` and `ai_providers.json` are in `.gitignore` for a reason
- **Test stealth features** on Windows 10/11 before submitting stealth-related PRs
- **Keep PRs focused** — one feature or fix per PR
- **Be respectful** — we're all here to build something awesome

---

## 💬 Questions?

Open a GitHub issue or start a Discussion — we're happy to help!

---

**⭐ Star the repo if you find Aura useful — it helps more people discover it!**

## Current desktop validation

Use `uv run --managed-python --python 3.12 -m pytest -q` for backend checks on every platform. Browser regression scripts in `tests/` cover dark layout, answer scrolling, microphone-optional native startup, audio transport, and current Windows hotkeys. Keep `.env`, `ai_providers.json`, transcript exports, generated `VeyraCue.app`, virtual environments, and runtime `output/` artifacts out of commits. The current user workflow and complete shortcut list are in [README.md](README.md).

`tests/test_cross_platform.py` covers platform routing, Unix launchers, and source isolation; `tests/cross_platform_check.js` checks native bridge flows in the browser. `tests/linux_runtime_check.py` exercises a real Qt/X11 desktop and a PulseAudio test sink named `veyracue_test`. Record virtual-desktop results separately from physical hardware/meeting validation. See [CROSS_PLATFORM.md](CROSS_PLATFORM.md) for supported desktop/audio configurations.

## Dependency changes

`pyproject.toml` is the source of dependency declarations; `uv.lock` records exact versions and package hashes. Add runtime packages with `uv add <package>` and test tools with `uv add --dev <package>`. Keep OS-specific packages behind platform markers. Do not edit the generated requirements exports by hand. After changing dependencies, regenerate them:

```bash
uv export --locked --no-dev --no-hashes --output-file requirements.txt
uv export --locked --only-group dev --no-hashes --output-file requirements-dev.txt
uv lock --check --managed-python --python 3.12
```

Commit the metadata, lockfile, and both exports together. Launchers use `uv sync --locked --no-dev`, so a stale lock fails visibly instead of selecting different packages on a user's device. After changing the managed Python version, update `.python-version`, `requires-python`, both launcher requests, and these setup/test commands together. Never copy `.venv` between devices or remove an existing environment while its app is running.
