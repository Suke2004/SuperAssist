import { devLog } from './config.js';
import liveInterviewUI from './live-interview.js';

export class WebSocketHandler {
    constructor(stateManager) {
        this.stateManager = stateManager;
        this.socket = null;
        this.providerManager = null; // Direct reference to the ProviderManager
        this.session_id = null;
        this.reconnect_attempts = 0;
        this.max_reconnect_attempts = 5;
        this.is_intentionally_closing = false;
        this.connection_timeout_ms = 10000;
        this.connectionPromise = null;
        this.reconnectTimer = null;
        this.checks = {};
        this.audioBuffer = [];
        this.audioSessionReady = false;
        this.audioHealth = {};
        this.lastAudioGapWarning = 0;
        this.initializeCheckElements();
    }

    initializeCheckElements() {
        this.checks = {
            micPermission: document.getElementById('check-mic-permission'),
            micSelection: document.getElementById('check-mic-selection'),
            backend: document.getElementById('check-backend'),
            deepgram: document.getElementById('check-deepgram'),
            aiProvider: document.getElementById('check-ai-provider'),
            aiSecondaryProvider: document.getElementById('check-ai-secondary-provider'),
            visionProvider: document.getElementById('check-vision-provider'),
            visionSecondaryProvider: document.getElementById('check-vision-secondary-provider'),
        };
    }

    connect() {
        if (this.connectionPromise) {
            return this.connectionPromise.promise;
        }

        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            return Promise.resolve();
        }

        this.is_intentionally_closing = false;
        this.audioSessionReady = false;
        // Derive the host from the page origin. main.py picks a free port at
        // startup and falls back off 8002 when it is busy, so a hardcoded port
        // would break the socket exactly when the fallback kicks in.
        const host = window.location.host || '127.0.0.1:8002';
        const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let url = `${scheme}//${host}/ws`;
        if (this.session_id) {
            url += `?session_id=${this.session_id}`;
        }

        this.updateCheckStatus(this.checks.backend, 'pending', 'Connecting...');

        let resolveConnection;
        let rejectConnection;
        const promise = new Promise((resolve, reject) => {
            resolveConnection = resolve;
            rejectConnection = reject;
        });
        this.connectionPromise = {
            promise,
            resolve: resolveConnection,
            reject: rejectConnection,
            timeout: null
        };

        try {
            const socket = new WebSocket(url);
            this.socket = socket;
            this.stateManager.setSocket(socket);

            // Clear any old listeners before attaching new ones
            socket.onopen = null;
            socket.onclose = null;
            socket.onerror = null;
            socket.onmessage = null;

            // Use addEventListener for all events for consistency and robustness.
            socket.addEventListener('open', (event) => this.onOpen(event, socket));
            socket.addEventListener('close', (event) => this.onClose(event, socket));
            socket.addEventListener('error', (event) => this.onError(event, socket));
            socket.addEventListener('message', (event) => this.onMessage(event, socket));

            const pendingConnection = this.connectionPromise;
            if (pendingConnection && pendingConnection.promise === promise) {
                pendingConnection.timeout = setTimeout(() => {
                    if (!this.connectionPromise || this.connectionPromise.promise !== promise) return;

                    this._rejectConnection(new Error('WebSocket connection timed out.'));
                    if (socket.readyState !== WebSocket.CLOSED) {
                        socket.close();
                    }
                }, this.connection_timeout_ms);
            }
        } catch (error) {
            this._rejectConnection(error);
        }

