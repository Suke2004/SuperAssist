// Hotkeys Module for Aura
// Provides keyboard shortcuts for transparency and other controls

import { devLog } from './config.js';
import muteManager from './mute-manager.js';
import liveInterviewUI from './live-interview.js';

export const isAppShortcut = event => !event.defaultPrevented && !window.__nativeHotkeys && (/Mac/.test(navigator.platform)
    ? event.altKey && !event.ctrlKey && !event.metaKey && (!event.shiftKey || !!window.pywebview?.api)
    : event.ctrlKey && event.shiftKey && event.metaKey && !event.altKey);

const shortcutCode = event => {
    const special = { ArrowLeft: 0x25, ArrowUp: 0x26, ArrowRight: 0x27, ArrowDown: 0x28,
        PageUp: 0x21, PageDown: 0x22, F1: 0x70, F2: 0x71, F3: 0x72, BracketLeft: 0xDB, BracketRight: 0xDD };
    if (/Mac/.test(navigator.platform)) {
        if (event.shiftKey) return { KeyS: 89, Comma: 0x25, Period: 0x27, KeyU: 0x26, KeyD: 0x28 }[event.code];
        const mac = { KeyX: 75, KeyZ: 72, Digit1: 0x70, Digit2: 0x71, Digit3: 0x72,
            Comma: 0x21, Period: 0x22, ArrowUp: 0x21, ArrowDown: 0x22, KeyI: 0x26, KeyJ: 0x28 };
        if (mac[event.code]) return mac[event.code];
    }
    return special[event.code] || (/^Key[HKVSPRQWETMUYOG]$/.test(event.code) ? event.code.charCodeAt(3) : undefined);
};

class HotkeyManager {
    constructor() {
        this.transparencyLevels = [0.2, 0.4, 0.6, 0.8, 1.0]; // 5 levels: 20%, 40%, 60%, 80%, 100%
        this.currentTransparencyLevel = 3; // Default to 80% (index 3)
        this.isEnabled = true;
        this.isAlwaysOnTop = true; // Track always-on-top state
        
        this.setupEventListeners();
        devLog('🎹 Hotkey manager initialized');
    }

    setupEventListeners() {
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
        document.addEventListener('keyup', this.handleKeyUp.bind(this));
        
    }

    handleKeyDown(event) {
        if (!this.isEnabled || !isAppShortcut(event) || event.repeat) return;
        if (window.pywebview?.api && /Mac|Linux/.test(navigator.platform)) {
            const code = shortcutCode(event);
            if (code !== undefined) {
                event.preventDefault();
                window.pywebview.api.shortcut(code);
            }
            return;
        }

        // Note: Ctrl+Shift+Win+M and Ctrl+Shift+Win+U are handled by global hotkeys only to prevent conflicts
        
        // Check for Alt+[ to decrease transparency
        if (event.code === 'BracketLeft' || event.key === '[') {
            event.preventDefault();
            this.decreaseTransparency();
            return;
        }

        // Check for Alt+] to increase transparency
        if (event.code === 'BracketRight' || event.key === ']') {
            event.preventDefault();
            this.increaseTransparency();
            return;
        }

        // P4: Ctrl+Shift+Win+G toggles full answers <-> quick hints mid-interview.
        if (event.key.toLowerCase() === 'g') {
            event.preventDefault();
            if (window.wsHandler && typeof window.wsHandler.toggleAnswerMode === 'function') {
                const fullMode = window.wsHandler.toggleAnswerMode();
                liveInterviewUI.addMessage(
                    fullMode ? '🎯 Answer mode: FULL answers' : '⚡ Answer mode: QUICK hints',
                    'system-message'
                );
            }
        }
    }

    handleKeyUp(event) {
        if (window.pywebview?.api && /Mac|Linux/.test(navigator.platform) &&
            ([0x21, 0x22].includes(shortcutCode(event)) || ['Alt', 'Control', 'Shift', 'Meta'].includes(event.key))) {
            window.pywebview.api.stop_scrolling();
        }
        // This method is kept for event listener consistency, but is currently empty.
    }

    decreaseTransparency() {
        if (this.currentTransparencyLevel > 0) {
            this.currentTransparencyLevel--;
            this.applyTransparency();
        }
    }

