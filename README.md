# VeyraCue desktop interview assistant

VeyraCue is a local desktop interview workspace with live transcription, suggested answers, screenshots, and typed follow-ups. Its dark interface runs inside Windows WebView2, macOS Cocoa/WebKit, or Linux Qt WebEngine. The live answer pane uses 14px body text (13px in narrow windows) with compact headings and an independently scrollable answer history.

## Launch and setup

Double-click `silent_run.vbs` to launch the desktop window with a hidden terminal. Use `run.bat` for diagnostic output. The launcher uses the existing virtual environment and provider configuration. Startup errors are recorded in `output/desktop-launch.log`.

On macOS/Linux, use `bash run.sh` or `bash run.sh --silent` for background startup. MacBooks capture meeting playback through BlackHole with a Multi-Output Device; Linux uses PulseAudio/PipeWire monitors. Read [MacBook and Linux setup](CROSS_PLATFORM.md) for required audio routing, permissions, libraries, and Wayland behavior. Windows launchers, audio capture, and shortcuts keep their existing path.

API keys remain in `.env` and `ai_providers.json`. Only providers with usable configured keys appear in the setup. Existing Deepgram and answer/vision engines are reused; no Parakeet account or subscription is required.

1. Add your name, target role/company, resume, job description, and answer preferences.
2. Continue to audio setup and choose **Windows direct audio**.
3. Select the same headphones or speakers used by your meeting. The default option displays the current Windows output name.
4. Start the interview. Answers appear automatically, or turn off Auto answer and use **Answer** for the pending question. **Chat** sends a typed follow-up; **Screenshot** requests visual context.

Windows direct audio uses WASAPI loopback and **does not ask to share the screen or audio**. It can capture a meeting or YouTube playing through the selected output. Screenshot capture asks for screen permission separately. Browser capture is an alternative that requires sharing a meeting tab or supported screen with its audio enabled.

The microphone is optional for Windows direct audio. If browser microphone permission fails, the session still captures the interviewer from system playback. Your own speech is not transcribed in that case. Restart after granting microphone access to capture both speakers.

## Scrolling and capture troubleshooting

- Interviews start with mouse interaction enabled. Scroll the answer pane with the wheel, trackpad, scrollbar, or the global PageUp/PageDown shortcuts. Scrolling up pauses automatic following; End or the down-arrow button returns to the latest answer.
- Click-through mode is optional. If clicks or wheel scrolling pass into the meeting underneath, press **Ctrl+Shift+Win+K** to turn it off. The global scroll shortcuts also work while click-through is enabled.
- While testing audio, play YouTube through your headphones and watch the system-audio status. **Audio detected (output name)** confirms playback reaches capture; **waiting for playback** means that output currently has no detected sound. Silence between questions is normal.
- If no sound is detected, compare the selected output with the meeting/browser output. End the session and select the correct output after plugging in headphones, changing devices, or changing the sample rate. Microphone permission is not required for direct output capture.
- If sound is detected but transcripts are absent, check the separate transcription status and the configured Deepgram key, quota, and network connection.
- **M** mutes only the assistant's microphone. **U** pauses all assistant audio capture. These controls do not mute the meeting application's microphone.
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

Capture is tied to the chosen playback device. It includes other sound on that device and cannot recover playback sent elsewhere. Recognition can still vary with accents, noise, unclear wording, and network outages. Reconnection queues are bounded; long outages can lose speech. Separate microphone and output transcription streams can incur separate provider usage.

**More → Save transcript** exports locally; End also exports the conversation. Exports, runtime logs, and validation artifacts are ignored by Git. Captured microphone/loopback audio is not saved by the normal app workflow.

## Documentation and validation

- [Audio capture methods and recovery](AUDIO_PLAN.md)
- [MacBook and Linux setup and shortcuts](CROSS_PLATFORM.md)
- [Desktop window and click-through controls](PROCTORING_STEALTH_GUIDE.md)
- Run backend checks with `venv\Scripts\python.exe -m pytest -q`.
- Browser checks live in `tests/parakeet_workspace_check.js`, `tests/audio_workspace_check.js`, `tests/meeting_hotkeys_check.js`, and `tests/answer_audio_check.js`; they target the local validation server on port 8017.

Based on the SuperAssist/Aura codebase under the existing [MIT license](LICENSE). The interface references [Parakeet AI's public workflow](https://www.parakeet-ai.com/); this is an independent local adaptation. Meeting shortcut references: [Zoom](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0067050) and [Google Meet](https://support.google.com/meet/answer/9298571?hl=en).
