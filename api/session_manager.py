import re
import uuid
import asyncio
import base64
import time
from datetime import datetime
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple
from fastapi import WebSocket

from .utils import send_json
from .metrics import app_metrics
from core.config import settings
from services.llm_service import MultiLLMManager
from services.stt_service import DeepgramManager
from services.vision_service import vision_service

# Session TTL: 30 minutes of inactivity with no WebSocket connected
SESSION_TTL_SECONDS = 30 * 60

# A1: window (seconds) over which audio-batch dominance hints are correlated
# with a Deepgram transcript. Transcripts arrive a few hundred ms after the
# speech they describe, so classification looks BACKWARD from the transcript
# timestamp instead of using the single most recent chunk's hint.
HINT_WINDOW_SECONDS = 1.5

# M4: buffered question text is capped (tail kept) so a runaway buffer can
# never grow without bound when no LLM is configured.
TRANSCRIPT_BUFFER_MAX_CHARS = 4000

# P3: bounded turn-by-turn record of the interview for export.
TRANSCRIPT_LOG_MAX_TURNS = 500


def classify_speaker(hint_timeline: Deque[Tuple[float, bool]], at_time: float,
                     window_seconds: float = HINT_WINDOW_SECONDS) -> str:
    """A1: classify who was speaking around *at_time* from the hint timeline.

    The timeline holds (timestamp, mic_dominant) pairs appended per audio
    batch. A transcript arriving at *at_time* is attributed by majority vote
    of the hints in [at_time - window, at_time]. Returns 'microphone' or
    'system'. With no hints in the window (silence gap), defaults to 'system'
    — the safe answer, since the interviewer asking the next question is the
    common case after a pause.
    """
    if not hint_timeline:
        return "system"
    mic = 0
    system = 0
    for ts, mic_dominant in reversed(hint_timeline):
        if ts < at_time - window_seconds:
            break
        if mic_dominant:
            mic += 1
        else:
            system += 1
    if mic == 0 and system == 0:
        return "system"
    return "microphone" if mic > system else "system"

