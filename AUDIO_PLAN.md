# Interview audio capture

Use Windows WASAPI loopback for the interviewer's audio and a separate browser microphone stream for the candidate. Select the exact output used by Zoom, Teams, Meet, or the meeting app, and wear headphones.

macOS uses a BlackHole/CoreAudio routed meeting input and a separate native microphone; Linux uses a PulseAudio/PipeWire playback monitor and a separate native microphone. These sources reuse the existing bounded queues, retry loop, source-specific transcription, and mute/cleanup behavior. See [platform setup](CROSS_PLATFORM.md) before choosing these methods. Windows retains WASAPI and its browser microphone.

| Method | Best use | Limitation |
| --- | --- | --- |
| Windows direct audio (default when available) | Desktop or browser meetings, including headphones | Captures all playback on the selected output; restart after switching outputs or changing its sample rate |
| macOS routed audio | MacBook meetings through headphones | Requires BlackHole and a Multi-Output Device containing headphones and BlackHole |
| Linux system audio | PulseAudio or PipeWire desktop meetings | Requires the playback monitor of the actual meeting output |
| Browser tab audio | One browser meeting tab, especially when other audio must be excluded | Requires explicit tab audio sharing and a browser that supports it |
| Browser screen audio | Fallback for a desktop meeting | Depends on sharing system audio; can include other playback |
| Microphone alone | In-person practice | Cannot reliably hear remote voices routed to headphones |

Implementation completed:

- PyAudioWPatch opens a shared WASAPI loopback input with the output's actual sample rate. Stereo is downmixed to mono without gain gates. Capture begins only when the user starts a session; screenshots request screen sharing separately.
- Native output and microphone use independent Deepgram connections. Source labels come from the capture stream, so simultaneous speakers and transcription lag do not depend on recent volume guesses. Candidate speech supplies context by default.
- Native output can start when browser microphone permission is denied or no microphone is available. In that case no microphone transcription connection is opened; the system-audio connection still starts. Browser audio capture continues to require its microphone and shared meeting audio.
- Direct capture has no screen-sharing prompt. The default selector displays the actual Windows output name, and the live system-audio status distinguishes audio detected from waiting for playback. Screenshot permission is requested separately.
- A bounded native queue, four-second transcription buffer, and bounded browser reconnect queue prevent runaway memory. Failed sends retain FIFO order, report gaps, and trigger the existing reconnect loop. Expired buffered audio is discarded.
- Capture retries device failures up to three times. A missing output or changed sample rate produces a visible error instead of silently switching to microphone-only capture. Browser capture remains selectable.
- Session startup waits for backend acknowledgement. Errors close partially opened resources and return to audio setup. Cleanup closes both transcription connections and native capture, even if another resource fails.
- Browser silence updates the capture heartbeat; backup activation suppresses the primary sender. Incorrect sample rates fail visibly.
- Browser capture rejects shares without a meeting audio track instead of starting with an inaudible interviewer. Only one sharing request is made; cancellation returns to audio setup.
- Quiet browser audio and native silence are preserved so words are not gated out and Deepgram can detect speech boundaries. Nova-3 uses a balanced, deduplicated technical vocabulary, prioritizing selected languages; blind phonetic replacements are removed.
- Finalized transcript segments accumulate until a real speech boundary. Endpointing allows 1.5 seconds of silence, followed by a short continuation grace period; SpeechStarted and interim results cancel pending answers. Delayed boundaries from an earlier fragment are ignored. Manual Answer remains immediate. A 2.5-second fallback handles final segments without boundary metadata.
- Full and quick answer prompts interpret imperfect English, fragments, and clear contextual speech-recognition errors using recent conversation. They preserve numbers and constraints and request a brief clarification when meaning is ambiguous. Raw transcripts remain available; no extra normalization API call is added.

Validation uses mocked device failures, channel routing, queue overflow, ordered resend, stale-buffer expiry, and cleanup failures, plus a local loopback hardware smoke check and browser transport checks. No API keys are replaced.

The 2026-10-25 validation also streamed a synthetic imperfect-English question with a measured 1.55-second pause through the configured Deepgram account. The complete question retained HashMap, cache, and database terms and triggered one answer request. A configured Groq model interpreted "cash" as "cache" from the database context. This checks the real APIs and timing; it does not measure recognition accuracy across human accents, background noise, or meeting applications.

Headphone playback was checked through the physical Realtek headphone output and WASAPI loopback at 48kHz. A synthetic spoken question played through that output reached Deepgram, retained HashMap, and triggered one question without a microphone connection. Browser checks cover native startup without microphone permission and the visible playback status. For a YouTube check, play audio through the chosen headphones, confirm **audio detected**, and inspect the independent transcription status if no words appear. Restart after changing playback devices.

Answer scrolling and all current Windows shortcuts are documented in [README.md](README.md). Click-through is an explicit toggle rather than an automatic interview-start setting, so mouse scrolling is available by default.

Two independent transcription streams can cost more than the previous single mixed stream. Loopback cannot recover sound played on another output device, and outages beyond the bounded buffer can lose speech. No microphone or loopback audio is saved to disk by this change.

References: [Microsoft loopback recording](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording), [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch).
