// Modular main.js - Entry point and coordination
import { StateManager } from './state-manager.js';
import { WebSocketHandler } from './websocket-handler.js';
import { ProviderManager } from './provider-manager.js';
import {
    setupMicrophone,
    startAudioProcessing,
    stopAudioProcessing,
    getScreenVideoTrack,
    isScreenSharingAvailable
} from './audio_handler.js';
import muteManager from './mute-manager.js';
import { autofillForTesting } from './dev.js';
import { loadConfig, isDev, devLog, devWarn, devError, applyConsoleGate } from './config.js';
import liveInterviewUI from './live-interview.js';
import hotkeyManager, { isAppShortcut } from './hotkeys.js';
import presetManager from './preset-manager.js';
import screenshotService from './screenshot-service.js';
import { ConfigManager } from './config-manager.js';
import { testStreamingMarkdown, testSampleMarkdown } from './streaming-markdown-demo.js';

// Initialize managers
const stateManager = new StateManager();
const webSocketHandler = new WebSocketHandler(stateManager);
const providerManager = new ProviderManager(stateManager, webSocketHandler);
const configManager = new ConfigManager(stateManager);

// Expose to window for inter-module integration
window.providerManager = providerManager;
window.configManager = configManager;
window.wsHandler = webSocketHandler; // P4: used by Ctrl+Shift+Win+G hotkey

// --- Dependency Injection ---
// Wire the managers together to avoid race conditions and reliance on globals.
// This ensures the WebSocketHandler has a direct reference to the ProviderManager.
webSocketHandler.setProviderManager(providerManager);

// --- DOM Elements ---
const views = {
    onboarding: document.getElementById('onboarding-view'),
    preflight: document.getElementById('preflight-view'),
    live: document.getElementById('live-view'),
};

const micSelect = document.getElementById('mic-select');
const proceedButton = document.getElementById('proceed-to-checks');
const startButton = document.getElementById('start-interview-button');
const backButton = document.getElementById('back-to-onboarding-btn');
let sessionTimer;
let sessionStartedAt;

// --- Tab Management ---
function setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab');

            // Update buttons
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update panes
            tabPanes.forEach(p => p.classList.remove('active'));
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.classList.add('active');

            // Refresh advanced config if switching to that tab
            if (targetId === 'advanced-config-tab') {
                configManager.loadInitialData();
            }
        });
    });

    // Wire up the Fill Demo Data button
    const fillDemoBtn = document.getElementById('fill-demo-btn');
    if (fillDemoBtn) {
        fillDemoBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            autofillForTesting();
            fillDemoBtn.textContent = '✅ Filled!';
            setTimeout(() => { fillDemoBtn.textContent = 'Try sample details'; }, 1500);
        });
    }
}


// --- View Management ---
function switchView(targetView) {
    Object.values(views).forEach(view => view.classList.remove('active'));
    views[targetView].classList.add('active');
    document.body.dataset.view = targetView;
}

function handleOnboarding() {
    const validation = document.getElementById('session-validation');
    validation.hidden = true;
    if (stateManager.handleOnboarding()) {
        switchView('preflight');
        runPreFlightChecks();
    } else {
        validation.textContent = 'Add your name, company, role, and resume, then choose an interview focus and AI model.';
        validation.hidden = false;
    }
}

async function runPreFlightChecks() {
    await loadAudioOutputs();
    // --- 1. Microphone Check ---
    // First, ensure we have microphone permissions as this is a prerequisite.
    const micPermissionCheck = document.getElementById('check-mic-permission');
    const micSelectionCheck = document.getElementById('check-mic-selection');

    providerManager.webSocketHandler.updateCheckStatus(micPermissionCheck, 'pending', 'Requesting Microphone...');
    const micPermission = await setupMicrophone();
    if (micPermission) {
        providerManager.webSocketHandler.updateCheckStatus(micPermissionCheck, 'success', 'Microphone Permission OK');
        providerManager.webSocketHandler.updateCheckStatus(micSelectionCheck, 'success', 'Microphone Selection Ready');
    } else {
        providerManager.webSocketHandler.updateCheckStatus(micPermissionCheck, 'error', 'Microphone Permission Denied');
        providerManager.webSocketHandler.updateCheckStatus(micSelectionCheck, 'error', 'Microphone Selection Failed');
        return;
    }

    // --- 2. Backend Connection and Session Establishment (NEW ASYNC FLOW) ---
    // We now `await` the connection. The `connect` method returns a promise that
    // only resolves after the WebSocket is open AND the server has confirmed
    // that a session (new or resumed) is established.
    try {
        providerManager.webSocketHandler.updateCheckStatus(providerManager.checks.backend, 'pending', 'Connecting to Backend...');
        await webSocketHandler.connect();
        providerManager.webSocketHandler.updateCheckStatus(providerManager.checks.backend, 'success', 'Backend Connected');
    } catch (error) {
        providerManager.webSocketHandler.updateCheckStatus(providerManager.checks.backend, 'error', 'Backend Connection Failed');
        console.error("Failed to establish WebSocket connection and session:", error);
        // The error status is already set within the WebSocketHandler's onError method.
        return; // Stop checks if backend connection fails.
    }

    // --- 3. AI Provider and Deepgram API Verification ---
    // These checks are now only run *after* the backend session is confirmed to be ready.
    // This ensures that the verification messages can be sent reliably.
    await providerManager.runPreFlightChecks();
}