    increaseTransparency() {
        if (this.currentTransparencyLevel < this.transparencyLevels.length - 1) {
            this.currentTransparencyLevel++;
            this.applyTransparency();
        }
    }

    async applyTransparency() {
        const transparency = this.transparencyLevels[this.currentTransparencyLevel];
        const percent = Math.round(transparency * 100);
        
        try {
            // Only allow transparency changes during live interview
            const currentView = document.querySelector('.view.active');
            const isLiveView = currentView && currentView.id === 'live-view';
            
            if (!isLiveView) {
                console.log('ℹ️ Transparency hotkeys only work during live interview');
                this.showTransparencyFeedback(100, 'Transparency only available in live interview');
                return;
            }
            
            // Apply Windows-level transparency
            const response = await fetch('/api/transparency', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ transparency: transparency })
            });
            
            if (response.ok) {
                devLog(`🪟 Transparency set to ${percent}% via hotkey`);
                this.showTransparencyFeedback(percent);
            }
        } catch (error) {
            console.error('❌ Error setting transparency via hotkey:', error);
        }
    }

    showTransparencyHint() {
        // This hint is no longer needed as the interaction is simpler
        // The feedback on change is sufficient
    }

    hideTransparencyHint() {
        // This hint is no longer needed as the interaction is simpler
    }

    showTransparencyFeedback(percent, message = null) {
        this.removeExistingFeedback();
        
        if (message) {
            devLog(`ℹ️ Transparency: ${message}`);
        } else {
            devLog(`🪟 Transparency: ${percent}% Opacity`);
        }
        
        // Suppress on-screen floating feedback during live view for stealth
        const liveViewActive = document.getElementById('live-view')?.classList.contains('active');
        if (liveViewActive) {
            return;
        }
        
        const feedback = document.createElement('div');
        feedback.id = 'transparency-feedback';
        
        if (message) {
            feedback.innerHTML = `
                <div class="transparency-feedback">
                    ℹ️ ${message}
                </div>
            `;
        } else {
            feedback.innerHTML = `
                <div class="transparency-feedback">
                    🪟 ${percent}% Opacity
                    <div class="transparency-bar">
                        ${this.generateTransparencyBar()}
                    </div>
                </div>
            `;
        }
        
        document.body.appendChild(feedback);
        
        // Auto-hide after 2 seconds
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.remove();
            }
        }, 2000);
    }

    generateTransparencyBar() {
        let bar = '';
        for (let i = 0; i < this.transparencyLevels.length; i++) {
            const isActive = i === this.currentTransparencyLevel;
            bar += `<span class="bar-segment ${isActive ? 'active' : ''}">${isActive ? '●' : '○'}</span>`;
        }
        return bar;
    }

    removeExistingHints() {
        // This hint is no longer needed
    }

    removeExistingFeedback() {
        const existing = document.getElementById('transparency-feedback');
        if (existing) existing.remove();
    }

    // Public methods for external control
    setEnabled(enabled) {
        this.isEnabled = enabled;
        devLog(`🎹 Hotkeys ${enabled ? 'enabled' : 'disabled'}`);
    }

    getCurrentTransparency() {
        return {
            level: this.currentTransparencyLevel + 1,
            percent: Math.round(this.transparencyLevels[this.currentTransparencyLevel] * 100),
            value: this.transparencyLevels[this.currentTransparencyLevel]
        };
    }

    setTransparencyLevel(level) {
        if (level >= 1 && level <= 5) {
            this.currentTransparencyLevel = level - 1;
            this.applyTransparency();
        }
    }

    // Note: Audio toggle methods removed - handled by global hotkeys only
}

// Create global instance
const hotkeyManager = new HotkeyManager();

// Global functions for console access
window.enableHotkeys = () => hotkeyManager.setEnabled(true);
window.disableHotkeys = () => hotkeyManager.setEnabled(false);
window.getTransparencyLevel = () => hotkeyManager.getCurrentTransparency();
window.setTransparencyLevel = (level) => hotkeyManager.setTransparencyLevel(level);
window.decreaseTransparency = () => hotkeyManager.decreaseTransparency();
window.increaseTransparency = () => hotkeyManager.increaseTransparency();

export default hotkeyManager;