        return promise;
    }

    _resolveConnection() {
        if (!this.connectionPromise) return;
        const pending = this.connectionPromise;
        this.connectionPromise = null;
        clearTimeout(pending.timeout);
        pending.resolve();
    }

    _rejectConnection(error) {
        if (!this.connectionPromise) return;
        const pending = this.connectionPromise;
        this.connectionPromise = null;
        clearTimeout(pending.timeout);
        pending.reject(error instanceof Error ? error : new Error(String(error)));
    }

    onOpen(event, socket = this.socket) {
        if (socket !== this.socket) return;
        console.log("[open] Connection established");
        // This is now handled by the ProviderManager
        // this.updateCheckStatus(this.checks.backend, 'success', 'Backend Connected');
        this.reconnect_attempts = 0;
    }

    onClose(event, socket = this.socket) {
        if (socket !== this.socket) return;
        this.audioSessionReady = false;
        this.pendingStart?.reject(new Error('Connection lost during audio startup'));
        console.log(`[close] Connection closed. Intentional: ${this.is_intentionally_closing}`);
        this._rejectConnection(new Error("WebSocket connection closed before session establishment."));
        // This is now handled by the ProviderManager
        // this.updateCheckStatus(this.checks.backend, 'error', 'Disconnected');
        if (!this.is_intentionally_closing) {
            this.handleReconnect();
        }
    }

    onError(error, socket = this.socket) {
        if (socket !== this.socket) return;
        console.error(`[error] WebSocket error:`, error);
        this._rejectConnection(new Error("WebSocket connection failed."));
        // Ensure the failed socket reaches close before a reconnect is
        // scheduled, so an error cannot leave an overlapping live attempt.
        if (socket && !this.is_intentionally_closing && socket.readyState !== WebSocket.CLOSED) {
            socket.close();
        }
        // This is now handled by the ProviderManager
        // this.updateCheckStatus(this.checks.backend, 'error', 'Connection Failed');
    }
    
    onMessage(event, socket = this.socket) {
        if (socket !== this.socket) return;
        const data = JSON.parse(event.data);
        devLog("Received from backend:", data);

        if (data.type === 'session_created') {
            const lostSession = this.session_id && this.session_id !== data.payload.session_id;
            if (lostSession) {
                this.audioBuffer = [];
                liveInterviewUI.addMessage('The server restarted and the previous session was lost. End and restart this session.', 'system-error');
                window.dispatchEvent(new CustomEvent('superassist:session-lost'));
            }
            this.session_id = data.payload.session_id;
            this.audioSessionReady = !lostSession;
            console.log(`🚀 New session started: ${this.session_id}`);
            // Resolve the connection promise now that session is confirmed.
            this._resolveConnection();
        } else if (data.type === 'session_resumed') {
            this.audioSessionReady = true;
            this.flushAudioBuffer();
            console.log(`✅ Session resumed: ${data.payload.session_id}`);
            liveInterviewUI.addMessage("Connection restored. Your session has been resumed.", "system-message");
            // Also resolve the promise on resume.
            this._resolveConnection();
        }
        
        this.handleMessage(data);
    }

    handleReconnect() {
        if (this.is_intentionally_closing || this.reconnectTimer || this.connectionPromise) {
            return;
        }

        if (this.reconnect_attempts < this.max_reconnect_attempts) {
            this.reconnect_attempts++;
            const delay = Math.pow(2, this.reconnect_attempts) * 1000;
            console.log(`Attempting to reconnect in ${delay / 1000}s... (Attempt ${this.reconnect_attempts})`);
            liveInterviewUI.addMessage(`Connection lost. Reconnecting... (Attempt ${this.reconnect_attempts})`, "system-error", true);
            
            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                if (this.is_intentionally_closing) return;

                // Reconnect attempts are observed so a failed attempt cannot
                // become an unhandled promise rejection. The close handler
                // schedules the next attempt when the socket terminates.
                this.connect().catch((error) => {
                    console.warn('Reconnect attempt failed:', error);
                    if (!this.is_intentionally_closing && !this.reconnectTimer) {
                        this.handleReconnect();
                    }
                });
            }, delay);
        } else {
            console.error("Max reconnect attempts reached.");
            liveInterviewUI.addMessage("Could not reconnect to the server. Please restart the interview.", "system-error");
        }
    }

    disconnect() {
        this.audioBuffer = [];
        this.audioSessionReady = false;
        this.is_intentionally_closing = true;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        this._rejectConnection(new Error("WebSocket connection intentionally closed."));
        if (this.socket) {
            this.socket.close();
        }
        this.session_id = null; // Clear session on intentional disconnect
    }

    // --- All original message handlers go here ---
    handleMessage(data) {
        switch (data.type) {
            case 'interview_started':
                this.audioSessionReady = true;
                this.flushAudioBuffer();
                this.pendingStart?.resolve(data.payload);
                break;
            case 'interview_start_failed':
                this.pendingStart?.reject(new Error(data.payload.message));
                break;
            case 'audio_capture_status':
            case 'stt_status':
                this.updateAudioHealth(data.type === 'audio_capture_status' ? (data.payload.source === 'microphone' ? 'Microphone capture' : 'Meeting capture') : `Transcription (${data.payload.source || 'audio'})`, data.payload);
                break;
            case 'api_key_status':
                this.handleApiKeyStatus(data.payload);
                break;
            case 'transcript_update':
                this.handleTranscriptUpdate(data.payload);
                break;
            case 'ai_processing_started':
                this.handleAiProcessingStarted(data.payload);
                break;
            case 'ai_answer_chunk':
                this.handleAiAnswerChunk(data.payload);
                break;
            case 'ai_answer_reset':
                this.handleAiAnswerReset();
                break;
            case 'ai_answer_complete':
                this.handleAiAnswerComplete(data.payload);
                break;
            case 'auto_answer_status':
                document.getElementById('auto-answer-toggle').checked = data.payload.enabled;
                break;
            case 'preset_initialized':
                this.handlePresetInitialized(data.payload);
                break;
            case 'preset_switched':
                this.handlePresetSwitched(data.payload);
                break;
            case 'preset_switch_failed':
                this.handlePresetSwitchFailed(data.payload);
                break;
            case 'vision_analysis_result':
                this.handleVisionAnalysisResult(data.payload);
                break;
            case 'error':
                this.handleError(data.payload);
                break;
            // Ignore session messages as they are handled in onMessage
            case 'session_created':
            case 'session_resumed':
                break;
            case 'session_reset_complete':
                console.log('✅ Session reset confirmed by backend');
                break;
            default:
                console.warn('Unknown message type:', data.type);
        }
    }

    // ... (All other handle... methods from the original file)
    // NOTE: This is a simplified representation. The actual file will contain the full implementations.
    setProviderManager(manager) {
        this.providerManager = manager;
    }

    handleApiKeyStatus(payload) {
        // This is the crucial fix: Delegate the UI update to the ProviderManager,
        // which now has a direct, guaranteed reference.
        if (this.providerManager) {
            this.providerManager.handleApiKeyStatus(payload);
        } else {
            console.error("Fatal Error: ProviderManager not injected into WebSocketHandler.");
        }
    }

    handleTranscriptUpdate(payload) {
        if (payload.speaker_role === 'candidate') {
            liveInterviewUI.addCandidateTranscript(payload.transcript, !payload.is_final);
        } else {
            liveInterviewUI.addInterviewerQuestion(payload.transcript, !payload.is_final);
        }
    }
    
    handleAiProcessingStarted(payload) {
        liveInterviewUI.startStreamingAIResponse(payload);
    }

    handleAiAnswerChunk(payload) {
        // Reset marker from MultiLLMManager: the previous provider failed
        // mid-stream and a fallback is about to stream a fresh answer.
        if (payload && payload.chunk_type === 'reset') {
            this.handleAiAnswerReset();
            return;
        }
        liveInterviewUI.appendStreamingChunk(payload.chunk);
    }

    handleAiAnswerReset() {
        liveInterviewUI.resetStreamingResponse();
    }

    handleAiAnswerComplete(payload) {
        liveInterviewUI.finalizeStreamingResponse(payload);
    }

    handlePresetInitialized(payload) {
        this.stateManager.updateState({
            currentPreset: payload.current_preset,
            availablePresets: payload.available_presets
        });
        if (window.presetManager) {
            presetManager.updatePresetDisplay(payload.current_preset);
            presetManager.updateHealthStatus(payload.health_status);
        }
    }

    handlePresetSwitched(payload) {
        this.stateManager.updateState({ currentPreset: payload.current_preset });
        if (window.presetManager) {
            presetManager.updatePresetDisplay(payload.current_preset);
            presetManager.showSwitchNotification(payload);
        }
    }

    handlePresetSwitchFailed(payload) {
        if (window.presetManager) {
            presetManager.showErrorNotification(payload.error, payload);
        }
    }
    
    handleVisionAnalysisResult(result) {
        console.log('📸 Vision analysis result received:', result.success ? 'SUCCESS' : 'FAILED');
        
        // Hide processing status if it exists
        if (this.hideVisionProcessingStatus) {
            this.hideVisionProcessingStatus();
        }
        
        // Resolve the promise in screenshot-service.js
        if (window.visionAnalysisResolver) {
            window.visionAnalysisResolver(result);
            window.visionAnalysisResolver = null; // Clear the resolver
        }
        
        // Display the result in the specialized vision UI
        if (result.success && result.analysis) {
            // Use the dedicated vision analysis method with proper metadata
            const metadata = {
                provider: result.provider,
                model: result.model,
                screenshotCount: result.screenshot_count,
                languages: result.languages
            };
            liveInterviewUI.addVisionAnalysis(result.analysis, metadata);
        } else if (!result.success && result.error) {
            liveInterviewUI.addMessage(`❌ Vision analysis failed: ${result.error}`, "system-error");
        }
    }

    handleError(payload) {
        this.pendingStart?.reject(new Error(payload.message || 'Session initialization failed'));
        console.error("WebSocket error:", payload);
        liveInterviewUI.addMessage(payload.message || 'The request could not be completed.', 'system-error');
        if (window.presetManager) {
            presetManager.showErrorNotification(payload.message);
        }
        if (window.liveInterviewUI && liveInterviewUI.currentStreamingElement) {
            liveInterviewUI.finalizeStreamingResponse({
                error: payload.message || "Error processing request",
                success: false
            });
        }
    }

    sendMessage(type, payload) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type, payload }));
        } else {
            console.error(`Cannot send message ${type}: WebSocket not connected.`);
        }
    }

    sendAudioChunk(chunk, is_muted, speakerHint = 'system') {
        if (window.muteManager?.isAudioPaused()) {
            this.audioBuffer = [];
            return;
        }
        if (is_muted && speakerHint === 'microphone') {
            return;
        }
        {
            // P1.1: High-speed binary WebSocket transport (2-byte header + Linear16 PCM)
            // Header: Byte 0 = speaker (0x01: mic, 0x02: system), Byte 1 = muted (0x01: true, 0x00: false)
            const rawBytes = ArrayBuffer.isView(chunk) ? new Uint8Array(chunk.buffer, chunk.byteOffset, chunk.byteLength) : new Uint8Array(chunk);
            const binaryFrame = new Uint8Array(2 + rawBytes.byteLength);
            binaryFrame[0] = speakerHint === 'microphone' ? 0x01 : 0x02;
            binaryFrame[1] = is_muted ? 0x01 : 0x00;
            binaryFrame.set(rawBytes, 2);
            this.audioBuffer.push({ at: Date.now(), frame: binaryFrame.buffer });
            let bytes = this.audioBuffer.reduce((sum, item) => sum + item.frame.byteLength, 0);
            let dropped = false;
            while (this.audioBuffer.length && (bytes > 384000 || Date.now() - this.audioBuffer[0].at > 4000)) {
                bytes -= this.audioBuffer.shift().frame.byteLength;
                dropped = true;
            }
            if (dropped && Date.now() - this.lastAudioGapWarning > 10000) {
                this.lastAudioGapWarning = Date.now();
                this.updateAudioHealth('Browser audio', { status: 'gap', detail: 'Connection stalled; oldest audio was dropped after the bounded buffer filled.' });
            }
            this.flushAudioBuffer();
        }
    }

    flushAudioBuffer() {
        while (this.audioBuffer.length && this.audioSessionReady && this.socket?.readyState === WebSocket.OPEN && this.socket.bufferedAmount < 384000) {
            const item = this.audioBuffer[0];
            if (Date.now() - item.at > 4000 || window.muteManager?.isAudioPaused()) {
                this.audioBuffer.shift();
                continue;
            }
            if (new Uint8Array(item.frame)[0] === 1 && window.muteManager?.isMicrophoneMuted()) {
                this.audioBuffer.shift();
                continue;
            }
            try { this.socket.send(item.frame); }
            catch (error) { break; }
            this.audioBuffer.shift();
        }
    }

    updateAudioHealth(source, payload) {
        this.audioHealth[source] = ['receiving', 'waiting'].includes(payload.status)
            ? `${payload.status === 'receiving' ? 'audio detected' : 'waiting for playback'} (${payload.detail})` : payload.status;
        const health = document.getElementById('audio-health');
        if (health) {
            health.hidden = false;
            health.textContent = Object.entries(this.audioHealth).map(([name, status]) => `${name}: ${status}`).join(' · ');
        }
        if (['failed', 'gap', 'reconnecting'].includes(payload.status)) {
            liveInterviewUI.addMessage(`${source}: ${payload.detail || payload.status}`, 'system-error');
        }
    }

    /**
     * Base64-encode a PCM buffer for transport.
     *
     * Sending the raw bytes as a JSON array of integers cost roughly 4 bytes of
     * text per byte of audio; base64 costs 1.33. Encoded in slices because
     * String.fromCharCode.apply exceeds the argument limit on large buffers.
     */
    bytesToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        const SLICE = 0x8000;
        let binary = '';
        for (let i = 0; i < bytes.length; i += SLICE) {
            binary += String.fromCharCode.apply(null, bytes.subarray(i, i + SLICE));
        }
        return btoa(binary);
    }

    async startInterview(microphoneAvailable = true) {
        const state = this.stateManager.getState();
        const initialMuteStatus = window.muteManager?.getMuteStatus() || { microphone: false, universal: false };
        
        const interviewPayload = {
            audioCaptureMode: document.getElementById('audio-capture-mode')?.value || 'browser',
            audioOutput: document.getElementById('audio-output-select')?.value || '',
            microphoneAvailable,
            audioInput: document.getElementById('mic-select')?.value || '',
            sttLanguage: state.sttLanguage || 'en', // P1: transcription language
            aiProvider: {
                provider: state.selectedProvider.name,
                model: state.selectedProvider.model
            },
            onboardingData: { ...state.onboardingData, selectedLanguages: state.selectedLanguages },
            is_muted: initialMuteStatus.microphone,
            is_universally_muted: initialMuteStatus.universal,
            process_all_speakers: document.getElementById('audio-capture-mode')?.value !== 'native',
            aiSecondaryProvider: state.selectedSecondaryProvider.name ? {
                provider: state.selectedSecondaryProvider.name,
                model: state.selectedSecondaryProvider.model
            } : null,
            visionProvider: state.selectedVisionProvider.name ? {
                provider: state.selectedVisionProvider.name,
                model: state.selectedVisionProvider.model
            } : null,
            visionSecondaryProvider: state.selectedSecondaryVisionProvider.name ? {
                provider: state.selectedSecondaryVisionProvider.name,
                model: state.selectedSecondaryVisionProvider.model
            } : null,
        };
        this.audioHealth = {};
        const started = new Promise((resolve, reject) => {
            this.pendingStart = { resolve, reject };
        });
        const timeout = setTimeout(() => this.pendingStart?.reject(new Error('Audio and transcription startup timed out')), 45000);
        this.sendMessage('start_interview', interviewPayload);
        try { return await started; }
        finally { clearTimeout(timeout); this.pendingStart = null; }
    }

    endInterview() {
        this.sendMessage('end_interview', {});
        this.disconnect();
    }

    /**
     * P4: live toggle between full answers and quick hints (Ctrl+Shift+Win+G).
     * Sends the new mode to the session; the backend prefixes the next prompt
     * accordingly. Returns the mode that was just activated.
     */
    toggleAnswerMode() {
        this.answerModeFull = this.answerModeFull === undefined ? true : !this.answerModeFull;
        const generateFullAnswers = this.answerModeFull;
        this.sendMessage('config_update', { generateFullAnswers });
        console.log(`🎯 Answer mode -> ${generateFullAnswers ? 'full answers' : 'quick hints'}`);
        return generateFullAnswers;
    }

    /**
     * P3: request the turn-by-turn transcript export; the backend writes a
     * local .txt file and returns its path for a user-facing notification.
     */
    async exportTranscript() {
        if (!this.session_id) {
            console.warn('No active session to export.');
            return null;
        }
        try {
            const response = await fetch('/api/export-transcript', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: this.session_id })
            });
            if (!response.ok) {
                const detail = await response.json().catch(() => ({}));
                console.warn('Transcript export failed:', detail.detail || response.status);
                liveInterviewUI.addMessage(`⚠️ Transcript export failed: ${detail.detail || response.statusText}`, "system-error");
                return null;
            }
            const result = await response.json();
            liveInterviewUI.addMessage(`💾 Transcript saved (${result.turns} turns): ${result.path}`, "system-message");
            return result.path;
        } catch (err) {
            console.error('Transcript export error:', err);
            return null;
        }
    }
    
    switchPreset(presetKey) {
        if (!this.stateManager.isLiveInterviewActive()) {
            presetManager.showErrorNotification('Start the interview first.');
            return;
        }
        this.sendMessage('switch_preset', { preset_key: presetKey });
    }

    updateCheckStatus(checkElement, status, text) {
        if (!checkElement) {
            devLog(`[updateCheckStatus] Warning: Attempted to update a null checkElement.`);
            return;
        }
        const indicator = checkElement.querySelector('.indicator');
        const textNode = Array.from(checkElement.childNodes).find(node =>
            node.nodeType === Node.TEXT_NODE && node.textContent.trim() !== ''
        );
        if (indicator) {
            indicator.textContent = status === 'success' ? '🟢' : status === 'error' ? '🔴' : '⚪';
        }
        if (textNode) {
            textNode.nodeValue = ` ${text}`;
        }
        devLog(`[UI UPDATE] Set ${checkElement.id} to ${status}: ${text}`);
    }

    checkAllSystemsGo() {
        // Delegate to ProviderManager which owns the UI elements
        if (this.providerManager) {
            return this.providerManager.checkAllSystemsGo();
        } else {
            console.error("Fatal Error: ProviderManager not injected into WebSocketHandler for checkAllSystemsGo.");
            return false;
        }
    }
}
