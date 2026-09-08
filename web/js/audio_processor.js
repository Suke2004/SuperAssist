// --- web/js/audio_processor.js ---

// Number of samples accumulated before a message is posted.
// 1024 = 8 render quanta (8 * 128) = ~21.3 ms @ 48 kHz.
// Chosen as an exact multiple of the 128-sample render quantum so a batch
// boundary can never fall inside a quantum. Drops the postMessage/WebSocket
// message rate from ~375/s to ~47/s (8x).
const BATCH_SAMPLES = 1024;

/**
 * Mixed audio processor that combines microphone and system audio
 * while tracking volume levels for speaker detection.
 */
class MixedProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.micInputIndex = 0;
        this.systemInputIndex = 1;

        // Batching state: PCM accumulates here and is posted once full.
        this.batch = new Int16Array(BATCH_SAMPLES);
        this.batchFill = 0;
        this.micLevelSum = 0;
        this.systemLevelSum = 0;
    }

    process(inputs, outputs, parameters) {
        const micInput = inputs[0] && inputs[0][0] ? inputs[0][0] : null;
        const systemInput = inputs[1] && inputs[1][0] ? inputs[1][0] : null;
        
        const micLen = micInput ? micInput.length : 0;
        const sysLen = systemInput ? systemInput.length : 0;
        const frameLength = Math.max(micLen, sysLen);
        if (frameLength === 0) return true;

        // Calculate RMS of this quantum to determine presence of voice
        let micEnergy = 0;
        let sysEnergy = 0;
        for (let i = 0; i < frameLength; i++) {
            if (i < micLen) micEnergy += micInput[i] * micInput[i];
            if (i < sysLen) sysEnergy += systemInput[i] * systemInput[i];
        }
        const micRMS = Math.sqrt(micEnergy / (micLen || 1));
        const sysRMS = Math.sqrt(sysEnergy / (sysLen || 1));

        // Intelligent soft noise gate:
        // If interviewer (system audio) is actively speaking (sysRMS > 0.003) and
        // mic is just ambient noise / breathing (micRMS < 0.012), heavily attenuate mic
        // so room noise does not contaminate the clean digital interviewer stream.
        let micGain = 1.0;
        if (sysRMS > 0.003 && micRMS < 0.012) {
            micGain = 0.05; // 95% attenuation of room noise during interviewer speech
        } else if (micRMS < 0.004) {
            micGain = 0.2; // Soft gate on pure room silence/fan noise
        }

        for (let i = 0; i < frameLength; i++) {
            const micSample = (i < micLen ? micInput[i] : 0) * micGain;
            const systemSample = i < sysLen ? systemInput[i] : 0;

            // Adaptive mixing:
            // If only one stream has active signal, avoid the 0.7x volume penalty
            // so quiet speakers aren't attenuated. If both are active, blend smoothly.
            let mixed;
            if (sysRMS > 0.003 && micRMS > 0.01) {
                // Both active: blend with limiter to avoid clipping
                mixed = (micSample + systemSample) * 0.75;
            } else if (sysRMS > 0.002) {
                // Interviewer solo: full clean signal without attenuation
                mixed = systemSample + micSample * 0.1;
            } else {
                // Candidate solo
                mixed = micSample;
            }

            // Soft-knee saturation / clamp to prevent 16-bit PCM overflow
            if (mixed > 1.0) mixed = 1.0;
            else if (mixed < -1.0) mixed = -1.0;

            // Convert to 16-bit PCM directly into the batch buffer
            const s = Math.fround(mixed);
            this.batch[this.batchFill++] = s < 0 ? s * 0x8000 : s * 0x7FFF;

            // Track volume levels across the whole batch
            this.micLevelSum += Math.abs(i < micLen ? micInput[i] : 0);
            this.systemLevelSum += Math.abs(systemSample);

            if (this.batchFill === BATCH_SAMPLES) {
                this.flushBatch();
            }
        }

        return true;
    }

    /**
     * Posts the accumulated batch with batch-averaged volume levels.
     * The batch buffer is replaced BEFORE postMessage transfers (detaches) it,
     * so the detached ArrayBuffer is never read or written again.
     */
    flushBatch() {
        const pcmData = this.batch;
        const sampleCount = this.batchFill;

        // Average the volume levels over the batch
        const micLevel = this.micLevelSum / sampleCount;
        const systemLevel = this.systemLevelSum / sampleCount;

        this.batch = new Int16Array(BATCH_SAMPLES);
        this.batchFill = 0;
        this.micLevelSum = 0;
        this.systemLevelSum = 0;

        // Send mixed audio with volume levels for speaker detection
        this.port.postMessage({
            audioData: pcmData.buffer,
            micLevel: micLevel,
            systemLevel: systemLevel
        }, [pcmData.buffer]);
    }
}

registerProcessor('mixed-processor', MixedProcessor);