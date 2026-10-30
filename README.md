# VeyraCue desktop interview assistant

VeyraCue is a local desktop interview workspace with live transcription, suggested answers, screenshots, and typed follow-ups. Its dark interface runs inside Windows WebView2, macOS Cocoa/WebKit, or Linux Qt WebEngine. The live answer pane uses 14px body text (13px in narrow windows) with compact headings and an independently scrollable answer history.

## Launch and setup

The launchers use [uv](https://docs.astral.sh/uv/) to download managed **Python 3.12** and install the exact dependencies in `uv.lock` into a local `.venv`. You do not need to install, upgrade, or activate system Python. First setup needs internet access; later launches reuse the environment and check the lockfile. Windows uses PowerShell to install uv if missing; macOS/Linux use `curl` and the official uv installer. You can [install uv manually](https://docs.astral.sh/uv/getting-started/installation/) first if your network blocks the installer.

| Platform | Diagnostic launch | Silent launch |
| --- | --- | --- |
| Windows 10/11, x64 | `run.bat` | Double-click `silent_run.vbs` |
| MacBook, Intel or Apple silicon | `bash run.sh` | `bash silent_run.sh`, or the macOS app described below |
| Linux desktop, x64 or ARM64 | `bash run.sh` | `bash silent_run.sh` |

Silent startup runs independently of the terminal and records diagnostics in `output/desktop-launch.log`. On macOS, `VeyraCue.command` is also available, but Finder briefly opens Terminal for a command file. To create a launcher that opens no Terminal, run `bash build_macos_launcher.sh` once in the project folder, then double-click `VeyraCue.app`. The builder includes the microphone permission description required by macOS. Keep that app beside `run.sh`; rebuild it if you move it elsewhere. For a Linux desktop shortcut, use your desktop's launcher editor with command `bash "/absolute/project/path/silent_run.sh"` and **Run in terminal** disabled.

MacBooks capture meeting playback through BlackHole with a Multi-Output Device; Linux uses PulseAudio/PipeWire monitors. Read [MacBook and Linux setup](CROSS_PLATFORM.md) for audio routing, permissions, system libraries, and Wayland behavior. uv manages Python and Python packages; audio drivers, a supported graphical desktop, and OS libraries are still required.

Use `run.bat --update` or `bash run.sh --update` to reinstall the locked packages when troubleshooting. Normal startup already synchronizes changes after a Git pull. The old `venv/` is left intact, and `.env`, provider configuration, and saved sessions are reused. Each device creates its own `.venv`; copy source/configuration as needed, never a virtual environment.

On macOS, keep `DEV_MODE=false` for normal use. Production capture-exclusion calls run on Cocoa's main thread; an unavailable sharing API is reported while startup continues. The Unix launcher also supports Apple's bundled Bash 3.2. If only development mode used to launch, pull the latest changes and follow [macOS startup troubleshooting](CROSS_PLATFORM.md#macos-startup-troubleshooting). Native Mac GUI/audio testing is still required, and capture exclusion depends on the OS and recording method.

API keys remain in `.env` and `ai_providers.json`. Only providers with usable configured keys appear in the setup. Existing Deepgram and answer/vision engines are reused; no Parakeet account or subscription is required.

Choose **Interview** or **Regular call** during setup. Regular calls do not require a resume or interview details. Attach up to eight `.txt`/`.md` documents (60,000 characters per file, 120,000 total); the assistant selects relevant passages and includes source IDs. Answer text size is adjustable in the live workspace.

Finalized speech, questions, answers, and screenshot analyses are checkpointed locally in `exports/sessions/` as JSON. **End** stops capture and saves a complete TXT export before showing the review screen. A save failure preserves the current record and offers retry. **Session history** opens saved records; **Generate AI summary** makes an explicit request to a configured engine and adds notes without replacing the raw record. These files contain conversation/profile content; API credentials are excluded. Live audio is not automatically restored after an app restart.

1. Add your name, target role/company, resume, job description, and answer preferences.
2. Continue to audio setup and choose **Windows direct audio**, **macOS routed audio**, or **Linux system audio** for your platform.
3. Select the playback output or routed input used by your meeting. On macOS this is BlackHole; on Linux it is the playback monitor.
4. Start the interview. Answers appear automatically, or turn off Auto answer and use **Answer** for the pending question. **Chat** sends a typed follow-up; **Screenshot** requests visual context.

Windows direct audio uses WASAPI loopback and **does not ask to share the screen or audio**. It can capture a meeting or YouTube playing through the selected output. Windows desktop screenshots capture the primary display directly. Browser capture is an alternative that requires sharing a meeting tab or supported screen with its audio enabled.

The microphone is optional for Windows direct audio. If browser microphone permission fails, the session still captures the interviewer from system playback. Your own speech is not transcribed in that case. Restart after granting microphone access to capture both speakers.

## Scrolling and capture troubleshooting

- **Screenshot** or **Ctrl+Shift+Win+S** captures directly into the vision queue and opens the queue when needed. Review the thumbnails, remove an unwanted image with **×**, then choose **Process** or **Ctrl+Shift+Win+P** to analyze the remaining images. Native desktop capture keeps the image inside the app; macOS needs Screen Recording permission, and Wayland uses an image picker. Vision mode and screenshot capture preserve your microphone mute and manual pause settings.
- Process sends one batch at a time. Screenshots captured during analysis stay queued for the next batch; successful analysis removes only the images it processed.
- Interviews start with mouse interaction enabled. Scroll the answer pane with the wheel, trackpad, scrollbar, or the global PageUp/PageDown shortcuts. Scrolling up pauses automatic following; End or the down-arrow button returns to the latest answer.
- Click-through mode is optional. If clicks or wheel scrolling pass into the meeting underneath, press **Ctrl+Shift+Win+K** to turn it off. The global scroll shortcuts also work while click-through is enabled.
- While testing audio, play YouTube through your headphones and watch the system-audio status. **Audio detected (output name)** confirms playback reaches capture; **waiting for playback** means that output currently has no detected sound. Silence between questions is normal.
- If no sound is detected, compare the selected output with the meeting/browser output. End the session and select the correct output after plugging in headphones, changing devices, or changing the sample rate. Microphone permission is not required for direct output capture.
- If sound is detected but transcripts are absent, check the separate transcription status and the configured Deepgram key, quota, and network connection.
- **M** mutes only the assistant's microphone. **U** pauses all assistant audio capture. These controls do not mute the meeting application's microphone.
- Use the full platform chord shown in the shortcut table. Each press triggers one action; holding a toggle key does not repeat it. A shortcut registered by the native listener is handled there, while unregistered keys have a fallback in the focused app window. OS permissions and shortcuts owned by another app can still limit global access; diagnostics are in `output/desktop-launch.log`.
- Complete answers also render when the provider returns a finished response without streaming chunks.

## All Windows shortcuts

Hold **Ctrl + Shift + Win** (the Windows logo key), then press the key below. Old Windows Alt shortcuts and legacy aliases are disabled. Exact chords are registered with Windows; a combination already owned by another app is left unbound and reported in `output/desktop-launch.log`.

| Key | Action |
| --- | --- |
| H | Show/hide the overlay |
| K | Toggle click-through mode |
| M | Mute/unmute the assistant microphone |
| U | Pause/resume all assistant audio capture |
| F1 | Set window opacity to 40% |
| F2 | Set window opacity to 70% |
| F3 | Set window opacity to 100% |
| [ | Decrease opacity |
| ] | Increase opacity |
| Q | Switch to primary answer model |
| W | Switch to secondary answer model |
| E | Automatically select an available answer model |
| G | Toggle full answers / quick hints |
| V | Toggle vision mode |
| S | Capture/queue a screenshot |
| P | Analyze the screenshot queue |
| R | Clear the screenshot queue |
| T | Switch vision model |
| O | Reset interview context |
| Y | Enable stealth mode: click-through, taskbar hiding, topmost, 70% opacity |
| Left / Right / Up / Down | Move the window 20px in that direction |
| PageUp / PageDown | Scroll answers up/down while held |

Inside the focused live window, outside input fields:

| Key | Action |
| --- | --- |
| Home or Ctrl+Home | Go to the first answer and enter reading mode |
| End or Ctrl+End | Go to the latest answer and resume following |
| Escape | Toggle reading mode; also closes the More menu |

In developer mode, Ctrl+J fills the onboarding form with sample data. It is not a global interview shortcut.

Linux uses the same table with Ctrl+Shift+Super. Global controls require X11; Wayland uses focused-window shortcuts and screenshot uploads. macOS keeps its Option shortcuts, including X for click-through and 1/2/3 for opacity. See the complete [platform shortcut table](CROSS_PLATFORM.md#shortcuts).

## Reliability and limits

Final speech segments are combined across pauses. Nova-3 receives bounded technical vocabulary without blind word replacements. The answer engine uses conversation context to interpret imperfect English and asks a brief clarification when meaning is ambiguous. Raw transcripts remain available for export.

Speech endpointing waits one second of silence, followed by a 200 ms continuation check before auto-answering. Continued speech cancels a pending answer. Streaming answers render at most once per browser frame and preserve your reading position; scroll to the bottom or use the down-arrow button to follow the latest text. Interview controls keep the arrow cursor while remaining clickable.

Capture is tied to the chosen playback device. It includes other sound on that device and cannot recover playback sent elsewhere. Recognition can still vary with accents, noise, unclear wording, and network outages. Reconnection queues are bounded; long outages can lose speech. Separate microphone and output transcription streams can incur separate provider usage.

**More → Save transcript** exports locally; End also exports the conversation. Exports, runtime logs, and validation artifacts are ignored by Git. Captured microphone/loopback audio is not saved by the normal app workflow.

## Documentation and validation

- [Audio capture methods and recovery](AUDIO_PLAN.md)
- [MacBook and Linux setup and shortcuts](CROSS_PLATFORM.md)
- [Desktop window and click-through controls](PROCTORING_STEALTH_GUIDE.md)
- Run backend checks with `uv run --managed-python --python 3.12 -m pytest -q`; uv installs the development group automatically.
- Maintain dependencies in `pyproject.toml` and commit `uv.lock`. Use `uv add <package>` or `uv add --dev <package>`. `requirements.txt` and `requirements-dev.txt` are generated compatibility exports for Python 3.12; see [CONTRIBUTING.md](CONTRIBUTING.md) for regeneration commands.
- Browser checks live in `tests/parakeet_workspace_check.js`, `tests/audio_workspace_check.js`, `tests/meeting_hotkeys_check.js`, and `tests/answer_audio_check.js`; they target the local validation server on port 8017.

Based on the SuperAssist/Aura codebase under the existing [MIT license](LICENSE). The interface references [Parakeet AI's public workflow](https://www.parakeet-ai.com/); this is an independent local adaptation. Meeting shortcut references: [Zoom](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0067050) and [Google Meet](https://support.google.com/meet/answer/9298571?hl=en).