class InterviewSession:
    """
    Represents a single, stateful interview session.
    This object persists even if the WebSocket connection is lost.
    """
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.websocket: Optional[WebSocket] = None
        self.llm_manager: Optional[MultiLLMManager] = None
        self.stt_manager: Optional[DeepgramManager] = None
        self.is_active: bool = False
        self.state: Dict[str, Any] = {
            "is_muted": False,
            "process_all_speakers": True,
            "is_universally_muted": False
        }
        self.transcript_buffer: str = ""
        self.silence_timer: Optional[asyncio.Task] = None
        self.last_activity_time: float = time.time()
        self._delayed_cleanup_task: Optional[asyncio.Task] = None
        # A1: rolling (timestamp, mic_dominant) hints, one per audio batch.
        # 200 entries at ~47 batches/s covers ~4s of history — well beyond
        # the 1.5s classification window.
        self.hint_timeline: Deque[Tuple[float, bool]] = deque(maxlen=200)
        # P3: turn-by-turn interview record for transcript export.
        self.transcript_log: List[Dict[str, Any]] = []
        # P4: live answer-mode flag (full answers vs quick hints), toggled
        # mid-interview via Alt+G without restarting.
        self.generate_full_answers: bool = True
        # P1: STT language for this session ('en' or 'multi').
        self.stt_language: str = getattr(settings, 'STT_LANGUAGE', 'en') or 'en'

    def cancel_delayed_cleanup(self):
        """Cancel any pending post-disconnect cleanup (client resumed in time)."""
        if self._delayed_cleanup_task and not self._delayed_cleanup_task.done():
            self._delayed_cleanup_task.cancel()
        self._delayed_cleanup_task = None

    def _touch(self):
        """Update last activity time."""
        self.last_activity_time = time.time()

    async def _send_json(self, type: str, payload: dict):
        """Safely sends a JSON message to the client's websocket."""
        if self.websocket:
            self._touch()
            await send_json(self.websocket, type, payload)

    async def handle_verify_deepgram(self, payload: dict):
        """Handles the deepgram verification request from the client."""
        from services.stt_service import verify_deepgram_api_key
        self._touch()
        print(f"➡️ [BACKEND] Received 'verify_deepgram' for session {self.session_id}")
        is_valid = await verify_deepgram_api_key()
        print(f"⬅️ [BACKEND] Sending 'api_key_status' for Deepgram. Valid: {is_valid}")
        await self._send_json("api_key_status", {"service": "deepgram", "valid": is_valid})

    async def handle_start_interview(self, payload: dict):
        """Handles the 'start_interview' message."""
        self._touch()
        print(f"🎬 Session {self.session_id}: Starting interview...")
        try:
            primary_provider_config = payload.get('aiProvider')
            secondary_provider_config = payload.get('aiSecondaryProvider')
            primary_vision_config = payload.get('visionProvider')
            secondary_vision_config = payload.get('visionSecondaryProvider')
            onboarding_context = payload.get('onboardingData', {})

            # P1: STT language chosen in onboarding ('en' | 'multi').
            stt_language = payload.get('sttLanguage')
            if stt_language in ('en', 'multi'):
                self.stt_language = stt_language
            
            self.state["is_muted"] = payload.get('is_muted', False)
            self.state["process_all_speakers"] = payload.get('process_all_speakers', True)
            self.state["is_universally_muted"] = payload.get('is_universally_muted', False)

            await self.initialize_managers(primary_provider_config, secondary_provider_config, primary_vision_config, secondary_vision_config, onboarding_context)
            
            current_preset = self.llm_manager.get_current_preset_info()
            health_results = await self.llm_manager.perform_health_checks()
            await self._send_json("preset_initialized", {
                "current_preset": current_preset,
                "available_presets": list(self.llm_manager.presets.keys()),
                "health_status": health_results
            })
            print(f"✅ Session {self.session_id}: Interview started and managers initialized.")
            
            # Automatically activate stealth mode (click-through ghost mode, taskbar hide, capture protection)
            try:
                import window_manager
                window_manager.window_manager.enable_proctoring_stealth_mode()
                print("🕵️ Stealth mode automatically enabled for session")
            except Exception as stealth_err:
                print(f"⚠️ Could not automatically enable stealth mode: {stealth_err}")
        except Exception as e:
            print(f"❌ CRITICAL: Session {self.session_id}: Failed to start interview: {e}")
            await self._send_json("error", {"message": f"Failed to initialize AI providers: {str(e)}"})

    async def handle_audio_chunk(self, payload: dict):
        """Handles incoming audio chunks."""
        self._touch()
        if self.state.get("is_universally_muted", False):
            return

        is_mic_muted = payload.get('is_muted', self.state.get("is_muted", False))
        self.state["is_muted"] = is_mic_muted
        speaker_hint = payload.get('speaker_hint', 'system')
        # A1: record per-batch hints on the timeline. Transcripts are later
        # attributed by majority vote over the window ending at their own
        # timestamp, so a single stale chunk can no longer misclassify a whole
        # utterance.
        self.hint_timeline.append((time.time(), speaker_hint == 'microphone'))

        # If microphone is muted and this chunk is from microphone, drop it immediately
        if is_mic_muted and speaker_hint == 'microphone':
            return

        if self.stt_manager:
            encoded = payload.get('audio_b64')
            if encoded:
                try:
                    audio_data = base64.b64decode(encoded)
                except (ValueError, TypeError) as decode_err:
                    print(f"⚠️ Discarding malformed audio chunk: {decode_err}")
                    return
            else:
                # Legacy shape: audio as a JSON array of byte values.
                audio_data = bytes(payload.get('audio', []))
            
            if audio_data:
                await self.stt_manager.send_audio(audio_data)

    async def handle_config_update(self, payload: dict):
        """Handles configuration updates from the client."""
        self._touch()
        # P4: Alt+G live toggle between full answers and quick hints.
        if 'generateFullAnswers' in payload:
            self.generate_full_answers = bool(payload['generateFullAnswers'])
            app_metrics.inc('answer_mode_hints' if not self.generate_full_answers
                            else 'answer_mode_full')
            print(f"🎯 Session {self.session_id}: answer mode -> "
                  f"{'full' if self.generate_full_answers else 'hints'}")
        if 'sttLanguage' in payload:
            lang = payload['sttLanguage']
            if lang in ('en', 'multi') and lang != self.stt_language:
                self.stt_language = lang
                app_metrics.inc('stt_language_changes')
                print(f"🌐 Session {self.session_id}: STT language -> {lang}")
        if 'processAllSpeakers' in payload or 'process_all_speakers' in payload:
            self.state["process_all_speakers"] = payload.get('processAllSpeakers', payload.get('process_all_speakers'))
        if 'isUniversallyMuted' in payload or 'is_universally_muted' in payload:
            now_universally_muted = payload.get('isUniversallyMuted', payload.get('is_universally_muted'))
            self.state["is_universally_muted"] = now_universally_muted
            if now_universally_muted:
                if self.silence_timer:
                    self.silence_timer.cancel()
                    self.silence_timer = None
                self.transcript_buffer = ""
                print(f"⏸️ Session {self.session_id}: Universal mute enabled (silence timer cancelled, buffer cleared)")
        if 'is_muted' in payload:
            now_mic_muted = payload['is_muted']
            self.state["is_muted"] = now_mic_muted
            if now_mic_muted:
                if self.silence_timer:
                    self.silence_timer.cancel()
                    self.silence_timer = None
                # User just muted the mic! If speech was buffered while speaking,
                # muting is the ultimate signal that speaking has finished — trigger immediate answer generation!
                if self.transcript_buffer and self.transcript_buffer.strip():
                    print(f"🎤 Session {self.session_id}: Mic muted with buffered speech -> processing immediately: '{self.transcript_buffer.strip()}'")
                    asyncio.create_task(self._process_aggregated_transcript())
            print(f"🎤 Session {self.session_id}: Microphone mute state updated to {self.state['is_muted']}")
        await self._send_json("config_updated", self.state)

    async def handle_switch_preset(self, payload: dict):
        """Handles preset switching."""
        self._touch()
        if not self.llm_manager:
            return await self._send_json("error", {"message": "AI providers not initialized"})
        
        preset_key = payload.get('preset_key')
        success, result = await self.llm_manager.switch_preset(preset_key)
        
        if success:
            await self._send_json("preset_switched", {"success": True, **result})
        else:
            await self._send_json("preset_switch_failed", {"success": False, **result})

    async def handle_vision_analysis(self, payload: dict):
        """Handles vision analysis requests."""
        self._touch()
        try:
            print(f"🔍 Session {self.session_id}: Processing vision analysis request...")
            
            screenshots = payload.get('screenshots', [])
            vision_config = payload.get('visionConfig', {})
            languages = payload.get('languages', [])
            
            if not screenshots:
                await self._send_json("vision_analysis_result", {
                    "success": False,
                    "error": "No screenshots provided for analysis"
                })
                return
            
            if not vision_config or not vision_config.get('provider') or not vision_config.get('model'):
                await self._send_json("vision_analysis_result", {
                    "success": False,
                    "error": "Vision provider configuration missing"
                })
                return
            
            provider_name = vision_config['provider']
            model_name = vision_config['model']
            
            print(f"Analyzing {len(screenshots)} screenshots with {provider_name}-{model_name}")
            app_metrics.inc("vision_requests")

            analysis, result_info = await vision_service.analyze_coding_problem(
                provider_name=provider_name,
                model_name=model_name,
                screenshots=screenshots,
                languages=languages
            )
            
            await self._send_json("vision_analysis_result", {
                "success": result_info.get("success", True),
                "analysis": analysis,
                "provider": provider_name,
                "model": model_name,
                "screenshot_count": len(screenshots),
                "languages": languages,
                **result_info
            })
            
            print(f"✅ Session {self.session_id}: Vision analysis completed successfully")
            
        except Exception as e:
            print(f"❌ CRITICAL: Session {self.session_id}: Vision analysis failed: {e}")
            await self._send_json("vision_analysis_result", {
                "success": False,
                "error": f"Vision analysis failed: {str(e)}"
            })

    async def handle_end_interview(self, payload: dict):
        """Handles the end of an interview."""
        print(f"🛑 Session {self.session_id}: Ending interview.")
        await self.cleanup()
        session_manager.remove_session(self.session_id)

    async def handle_reset_session(self, payload: dict):
        """Handles the reset of a session's context."""
        self._touch()
        print(f"🔄 Session {self.session_id}: Resetting interview context...")
        self.transcript_buffer = ""
        if self.silence_timer:
            self.silence_timer.cancel()
        
        if self.llm_manager:
            self.llm_manager.reset_context()

        await self._send_json("session_reset_complete", {"status": "ok"})
        print(f"✅ Session {self.session_id}: Context has been reset.")

    async def initialize_managers(self, primary_provider_config, secondary_provider_config, primary_vision_config, secondary_vision_config, onboarding_context):
        """Initializes all necessary managers for the session."""
        self.llm_manager = MultiLLMManager()
        config_loaded = self.llm_manager.load_configuration(
            primary_config=primary_provider_config,
            secondary_config=secondary_provider_config
        )
        if not config_loaded:
            raise ValueError("Failed to load AI provider configuration.")
        
        self.llm_manager.initialize_candidate_context(onboarding_context)
        vision_service.set_context_manager(self.llm_manager.shared_context)
        await self.llm_manager.perform_health_checks()

        vision_service.load_vision_providers(
            primary_config=primary_vision_config,
            secondary_config=secondary_vision_config
        )

        user_languages = onboarding_context.get('selectedLanguages', [])
        # P1: honor the session's STT language (en|multi) set at interview
        # start or via config updates.
        stt_language = self.stt_language or getattr(settings, 'STT_LANGUAGE', 'en')
        self.stt_manager = DeepgramManager(self.on_transcript, user_languages,
                                           language=stt_language)
        await self.stt_manager.start()
        
        self.is_active = True

    async def _process_aggregated_transcript(self):
        """Processes the buffered transcript after a period of silence."""
        if not self.transcript_buffer:
            return

        # Abort immediately if universally muted
        if self.state.get("is_universally_muted"):
            self.transcript_buffer = ""
            return

        transcript = self.transcript_buffer
        self.transcript_buffer = ""
        
        print(f"✅ Silence detected. Processing transcript for session {self.session_id}: {transcript}")
        if not self.llm_manager or not self.websocket:
            return

        try:
            # P4: quick-hint mode prefixes the prompt so the LLM answers with a
            # concise hint instead of full code, without touching provider config.
            mode = "full"
            prompt = transcript
            if not self.generate_full_answers:
                mode = "hints"
                prompt = (
                    "QUICK HINT MODE - reply with a concise 2-3 line hint only "
                    "(approach + key insight), no full code:\n" + transcript
                )

            await self._send_json("ai_processing_started", {
                "question": transcript, "mode": mode
            })

            async def stream_callback(chunk: str, chunk_type: str):
                return await self._send_json("ai_answer_chunk", {"chunk": chunk, "chunk_type": chunk_type})

            _started = time.monotonic()
            answer, result_info = await self.llm_manager.get_ai_answer(
                prompt, stream_callback, generate_full_answers=self.generate_full_answers
            )
            app_metrics.inc("questions_answered")
            if result_info.get("success"):
                app_metrics.record_answer_latency((time.monotonic() - _started) * 1000.0)
            # fallbacks_used is recorded inside MultiLLMManager.get_ai_answer

            await self._send_json("ai_answer_complete", {"answer": answer, **result_info})
            if not self.generate_full_answers:
                app_metrics.inc('hint_answers')
            print(f"🤖 AI STREAMING COMPLETE for session {self.session_id}")

        except Exception as e:
            print(f"❌ CRITICAL: Error processing transcript for session {self.session_id}: {e}")
            await self._send_json("error", {"message": "Error processing transcript."})

    async def on_transcript(self, data):
        """Callback from Deepgram. Handles transcript logic and adaptive silence detection."""
        if self.state.get("is_universally_muted"):
            return

        self._touch()
        await self._send_json("transcript_update", data)

        transcript = data.get('transcript', '').strip()
        is_final = data.get('is_final', False)
        if not transcript:
            return

        # A1: attribute the transcript by majority vote of audio hints in the
        # window before now (transcript lags its speech by a few hundred ms).
        is_candidate_speech = (
            classify_speaker(self.hint_timeline, time.time()) == 'microphone'
        )
        
        # When microphone is muted, NEVER process candidate speech as a prompt under any circumstance
        if is_candidate_speech and self.state.get("is_muted"):
            return

        # If candidate speech and process_all_speakers is explicitly disabled, treat as candidate answer context,
        # unless it is an explicit question or prompt directed at the copilot
        if is_candidate_speech and not self.state.get("process_all_speakers", True):
            prompt_triggers = (
                "can you", "could you", "how do", "how would", "what is", "what are",
                "explain", "solve", "dry run", "give me", "write a", "code this",
                "tell me", "why does", "walk through", "help me", "what if", "show me"
            )
            lower_transcript = transcript.lower()
            if transcript.endswith('?') or any(lower_transcript.startswith(pt) or f" {pt}" in lower_transcript for pt in prompt_triggers):
                should_process = True
            else:
                should_process = False
        else:
            should_process = True

        if is_final:
            # P3: record every final turn in the exportable log.
            self.transcript_log.append({
                'speaker': 'candidate' if is_candidate_speech else 'interviewer',
                'text': transcript,
                'timestamp': datetime.now().isoformat()
            })
            if len(self.transcript_log) > TRANSCRIPT_LOG_MAX_TURNS:
                del self.transcript_log[:len(self.transcript_log) - TRANSCRIPT_LOG_MAX_TURNS]

            if should_process:
                # Hygiene: strip standalone filler words ("um", "uh", "erm")
                # that survive Deepgram's filler_words=false in some accents,
                # along with the punctuation hanging off them, so the LLM
                # prompt stays clean.
                transcript = re.sub(r'\s*\b(um+|uh+|erm+|hmm+)\b[.,!?;]*(\.\.\.)*\s*',
                                    ' ', transcript, flags=re.IGNORECASE).strip()
                transcript = re.sub(r'\s{2,}', ' ', transcript)
                transcript = re.sub(r'^[\s,.;]+|[\s,.;]+$', '', transcript)
                self.transcript_buffer = (self.transcript_buffer + " " + transcript).strip()
                
                # Adaptive silence threshold:
                # If question ends with '?', interviewer has finished asking - answer immediately (400ms)
                # If statement ends with '.' or '!', wait 500ms
                # Otherwise (mid-sentence pause), wait 700ms
                if transcript.endswith('?'):
                    silence_wait = 0.4
                elif transcript.endswith('.') or transcript.endswith('!'):
                    silence_wait = 0.5
                else:
                    silence_wait = 0.7

                if self.silence_timer:
                    self.silence_timer.cancel()
                
                async def delayed_processing(wait_time):
                    await asyncio.sleep(wait_time)
                    await self._process_aggregated_transcript()
                
                self.silence_timer = asyncio.create_task(delayed_processing(silence_wait))
            else:
                if self.llm_manager:
                    self.llm_manager.process_candidate_response(transcript)
        else:
            # Interim result: if still speaking, push back silence timer so it doesn't fire prematurely
            # but still fires promptly after pause
            if should_process and self.transcript_buffer:
                if self.silence_timer:
                    self.silence_timer.cancel()
                async def delayed_processing(wait_time):
                    await asyncio.sleep(wait_time)
                    await self._process_aggregated_transcript()
                self.silence_timer = asyncio.create_task(delayed_processing(0.7))

    async def cleanup(self):
        """Cleans up resources for the session."""
        if self.stt_manager:
            await self.stt_manager.finish()
        if self.silence_timer and not self.silence_timer.done():
            self.silence_timer.cancel()
        self.is_active = False
        print(f"Session {self.session_id} cleaned up.")


