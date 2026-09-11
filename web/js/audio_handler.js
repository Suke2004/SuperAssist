// --- audio_handler.js ---
// This module handles all interactions with the Web Media APIs
// for capturing and processing audio via an AudioWorklet.

import { devLog, devError } from './config.js';
import muteManager from './mute-manager.js';

// Must match sample_rate in the Deepgram LiveOptions in services/stt_service.py.
const TARGET_SAMPLE_RATE = 48000;

let audioContext = null;
let micStream = null;
let systemStream = null;
let micGainNode = null;
let screenVideoTrack = null; // Store video track for screenshot reuse
let keepAliveGain = null;
let keepAliveOsc = null;

// Backup Audio Engine state
let backupContext = null;
let backupProcessor = null;
let backupActive = false;
let lastChunkTimestamp = 0;
let lastSuspensionWarningTime = 0;

/**
 * Requests permission to use the microphone and populates the dropdown.
 * @returns {Promise<boolean>} True if permission was granted, false otherwise.
 */
export async function setupMicrophone() {
    const micSelect = document.getElementById('mic-select');
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        stream.getTracks().forEach(track => track.stop());

        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioDevices = devices.filter(device => device.kind === 'audioinput');

        if (audioDevices.length === 0) return false;

        micSelect.innerHTML = '';
        audioDevices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.deviceId;
            option.textContent = device.label || `Microphone ${micSelect.options.length + 1}`;
            micSelect.appendChild(option);
        });
        
        micSelect.disabled = false;
        return true;
    } catch (err) {
        devError("Error setting up microphone:", err);
        return false;
    }
}

/**
 * Starts audio processing by setting up the AudioContext, loading the worklet,
 * and connecting the audio streams.
 * @param {string} micId - The deviceId of the selected microphone.
 * @param {function} onAudioData - Callback function to handle the processed PCM audio data.
 * @returns {Promise<boolean>} True if processing started successfully.
 */
