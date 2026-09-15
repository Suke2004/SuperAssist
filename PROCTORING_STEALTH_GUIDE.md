# 🕵️ Proctoring Stealth Guide - Undetectable AI Assistant Usage

This guide explains how to use your AI assistant application completely undetectably during proctored exams, interviews, or monitored sessions.

## 🎯 How Proctoring Software Detects Cheating

Proctoring platforms like **Proctorio**, **Honorlock**, **ExamSoft**, **Respondus**, and others detect:

1. **Focus Changes** - When you click on other windows or applications
2. **Tab Switching** - Moving between browser tabs  
3. **Screen Recording** - Capturing what's displayed on your screen
4. **Window Detection** - Finding suspicious application windows
5. **Mouse Movement** - Tracking cursor position and clicks

## 🛡️ Our Stealth Countermeasures

### 1. Ghost Mode (Click-Through)
- Window becomes **completely click-through**
- Cannot accidentally gain focus by clicking
- Prevents focus change detection
- **Windows:** `WS_EX_TRANSPARENT` style
- **macOS:** Cocoa `NSWindow.setIgnoresMouseEvents_(True)`

### 2. Focus-Free Visibility  
- Window shows/hides **without ever gaining focus**
- **Windows:** Uses `SW_SHOWNOACTIVATE` instead of `SW_SHOW`
- **macOS:** Uses `NSWindow.orderFrontRegardless()` (shows without activating or stealing keyboard focus)
- Proctoring software never detects window activation

### 3. Screen Capture Protection
- Window is excluded from all screen recordings, screen sharing, and screenshots
- **Windows:** Uses `WDA_EXCLUDEFROMCAPTURE` API (appears as black rectangle)
- **macOS:** Uses Cocoa `NSWindow.setSharingType_(0)` (`NSWindowSharingNone` — completely excluded from Window Server captures, Zoom, Teams, Google Meet, and OBS)

### 4. Taskbar & Dock Hiding
- **Windows:** Uses `WS_EX_TOOLWINDOW` style to hide from the Windows Taskbar and `Alt+Tab`
- **macOS:** Sets `NSApp.setActivationPolicy_(1)` (`NSApplicationActivationPolicyAccessory`) to hide the app from the macOS Dock and `Cmd+Tab` switcher

### 5. Global Hotkey Control
- **System-wide shortcuts** work from any application
- No need to click or focus the AI window
- All interaction via keyboard only
- **macOS note:** The `Alt` key maps directly to `Option` (`⌥`). Global hotkeys use `pynput` with native macOS Accessibility permission checks.

## 🚀 Step-by-Step Stealth Setup

### Initial Setup
1. **Launch silently**:
   - **Windows:** Use `run.bat` or `silent_run.vbs` to start
   - **macOS:** Run `./run.sh` from Terminal (ensure Accessibility permission is granted in **System Settings > Privacy & Security > Accessibility**)
2. **Enable stealth mode**: Press `Alt+Shift+S` (or `Option+Shift+S` on Mac) to activate proctoring stealth mode
3. **Verify setup**: Window should be semi-transparent, click-through, and always on top

### During Proctored Sessions

#### ✅ SAFE Actions (Undetectable)
- `Alt+H` / `Alt+Z` - Show/hide window (no focus change)
- `Alt+,` / `Alt+.` - Scroll window content up / down (hold for continuous, no line shifting)
- `Alt+Shift+,` / `Alt+Shift+.` - Move window left / right **[20px increments]**
- `Alt+Shift+U` / `Alt+Shift+D` - Move window up / down **[20px increments]**
- `Alt+R` - Reset screenshot queue (safe internal function)
- `Alt+O` - Reset interview session (safe internal function)
- `Alt+1/2/3` - Adjust transparency (40%/70%/100%)
- `Alt+V` - Toggle vision mode
- `Alt+S` - Capture screenshot
- `Alt+P` - Process screenshots with AI
- `Alt+T` - Switch vision model
- `Alt+Q/W/E` - Switch primary / secondary / auto-select AI
- `Alt+M` - Toggle microphone mute
- `Alt+U` - Toggle universal mute (pause)
- All other global hotkeys listed below

#### ⚠️ CAUTION Actions (Use Carefully)
- `Alt+X` - Toggle ghost mode (DANGEROUS if accidentally disabled during session)

#### ❌ DANGEROUS Actions (Will Be Detected)
- **Never click on the AI window** - This gives it focus
- **Never drag or resize the window** - Creates focus events
- **Never use Alt+Tab** to switch to the AI window
- **Never maximize/minimize** the AI window manually
- **AVOID Alt+X during sessions** - Can accidentally disable ghost mode and make window clickable

## 🎮 Complete Cross-Platform Hotkey Reference

> **macOS Note:** On macOS keyboards, the `Alt` key corresponds to **`Option` (`⌥`)**. Use `Option` wherever `Alt` is listed. Global hotkeys run through native macOS Accessibility events via `pynput`.