// These functions are now handled by the modules

// This function is now handled by WebSocketHandler

// This function is now handled by WebSocketHandler

async function startInterview() {
    switchView('live');
    liveInterviewUI.init();
    liveInterviewUI.initialize();
    hotkeyManager.setEnabled(true);

    // A4: surface device-loss events from audio_handler as visible warnings —
    // a dead mic or stopped screen-share used to fail silently mid-interview.
    if (!window.__deviceLossListenersAttached) {
        window.addEventListener('superassist:device-loss', (e) => {
            liveInterviewUI.addMessage(
                `⚠️ ${e.detail?.device || 'Audio device'} stopped unexpectedly! Transcription may be interrupted — restart the interview or re-select your devices.`,
                'system-error'
            );
        });
        window.addEventListener('superassist:audio-suspended', () => {
            if (!window.__backupAudioActive) {
                liveInterviewUI.addMessage(
                    '⚠️ Audio engine was briefly suspended by OS — attempting automatic resume...',
                    'system-error'
                );
            }
        });
        window.addEventListener('superassist:backup-audio-started', () => {
            window.__backupAudioActive = true;
            liveInterviewUI.addMessage(
                '🛡️ Backup audio engine activated — speech capture is running smoothly.',
                'system-message'
            );
        });
        window.addEventListener('superassist:no-system-audio', () => {
            liveInterviewUI.addMessage(
                '⚠️ System audio was NOT shared! The interviewer\'s voice will not be captured. To fix: End Interview, click Start Interview again, select "Entire Screen", and ensure "Also share system audio" is checked at the bottom-left.',
                'system-error'
            );
        });
        window.__deviceLossListenersAttached = true;
    }

    const onAudioData = (audioData, speakerHint) => {
        webSocketHandler.sendAudioChunk(audioData, muteManager.isMicrophoneMuted(), speakerHint);
    };

    const nativeCapture = document.getElementById('audio-capture-mode').value === 'native';
    const processingStarted = await startAudioProcessing(micSelect.value, onAudioData, !nativeCapture);

    if (!processingStarted && !nativeCapture) {
        console.error("❌ Could not start audio streams. Please check permissions and try again.");
        switchView('preflight');
        const notice = document.getElementById('audio-setup-error');
        notice.hidden = false;
        notice.textContent = 'Audio capture could not start. Check microphone access. For browser capture, select your meeting tab or entire screen and enable Share audio.';
        hotkeyManager.setEnabled(false);
        return;
    }
    if (!processingStarted && nativeCapture) {
        liveInterviewUI.addMessage('Microphone access is unavailable. Windows system audio will still capture the interviewer. Enable microphone access and restart if you also want your own speech transcribed.', 'system-message');
    }

    try {
        await webSocketHandler.startInterview();
    } catch (error) {
        stopAudioProcessing();
        hotkeyManager.setEnabled(false);
        webSocketHandler.endInterview();
        switchView('preflight');
        const notice = document.getElementById('audio-setup-error');
        notice.textContent = `Session could not start: ${error.message}. Check the selected output or use browser capture.`;
        notice.hidden = false;
        await webSocketHandler.connect();
        return;
    }
    document.getElementById('live-session-title').textContent = `${stateManager.appState.onboardingData.role} at ${stateManager.appState.onboardingData.company}`;
    webSocketHandler.sendMessage('set_auto_answer', { enabled: document.getElementById('auto-answer-toggle').checked });
    sessionStartedAt = Date.now();
    clearInterval(sessionTimer);
    sessionTimer = setInterval(() => {
        const seconds = Math.floor((Date.now() - sessionStartedAt) / 1000);
        document.getElementById('session-timer').textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    }, 1000);
}

