"""CoreAudio routed inputs and PulseAudio/PipeWire playback monitors."""
import sys
from threading import Event, Thread

from services.native_audio import NativeLoopback


def _devices():
    import soundcard as sc
    inputs = sc.all_microphones(include_loopback=sys.platform == 'linux')
    if sys.platform == 'linux':
        outputs = [d for d in inputs if d.isloopback]
    else:
        outputs = [d for d in inputs if any(term in d.name.lower()
                   for term in ('blackhole', 'soundflower', 'loopback', 'vb-cable'))]
    microphones = [d for d in inputs if d not in outputs]
    return sc, outputs, microphones


def list_devices():
    info = {'available': False, 'devices': [], 'microphones': [],
            'native_microphone': True, 'platform': sys.platform,
            'label': 'macOS routed audio' if sys.platform == 'darwin' else 'Linux system audio'}
    try:
        sc, outputs, microphones = _devices()
        default = outputs[0] if outputs else None
        if sys.platform == 'linux' and outputs:
            speaker_id = str(sc.default_speaker().id)
            default = next((d for d in outputs if str(d.id) == speaker_id + '.monitor'), default)
        info.update(available=bool(outputs),
                    devices=[{'id': str(d.id), 'name': d.name, 'sample_rate': 48000} for d in outputs],
                    microphones=[{'id': str(d.id), 'name': d.name} for d in microphones],
                    default=default.name if default else '', default_id=str(default.id) if default else '')
        if not outputs:
            info['error'] = ('Install BlackHole 2ch and route the meeting to a Multi-Output Device containing '
                             'BlackHole and your headphones. See CROSS_PLATFORM.md.' if sys.platform == 'darwin'
                             else 'No playback monitor found. Start PulseAudio or PipeWire with pipewire-pulse.')
    except Exception as error:
        info['error'] = f'Native audio unavailable: {error}'
    return info


class PortableCapture(NativeLoopback):
    def __init__(self, on_audio, on_status, device_name='', microphone=False):
        super().__init__(on_audio, on_status, device_name)
        self.microphone = microphone

    def _open(self):
        sc, outputs, microphones = _devices()
        devices = microphones if self.microphone else outputs
        selected = self.device_name
        if not selected:
            if self.microphone:
                selected = str(sc.default_microphone().id)
            else:
                selected = list_devices().get('default_id', '')
        device = next((d for d in devices if selected in (str(d.id), d.name)), None)
        if device is None:
            raise RuntimeError('The selected microphone or meeting audio device is unavailable. Check audio routing and restart.')
        # SoundCard performs platform resampling; the existing STT transport stays Linear16/48kHz.
        self.sample_rate, self.channels, self.name = 48000, 1, device.name
        self.device_name = str(device.id)
        self.stream = _RecorderStream(self, device)


class _RecorderStream:
    """Adapt a blocking recorder to the existing bounded queue and device-retry loop."""
    def __init__(self, owner, device):
        self.owner, self.device = owner, device
        self.stop = Event()
        self.ready = Event()
        self.error = None
        self.thread = None

    def start_stream(self):
        self.thread = Thread(target=self._read, daemon=True)
        self.thread.start()
        if not self.ready.wait(10):
            self.stop.set()
            raise RuntimeError('Audio permission or device startup timed out. Check system microphone permission.')
        if self.error:
            raise RuntimeError(str(self.error))

    def _read(self):
        try:
            import numpy as np
            with self.device.recorder(samplerate=48000, blocksize=960) as recorder:
                self.ready.set()
                while not self.stop.is_set():
                    frames = recorder.record(numframes=960)
                    if self.stop.is_set() or self.owner.paused:
                        continue
                    mono = np.nan_to_num(frames).mean(axis=1)
                    pcm = (np.clip(mono, -1, 1) * 32767).astype('<i2').tobytes()
                    self.owner.loop.call_soon_threadsafe(self.owner._enqueue, pcm)
        except Exception as error:
            self.error = error
        finally:
            self.ready.set()

    def is_active(self):
        if self.error:
            raise RuntimeError(str(self.error))
        return self.thread is not None and self.thread.is_alive() and not self.stop.is_set()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2)
            # shortcut: a stalled OS recorder can outlive shutdown; use a subprocess if a driver cannot unblock.
            if self.thread.is_alive():
                raise RuntimeError('Audio driver did not stop; restart the app before starting another session.')