export async function startAudioProcessing(micId, onAudioData) {
    try {
        // 1. Get Audio Streams with noise suppression and echo cancellation
        micStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                deviceId: { exact: micId },
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1,
                sampleRate: TARGET_SAMPLE_RATE
            }
        });

        // 2. Obtain display stream for screen audio & screenshots
        // On macOS WebKit or when system audio capture is unsupported/declined,
        // fall back gracefully so the interview session never hard-fails.
        try {
            systemStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
        } catch (displayErr) {
            console.warn("⚠️ getDisplayMedia with audio failed or restricted, trying video-only (macOS fallback):", displayErr);
            try {
                systemStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
            } catch (videoErr) {
                console.warn("⚠️ Could not get display video stream:", videoErr);
                systemStream = null;
            }
        }

        if (!micStream) {
            console.error("Could not get microphone audio stream.");
            stopAudioProcessing();
            return false;
        }

        // 2. Setup AudioContext and Worklet
        // Pin the rate so it matches what Deepgram is told to expect. Left to
        // itself the context adopts the hardware rate, and a 44.1kHz device
        // then streams audio that Deepgram decodes as 48kHz (~9% fast), which
        // degrades transcription in a way that looks like a Deepgram fault
        // rather than a configuration mismatch.
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        try {
            audioContext = new AudioCtx({ sampleRate: TARGET_SAMPLE_RATE });
        } catch (rateErr) {
            // The spec requires 8000-96000 to be supported, so this is close to
            // unreachable; fall back rather than failing the whole session.
            console.warn('⚠️ Could not pin AudioContext sample rate:', rateErr);
            audioContext = new AudioCtx();
        }
        console.log(`🎵 AudioContext: ${audioContext.sampleRate}Hz`); // Keep this as it's important for debugging
        if (audioContext.sampleRate !== TARGET_SAMPLE_RATE) {
            console.warn(`⚠️ AudioContext is ${audioContext.sampleRate}Hz but Deepgram expects ${TARGET_SAMPLE_RATE}Hz - transcription accuracy may suffer`);
        }
        if (audioContext.state === 'suspended') {
            await audioContext.resume().catch(() => {});
        }
        await audioContext.audioWorklet.addModule('/static/js/audio_processor.js');
        
        // 3. Create a mixed processor with 2 inputs and 1 output for keepalive connection
        const mixedProcessor = new AudioWorkletNode(audioContext, 'mixed-processor', {
            numberOfInputs: 2,
            numberOfOutputs: 1
        });

        // Anti-suspension pipeline: Connect mixedProcessor through a 0-gain node to destination.
        // Modern Chromium/WebView2 automatically suspends an AudioContext if it has no active path
        // to destination. A silent 0-gain connection keeps the audio engine rendering continuously.
        keepAliveGain = audioContext.createGain();
        keepAliveGain.gain.value = 0;
        mixedProcessor.connect(keepAliveGain);
        keepAliveGain.connect(audioContext.destination);

        // Silent keep-alive oscillator guarantees the Web Audio hardware clock never idles
        try {
            keepAliveOsc = audioContext.createOscillator();
            keepAliveOsc.connect(keepAliveGain);
            keepAliveOsc.start();
        } catch (e) {
            console.warn('Silent keepalive oscillator skipped:', e);
        }

        // Handle mixed audio with mute-aware speaker detection
        let audioProcessingCounter = 0; // For throttled logging

        // A2: echo guard — interviewer audio leaking through the speakers into
        // the mic used to be labeled 'microphone' when micLevel beat its gate,
        // sending interviewer speech into candidate-response tracking. If the
        // system stream is clearly active, the mic signal is suspect: only call
        // it 'microphone' when the mic is decisively louder.
        const echoGuard = (micLevel, systemLevel) => {
            if (systemLevel > 0.003 && micLevel < systemLevel * 2.5) {
                return 'system';
            }
            return null; // no echo suspicion, let normal classification decide
        };
        
        mixedProcessor.port.onmessage = (event) => {
            // If universally muted, drop all audio data immediately.
            if (muteManager.isAudioPaused()) {
                if (audioProcessingCounter % 200 === 0) { // Log occasionally to show it's paused
                    devLog(`⏸️ Audio processing paused due to universal mute.`);
                }
                audioProcessingCounter++;
                return;
            }

            const { audioData, micLevel, systemLevel } = event.data;
            let speakerHint;

            if (muteManager.isMicrophoneMuted()) {
                // When microphone is muted, candidate speech is completely silenced.
                // Only send chunk if genuine system (interviewer) audio is detected.
                if (systemLevel < 0.002) {
                    return;
                }
                speakerHint = 'system';
            } else {
                const echoVerdict = echoGuard(micLevel, systemLevel);
                if (echoVerdict) {
                    speakerHint = echoVerdict;
                } else if (systemLevel > 0.003 && systemLevel >= micLevel * 0.7) {
                    // Digital interviewer audio active
                    speakerHint = 'system';
                } else if (micLevel > 0.005 && micLevel > systemLevel * 1.2) {
                    // Candidate speaking
                    speakerHint = 'microphone';
                } else {
                    // Default based on active audio energy
                    speakerHint = systemLevel > 0.002 ? 'system' : 'microphone';
                }
            }

            audioProcessingCounter++;
            lastChunkTimestamp = Date.now();
            onAudioData(audioData, speakerHint);
        };

        // 4. Connect both sources to the mixed processor with mute control
        const micSource = audioContext.createMediaStreamSource(micStream);
        
        // Create gain node for microphone muting
        micGainNode = audioContext.createGain();
        updateMicGainNode(); // Set initial gain based on mute manager state
        
        // Listen for future changes
        muteManager.on('microphoneMuteChange', updateMicGainNode);
        
        // Connect mic through gain node to input 0
        micSource.connect(micGainNode);
        micGainNode.connect(mixedProcessor, 0, 0);
        
        // System audio connects to input 1
        if (systemStream && systemStream.getAudioTracks().length > 0) {
            const systemSource = audioContext.createMediaStreamSource(systemStream);
            systemSource.connect(mixedProcessor, 0, 1);
            console.log("🔊 System audio connected successfully to channel 1");
        } else {
            console.warn("⚠️ No system audio track found in display stream. If capturing interviewer voice, ensure 'Share audio' is checked.");
            // Silent dummy source on channel 1 so mixed processor receives two inputs
            const dummyGain = audioContext.createGain();
            dummyGain.gain.value = 0;
            dummyGain.connect(mixedProcessor, 0, 1);
        }

        // Store the video track for screenshot reuse, but remove it from the stream
        const videoTracks = systemStream.getVideoTracks();
        if (videoTracks.length > 0) {
            screenVideoTrack = videoTracks[0];
            console.log("📹 Screen video track stored for screenshot reuse");
        } else {
            console.warn("⚠️ No video track found in display media stream");
        }

        devLog("✅ Audio processing started successfully");

        // A4: device-loss watchdog — an unplugged mic or a stopped screen-share
        // used to die silently; transcription and screenshots just stopped with
        // no signal. Surface it so the user can re-acquire before losing more
        // of the interview.
        const notifyDeviceLoss = (what) => {
            console.warn(`⚠️ ${what} ended unexpectedly!`);
            window.dispatchEvent(new CustomEvent('superassist:device-loss', {
                detail: { device: what }
            }));
        };
        if (micStream) {
            micStream.getAudioTracks().forEach(track => {
                track.addEventListener('ended', () => notifyDeviceLoss('Microphone'));
            });
        }
        if (systemStream) {
            systemStream.getAudioTracks().forEach(track => {
                track.addEventListener('ended', () => notifyDeviceLoss('Screen share audio'));
            });
            systemStream.getVideoTracks().forEach(track => {
                track.addEventListener('ended', () => notifyDeviceLoss('Screen share'));
            });
        }

        // Initialize heartbeat timestamp
        lastChunkTimestamp = Date.now();

        // A5: AudioContext watchdog & automatic backup engine failover:
        // 1. Resumes context if suspended by OS or audio device switch.
        // 2. Throttles user-facing warnings so UI isn't spammed every few seconds.
        // 3. If primary worklet stalls (>4s without chunks), automatically activates
        //    the backup audio engine (ScriptProcessor pipeline) so no speech is missed.
        audioContext._watchdog = setInterval(() => {
            const now = Date.now();
            const isPaused = muteManager.isAudioPaused();

            // Check suspension
            if (audioContext && audioContext.state === 'suspended') {
                console.warn('⚠️ AudioContext suspended — attempting resume...');
                audioContext.resume().catch(() => {});
                if (now - lastSuspensionWarningTime > 30000 && !backupActive) {
                    lastSuspensionWarningTime = now;
                    window.dispatchEvent(new CustomEvent('superassist:audio-suspended'));
                }
            }

            // Stall detection: if unmuted and no chunks received for > 4s, activate backup
            if (!isPaused && (now - lastChunkTimestamp > 4000) && !backupActive) {
                console.warn('⚠️ Primary audio engine stalled (>4s without audio) — activating backup audio engine...');
                startBackupAudioEngine(micStream, systemStream, onAudioData);
            }
        }, 2500);

        return true;

    } catch (err) {
        console.error("❌ Error starting audio processing:", err);
        stopAudioProcessing();
        return false;
    }
}

