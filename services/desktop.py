"""Native desktop bridge; screenshots are requested explicitly and kept in memory."""
import base64
import subprocess
import sys
import tempfile
from pathlib import Path
from threading import Event, current_thread, main_thread
from urllib.parse import urlsplit


def create_qt_dispatcher(native_window):
    from qtpy.QtCore import QObject, Signal, Slot, Qt, QThread

    class Dispatcher(QObject):
        requested = Signal(object)

        def __init__(self):
            super().__init__()
            self.requested.connect(self.run, Qt.ConnectionType.QueuedConnection)
            self.moveToThread(native_window.thread())

        @Slot(object)
        def run(self, callback):
            callback()

        def invoke(self, callback):
            if QThread.currentThread() == self.thread():
                return callback()
            return _wait_for_ui(self.requested.emit, callback)

    return Dispatcher()


def _wait_for_ui(schedule, callback):
    done, result = Event(), []

    def run():
        try:
            result.append((True, callback()))
        except Exception as error:
            result.append((False, error))
        finally:
            done.set()

    schedule(run)
    if not done.wait(5):
        raise RuntimeError('Desktop window did not respond.')
    success, value = result[0]
    if not success:
        raise value
    return value


def call_on_macos_ui(callback):
    if current_thread() is main_thread():
        return callback()
    from PyObjCTools.AppHelper import callAfter
    return _wait_for_ui(callAfter, callback)


class DesktopAPI:
    def __init__(self):
        self._window = None
        self._origin = None

    def _is_local(self):
        if self._window is None or self._origin is None:
            return False
        try:
            url = urlsplit(self._window.get_current_url())
            return (url.scheme, url.hostname, url.port) == self._origin
        except Exception:
            return False

    def capture_screenshot(self):
        try:
            if not self._is_local():
                raise RuntimeError('Desktop capture is available only inside the local app.')
            if sys.platform == 'darwin':
                from Quartz import CGPreflightScreenCaptureAccess, CGRequestScreenCaptureAccess
                if not CGPreflightScreenCaptureAccess():
                    CGRequestScreenCaptureAccess()
                    raise RuntimeError('Grant Screen Recording permission to Python/VeyraCue, then restart the app.')
                with tempfile.TemporaryDirectory(prefix='veyracue-') as folder:
                    path = Path(folder) / 'screen.png'
                    subprocess.run(['/usr/sbin/screencapture', '-x', '-m', '-t', 'png', str(path)],
                                   check=True, timeout=10, capture_output=True)
                    data = path.read_bytes()
            elif sys.platform in ('win32', 'linux'):
                import os
                if sys.platform == 'linux' and os.environ.get('XDG_SESSION_TYPE') == 'wayland':
                    return {'upload_required': True}
                import mss
                import mss.tools
                with mss.mss() as capture:
                    image = capture.grab(capture.monitors[1])
                    # The browser encodes the final JPEG; keep this lossless intermediate fast.
                    data = mss.tools.to_png(image.rgb, image.size, level=1)
            else:
                raise RuntimeError('Native screen capture is unavailable on this platform.')
            return {'data_url': 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')}
        except Exception as error:
            return {'error': str(error)}

    def shortcut(self, key):
        import window_manager
        if self._is_local() and isinstance(key, int) and not isinstance(key, bool):
            callback = window_manager.window_manager.shortcut_bindings.get(key)
            if callback:
                callback()
                return True
        return False

    def capabilities(self):
        import window_manager
        manager = window_manager.window_manager
        return {'platform': sys.platform, 'global_hotkeys': manager.global_hotkeys_active,
                'registered_hotkeys': sorted(manager.registered_hotkeys)}

    def stop_scrolling(self):
        import window_manager
        if self._is_local():
            window_manager.window_manager.scrolling_up = False
            window_manager.window_manager.scrolling_down = False
