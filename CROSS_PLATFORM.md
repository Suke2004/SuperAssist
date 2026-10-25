# VeyraCue on Windows, MacBook, and Linux

The app remains a native desktop window with the same live answers, providers, conversation history, answer scrolling, and vision queue. Existing `.env` and `ai_providers.json` files are reused locally. Install dependencies separately on each operating system; virtual environments cannot be copied between Windows, macOS, and Linux.

| Platform | Desktop | Meeting audio | Global shortcuts |
| --- | --- | --- | --- |
| Windows 10/11 | WebView2; existing launcher | Existing WASAPI loopback | Existing Ctrl+Shift+Win combinations |
| MacBook, Intel or Apple silicon | Native Cocoa/WebKit | BlackHole/CoreAudio routed input; independent native microphone | Option combinations; Accessibility permission required |
| Linux X11 | Qt WebEngine | PulseAudio or PipeWire playback monitor; independent native microphone | Ctrl+Shift+Super combinations |
| Linux Wayland | Qt WebEngine | PulseAudio/PipeWire monitor | Same combinations inside the focused window; global capture is disabled |

## macOS setup

Use Python 3.10+ and macOS 11 or newer. Install a Python build matching your Mac's architecture. From the project folder, run `bash run.sh`; the launcher creates a Unix `.venv` and installs the macOS dependencies. It also supports `bash run.sh --update`.

For interview audio through headphones:

