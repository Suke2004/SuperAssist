"""Windows output capture, independent of screen sharing and browser throttling."""
import asyncio
import sys
from array import array

try:
    import pyaudiowpatch as pa
except ImportError:
    pa = None


def list_audio_outputs():
    if sys.platform != "win32" or pa is None:
        return {"available": False, "devices": []}
    try:
        with pa.PyAudio() as audio:
            default = audio.get_default_wasapi_loopback()
            devices = [{"name": d["name"], "sample_rate": int(d["defaultSampleRate"])}
                       for d in audio.get_loopback_device_info_generator()]
            return {"available": True, "default": default["name"], "devices": devices}
    except (OSError, ValueError) as error:
        return {"available": False, "devices": [], "error": str(error)}


def mono_pcm(data, channels):
    if channels == 1:
        return data
    samples = array("h", data)
    return array("h", (int(sum(samples[i:i + channels]) / channels)
                       for i in range(0, len(samples), channels))).tobytes()


class NativeLoopback:
    def __init__(self, on_audio, on_status, device_name=""):
        self.on_audio = on_audio
        self.on_status = on_status
        self.device_name = device_name
        self.audio = None
        self.stream = None
        self.sample_rate = None
        self.task = None
        self.stopped = False
        self.paused = False
        self.queue = asyncio.Queue(maxsize=100)  # At most two seconds at 20ms/frame.
        self.dropped = 0

    async def open(self):
        self.loop = asyncio.get_running_loop()
        opening = asyncio.create_task(asyncio.to_thread(self._open))
        try:
            await asyncio.shield(opening)
        except asyncio.CancelledError:
            await opening
            await asyncio.to_thread(self._close)
            raise

    def _open(self):
        if pa is None or sys.platform != "win32":
            raise RuntimeError("Windows audio capture is unavailable. Select browser audio capture.")
        self.audio = pa.PyAudio()
        try:
            if self.device_name:
                device = next((d for d in self.audio.get_loopback_device_info_generator()
                               if d["name"] == self.device_name), None)
                if device is None:
                    raise RuntimeError("The selected output is unavailable. Reconnect it or choose another output.")
            else:
                device = self.audio.get_default_wasapi_loopback()
            rate = int(device["defaultSampleRate"])
            if self.sample_rate is not None and rate != self.sample_rate:
                raise RuntimeError("Output sample rate changed. Restart the session to use the new rate.")
            self.sample_rate = rate
            self.channels = int(device["maxInputChannels"])
            self.name = device["name"]
            self.stream = self.audio.open(format=pa.paInt16, channels=self.channels,
                rate=rate, input=True, input_device_index=device["index"],
                frames_per_buffer=max(1, rate // 50), stream_callback=self._callback,
                start=False)
        except Exception:
            self._close()
            raise

    def _callback(self, data, frame_count, time_info, status):
        if self.stopped:
            return None, pa.paComplete
        if self.paused:
            return None, pa.paContinue
        try:
            self.loop.call_soon_threadsafe(self._enqueue, data, bool(status & pa.paInputOverflow))
        except RuntimeError:
            self.stopped = True
            return None, pa.paComplete
        return None, pa.paContinue

    def _enqueue(self, data, overflow=False):
        if self.stopped or self.paused:
            return
        if self.queue.full():
            self.queue.get_nowait()
            self.dropped += 1
        if overflow:
            self.dropped += 1
        self.queue.put_nowait(data)

    async def start(self):
        await asyncio.to_thread(self.stream.start_stream)
        self.task = asyncio.create_task(self._consume())
        await self.on_status("connected", self.name)

    async def _consume(self):
        while not self.stopped:
            try:
                if not self.stream.is_active():
                    raise OSError("Output audio device stopped")
                try:
                    data = await asyncio.wait_for(self.queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    # WASAPI can omit silent frames; STT still needs silence to end an utterance.
                    if not self.paused:
                        await self.on_audio(bytes(self.sample_rate))  # 500ms of mono Linear16.
                    continue
                await self.on_audio(mono_pcm(data, self.channels))
                if self.dropped:
                    lost, self.dropped = self.dropped, 0
                    await self.on_status("gap", f"Audio overrun: {lost} frame(s) lost. Check network and system load.")
            except (OSError, RuntimeError) as error:
                await self.on_status("reconnecting", str(error))
                await asyncio.to_thread(self._close)
                for attempt in range(1, 4):
                    await asyncio.sleep(attempt)
                    try:
                        await self.open()
                        await asyncio.to_thread(self.stream.start_stream)
                        while not self.queue.empty():
                            self.queue.get_nowait()
                        await self.on_status("connected", self.name)
                        break
                    except Exception as reopen_error:
                        await asyncio.to_thread(self._close)
                        if attempt == 3:
                            await self.on_status("failed", str(reopen_error))
                            return

    def _close(self):
        try:
            if self.stream is not None:
                self.stream.close()
        finally:
            self.stream = None
            if self.audio is not None:
                self.audio.terminate()
                self.audio = None

    async def finish(self):
        self.stopped = True
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        await asyncio.to_thread(self._close)
        while not self.queue.empty():
            self.queue.get_nowait()
