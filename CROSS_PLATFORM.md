# VeyraCue on Windows, MacBook, and Linux

The app remains a native desktop window with the same live answers, providers, conversation history, answer scrolling, and vision queue. Existing `.env` and `ai_providers.json` files are reused locally. uv supplies managed Python 3.12 and installs the platform-specific packages from a universal `uv.lock`. A missing, outdated, or newer system Python does not affect the launcher. Create `.venv` separately on each device; virtual environments cannot be copied between Windows, macOS, and Linux. The old `venv/` is not modified.

| Platform | Desktop | Meeting audio | Global shortcuts |
| --- | --- | --- | --- |
| Windows 10/11 | WebView2; existing launcher | Existing WASAPI loopback | Existing Ctrl+Shift+Win combinations |
| MacBook, Intel or Apple silicon | Native Cocoa/WebKit | BlackHole/CoreAudio routed input; independent native microphone | Option combinations; Accessibility permission required |
| Linux X11 | Qt WebEngine | PulseAudio or PipeWire playback monitor; independent native microphone | Ctrl+Shift+Super combinations |
| Linux Wayland | Qt WebEngine | PulseAudio/PipeWire monitor | Same combinations inside the focused window; global capture is disabled |

## macOS setup

Use macOS 11 or newer on an Intel or Apple silicon Mac. From the project folder, run `bash run.sh`; it installs uv if needed, downloads managed Python 3.12 for the host architecture, and creates `.venv` with the locked macOS dependencies. No separate Python installation is needed. The launcher supports macOS's bundled Bash 3.2. Use a native terminal on Apple silicon, rather than a Rosetta terminal, to avoid installing an emulated x64 runtime. `bash run.sh --update` reinstalls the locked packages without changing their versions.

For interview audio through headphones:

1. Install [BlackHole 2ch](https://github.com/ExistentialAudio/BlackHole) following its installer instructions. VeyraCue does not install an audio driver or change your system routing automatically.
2. Connect your headphones, open **Audio MIDI Setup**, and create a **Multi-Output Device** containing your headphones and BlackHole 2ch. Set the component devices to 48kHz, use your physical output as the primary device, and enable drift correction on BlackHole.
3. Choose that Multi-Output Device as the meeting's speaker output, or as the macOS output when the meeting uses the system default. Audio must reach both BlackHole and the headphones.
4. In VeyraCue audio setup, choose **macOS routed audio**, select **BlackHole 2ch**, and choose your physical microphone separately. The app excludes physical microphones from its meeting-output list.
5. Start the interview and confirm **audio detected** while playing speech. No browser screen-sharing prompt is needed for this audio path. Microphone permission is requested by the OS when native recording begins. A denied/unavailable candidate microphone leaves meeting capture running.

In **System Settings → Privacy & Security**, grant **Microphone** for recording, **Accessibility/Input Monitoring** for global shortcuts, and **Screen Recording** for screenshots to the Python/launcher process identified by macOS. Restart the app after changing permissions. Without global shortcut permission, the Dock remains available and Show/Hide minimizes the window; click-through stays disabled so the app can be recovered.

For background startup, run `bash silent_run.sh` (`bash run.sh --silent` also works). The app runs independently and logs to `output/desktop-launch.log`. `VeyraCue.command` can be made executable with `chmod +x VeyraCue.command` and double-clicked, but Finder briefly opens Terminal for it.

For a completely terminal-free launcher, build the bundled AppleScript in the project folder:

```bash
bash build_macos_launcher.sh
open VeyraCue.app
```

The builder compiles the bundled AppleScript and adds the microphone usage description to the app's Info.plist. Keep `VeyraCue.app` in the project folder beside `silent_run.sh`; its launch path is resolved from the app's location. Double-click that app for subsequent launches. First-run downloads may take longer before the desktop window appears; inspect the log for startup failures. Revisit macOS permissions when changing Python environments, because the OS may identify the new interpreter separately.

Screenshots use the native macOS screen-capture tool after Screen Recording permission is granted. The Screenshot button and Option+S capture directly into the queue, activating vision mode when needed. Review its thumbnails, remove an image with ×, and use Process or Option+P to analyze the queue. Capture opens no image viewer, and vision mode preserves manual mute/pause settings. Temporary screenshot files are deleted after loading; queued images remain in memory until sent to the selected vision engine or cleared.

### macOS startup troubleshooting

If startup worked with `DEV_MODE=true` but failed with `DEV_MODE=false`, update the checkout with `git pull --ff-only`, keep `DEV_MODE=false` in the project's `.env`, and run `bash run.sh`. Normal startup requests capture exclusion; development mode skips that request and enables webview debugging. Native window lookup, the sharing setter, and its verification now run on Cocoa's main thread, including when pywebview invokes the shown callback from a worker thread. This fixes an unsafe production startup path without changing transcription or answer generation.

If macOS cannot apply or verify capture exclusion, the app logs a warning and continues setup. `NSWindowSharingNone applied` confirms the window setting, but exclusion still depends on macOS and the recording method. `Capture exclusion unavailable` or `Native NSWindow unavailable` means exclusion was not confirmed; the overlay may appear in shared screens. Test the recording method you actually use.

For a silent launch that produces no window, inspect its diagnostics:

```bash
tail -n 80 output/desktop-launch.log
sw_vers
uname -m
```

Run `bash run.sh` in Terminal to see the full Python traceback if the error persists. An `APP_SYNC_FLAGS[@]: unbound variable` error comes from an older launcher under Bash 3.2; update `run.sh`. For a dependency import error, run `bash run.sh --update`. Launch through these scripts so the app uses its own managed `.venv`; a copied Windows environment or direct system-Python launch does not provide the macOS packages.

After updating, confirm foreground startup with `DEV_MODE=false`, then test microphone permission, BlackHole playback, and answer scrolling during generation. Close the app before testing `bash silent_run.sh` or `VeyraCue.app` so the checks exercise a fresh launch.

## Linux setup

Use a graphical desktop session with PulseAudio or PipeWire's PulseAudio compatibility service. uv installs managed Python 3.12 and Qt WebEngine; system Python and `python3-venv` are not required. The locked Qt wheels require glibc 2.34+ on x64 (for example Ubuntu 22.04+ or Debian 12+) and glibc 2.39+ on ARM64 (for example Ubuntu 24.04+). Alpine/musl and 32-bit Linux do not have the required desktop wheels in this lockfile.

On Debian/Ubuntu, install the OS libraries before running the launcher:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends curl ca-certificates build-essential linux-libc-dev libpulse0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libwayland-cursor0 libegl1 libnss3 libasound2 libdbus-1-3 libxkbcommon-x11-0 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libxtst6
bash run.sh
```

On Ubuntu 24.04+ use `libasound2t64` in place of `libasound2`. Other distributions need equivalent Qt/X11 and PulseAudio client libraries, kernel development headers, and a C compiler for pynput's evdev dependency. The managed Python distribution supplies its own Python headers. Keep your existing desktop audio server; do not install a second server over an active PipeWire setup. `pactl info` can confirm that PulseAudio or PipeWire's compatibility service is reachable.

Choose **Linux system audio**, select the monitor of the headphones/speakers used by your meeting, and select your microphone separately. The default monitor follows the current default sink when listed. A specific selection remains tied to that device; restart after changing outputs. The capture implementation uses 48kHz mono PCM, source labels, bounded queues, playback status, and the existing device retry/transcription recovery path.

Run `bash silent_run.sh` for background startup with no terminal output or continuing terminal dependency. Inspect `output/desktop-launch.log` if no window appears. A desktop shortcut can use command `bash "/absolute/project/path/silent_run.sh"` with **Run in terminal** disabled. `bash run.sh --update` reinstalls locked dependencies. Do not run the graphical app as root; Qt Chromium requires a normal desktop user.

Choose an **X11/Xorg session** at login for global shortcuts, click-through, taskbar hiding, and native screenshots. Screenshot captures add directly to the vision queue; remove unwanted thumbnails before choosing Process. Capturing or toggling vision mode preserves manual mute/pause settings. A compositor/window manager can override topmost, opacity, or taskbar requests. If global shortcuts are unavailable, taskbar hiding and click-through remain disabled and Show/Hide minimizes the window.

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

The focused desktop window uses the same action bindings as the native listener, including mute, screenshot capture, queue clearing, movement, and scrolling. Registered native keys are excluded from browser dispatch individually so one press cannot toggle twice. Unregistered keys retain a focused-window fallback. Global access still requires the platform's permissions and an available chord; a shortcut owned by another application is reported and left unregistered.

## Validation and limits

Run `uv run --managed-python --python 3.12 -m pytest -q` from the project folder. It installs the development group and uses the same managed runtime. Tests cover launcher working directories, locked setup, background logging, setup failures, platform renderer selection, output/microphone separation, PCM conversion, permission errors, exact modifier handling, pause/cleanup, screenshots, and Windows regressions. macOS regressions exercise Cocoa lookup/setter/readback on the main thread, failed or unverifiable capture exclusion, and continued production setup after a sharing API error. Browser platform checks are in `tests/cross_platform_check.js`.

For this startup fix, the full suites passed on Windows (238 passed, 2 skipped) and Linux (230 passed, 10 skipped). The launcher regression also passed under Bash 3.2 compiled on Linux, covering normal, update, install, and silent startup. The same check reproduced the empty-array error in the old launcher. This verifies shell compatibility, not execution on macOS itself.

The subsequent screenshot/shortcut fix passed 330 Windows tests and 322 Linux tests. `tests/screenshot_shortcuts_check.js` covers all 26 action mappings for Windows, macOS, and Linux browser platform settings, repeated/disabled keys, individual native-key suppression, microphone mute/pause, answer and vision model toggles, manual pause preservation, queue removal, and explicit analysis. It also checks one in-flight analysis at a time, preservation of newer captures, and retry after a failed analysis. A Windows native check registered all 26 chords and captured a 2880×1800 primary-display image without launching a viewer. Physical Mac shortcut permissions and native screenshot capture still require on-device confirmation.

The Debian/WSL X11 runtime check captured synthetic playback from a real PulseAudio monitor at 48kHz and exercised Qt window controls, an actual global shortcut dispatch, and native screenshot queuing. This uses a virtual desktop/test sink; it does not establish microphone/headphone behavior on every physical Linux device. Windows and Linux backend suites and browser platform checks also passed. The locked production dependencies resolve for both `aarch64-apple-darwin` and `x86_64-apple-darwin` in uv dry runs. These checks and the mocked Cocoa tests do not establish native Mac GUI or audio behavior; on-device testing of the reported Python error remains outstanding.

Windows capture protection remains in its existing path. Linux has no app-level capture exclusion here; the overlay can be visible in screen sharing. macOS capture exclusion varies by OS and recording method. Share the meeting window/tab when that is appropriate to your workflow.

Physical MacBook audio routing, Bluetooth device switching, permissions, and compositor-specific Linux behavior require testing on those devices. A blocked OS audio driver can outlive the bounded shutdown wait; restart the app if that error is reported. Neither platform can capture audio routed to another output or repair recognition during a network outage.

References: [SoundCard](https://github.com/bastibe/SoundCard), [BlackHole](https://github.com/ExistentialAudio/BlackHole), [pywebview installation](https://pywebview.flowrl.com/guide/installation.html).
