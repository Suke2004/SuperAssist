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

### 2. Focus-Free Visibility  
- Window shows/hides **without ever gaining focus**
- Uses `SW_SHOWNOACTIVATE` instead of `SW_SHOW`
- Proctoring software never detects window activation

### 3. Screen Capture Protection
- Window appears as **black rectangle** in recordings
- Uses Windows `WDA_EXCLUDEFROMCAPTURE` API
- Invisible to screen sharing and recording software

### 4. Global Hotkey Control
- **System-wide shortcuts** work from any application
- No need to click or focus the AI window
- All interaction via keyboard only

## 🚀 Step-by-Step Stealth Setup

### Initial Setup
1. **Launch silently**: Use `silent_run.vbs` to start without visible console
2. **Enable stealth mode**: Press `Alt+Shift+S` to activate proctoring stealth mode
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

## 🎮 Complete Hotkey Reference

### Window Management
- `Alt+Shift+S` - **Enable proctoring stealth mode** (one-time setup)
- `Alt+H` - Toggle visibility (stealth - no focus change, safe from VS Code wrap)
- `Alt+X` - Toggle ghost mode (click-through)
- `Alt+Shift+,` / `Alt+Shift+.` - Move window left / right (stealth, 20px)
- `Alt+Shift+U` - Move window up (stealth, 20px)
- `Alt+Shift+D` - Move window down (stealth, 20px)

### Scrolling (No Arrow Keys)
- `Alt+,` (Comma) - Continuous scroll up (hold to keep scrolling, release to stop)
- `Alt+.` (Period) - Continuous scroll down (hold to keep scrolling, release to stop)

### Transparency Control  
- `Alt+1` - Transparent (40% opacity) - best for exams
- `Alt+2` - Semi-transparent (70% opacity) - balanced
- `Alt+3` - Opaque (100% opacity) - full visibility

### AI Features
- `Alt+Q` - Switch to primary AI preset
- `Alt+W` - Switch to secondary AI preset
- `Alt+E` - Auto-select best AI preset
- `Alt+V` - Toggle vision mode
- `Alt+S` - Capture screenshot
- `Alt+P` - Process screenshots with AI
- `Alt+R` - Reset screenshot queue
- `Alt+O` - **Reset interview session** (stealth)
- `Alt+T` - Switch vision model

### Audio Control
- `Alt+M` - Toggle microphone mute
- `Alt+U` - Toggle universal mute (pause)

## 🎯 Proctoring Session Workflow

### Before the Session
1. Start application with `silent_run.vbs`
2. Press `Alt+Shift+S` to enable proctoring stealth mode
3. Test all hotkeys to ensure they work
4. Position window in a corner at 40% transparency (`Alt+1`)

### During the Session
1. **Keep the proctored application in focus at all times**
2. Use only global hotkeys to interact with AI assistant
3. **Never click on the AI window** - it's click-through anyway
4. Use `Alt+Z` to show/hide as needed
5. Use `Alt+Left/Right` and `Alt+I/J` to reposition window
6. Use `Alt+Up/Down` to scroll content without clicking
7. Use `Alt+1` for maximum stealth (40% transparency)

### Emergency Hide
- `Alt+Z` - Instantly hide window without focus change
- Window remains ready for immediate recall

## 🔧 Technical Details

### Focus-Free Technology
```
SW_SHOWNOACTIVATE (4) - Shows window without activation
vs
SW_SHOW (5) - Shows window and gives it focus (DANGEROUS)
```

### Ghost Mode Implementation  
```
WS_EX_TRANSPARENT - Makes window click-through
Combined with WS_EX_LAYERED for transparency
Always-on-top positioning without focus
```

### Screen Capture Protection
```
WDA_EXCLUDEFROMCAPTURE - Excludes from all capture methods
- Screen recording software (OBS, Camtasia, etc.)
- Screen sharing (Teams, Zoom, etc.)  
- Screenshots and screen capture APIs
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
- Use `Alt+Left/Right` - Move horizontally (20px per press)
- Use `Alt+I` - Move window up (20px per press)
- Use `Alt+J` - Move window down (20px per press)
- **No focus change** - Window moves without activation
- **Perfect for repositioning** during sessions without detection

### Stealth Content Scrolling
- Use `Alt+Up` - Scroll content up (hold for continuous)
- Use `Alt+Down` - Scroll content down (hold for continuous)
- **No focus change** - Content scrolls without activating window
- **Hold and release** - Scrolling continues while held, stops on release

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