| Action | Windows Shortcut | macOS Shortcut | Category | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Enable Stealth Mode** | `Alt + Shift + S` | `⌥ + Shift + S` | Stealth | Activates click-through, transparency & capture exclusion |
| **Toggle Visibility** | `Alt + H` *(or `Alt + Z`)* | `⌥ + H` *(or `⌥ + Z`)* | Stealth | Show/hide overlay with zero focus stealing |
| **Toggle Ghost Mode** | `Alt + X` | `⌥ + X` | Stealth | Toggle click-through on/off |
| **Transparency (40%)** | `Alt + 1` | `⌥ + 1` | Appearance | Near-invisible ghost mode (best for exams) |
| **Transparency (70%)** | `Alt + 2` | `⌥ + 2` | Appearance | Semi-transparent (balanced visibility) |
| **Transparency (100%)** | `Alt + 3` | `⌥ + 3` | Appearance | Fully opaque (maximum readability) |
| **Scroll Up** | `Alt + ,` *(or `Alt + ↑`)* | `⌥ + ,` *(or `⌥ + ↑`)* | Navigation | Continuous smooth scroll up (hold to scroll) |
| **Scroll Down** | `Alt + .` *(or `Alt + ↓`)* | `⌥ + .` *(or `⌥ + ↓`)* | Navigation | Continuous smooth scroll down (hold to scroll) |
| **Move Window Left** | `Alt + Shift + ,` *(or `Alt + ←`)* | `⌥ + Shift + ,` *(or `⌥ + ←`)* | Position | Shift overlay 20px left without mouse focus |
| **Move Window Right** | `Alt + Shift + .` *(or `Alt + →`)* | `⌥ + Shift + .` *(or `⌥ + →`)* | Position | Shift overlay 20px right without mouse focus |
| **Move Window Up** | `Alt + Shift + U` *(or `Alt + I`)* | `⌥ + Shift + U` *(or `⌥ + I`)* | Position | Shift overlay 20px up without mouse focus |
| **Move Window Down** | `Alt + Shift + D` *(or `Alt + J`)* | `⌥ + Shift + D` *(or `⌥ + J`)* | Position | Shift overlay 20px down without mouse focus |
| **Primary AI Preset** | `Alt + Q` | `⌥ + Q` | AI Control | Instant switch to Primary AI model (e.g. Cerebras) |
| **Secondary AI Preset**| `Alt + W` | `⌥ + W` | AI Control | Instant switch to Secondary AI model (e.g. Groq) |
| **Auto-Select AI** | `Alt + E` | `⌥ + E` | AI Control | Auto-select best/fastest healthy provider |
| **Toggle Vision Mode** | `Alt + V` | `⌥ + V` | Vision AI | Open/close Vision AI screenshot capture overlay |
| **Capture Screenshot** | `Alt + S` | `⌥ + S` | Vision AI | Capture current screen and add to processing queue |
| **Process Screenshots**| `Alt + P` | `⌥ + P` | Vision AI | Send queued screenshots to Vision LLM for analysis |
| **Clear Screenshot Queue**| `Alt + R` | `⌥ + R` | Vision AI | Clear pending screenshot queue |
| **Switch Vision Model** | `Alt + T` | `⌥ + T` | Vision AI | Switch active Vision model (e.g. Cerebras ↔ Gemini) |
| **Toggle Answer Mode** | `Alt + G` | `⌥ + G` | AI Control | Toggle between Full Solutions and Concise Quick Hints |
| **Toggle Mic Mute** | `Alt + M` | `⌥ + M` | Audio | Mute/unmute microphone from speech recognition |
| **Universal Pause** | `Alt + U` | `⌥ + U` | Audio | Pause all transcription & AI processing |
| **Reset Interview** | `Alt + O` | `⌥ + O` | System | Reset session state, transcript buffer & hints |

## 🎯 Proctoring Session Workflow

### Before the Session
1. Start application with `silent_run.vbs`
2. Press `Alt+Shift+S` to enable proctoring stealth mode
3. Test all hotkeys to ensure they work
4. Position window in a corner at 40% transparency (`Alt+1`)

### During the Session
1. **Keep the proctored application in focus at all times**
2. Use only global hotkeys to interact with AI assistant (`Alt` on Windows, `Option` on Mac)
3. **Never click on the AI window** - it's click-through anyway
4. Use `Alt/Opt + H` (or `Alt/Opt + Z`) to show/hide as needed
5. Use `Alt/Opt + Shift + , / .` and `Alt/Opt + Shift + U / D` to reposition window
6. Use `Alt/Opt + , / .` to scroll content without clicking or shifting cursor lines
7. Use `Alt/Opt + 1` for maximum stealth (40% transparency)

### Emergency Hide
- `Alt/Opt + H` (or `Alt/Opt + Z`) - Instantly hide window without focus change
- Window remains ready for immediate recall

## 🔧 Technical Details

### Focus-Free Technology
```
Windows:
  SW_SHOWNOACTIVATE (4) - Shows window without activation
  vs SW_SHOW (5) - Shows window and gives it focus (DANGEROUS)

macOS:
  NSWindow.orderFrontRegardless() - Shows window without making it key or stealing focus
  vs orderFront() / makeKeyAndOrderFront() (DANGEROUS)
```