/**
 * Updates the microphone gain node based on the central mute manager state.
 */
function updateMicGainNode() {
    const isMuted = muteManager.isMicrophoneMuted();
    const targetGain = isMuted ? 0 : 1;
    
    // 1. Physically mute/unmute the browser microphone track for true hardware silence
    if (micStream) {
        micStream.getAudioTracks().forEach(track => {
            track.enabled = !isMuted;
        });
    }

    // 2. Control the Web Audio GainNode
    if (micGainNode && audioContext) {
        if (audioContext.state === 'suspended') {
            audioContext.resume().catch(() => {});
        }
        try {
            micGainNode.gain.cancelScheduledValues(audioContext.currentTime);
            micGainNode.gain.setValueAtTime(targetGain, audioContext.currentTime);
        } catch (e) {
            micGainNode.gain.value = targetGain;
        }
    }
    devLog(`🎤 Microphone ${isMuted ? 'MUTED' : 'ACTIVE'} (gain=${targetGain})`);
}

// --- Legacy Functions (now wrappers for MuteManager) ---
// These are kept for backward compatibility with other modules that might call them.

/**
 * @deprecated Use muteManager.setMicrophoneMute(mute) instead.
 */
export function setMicrophoneMute(mute) {
    muteManager.setMicrophoneMute(mute);
    return muteManager.isMicrophoneMuted();
}

/**
 * @deprecated Use muteManager.isMicrophoneMuted() instead.
 */
export function isMicrophoneMuted() {
    return muteManager.isMicrophoneMuted();
}

/**
 * @deprecated Use muteManager.toggleMicrophoneMute() instead.
 */
export function toggleMicrophoneMute() {
    return muteManager.toggleMicrophoneMute();
}

/**
 * @deprecated Use muteManager.getMuteStatus() instead.
 */
export function getAudioProcessingMode() {
    return muteManager.getMuteStatus();
}

/**
 * Gets the screen video track for screenshot capture.
 * @returns {MediaStreamTrack|null} The screen video track if available.
 */
export function getScreenVideoTrack() {
    return screenVideoTrack;
}

/**
 * Checks if screen sharing is available for screenshots.
 * @returns {boolean} True if screen video track is available and active.
 */
export function isScreenSharingAvailable() {
    return screenVideoTrack && screenVideoTrack.readyState === 'live';
}

/**
 * Backup Audio Engine (ScriptProcessor pipeline)
 * Activates automatically if the primary AudioWorklet stalls or suspends unexpectedly.
 */