1. Install [BlackHole 2ch](https://github.com/ExistentialAudio/BlackHole) following its installer instructions. VeyraCue does not install an audio driver or change your system routing automatically.
2. Connect your headphones, open **Audio MIDI Setup**, and create a **Multi-Output Device** containing your headphones and BlackHole 2ch. Set the component devices to 48kHz, use your physical output as the primary device, and enable drift correction on BlackHole.
3. Choose that Multi-Output Device as the meeting's speaker output, or as the macOS output when the meeting uses the system default. Audio must reach both BlackHole and the headphones.
4. In VeyraCue audio setup, choose **macOS routed audio**, select **BlackHole 2ch**, and choose your physical microphone separately. The app excludes physical microphones from its meeting-output list.
5. Start the interview and confirm **audio detected** while playing speech. No browser screen-sharing prompt is needed for this audio path. Microphone permission is requested by the OS when native recording begins. A denied/unavailable candidate microphone leaves meeting capture running.

In **System Settings → Privacy & Security**, grant **Microphone** for recording, **Accessibility/Input Monitoring** for global shortcuts, and **Screen Recording** for screenshots to the Python/launcher process identified by macOS. Restart the app after changing permissions. Without global shortcut permission, the Dock remains available and Show/Hide minimizes the window; click-through stays disabled so the app can be recovered.

For background startup, run `bash run.sh --silent`, or allow `VeyraCue.command` to execute with `chmod +x VeyraCue.command` and double-click it. The command launcher may briefly open Terminal; the app then runs independently and logs to `output/desktop-launch.log`. Close the launcher terminal after it exits. First-run installation can take longer; check that log for startup errors.

Screenshots use the native macOS screen-capture tool after Screen Recording permission is granted. Temporary screenshot files are deleted after loading; queued images remain in memory until sent to the selected vision engine or cleared.

## Linux setup

Use Python 3.10+ in a graphical desktop session. Qt WebEngine is installed by `run.sh`; PulseAudio or PipeWire's PulseAudio compatibility service must be running for native audio.

On Debian/Ubuntu, install the OS libraries before running the launcher:

```bash
sudo apt-get install --no-install-recommends python3 python3-venv python3-dev build-essential linux-libc-dev libpulse0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libwayland-cursor0 libegl1 libnss3 libasound2 libdbus-1-3 libxkbcommon-x11-0 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libxtst6
bash run.sh
```

Other distributions need their equivalent Qt/X11 and PulseAudio client libraries, plus Python/kernel development headers and a C compiler for pynput's evdev dependency. Keep your existing desktop audio server; do not install a second server over an active PipeWire setup. `pactl info` can confirm that PulseAudio or PipeWire's compatibility service is reachable.

Choose **Linux system audio**, select the monitor of the headphones/speakers used by your meeting, and select your microphone separately. The default monitor follows the current default sink when listed. A specific selection remains tied to that device; restart after changing outputs. The capture implementation uses 48kHz mono PCM, source labels, bounded queues, playback status, and the existing device retry/transcription recovery path.

Run `bash run.sh --silent` for background startup with no continuing terminal dependency. `bash run.sh --update` refreshes dependencies. Do not run the graphical app as root; Qt Chromium requires a normal desktop user.

Choose an **X11/Xorg session** at login for global shortcuts, click-through, taskbar hiding, and native screenshots. A compositor/window manager can override topmost, opacity, or taskbar requests. If global shortcuts are unavailable, taskbar hiding and click-through remain disabled and Show/Hide minimizes the window.

On **Wayland**, live answers and native audio still work. Shortcut commands work while the app is focused. The Screenshot button opens an image picker: take a screenshot using your desktop's screenshot tool, then select that image for the existing vision queue. Global shortcuts and unattended desktop screenshots are not claimed on Wayland.

## Shortcuts

Windows shortcuts are unchanged; see [README.md](README.md). Linux uses the same keys and actions with **Ctrl+Shift+Super** (Super is usually the Windows-logo key). The displayed shortcut hints follow the current platform. Exact modifier checks avoid matching ordinary meeting-app shortcuts; Unix listeners do not suppress meeting keystrokes.

macOS uses **Option** plus:

| Key | Action |
| --- | --- |
| H | Show/hide; minimize when global shortcuts are unavailable |
| X | Toggle click-through |
| M / U | Microphone mute / pause all capture |
| 1 / 2 / 3 | 40% / 70% / 100% opacity |
| [ / ] | Decrease/increase opacity |
| Q / W / E | Primary / secondary / automatic answer model |
| G | Full answers / quick hints |
| V / S / P / R / T | Vision mode / screenshot / analyze queue / clear queue / vision model |
| O | Reset interview context |
| Shift+S | Explicit desktop stealth controls |
| Shift+, / Shift+. / Shift+U / Shift+D | Move left / right / up / down |
| , / . | Scroll answers up/down while held |

Mac global shortcuts use physical key codes so Option-generated symbols do not replace the intended shortcut letter. The existing Option+Z, arrow, and I/J aliases remain. Home/End/Escape answer reading controls remain local on all platforms; on a MacBook keyboard, Fn+Left/Fn+Right typically provide Home/End.

## Validation and limits

Run `python -m pytest` in the platform's virtual environment. Tests cover platform renderer selection, output/microphone separation, PCM conversion, permission errors, exact modifier handling, pause/cleanup, screenshots, and Windows regressions. Browser platform checks are in `tests/cross_platform_check.js`.

The Debian/WSL X11 runtime check captured synthetic playback from a real PulseAudio monitor at 48kHz and exercised Qt window controls, an actual global shortcut dispatch, and native screenshot queuing. This uses a virtual desktop/test sink; it does not establish microphone/headphone behavior on every physical Linux device. Windows and Linux backend suites and browser platform checks also passed. Mac paths are covered by unit/bridge tests; physical MacBook testing remains outstanding.

Windows capture protection remains in its existing path. Linux has no app-level capture exclusion here; the overlay can be visible in screen sharing. macOS capture exclusion varies by OS and recording method. Share the meeting window/tab when that is appropriate to your workflow.

Physical MacBook audio routing, Bluetooth device switching, permissions, and compositor-specific Linux behavior require testing on those devices. A blocked OS audio driver can outlive the bounded shutdown wait; restart the app if that error is reported. Neither platform can capture audio routed to another output or repair recognition during a network outage.

References: [SoundCard](https://github.com/bastibe/SoundCard), [BlackHole](https://github.com/ExistentialAudio/BlackHole), [pywebview installation](https://pywebview.flowrl.com/guide/installation.html).
