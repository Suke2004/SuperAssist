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

# Binary audio frames are normally 2,050 bytes (2-byte header plus 1,024
# Linear16 samples). Keep a generous ceiling so malformed clients cannot
# enqueue unbounded payloads or force excessive STT work.
BINARY_AUDIO_HEADER_BYTES = 2
MAX_BINARY_AUDIO_BYTES = 64 * 1024


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
        self._send_lock = asyncio.Lock()
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
        self._last_word_end = 0.0
        self._speech_started_at = -1.0
        self.last_activity_time: float = time.time()
        self._delayed_cleanup_task: Optional[asyncio.Task] = None
        self._answer_tasks = set()
        self._answer_lock = asyncio.Lock()
        # A1: rolling (timestamp, mic_dominant) hints, one per audio batch.
        # 200 entries at ~47 batches/s covers ~4s of history — well beyond
        # the 1.5s classification window.
        self.hint_timeline: Deque[Tuple[float, bool]] = deque(maxlen=200)
        # P3: turn-by-turn interview record for transcript export.
        self.transcript_log: List[Dict[str, Any]] = []
        # P4: live answer-mode flag (full answers vs quick hints), toggled
        # mid-interview via Alt+G without restarting.
        self.generate_full_answers: bool = True
        self.auto_answer_enabled: bool = True
        self.audio_capture_mode = "browser"
        self.audio_output = ""
        self.microphone_available = True
        self.native_audio = None
        self.mic_stt_manager = None
        self._health_task = None
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

    def clear_websocket(self, websocket: WebSocket) -> bool:
        """Clear the socket only when it is still the session's active socket."""
        if self.websocket is not websocket:
            return False
        self.websocket = None
        return True

    async def _send_json(self, type: str, payload: dict):
        """Safely sends a JSON message to the client's websocket."""
        async with self._send_lock:
            websocket = self.websocket
            if websocket:
                self._touch()
                return await send_json(websocket, type, payload)
        return False

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
        if self.is_active:
            await self._send_json('error', {'message': 'This interview is already running.'})
            return
        print(f"🎬 Session {self.session_id}: Starting interview...")
        try:
            primary_provider_config = payload.get('aiProvider')
            secondary_provider_config = payload.get('aiSecondaryProvider')
            primary_vision_config = payload.get('visionProvider')
            secondary_vision_config = payload.get('visionSecondaryProvider')
            onboarding_context = payload.get('onboardingData', {})
            capture_mode = payload.get('audioCaptureMode', 'browser')
            output = payload.get('audioOutput', '')
            microphone_available = payload.get('microphoneAvailable', True)
            if capture_mode not in ('browser', 'native') or not isinstance(output, str) or len(output) > 512 or not isinstance(microphone_available, bool):
                raise ValueError('Invalid audio capture settings.')
            self.audio_capture_mode = capture_mode
            self.audio_output = output
            self.microphone_available = microphone_available

            # P1: STT language chosen in onboarding ('en' | 'multi').
            stt_language = payload.get('sttLanguage')
            if stt_language in ('en', 'multi'):
                self.stt_language = stt_language
            
            self.state["is_muted"] = payload.get('is_muted', False)
            self.state["process_all_speakers"] = payload.get('process_all_speakers', True)
            self.state["is_universally_muted"] = payload.get('is_universally_muted', False)

            await self.initialize_managers(primary_provider_config, secondary_provider_config, primary_vision_config, secondary_vision_config, onboarding_context)
            if self.native_audio:
                await self.native_audio.start()
            if not await self._send_json("interview_started", {"audio_capture_mode": self.audio_capture_mode}):
                await self.cleanup()
                return
            self._health_task = asyncio.create_task(self._report_provider_health())
            print(f"✅ Session {self.session_id}: Interview started and managers initialized.")
            
            # Keep mouse scrolling available; click-through is an explicit user toggle.
            try:
                import window_manager
                window_manager.window_manager.enable_proctoring_stealth_mode(click_through=False)
                print("🕵️ Stealth mode automatically enabled for session")
            except Exception as stealth_err:
                print(f"⚠️ Could not automatically enable stealth mode: {stealth_err}")
        except Exception as e:
            print(f"❌ CRITICAL: Session {self.session_id}: Failed to start interview: {e}")
            await self.cleanup()
            await self._send_json("interview_start_failed", {"message": str(e)})
            await self._send_json("error", {"message": f"Failed to initialize AI providers: {str(e)}"})

    async def handle_binary_audio(self, data: bytes):
        """P1.1: Fast zero-copy handler for binary audio frames.
        
        Frame layout:
          - Byte 0: speaker_hint (0x01: microphone, 0x02: system)
          - Byte 1: is_muted (0x01: muted, 0x00: unmuted)
          - Bytes 2+: Linear16 PCM audio data
        """
        self._touch()
        if not isinstance(data, (bytes, bytearray, memoryview)):
            app_metrics.inc("invalid_audio_frames")
            return
        frame = bytes(data)
        if (
            len(frame) <= BINARY_AUDIO_HEADER_BYTES
            or len(frame) > MAX_BINARY_AUDIO_BYTES
            or (len(frame) - BINARY_AUDIO_HEADER_BYTES) % 2 != 0
            or frame[0] not in (1, 2)
            or frame[1] not in (0, 1)
        ):
            app_metrics.inc("invalid_audio_frames")
            return
        if self.state.get("is_universally_muted", False):
            return

        speaker_flag = frame[0]
        muted_flag = frame[1]
        speaker_hint = 'microphone' if speaker_flag == 1 else 'system'
        is_mic_muted = (muted_flag == 1) or self.state.get("is_muted", False)
        self.state["is_muted"] = is_mic_muted

        self.hint_timeline.append((time.time(), speaker_hint == 'microphone'))

        # If microphone is muted and this chunk is from microphone, drop it immediately
        if is_mic_muted and speaker_hint == 'microphone':
            return

        if self.stt_manager:
            audio_pcm = frame[BINARY_AUDIO_HEADER_BYTES:]
            if audio_pcm:
                if self.audio_capture_mode == 'native':
                    if speaker_hint == 'microphone' and self.mic_stt_manager:
                        await self.mic_stt_manager.send_audio(audio_pcm)
                else:
                    await self.stt_manager.send_audio(audio_pcm)

    async def handle_audio_chunk(self, payload: dict):
        """Handles incoming legacy JSON audio chunks."""
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
                if self.audio_capture_mode == 'native':
                    if speaker_hint == 'microphone' and self.mic_stt_manager:
                        await self.mic_stt_manager.send_audio(audio_data)
                else:
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
            if self.native_audio:
                self.native_audio.paused = bool(now_universally_muted)
            if now_universally_muted:
                for manager in (self.stt_manager, self.mic_stt_manager):
                    if manager and hasattr(manager, 'clear_audio_buffer'):
                        await manager.clear_audio_buffer()
                if self.native_audio:
                    while not self.native_audio.queue.empty():
                        self.native_audio.queue.get_nowait()
                if self.silence_timer:
                    self.silence_timer.cancel()
                    self.silence_timer = None
                self.transcript_buffer = ""
                print(f"⏸️ Session {self.session_id}: Universal mute enabled (silence timer cancelled, buffer cleared)")
        if 'is_muted' in payload:
            now_mic_muted = payload['is_muted']
            self.state["is_muted"] = now_mic_muted
            if now_mic_muted:
                if self.mic_stt_manager:
                    await self.mic_stt_manager.clear_audio_buffer()
                if self.silence_timer:
                    self.silence_timer.cancel()
                    self.silence_timer = None
                # User just muted the mic! If speech was buffered while speaking,
                # muting is the ultimate signal that speaking has finished — trigger immediate answer generation!
                if self.auto_answer_enabled and self.transcript_buffer.strip():
                    print(f"🎤 Session {self.session_id}: Mic muted with buffered speech -> processing immediately: '{self.transcript_buffer.strip()}'")
                    self._queue_answer()
            print(f"🎤 Session {self.session_id}: Microphone mute state updated to {self.state['is_muted']}")
        await self._send_json("config_updated", self.state)

    def _queue_answer(self, question: Optional[str] = None):
        task = asyncio.create_task(self._process_aggregated_transcript(question))
        self._answer_tasks.add(task)
        task.add_done_callback(self._answer_tasks.discard)

    async def handle_ask_question(self, payload: dict):
        question = payload.get("question") if isinstance(payload, dict) else None
        if not isinstance(question, str) or not question.strip() or len(question) > TRANSCRIPT_BUFFER_MAX_CHARS:
            return await self._send_json("error", {"message": f"Question must be nonblank text of at most {TRANSCRIPT_BUFFER_MAX_CHARS} characters."})
        if not self.is_active or not self.llm_manager:
            return await self._send_json("error", {"message": "Start an interview before asking a question."})
        if self.state.get("is_universally_muted"):
            return await self._send_json("error", {"message": "Resume the interview before asking a question."})
        self._touch()
        self._queue_answer(question.strip())

    async def handle_request_answer(self, payload: dict):
        if not self.is_active or not self.llm_manager:
            return await self._send_json("error", {"message": "Start an interview before requesting an answer."})
        if self.state.get("is_universally_muted"):
            return await self._send_json("error", {"message": "Resume the interview before requesting an answer."})
        if not self.transcript_buffer.strip():
            return await self._send_json("error", {"message": "No interviewer question has been transcribed yet."})
        if self.silence_timer:
            self.silence_timer.cancel()
            self.silence_timer = None
        question, self.transcript_buffer = self.transcript_buffer, ""
        self._touch()
        self._queue_answer(question)

    async def handle_set_auto_answer(self, payload: dict):
        enabled = payload.get("enabled") if isinstance(payload, dict) else None
        if not isinstance(enabled, bool):
            return await self._send_json("error", {"message": "Auto answer enabled must be a boolean."})
        self.auto_answer_enabled = enabled
        if self.silence_timer:
            self.silence_timer.cancel()
            self.silence_timer = None
        self._touch()
        await self._send_json("auto_answer_status", {"enabled": enabled})
        if enabled and self.is_active and self.transcript_buffer.strip():
            self._queue_answer()

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

        vision_service.load_vision_providers(
            primary_config=primary_vision_config,
            secondary_config=secondary_vision_config
        )

        user_languages = onboarding_context.get('selectedLanguages', [])
        # P1: honor the session's STT language (en|multi) set at interview
        # start or via config updates.
        stt_language = self.stt_language or getattr(settings, 'STT_LANGUAGE', 'en')
        if self.audio_capture_mode == 'native':
            from services.native_audio import NativeLoopback
            self.native_audio = NativeLoopback(self._send_native_audio, self._native_audio_status, self.audio_output)
            await self.native_audio.open()
            self.native_audio.paused = bool(self.state.get('is_universally_muted'))
            self.stt_manager = DeepgramManager(self._system_transcript, user_languages,
                language=stt_language, sample_rate=self.native_audio.sample_rate)
            if self.microphone_available:
                self.mic_stt_manager = DeepgramManager(self._microphone_transcript, user_languages, language=stt_language)
        else:
            self.stt_manager = DeepgramManager(self.on_transcript, user_languages, language=stt_language)
        starts = [asyncio.create_task(manager.start()) for manager in (self.stt_manager, self.mic_stt_manager) if manager]
        try:
            await asyncio.gather(*starts)
        except BaseException:
            for task in starts:
                task.cancel()
            await asyncio.gather(*starts, return_exceptions=True)
            raise
        
        self.is_active = True

    async def _report_provider_health(self):
        try:
            health = await self.llm_manager.perform_health_checks()
            await self._send_json('preset_initialized', {
                'current_preset': self.llm_manager.get_current_preset_info(),
                'available_presets': list(self.llm_manager.presets.keys()), 'health_status': health})
        except Exception as error:
            print(f'Provider health check failed: {error}')

    async def _send_native_audio(self, pcm):
        if self.is_active and not self.state.get('is_universally_muted') and self.stt_manager:
            await self.stt_manager.send_audio(pcm)

    async def _native_audio_status(self, status, detail):
        await self._send_json('audio_capture_status', {'status': status, 'detail': detail, 'source': 'system'})

    async def _system_transcript(self, data):
        await self.on_transcript({**data, 'speaker_role': 'interviewer', 'source': 'system'})

    async def _microphone_transcript(self, data):
        if not self.state.get('is_muted') or data.get('type') == 'stt_status':
            await self.on_transcript({**data, 'speaker_role': 'candidate', 'source': 'microphone'})

    async def _process_aggregated_transcript(self, question: Optional[str] = None):
        """Processes the buffered transcript after a period of silence."""
        current_task = asyncio.current_task()
        if current_task is not None:
            self._answer_tasks.add(current_task)

        try:
            # Multiple silence/mute triggers can arrive for one session while
            # an answer is still streaming.  Serialize them; a later caller
            # will process any transcript buffered while the first answer ran.
            async with self._answer_lock:
                if self.silence_timer is current_task:
                    self.silence_timer = None
                await self._process_aggregated_transcript_once(question)
        finally:
            if current_task is not None:
                self._answer_tasks.discard(current_task)

    async def _process_aggregated_transcript_once(self, question: Optional[str] = None):
        """Process one buffered transcript while the session lock is held."""
        if question is None and not self.auto_answer_enabled:
            return
        if question is None and not self.transcript_buffer:
            return

        # Abort immediately if universally muted
        if self.state.get("is_universally_muted"):
            self.transcript_buffer = ""
            return

        transcript = question if question is not None else self.transcript_buffer
        if question is None:
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

    def _schedule_transcript_answer(self, delay):
        if self.silence_timer:
            self.silence_timer.cancel()
        self.silence_timer = None
        if not self.auto_answer_enabled or not self.transcript_buffer:
            return

        async def delayed_processing():
            await asyncio.sleep(delay)
            # Keep the timer cancellable while waiting for an earlier answer's lock.
            try:
                await self._process_aggregated_transcript()
            finally:
                if self.silence_timer is asyncio.current_task():
                    self.silence_timer = None

        self.silence_timer = asyncio.create_task(delayed_processing())

    async def on_transcript(self, data):
        """Accumulate finalized segments until the speaker actually finishes."""
        if self.state.get("is_universally_muted"):
            return

        self._touch()
        if isinstance(data, dict) and data.get("type") == "stt_status":
            if data.get('status') == 'connected' and data.get('source') != 'microphone':
                self._last_word_end = 0.0
                self._speech_started_at = -1.0
            await self._send_json("stt_status", data)
            return

        is_candidate_speech = (data['speaker_role'] == 'candidate' if data.get('speaker_role')
                               else classify_speaker(self.hint_timeline, time.time()) == 'microphone')
        if data.get('type') in ('speech_started', 'utterance_end'):
            if is_candidate_speech and (self.state.get('is_muted') or not self.state.get('process_all_speakers', True)):
                return
            if data['type'] == 'speech_started':
                self._speech_started_at = data.get('timestamp') or 0.0
                if self.silence_timer:
                    self.silence_timer.cancel()
                    self.silence_timer = None
            else:
                end = data.get('last_word_end')
                # Ignore a delayed boundary belonging to speech before the latest continuation.
                if end is not None and (end < self._last_word_end or end <= self._speech_started_at):
                    return
                self._schedule_transcript_answer(0.2)
            return
        await self._send_json("transcript_update", {
            **data, "speaker_role": "candidate" if is_candidate_speech else "interviewer"
        })

        transcript = data.get('transcript', '').strip()
        is_final = data.get('is_final', False)
        if not transcript:
            return

        # A1: attribute the transcript by majority vote of audio hints in the
        # window before now (transcript lags its speech by a few hundred ms).
        
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

        if not self.auto_answer_enabled and is_candidate_speech:
            should_process = False

        if should_process and data.get('last_word_end') is not None:
            self._last_word_end = max(self._last_word_end, data['last_word_end'])

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
                self.transcript_buffer = (self.transcript_buffer + " " + transcript).strip()[-TRANSCRIPT_BUFFER_MAX_CHARS:]

                if not self.auto_answer_enabled:
                    return
                
                # Endpointing already includes a 1.5-second pause; punctuation is not a boundary.
                self._schedule_transcript_answer(0.35 if data.get('speech_final') else 2.5)
            else:
                if self.llm_manager:
                    self.llm_manager.process_candidate_response(transcript)
        else:
            # Never answer the earlier fragment while the rest is still being recognized.
            if should_process:
                if self.silence_timer:
                    self.silence_timer.cancel()
                    self.silence_timer = None

    async def cleanup(self):
        """Cleans up resources for the session."""
        if self.silence_timer and not self.silence_timer.done():
            self.silence_timer.cancel()
        answer_tasks = [
            task for task in self._answer_tasks
            if task is not asyncio.current_task() and not task.done()
        ]
        for task in answer_tasks:
            task.cancel()
        if answer_tasks:
            await asyncio.gather(*answer_tasks, return_exceptions=True)

        self.is_active = False
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            await asyncio.gather(self._health_task, return_exceptions=True)
        self._health_task = None
        try:
            resources = [resource for resource in (self.native_audio, self.mic_stt_manager, self.stt_manager) if resource]
            for result in await asyncio.gather(*(resource.finish() for resource in resources), return_exceptions=True):
                if isinstance(result, Exception):
                    print(f'Audio cleanup error: {result}')
            self.native_audio = None
            self.mic_stt_manager = None
        finally:
            if self.llm_manager:
                try:
                    await self.llm_manager.close()
                except Exception as e:
                    print(f"Warning: error closing LLM resources for session {self.session_id}: {e}")
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
        
        # Concurrency safety: snapshot items list to avoid mutation during iteration
        for sid, session in list(self.active_sessions.items()):
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
                self.active_sessions.pop(sid, None)
                print(f"🧹 Cleaned up stale session: {sid} (remaining: {len(self.active_sessions)})")
        
        if stale_ids:
            print(f"🧹 Cleaned up {len(stale_ids)} stale session(s)")

# Create a single, global instance of the SessionManager
session_manager = SessionManager()