async function endInterview() {
    clearInterval(sessionTimer);
    document.getElementById('session-timer').textContent = '00:00';
    console.log('🔚 Ending interview and clearing state...');

    // P3: save the turn-by-turn transcript before the session is torn down.
    try { await webSocketHandler.exportTranscript(); } catch (e) { console.warn('Transcript export skipped:', e); }

    // Stop all audio processing
    stopAudioProcessing();

    // Send end interview signal to backend
    webSocketHandler.endInterview();

    // Disable hotkeys
    hotkeyManager.setEnabled(false);

    // Clear conversation UI
    if (window.liveInterviewUI) {
        liveInterviewUI.clearConversation();
    }

    // Comprehensive state clearing
    stateManager.clearInterviewState();

    // Reset preset manager if available
    if (window.presetManager) {
        presetManager.clearNotifications?.();
    }

    // Switch back to onboarding
    switchView('onboarding');

    console.log('✅ Interview ended and state cleared successfully');
}

async function resetInterview() {
    console.log('🔄 Resetting interview...');

    // Send reset signal to backend
    webSocketHandler.sendMessage('reset_session', {});

    // Clear conversation UI
    if (window.liveInterviewUI) {
        liveInterviewUI.clearConversation();
        liveInterviewUI.showActivity('Listening...');
    }

    console.log('✅ Interview reset successfully');
}

// Provider management functions are now handled by ProviderManager


// --- Preset Switching Functions ---
function switchPreset(presetKey) {
    return webSocketHandler.switchPreset(presetKey);
}

// --- Transparency Functions ---
async function setTransparency(level) {
    return await liveInterviewUI.setTransparency(level);
}

function getSystemStatus() {
    return stateManager.getSystemStatus();
}

// --- Vision Mode Functions ---
function switchVisionModel() {
    return stateManager.switchVisionModel();
}

function toggleVisionMode() {
    return stateManager.toggleVisionMode();
}

// --- Screenshot Functions ---
async function captureScreenshot() {
    return await stateManager.captureScreenshot();
}

async function processScreenshots() {
    return await stateManager.processScreenshots();
}

async function resetScreenshotQueue() {
    return await stateManager.resetScreenshotQueue();
}

// --- Audio Toggle Functions ---
function toggleMicMute() {
    return stateManager.toggleMicMute();
}

function toggleUniversalMute() {
    return stateManager.toggleUniversalMute();
}

// --- Event Listeners ---
function setupEventListeners() {
    proceedButton?.addEventListener('click', handleOnboarding);
    startButton?.addEventListener('click', startInterview);
    backButton?.addEventListener('click', () => switchView('onboarding'));
    document.getElementById('audio-capture-mode').addEventListener('change', updateAudioCaptureHelp);
    window.addEventListener('superassist:session-lost', () => {
        stopAudioProcessing();
        hotkeyManager.setEnabled(false);
        clearInterval(sessionTimer);
        switchView('preflight');
        const notice = document.getElementById('audio-setup-error');
        notice.hidden = false;
        notice.textContent = 'The server restarted. Start a new session to resume transcription.';
    });
    navigator.mediaDevices?.addEventListener('devicechange', () => {
        if (stateManager.isLiveInterviewActive() && document.getElementById('audio-capture-mode').value === 'native') {
            liveInterviewUI.addMessage('Audio devices changed. If your meeting moved to different headphones or speakers, end this session and select the new output before restarting.', 'system-message');
        }
    });
    document.querySelectorAll('[data-workspace-tab]').forEach(button => {
        button.addEventListener('click', () => {
            if (stateManager.isLiveInterviewActive()) {
                liveInterviewUI.addMessage('End this session before changing session settings.', 'system-message');
                return;
            }
            switchView('onboarding');
            document.querySelector(`[data-tab="${button.dataset.workspaceTab}"]`).click();
            document.querySelectorAll('.workspace-nav').forEach(item => item.classList.toggle('active', item === button));
        });
    });
    document.getElementById('answer-btn').addEventListener('click', () => webSocketHandler.sendMessage('request_answer', {}));
    const moreMenu = document.querySelector('.live-more');
    document.addEventListener('click', event => {
        if (!moreMenu.contains(event.target) || event.target.closest('.live-more-menu button')) moreMenu.open = false;
    });
    moreMenu.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            moreMenu.open = false;
            moreMenu.querySelector('summary').focus();
        }
    });
    document.getElementById('auto-answer-toggle').addEventListener('change', event => {
        webSocketHandler.sendMessage('set_auto_answer', { enabled: event.target.checked });
    });
    document.getElementById('chat-btn').addEventListener('click', () => document.getElementById('chat-question').focus());
    document.getElementById('chat-form').addEventListener('submit', event => {
        event.preventDefault();
        const input = document.getElementById('chat-question');
        const question = input.value.trim();
        if (!question || !webSocketHandler.socket || webSocketHandler.socket.readyState !== WebSocket.OPEN) return;
        webSocketHandler.sendMessage('ask_question', { question });
        liveInterviewUI.addMessage(question, 'candidate');
        input.value = '';
    });
    document.getElementById('export-transcript-btn').addEventListener('click', async () => {
        try { await webSocketHandler.exportTranscript(); }
        catch (error) { liveInterviewUI.addMessage('Could not save the transcript. Try again before ending the session.', 'system-error'); }
    });
    document.getElementById('screenshot-btn').addEventListener('click', async () => {
        if (!stateManager.appState.visionMode.isActive && !stateManager.toggleVisionMode()) return;
        const captured = await captureScreenshot();
        if (captured) await processScreenshots();
    });
    document.getElementById('transcript-stream').addEventListener('scroll', event => {
        const stream = event.currentTarget;
        liveInterviewUI.transcriptReading = stream.scrollHeight - stream.scrollTop - stream.clientHeight > 80;
    }, { passive: true });

    // Provider change listeners
    const providerSelect = document.getElementById('ai-provider-select');
    const secondaryProviderSelect = document.getElementById('ai-secondary-provider-select');
    const visionProviderSelect = document.getElementById('vision-provider-select');
    const visionSecondaryProviderSelect = document.getElementById('vision-secondary-provider-select');

    providerSelect?.addEventListener('change', providerManager.updateModelDropdown.bind(providerManager));
    secondaryProviderSelect?.addEventListener('change', providerManager.updateSecondaryModelDropdown.bind(providerManager));
    visionProviderSelect?.addEventListener('change', providerManager.updateVisionModelDropdown.bind(providerManager));
    visionSecondaryProviderSelect?.addEventListener('change', providerManager.updateSecondaryVisionModelDropdown.bind(providerManager));

    setupGlobalCopyHandler();
}

