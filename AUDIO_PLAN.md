# Interview audio capture

Use Windows WASAPI loopback for the interviewer's audio and a separate browser microphone stream for the candidate. Select the exact output used by Zoom, Teams, Meet, or the meeting app, and wear headphones.

| Method | Best use | Limitation |
| --- | --- | --- |
| Windows direct audio (default when available) | Desktop or browser meetings, including headphones | Captures all playback on the selected output; restart after switching outputs or changing its sample rate |
| Browser tab audio | One browser meeting tab, especially when other audio must be excluded | Requires explicit tab audio sharing and a browser that supports it |
| Browser screen audio | Fallback for a desktop meeting | Depends on sharing system audio; can include other playback |
| Microphone alone | In-person practice | Cannot reliably hear remote voices routed to headphones |

Implementation completed:

- PyAudioWPatch opens a shared WASAPI loopback input with the output's actual sample rate. Stereo is downmixed to mono without gain gates. Capture begins only when the user starts a session; screenshots request screen sharing separately.
- Native output and microphone use independent Deepgram connections. Source labels come from the capture stream, so simultaneous speakers and transcription lag do not depend on recent volume guesses. Candidate speech supplies context by default.
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

Two independent transcription streams can cost more than the previous single mixed stream. Loopback cannot recover sound played on another output device, and outages beyond the bounded buffer can lose speech. No microphone or loopback audio is saved to disk by this change.

References: [Microsoft loopback recording](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording), [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch).