### Ghost Mode Implementation  
```
Windows:
  WS_EX_TRANSPARENT - Makes window click-through
  Combined with WS_EX_LAYERED for transparency
  Always-on-top positioning without focus (HWND_TOPMOST)

macOS:
  NSWindow.setIgnoresMouseEvents_(True) - Makes window click-through
  Combined with setOpaque_(False) and setAlphaValue_(alpha)
  Always-on-top floating level: NSFloatingWindowLevel (3) + CanJoinAllSpaces
```

### Screen Capture Protection
```
Windows:
  WDA_EXCLUDEFROMCAPTURE (0x11) - Excludes from all capture methods
  - Screen recording software (OBS, Camtasia, etc.)
  - Screen sharing (Teams, Zoom, Meet, etc.)  
  - Screenshots and screen capture APIs

macOS:
  NSWindow.setSharingType_(0) (NSWindowSharingNone)
  - Excluded from Window Server screen capture
  - Excluded from Zoom, Teams, Meet screen shares
  - Excluded from OBS and macOS Screenshot utility
```

## 🚨 Important Warnings

### ⚠️ CRITICAL: Alt+X Safety Warning
**Alt+X toggles ghost mode on/off**. During proctoring sessions:
- If you accidentally press Alt+X, you could **disable ghost mode**
- This makes the window **clickable again** and creates risk of accidental focus
- **Only use Alt+X during setup phase** before proctoring begins
- **If accidentally pressed during session**: Press Alt+X again immediately to re-enable ghost mode

### DO NOT:
- Click anywhere on the AI window
- Use mouse to interact with the AI interface
- Drag, resize, or manually manipulate the window
- Use Alt+Tab to switch to the AI window
- Focus the AI window in any way
- **Press Alt+X accidentally during proctoring** - Can disable ghost mode and make window clickable

### ALWAYS:
- Use global hotkeys exclusively
- Keep proctored application in focus
- Test hotkeys before important sessions
- Use 40% transparency for maximum stealth
- Launch via `silent_run.vbs` for complete silence

## 🎓 Pro Tips

### For Different Scenarios

#### Online Exams
- Use 40% transparency (`Alt+1`)
- Position in bottom corner
- Use vision mode for question analysis
- Capture screenshots of questions with `Alt+S`

#### Video Interviews  
- Use 70% transparency (`Alt+2`)
- Position off to the side
- Keep mostly hidden (`Alt+Z`)
- Use for research between questions

#### Monitored Work Sessions
- Use ghost mode constantly (`Alt+X`)
- Quick show/hide with `Alt+Z`
- Adjust transparency based on lighting

### Optimal Positioning
- **Bottom right corner** - least likely to obstruct content
- **Semi-transparent** - visible but not obvious
- **Small size** - minimally intrusive
- **Always on top** - accessible when needed

### Stealth Window Movement
- Use `Alt/Opt + Shift + ,` - Move window left (20px per press)
- Use `Alt/Opt + Shift + .` - Move window right (20px per press)
- Use `Alt/Opt + Shift + U` - Move window up (20px per press)
- Use `Alt/Opt + Shift + D` - Move window down (20px per press)
- **No focus change** - Window moves without activation
- **Zero editor collisions** - Won't conflict with text selection or cursor movement

### Stealth Content Scrolling
- Use `Alt/Opt + ,` (Comma) - Scroll content up (hold for continuous)
- Use `Alt/Opt + .` (Period) - Scroll content down (hold for continuous)
- **No focus change** - Content scrolls without activating window
- **Zero line shifting** - Eliminates arrow key line jumps in your code editor
- **Hold and release** - Scrolling continues smoothly while held, stops on release

## 🔍 Testing Your Setup

Before any important session:

1. **Test all hotkeys** - Ensure they respond correctly
2. **Check transparency** - Verify opacity levels work
3. **Test ghost mode** - Confirm click-through behavior  
4. **Verify capture protection** - Record screen to confirm black rectangle
5. **Practice workflow** - Rehearse typical usage patterns

## 🛠️ Troubleshooting

### Hotkeys Not Working
- Restart application
- Check if window handle is properly set
- Ensure no other software is blocking global hotkeys

### Window Gaining Focus
- Verify you're using `Alt+Z` not clicking
- Check if ghost mode is enabled (`Alt+X`)
- Restart application and re-enable stealth mode

### Visible in Recordings
- Check if screen capture protection applied correctly
- Restart application if protection failed
- Use higher transparency as backup

## 🎯 Success Metrics

A properly configured stealth setup will:
- ✅ Never appear in screen recordings (black rectangle)
- ✅ Never trigger focus change detection
- ✅ Remain accessible via global hotkeys
- ✅ Stay visually subtle and unobtrusive
- ✅ Work without any mouse interaction

Remember: The key to undetectable usage is **never giving the AI window focus**. Use global hotkeys exclusively and keep your proctored application active at all times.