class SessionManager:
    """
    Manages all active interview sessions.
    Includes TTL-based cleanup for stale sessions.
    """
    def __init__(self):
        self.active_sessions: Dict[str, InterviewSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    def create_session(self) -> InterviewSession:
        """Creates a new, unique interview session."""
        session_id = str(uuid.uuid4())
        session = InterviewSession(session_id)
        self.active_sessions[session_id] = session
        print(f"Created new session: {session_id} (total active: {len(self.active_sessions)})")
        return session

    def get_session(self, session_id: str) -> Optional[InterviewSession]:
        """Retrieves an existing session by its ID."""
        session = self.active_sessions.get(session_id)
        if session:
            session._touch()
        return session

    def remove_session(self, session_id: str):
        """Removes a session and cleans up its resources."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            print(f"Removed session: {session_id} (remaining: {len(self.active_sessions)})")

    def start_cleanup_task(self):
        """Start the background cleanup task for stale sessions."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            print("Session cleanup task started (checks every 5 minutes)")

    def schedule_delayed_cleanup(self, session_id: str, grace_seconds: float):
        """Schedule cleanup of a disconnected session after a grace period.

        Called when a WebSocket drops. If the client reconnects in time, the
        resumed session cancels the task via InterviewSession.cancel_delayed_cleanup.
        """
        session = self.active_sessions.get(session_id)
        if not session:
            return
        session.cancel_delayed_cleanup()
        session._delayed_cleanup_task = asyncio.create_task(
            self._delayed_cleanup(session_id, grace_seconds)
        )

    async def _delayed_cleanup(self, session_id: str, grace_seconds: float):
        """Tear down a session that stayed disconnected past the grace period."""
        try:
            await asyncio.sleep(grace_seconds)
        except asyncio.CancelledError:
            return

        session = self.active_sessions.get(session_id)
        if session is None:
            return
        if session.websocket is not None:
            return  # Client reconnected without cancelling through resume path

        print(f"Cleaning up disconnected session after grace period: {session_id}")
        app_metrics.inc("delayed_cleanups")
        try:
            await session.cleanup()
        except Exception as e:
            print(f"Warning: error cleaning up session {session_id}: {e}")
        self.remove_session(session_id)

    async def _cleanup_loop(self):
        """Periodically clean up stale sessions."""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            await self._cleanup_stale_sessions()

    async def _cleanup_stale_sessions(self):
        """Remove sessions that have been inactive and disconnected for too long."""
        now = time.time()
        stale_ids = []
        
        for sid, session in self.active_sessions.items():
            if session.websocket is None:
                idle_time = now - session.last_activity_time
                if idle_time > SESSION_TTL_SECONDS:
                    stale_ids.append(sid)
        
        for sid in stale_ids:
            session = self.active_sessions.get(sid)
            if session:
                try:
                    await session.cleanup()
                except Exception as e:
                    print(f"⚠️ Error cleaning up stale session {sid}: {e}")
                del self.active_sessions[sid]
                print(f"🧹 Cleaned up stale session: {sid} (remaining: {len(self.active_sessions)})")
        
        if stale_ids:
            print(f"🧹 Cleaned up {len(stale_ids)} stale session(s)")

# Create a single, global instance of the SessionManager
session_manager = SessionManager()