async function loadAudioOutputs() {
    const mode = document.getElementById('audio-capture-mode');
    const output = document.getElementById('audio-output-select');
    try {
        const response = await fetch('/api/audio-outputs');
        if (!response.ok) throw new Error('Could not list audio outputs');
        const info = await response.json();
        if (info.available && !mode.querySelector('[value=native]')) {
            mode.add(new Option('Windows direct audio (recommended)', 'native'));
            mode.value = 'native';
        }
        const selected = output.value;
        output.replaceChildren(new Option(info.default ? `Windows default — ${info.default.replace(' [Loopback]', '')}` : 'Windows default output', ''));
        for (const device of info.devices) output.add(new Option(device.name.replace(' [Loopback]', ''), device.name));
        if (info.devices.some(d => d.name === selected)) output.value = selected;
    } catch (error) {
        console.warn('Native output capture unavailable:', error);
    }
    updateAudioCaptureHelp();
}

function updateAudioCaptureHelp() {
    const native = document.getElementById('audio-capture-mode').value === 'native';
    document.getElementById('audio-output-select').disabled = !native;
    document.getElementById('audio-capture-help').textContent = native
        ? 'No screen-sharing prompt is needed. Play meeting or YouTube audio through the selected headphones/speakers. System sound is captured directly, separately from your microphone. After changing output devices, restart the session.'
        : 'Choose your meeting browser tab and enable Share audio. For a desktop meeting, share the entire screen with system audio. Use headphones.';
}

// Delegated copy handler for all code blocks
function setupGlobalCopyHandler() {
    document.addEventListener('click', async (e) => {
        const copyBtn = e.target.closest('.copy-btn, .copy-button');
        if (!copyBtn) return;
        
        const container = copyBtn.closest('.code-block-container, .code-block');
        if (!container) return;
        
        let textToCopy = '';
        const blockId = container.dataset.blockId;
        if (blockId && window.liveInterviewUI?.markdownParser?.codeBlockSources?.has(blockId)) {
            textToCopy = window.liveInterviewUI.markdownParser.codeBlockSources.get(blockId);
        } else {
            const codeElem = container.querySelector('code');
            textToCopy = codeElem ? codeElem.textContent : '';
        }
        
        if (textToCopy) {
            try {
                await navigator.clipboard.writeText(textToCopy);
                const originalText = copyBtn.textContent;
                copyBtn.textContent = '✅';
                setTimeout(() => {
                    copyBtn.textContent = originalText;
                }, 2000);
            } catch (err) {
                console.warn('Copy failed:', err);
            }
        }
    });
}

