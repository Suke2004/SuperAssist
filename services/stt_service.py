import asyncio
import time
from collections import deque
from typing import Deque, Optional
import httpx
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)
from core.config import settings
from api.metrics import app_metrics

async def verify_deepgram_api_key():
    """
    Verifies the Deepgram API key by making a direct HTTP request.
    This is the most reliable method, independent of SDK changes.
    Returns True if the key is valid, False otherwise.
    """
    if not settings.DEEPGRAM_API_KEY:
        return False

    url = "https://api.deepgram.com/v1/projects"
    headers = {
        "Authorization": f"Token {settings.DEEPGRAM_API_KEY}"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                print("INFO: Deepgram API key is valid.")
                return True
            else:
                print(f"ERROR: Deepgram API key verification failed. Status: {response.status_code}, Response: {response.text}")
                return False
    except httpx.RequestError as e:
        print(f"ERROR: A network error occurred while verifying Deepgram key: {e}")
        return False


class DeepgramManager:
    """
    Manages the connection to Deepgram for live transcription.
    """
    def __init__(self, transcript_callback, user_languages=None, language: str = "en", sample_rate: int = 48000):
        self.transcript_callback = transcript_callback
        self.dg_connection = None
        self.is_connected = False
        self.stop_event = asyncio.Event()
        self.user_languages = user_languages or []
        # P1: transcription language — 'en' or 'multi' (Deepgram nova-3
        # supports multi-language code-switching via language="multi").
        self.language = language if language in ("en", "multi") else "en"
        if sample_rate not in (8000, 16000, 22050, 24000, 32000, 44100, 48000, 96000):
            raise ValueError('Unsupported capture sample rate.')
        self.sample_rate = sample_rate
        self._send_lock = asyncio.Lock()
        self._language_lock = asyncio.Lock()
        self._flush_complete = asyncio.Event()
        self.context_keyterms = []
        self._last_gap_warning = 0.0
        self._last_audio_at = 0.0
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_base_delay = 1.0  # seconds
        # A1: singleflight guard - only one reconnect loop may run at a time.
        # on_error and on_close both fire for the same dropped socket; without
        # the guard each spawns its own reconnect task and two loops race,
        # opening duplicate Deepgram connections.
        self._reconnect_task: asyncio.Task = None
        # Initial-connection retry budget (A2): the very first start() gets a
        # bounded number of attempts before we give up and raise.
        self._initial_connect_max_attempts = 3
        
        # Four seconds of mono PCM, independent of the capture frame size.
        self.audio_ring_buffer: Deque[bytes] = deque()
        
        # Setup Deepgram client
        config = DeepgramClientOptions(
            verbose=False,  # Disable verbose logging to reduce spam
            options={"keepalive": "true"}
        )
        self.deepgram = DeepgramClient(settings.DEEPGRAM_API_KEY, config)

    def get_programming_keyterms(self, user_languages=None):
        """Use a small, balanced vocabulary without forcing phonetic replacements."""
        language_terms = {
            'python': ['Python', 'Django', 'Flask', 'pandas', 'NumPy'],
            'java': ['Java', 'Spring', 'JVM', 'Maven'],
            'javascript': ['JavaScript', 'Node.js', 'React', 'Vue', 'Angular'],
            'typescript': ['TypeScript', 'generics'],
            'c++': ['C++', 'STL', 'vector'],
            'sql': ['SQL', 'JOIN', 'GROUP BY', 'window function'],
        }
        terms = list(self.context_keyterms)
        for language in user_languages or []:
            terms.extend(language_terms.get(language.lower(), [language]))
        terms.extend([
            'API', 'REST', 'GraphQL', 'SQL', 'NoSQL', 'PostgreSQL', 'MongoDB',
            'Redis', 'microservices', 'load balancer', 'rate limiting', 'sharding',
            'replication', 'distributed systems', 'eventual consistency', 'Kafka',
            'Docker', 'Kubernetes', 'AWS', 'CI/CD', 'OAuth', 'JWT',
            'time complexity', 'space complexity', 'Big O', 'binary search',
            'linked list', 'binary search tree', 'hash map', 'hash set',
            'priority queue', 'trie', 'depth first search', 'breadth first search',
            'dynamic programming', 'memoization', 'backtracking', 'sliding window',
            'two pointers', 'two sum', 'merge intervals', 'LRU cache',
            'recursion', 'concurrency', 'deadlock', 'polymorphism', 'encapsulation',
            'inheritance', 'dependency injection', 'unit testing', 'LeetCode',
        ])
        seen = set()
        result = []
        for term in terms:
            if term.casefold() not in seen:
                seen.add(term.casefold())
                result.append(term)
        return result[:75]  # Bounded short phrases stay within the provider's keyterm budget.

    async def start(self):
        """Starts the Deepgram transcription connection, retrying initial failures.

        A2: previously a failed first connect was only printed and every audio
        chunk was then silently dropped forever. Now the connection is retried
        with the same exponential backoff used for reconnects, and if all
        attempts fail the exception propagates so handle_start_interview can
        surface a real error to the user.
        """
        last_error = None
        for attempt in range(1, self._initial_connect_max_attempts + 1):
            if self.stop_event.is_set():
                raise RuntimeError('Transcription startup was stopped')
            try:
                await self._connect_once()
                self._reconnect_attempts = 0  # Reset on successful connect
                print("Deepgram connection started successfully")
                return
            except Exception as e:
                last_error = e
                self.is_connected = False
                app_metrics.inc("deepgram_connect_failures")
                print(f"Deepgram connect attempt {attempt}/{self._initial_connect_max_attempts} failed: {e}")
                if attempt < self._initial_connect_max_attempts:
                    delay = self._reconnect_base_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        self.is_connected = False
        print(f"ERROR: Could not start Deepgram connection after "
              f"{self._initial_connect_max_attempts} attempts: {last_error}")
        raise RuntimeError(f"Deepgram connection failed: {last_error}") from last_error

    async def set_language(self, language):
        if language not in ('en', 'multi'):
            raise ValueError('Unsupported transcription language.')
        async with self._language_lock:
            if language == self.language:
                return
            previous_language = self.language
            task = self._reconnect_task
            if task and task is not asyncio.current_task() and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self.language = language
            self.is_connected = False
            try:
                await self._connect_once()
            except Exception:
                self.language = previous_language
                try:
                    await self._connect_once()
                except Exception:
                    await self._emit_status('failed', 'Transcription language update failed; reconnect required.')
                raise

    async def flush(self):
        if not self.is_connected or not self.dg_connection or not self._last_audio_at:
            return
        self._flush_complete.clear()
        if await asyncio.wait_for(self.dg_connection.send('{"type":"Finalize"}'), timeout=1) is False:
            raise ConnectionError('Final transcription was rejected')
        await asyncio.wait_for(self._flush_complete.wait(), timeout=2)

    async def _connect_once(self):
        """Create a fresh Deepgram connection and start it (single attempt)."""
        previous = self.dg_connection
        self.dg_connection = self.deepgram.listen.asynclive.v("1")
        connection = self.dg_connection
        for event, callback in ((LiveTranscriptionEvents.Open, self.on_open),
                (LiveTranscriptionEvents.Transcript, self.on_message),
                (LiveTranscriptionEvents.SpeechStarted, self.on_speech_started),
                (LiveTranscriptionEvents.UtteranceEnd, self.on_utterance_end),
                (LiveTranscriptionEvents.Error, self.on_error), (LiveTranscriptionEvents.Close, self.on_close)):
            async def current_callback(*args, _callback=callback, **kwargs):
                if connection is self.dg_connection:
                    await _callback(*args, **kwargs)
            connection.on(event, current_callback)
        if previous is not None:
            try:
                await asyncio.wait_for(previous.finish(), timeout=2)
            except Exception:
                pass  # A failed old socket must not prevent a replacement connection.

        # Generate programming and technical keyterms for better accuracy (List[str])
        programming_keyterms = self.get_programming_keyterms(self.user_languages)
        
        # Optimized settings for real-time transcription with Nova-3
        options = LiveOptions(
            model="nova-3",  # Updated to Nova-3 for better accuracy
            language=self.language,  # P1: 'en' or 'multi' (code-switching)
            smart_format=True,
            encoding="linear16",
            channels=1,
            sample_rate=self.sample_rate,
            diarize=False,
            punctuate=True,
            # Leave room for natural pauses; the session cancels answers when speech resumes.
            utterance_end_ms="1500",
            endpointing=1000,
            # Additional settings
            vad_events=True,
            interim_results=True,
            filler_words=False,  # Suppress filler words for cleaner technical transcripts
            numerals=True,
            multichannel=False,
            alternatives=1,
            # Programming keyterms for better technical accuracy
            keyterm=programming_keyterms,

        )
        
        try:
            if await asyncio.wait_for(self.dg_connection.start(options), timeout=10) is False:
                raise ConnectionError('Transcription connection could not start')
            self.is_connected = True
        except Exception as e:
            self.is_connected = False
            raise  # A2: propagate so start() can retry and eventually surface the error

    async def _reconnect(self):
        """Attempt to reconnect to Deepgram with exponential backoff.

        A1: singleflight - if a reconnect loop is already running, this call
        returns immediately instead of spawning a second racing loop.
        """
        if self.stop_event.is_set():
            return
        existing = self._reconnect_task
        if existing is not None and not existing.done():
            return  # Another reconnect loop is already in flight
        self._reconnect_task = asyncio.current_task()
        try:
            await self._reconnect_loop()
        finally:
            self._reconnect_task = None

    async def _reconnect_loop(self):
        """Reconnect rounds with exponential backoff until success or max attempts.

        All rounds run inside the SAME task (the singleflight holder), so a
        failure never spawns a replacement task and the attempt count stays honest.
        """
        if self.stop_event.is_set():
            return
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            print(f"❌ Deepgram: max reconnect attempts ({self._max_reconnect_attempts}) reached, giving up")
            return

        while not self.stop_event.is_set() and self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_attempts += 1
            delay = self._reconnect_base_delay * (2 ** (self._reconnect_attempts - 1))
            print(f"🔄 Deepgram reconnect attempt {self._reconnect_attempts}/{self._max_reconnect_attempts} in {delay:.1f}s...")
            await self._emit_status("reconnecting", f"Attempt {self._reconnect_attempts}/{self._max_reconnect_attempts}")
            await asyncio.sleep(delay)

            if self.stop_event.is_set():
                return

            try:
                await self.start()  # start() applies its own per-round retry budget
                print(f"✅ Deepgram reconnected after {self._reconnect_attempts} attempt(s)")
                return
            except Exception as e:
                self.is_connected = False
                print(f"❌ Deepgram reconnect failed: {e}")
                app_metrics.inc("deepgram_reconnects")
                # Loop continues to the next backoff round

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            print(f"❌ Deepgram: max reconnect attempts ({self._max_reconnect_attempts}) reached, giving up")
            await self._emit_status("failed", "Max reconnect attempts reached")

    async def _emit_status(self, status: str, detail: str = ""):
        """Emit STT connection health status to transcript callback."""
        if getattr(self, "transcript_callback", None):
            try:
                await self.transcript_callback({
                    "type": "stt_status",
                    "status": status,
                    "detail": detail
                })
            except Exception as e:
                print(f"Failed to emit STT status: {e}")

    async def on_open(self, *args, **kwargs):
        print("🔗 Deepgram connection opened")
        self._reconnect_attempts = 0
        async with self._send_lock:
            self.is_connected = True
            await self._drain_audio()
        if self.is_connected:
            await self._emit_status("connected")

    async def on_speech_started(self, *args, **kwargs):
        if not self.stop_event.is_set():
            result = kwargs.get('speech_started')
            await self.transcript_callback({'type': 'speech_started',
                'timestamp': getattr(result, 'timestamp', None)})

    async def on_utterance_end(self, *args, **kwargs):
        if not self.stop_event.is_set():
            result = kwargs.get('utterance_end')
            await self.transcript_callback({
                'type': 'utterance_end',
                'last_word_end': getattr(result, 'last_word_end', None),
            })

    async def on_message(self, *args, **kwargs):
        if self.stop_event.is_set():
            return
        try:
            result = kwargs['result']
            alternatives = result.channel.alternatives
            if not alternatives:
                return
            alternative = alternatives[0]
            transcript = alternative.transcript.strip()
            words = getattr(alternative, 'words', None) or []
            metadata = {
                'speech_final': bool(getattr(result, 'speech_final', False)),
                'confidence': getattr(alternative, 'confidence', None),
                'last_word_end': getattr(words[-1], 'end', None) if words else None,
            }
            if not transcript:
                if getattr(result, 'from_finalize', False):
                    self._flush_complete.set()
                if metadata['speech_final']:
                    await self.transcript_callback({'type': 'utterance_end', **metadata})
                return
            speaker = getattr(words[0], 'speaker', None) if words else None
            speaker = speaker if speaker is not None else 0
            if getattr(result, 'is_final', False):
                await self.send_final_result(speaker, transcript, **metadata)
            else:
                await self.transcript_callback({
                    'speaker': speaker, 'transcript': transcript,
                    'is_final': False, **metadata,
                })
            if getattr(result, 'from_finalize', False):
                self._flush_complete.set()
        except Exception as error:
            print(f'Transcript processing failed: {error}')

    async def send_final_result(self, speaker, transcript, **metadata):
        """Keep the recognized text and endpoint metadata together."""
        await self.transcript_callback({
            'speaker': speaker, 'transcript': transcript, 'is_final': True, **metadata,
        })

    async def on_error(self, *args, **kwargs):
        if self.stop_event.is_set():
            return
        error = kwargs.get('error', 'unknown')
        print(f"❌ Deepgram error: {error}")
        self.is_connected = False
        await self._emit_status("reconnecting", f"Error: {error}")
        # Trigger auto-reconnect on error (singleflight-guarded in _reconnect)
        asyncio.create_task(self._reconnect())

    async def on_close(self, *args, **kwargs):
        print("🔌 Deepgram connection closed")
        self.is_connected = False
        # Auto-reconnect if we didn't intentionally close (singleflight-guarded,
        # so on_error + on_close firing together only produces one loop)
        if not self.stop_event.is_set():
            print("⚠️ Unexpected Deepgram close, attempting reconnect...")
            await self._emit_status("reconnecting", "Connection closed unexpectedly")
            asyncio.create_task(self._reconnect())

    async def send_audio(self, audio_chunk, source='unknown'):
        """Sends an audio chunk to Deepgram, buffering if temporarily disconnected."""
        if self.stop_event.is_set():
            return
        async with self._send_lock:
            ring = self.audio_ring_buffer
            self._last_audio_at = time.monotonic()
            dropped = ring.maxlen is not None and len(ring) == ring.maxlen
            ring.append(bytes(audio_chunk))
            # Bound by duration as well as frame count (the backup sends larger frames).
            while ring and sum(map(len, ring)) > self.sample_rate * 2 * 4:
                ring.popleft()
                dropped = True
            if dropped and time.monotonic() - self._last_gap_warning > 10:
                self._last_gap_warning = time.monotonic()
                await self._emit_status('gap', 'Audio buffer exceeded four seconds; oldest speech was dropped.')
            await self._drain_audio()

    async def _drain_audio(self):
        ring = self.audio_ring_buffer
        if ring and time.monotonic() - self._last_audio_at > 4:
            ring.clear()
            await self._emit_status('gap', 'Expired audio was dropped after the connection outage.')
        while ring and self.is_connected and self.dg_connection:
            try:
                sent = await asyncio.wait_for(self.dg_connection.send(ring[0]), timeout=2)
                if sent is False:
                    raise ConnectionError('Transcription socket rejected audio')
            except Exception:
                self.is_connected = False
                await self._emit_status('reconnecting', 'Transcription send failed; retaining queued audio.')
                asyncio.create_task(self._reconnect())
                return
            ring.popleft()

    async def clear_audio_buffer(self):
        async with self._send_lock:
            self.audio_ring_buffer.clear()

    async def finish(self):
        """Signals the connection to close and finishes it."""
        print("🛑 Closing Deepgram connection...")
        self.stop_event.set()
        
        # A1: stop any in-flight reconnect loop before closing the socket.
        task = self._reconnect_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._reconnect_task = None

        if self.dg_connection:
            await self.dg_connection.finish()
            print("✅ Deepgram connection closed successfully")
        self.is_connected = False
        await self.clear_audio_buffer()