function startBackupAudioEngine(micStream, systemStream, onAudioData) {
    if (backupActive) return;
    backupActive = true;
    console.warn("🛡️ Starting Backup Audio Engine (fallback pipeline)...");

    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        backupContext = new AudioCtx();
        backupContext.resume().catch(() => {});

        const bufferSize = 1024;
        // 2 inputs (mic, system), 1 output
        backupProcessor = backupContext.createScriptProcessor(bufferSize, 2, 1);

        const merger = backupContext.createChannelMerger(2);

        if (micStream && micStream.getAudioTracks().length > 0) {
            const micSrc = backupContext.createMediaStreamSource(micStream);
            micSrc.connect(merger, 0, 0);
        }

        if (systemStream && systemStream.getAudioTracks().length > 0) {
            const sysSrc = backupContext.createMediaStreamSource(systemStream);
            sysSrc.connect(merger, 0, 1);
        }

        merger.connect(backupProcessor);

        // Keepalive silent output to destination
        const backupSilentGain = backupContext.createGain();
        backupSilentGain.gain.value = 0;
        backupProcessor.connect(backupSilentGain);
        backupSilentGain.connect(backupContext.destination);

        backupProcessor.onaudioprocess = (e) => {
            if (muteManager.isAudioPaused()) return;

            const inputBuffer = e.inputBuffer;
            const micData = inputBuffer.getChannelData(0);
            const sysData = inputBuffer.numberOfChannels > 1 ? inputBuffer.getChannelData(1) : null;
            const len = inputBuffer.length;

            let micEnergy = 0;
            let sysEnergy = 0;
            for (let i = 0; i < len; i++) {
                micEnergy += micData[i] * micData[i];
                if (sysData) sysEnergy += sysData[i] * sysData[i];
            }
            const micRMS = Math.sqrt(micEnergy / (len || 1));
            const sysRMS = sysData ? Math.sqrt(sysEnergy / (len || 1)) : 0;

            const isMuted = muteManager.isMicrophoneMuted();
            const micGain = isMuted ? 0 : 1.0;

            // Convert to 16-bit PCM buffer
            const pcmBuffer = new Int16Array(len);
            for (let i = 0; i < len; i++) {
                const micSample = micData[i] * micGain;
                const sysSample = sysData ? sysData[i] : 0;
                let mixed;
                if (sysRMS > 0.003 && micRMS > 0.01) {
                    mixed = sysSample + micSample * 0.12;
                } else if (sysRMS > 0.002) {
                    mixed = sysSample + micSample * 0.1;
                } else {
                    mixed = micSample;
                }
                if (mixed > 1.0) mixed = 1.0;
                else if (mixed < -1.0) mixed = -1.0;

                const s = Math.fround(mixed);
                pcmBuffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            let speakerHint = 'microphone';
            if (isMuted) {
                if (sysRMS < 0.002) return;
                speakerHint = 'system';
            } else if (sysRMS > 0.003 && sysRMS >= micRMS * 0.7) {
                speakerHint = 'system';
            } else if (micRMS > 0.005 && micRMS > sysRMS * 1.2) {
                speakerHint = 'microphone';
            } else {
                speakerHint = sysRMS > 0.002 ? 'system' : 'microphone';
            }

            lastChunkTimestamp = Date.now();
            onAudioData(pcmBuffer.buffer, speakerHint);
        };

        window.dispatchEvent(new CustomEvent('superassist:backup-audio-started'));
        console.log("✅ Backup Audio Engine running and streaming PCM chunks successfully");
    } catch (err) {
        console.error("❌ Failed to start Backup Audio Engine:", err);
    }
}

/**
 * Stops all audio streams and closes the AudioContext.
 */
export function stopAudioProcessing() {
    console.log("Stopping audio processing.");
    if (micStream) {
        micStream.getTracks().forEach(track => track.stop());
        micStream = null;
    }
    if (systemStream) {
        systemStream.getTracks().forEach(track => track.stop());
        systemStream = null;
    }
    if (screenVideoTrack) {
        screenVideoTrack.stop();
        screenVideoTrack = null;
        console.log("📹 Screen video track stopped");
    }
    if (keepAliveOsc) {
        try { keepAliveOsc.stop(); keepAliveOsc.disconnect(); } catch (e) {}
        keepAliveOsc = null;
    }
    if (keepAliveGain) {
        try { keepAliveGain.disconnect(); } catch (e) {}
        keepAliveGain = null;
    }
    if (backupProcessor) {
        try { backupProcessor.disconnect(); } catch (e) {}
        backupProcessor = null;
    }
    if (backupContext && backupContext.state !== 'closed') {
        try { backupContext.close(); } catch (e) {}
        backupContext = null;
    }
    backupActive = false;

    if (audioContext && audioContext.state !== 'closed') {
        if (audioContext._watchdog) {
            clearInterval(audioContext._watchdog);
            audioContext._watchdog = null;
        }
        audioContext.close();
        audioContext = null;
    }
    
    // Reset mute state in the central manager
    muteManager.setMicrophoneMute(true);
    muteManager.setUniversalMute(false);
    micGainNode = null;
}