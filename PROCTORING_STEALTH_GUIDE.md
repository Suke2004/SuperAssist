# VeyraCue desktop window controls

MacBook and Linux desktop controls, permissions, shortcuts, and capture limitations are described in [CROSS_PLATFORM.md](CROSS_PLATFORM.md). On Unix platforms, click-through/taskbar hiding require working global shortcuts; otherwise the app stays recoverable through the Dock/taskbar and Show/Hide minimizes it. Linux Wayland uses focused controls and explicit screenshot uploads. Windows behavior below is unchanged.

The interview window starts on top with mouse interaction enabled. This allows answer scrolling, text selection, Chat, and toolbar actions. Starting an interview does not automatically enable click-through.

## Click-through and scrolling

**Ctrl+Shift+Win+K** toggles click-through. While enabled, mouse input goes to the application underneath the overlay. Use **Ctrl+Shift+Win+PageUp/PageDown** to scroll the answer history without focusing the overlay, or press K with the same modifiers to restore mouse scrolling.

Scrolling up enters reading mode so transcript/answer updates do not pull you away from the text. Inside the focused live window, Home goes to the first answer, End resumes following the latest answer, and Escape toggles reading mode. The down-arrow button also jumps to the latest answer.

## Visibility and opacity

- **Ctrl+Shift+Win+H** hides/restores the window.
- **Ctrl+Shift+Win+F1/F2/F3** sets 40%/70%/100% opacity.
- **Ctrl+Shift+Win+[ / ]** decreases/increases opacity.
- **Ctrl+Shift+Win+arrow keys** moves the window by 20px.
- **Ctrl+Shift+Win+Y** explicitly enables click-through, taskbar hiding, topmost placement, and 70% opacity. Press K with the modifiers afterward to restore mouse interaction.

Old Windows Alt bindings are disabled. A shortcut already registered elsewhere is left unbound and logged. See [README.md](README.md#all-windows-shortcuts) for every current shortcut.

## Screen and audio capture

Windows direct audio requires no screen-sharing prompt. It captures playback on the selected output, independently of the browser microphone. Screenshot actions request screen capture separately. Choose the meeting's exact output device and watch for **audio detected** in the system-audio status.

The desktop uses Windows capture protection when developer mode is disabled. Protection depends on the capture application and platform; it is not a guarantee against every recording tool. Capture failures are logged. See [AUDIO_PLAN.md](AUDIO_PLAN.md) for audio routing, recovery, and limitations.
