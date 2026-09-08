// --- mute-manager.js ---
// Centralized module for managing all mute states in the application.
// This includes microphone mute, universal mute (system pause), and any future mute-related features.

import { devLog } from './config.js';

class MuteManager {
    constructor() {
        // --- State Properties ---
        this._isMicrophoneMuted = true; // Traditional microphone mute (input to app)
        this._isUniversallyMuted = false; // System-wide pause for all audio processing

        // --- Event Handling ---
        this.eventListeners = new Map();

        devLog('🔇 Mute Manager initialized');
    }

    // --- Event Emitter ---
    on(eventName, listener) {
        if (!this.eventListeners.has(eventName)) {
            this.eventListeners.set(eventName, []);
        }
        this.eventListeners.get(eventName).push(listener);
    }

    emit(eventName, data) {
        if (this.eventListeners.has(eventName)) {
            this.eventListeners.get(eventName).forEach(listener => listener(data));
        }
    }

    // --- Microphone Mute ---
    setMicrophoneMute(isMuted) {
        if (this._isMicrophoneMuted === isMuted) return;
        this._isMicrophoneMuted = isMuted;
        devLog(`🎤 Microphone mute state changed to: ${isMuted}`);
        this.emit('microphoneMuteChange', this._isMicrophoneMuted);
        this.emit('stateChange', this.getMuteStatus());
    }

    toggleMicrophoneMute() {
        this.setMicrophoneMute(!this._isMicrophoneMuted);
        return this._isMicrophoneMuted;
    }

    // --- Universal Mute (System Pause) ---
    setUniversalMute(isMuted) {
        if (this._isUniversallyMuted === isMuted) return;
        this._isUniversallyMuted = isMuted;
        devLog(`⏸️ Universal mute state changed to: ${isMuted}`);
        this.emit('universalMuteChange', this._isUniversallyMuted);
        this.emit('stateChange', this.getMuteStatus());

        // Notify the backend about the change
        if (typeof window.sendSocketMessage === 'function') {
            window.sendSocketMessage('config_update', {
                isUniversallyMuted: this._isUniversallyMuted
            });
        }
    }

    toggleUniversalMute() {
        this.setUniversalMute(!this._isUniversallyMuted);
        return this._isUniversallyMuted;
    }

    // --- State Getters ---
    isMicrophoneMuted() {
        return this._isMicrophoneMuted;
    }

    isUniversallyMuted() {
        return this._isUniversallyMuted;
    }

    // Returns true if ANY form of mute is active that would stop audio processing.
    isAudioPaused() {
        return this.isUniversallyMuted();
    }

    getMuteStatus() {
        return {
            microphone: this.isMicrophoneMuted(),
            universal: this.isUniversallyMuted(),
            isAudioPaused: this.isAudioPaused(),
            description: this.getCurrentStateDescription()
        };
    }

    getCurrentStateDescription() {
        if (this.isUniversallyMuted()) {
            return 'System Paused: All audio processing is stopped.';
        }
        if (this.isMicrophoneMuted()) {
            return 'Microphone Muted: Only interviewer speech is being processed.';
        }
        return 'Active: All speakers are being processed.';
    }
}

// Create a singleton instance
const muteManager = new MuteManager();

// --- Global Functions for Console and Module Access ---
window.muteManager = muteManager;
window.toggleUniversalMute = () => muteManager.toggleUniversalMute();
window.enableUniversalMute = () => muteManager.setUniversalMute(true);
window.disableUniversalMute = () => muteManager.setUniversalMute(false);
window.getMuteStatus = () => muteManager.getMuteStatus();
window.pauseInterview = window.enableUniversalMute; // Alias
window.resumeInterview = window.disableUniversalMute; // Alias

// For modules
export default muteManager;