// Main initialization
window.addEventListener('DOMContentLoaded', async () => {
    await loadConfig();
    applyConsoleGate(); // Suppress console.log/debug/info when DEV_MODE is off
    await providerManager.loadAiProviders();
    liveInterviewUI.init();
    setupEventListeners();
    setupDeveloperShortcuts();
    setupPresetHotkeys();
    setupTabs();
    hotkeyManager.setEnabled(false);
    switchView('onboarding');
});

// --- Developer Shortcuts ---
function setupDeveloperShortcuts() {

    devLog('🛠️ Developer shortcuts enabled');

    // Console helper functions
    if (isDev) {
        console.log(`
🧪 === AURA DEVELOPER TOOLS ===
Available testing functions:
• testSampleMarkdown() - Test with sample markdown content  
• testStreamingMarkdown() - Test with comprehensive scenarios
• closeAllTestWindows() - Close all test windows manually
• closeTestWindow('id') - Close specific test window
• autofillForTesting() - Auto-fill onboarding form
• Ctrl+J - Auto-fill form shortcut

📝 Real-time Markdown Testing:
The new hybrid streaming markdown parser integrates with the existing 
MarkdownProcessor to provide real-time rendering that's compatible 
with code blocks, syntax highlighting, and all existing features.

🕒 Auto-Close Feature:
Test windows now auto-close after 10 seconds with countdown display.
Manual close (× button) cancels auto-close timer.

Try: testSampleMarkdown()

🔧 Code Block Fix Applied:
• Fixed missing code blocks in streaming responses
• Added proper syntax highlighting with Prism.js
• Integrated with existing MarkdownProcessor system
• Real-time code block rendering during streaming
        `);
    }

    window.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'j') {
            e.preventDefault();
            devLog('🛠️ Auto-filling form via Ctrl+J');
            autofillForTesting();
        }
    });
}

function setupPresetHotkeys() {
    devLog('🎹 Setting up preset switching and vision hotkeys');
    document.addEventListener('keydown', (e) => {
        // Only work during live interview and if not focusing on input fields
        if (!e.target.matches('input, textarea, select') && stateManager.isLiveInterviewActive()) {
            if (isAppShortcut(e) && !e.repeat) {
                switch (e.key.toLowerCase()) {
                    case 'q':
                        e.preventDefault();
                        switchPreset('primary');
                        devLog('🔄 Hotkey: Switching to primary preset');
                        break;
                    case 'w':
                        e.preventDefault();
                        switchPreset('secondary');
                        devLog('🔄 Hotkey: Switching to secondary preset');
                        break;
                    case 'e':
                        e.preventDefault();
                        switchPreset('auto');
                        devLog('🔄 Hotkey: Auto-selecting best preset');
                        break;
                    case 't':
                        e.preventDefault();
                        switchVisionModel();
                        devLog('🔄 Hotkey: Switching vision model');
                        break;
                    case 'v':
                        e.preventDefault();
                        toggleVisionMode();
                        devLog('👁️ Hotkey: Toggling vision mode');
                        break;
                    case 's':
                        e.preventDefault();
                        captureScreenshot();
                        devLog('📸 Hotkey: Capturing screenshot');
                        break;
                    case 'p':
                        e.preventDefault();
                        processScreenshots();
                        devLog('🔄 Hotkey: Processing screenshots');
                        break;
                }
            }
        }
    });
}

// --- Global Exports ---
// Make functions globally accessible for hotkeys and external calls
window.switchPreset = switchPreset;
window.setTransparency = setTransparency;
window.getSystemStatus = getSystemStatus;
window.switchVisionModel = switchVisionModel;
window.toggleVisionMode = toggleVisionMode;
window.captureScreenshot = captureScreenshot;
window.processScreenshots = processScreenshots;
window.resetScreenshotQueue = resetScreenshotQueue;
window.toggleMicMute = toggleMicMute;
window.toggleUniversalMute = toggleUniversalMute;
window.endInterview = endInterview;
window.resetInterview = resetInterview;
window.getScreenVideoTrack = getScreenVideoTrack;
window.isScreenSharingAvailable = isScreenSharingAvailable;
window.testStreamingMarkdown = testStreamingMarkdown;
window.testSampleMarkdown = testSampleMarkdown;

// Export managers for other modules
window.appState = stateManager.getState();
window.sendSocketMessage = (type, payload) => webSocketHandler.sendMessage(type, payload);
window.webSocketHandler = webSocketHandler;

// Export for external use
export { switchView, startInterview, endInterview, stateManager, webSocketHandler, providerManager };
