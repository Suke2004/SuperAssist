# 🤝 Contributing to SuperAssist

First off — **thank you** for wanting to contribute! Every bug report, feature idea, and pull request makes SuperAssist better for everyone.

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

# OR manual setup:
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
cp ai_providers.example.json ai_providers.json
python main.py
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
   - Your OS version and Python version

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
└── silent_run.vbs          # Invisible launch for Windows
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
| 🧪 **Testing** | Unit tests, mock audio tests, CI/CD pipeline | 🚧 Open |

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
