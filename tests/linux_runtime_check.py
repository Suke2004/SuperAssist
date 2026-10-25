"""Run on a Linux test desktop with a PulseAudio sink named veyracue_test."""
import asyncio
import base64
import json
import sys
import time
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import soundcard as sc
import main
from services.desktop import DesktopAPI
from services.portable_audio import PortableCapture, list_devices

async def check_audio():
    peak = 0

    async def received(pcm):
        nonlocal peak
        peak = max(peak, max(map(abs, array('h', pcm)), default=0))

    async def status(*args):
        pass

    info = list_devices()
    device = next(d for d in info['devices'] if 'veyracue_test' in d['id'])
    capture = PortableCapture(received, status, device['id'])
    try:
        await capture.open()
        await capture.start()
        signal = (0.3 * np.sin(2 * np.pi * 440 * np.arange(24000) / 48000)).astype('float32')
        await asyncio.to_thread(sc.get_speaker('veyracue_test').play, signal, samplerate=48000)
        await asyncio.sleep(0.3)
        assert peak > 1000, f'Playback monitor did not capture signal: {peak}'
        return {'playback_peak': peak, 'sample_rate': capture.sample_rate}
    finally:
        await capture.finish()


result = asyncio.run(check_audio())
main.app_metrics.save_to_disk = lambda: None  # Keep the runtime check out of the user's metrics file.
main.asyncio_service_thread.start()
window = main.setup_webview_window()


def check_desktop():
    try:
        assert window.events.loaded.wait(30), 'Desktop page did not load'
        manager = main.window_manager.window_manager
        deadline = time.monotonic() + 10
        while not manager.global_hotkeys_active and time.monotonic() < deadline:
            time.sleep(0.1)
        assert manager.native_window is not None and manager.global_hotkeys_active
        assert manager.set_always_on_top(True)
        assert manager.set_transparency(0.75)
        assert manager.move_window(20, 20)
        from pynput import keyboard
        original_x = manager._linux_call(lambda: manager.native_window.pos().x())
        controller = keyboard.Controller()
        for key in (keyboard.Key.ctrl, keyboard.Key.shift, keyboard.Key.cmd):
            controller.press(key)
        controller.press(keyboard.Key.right)
        controller.release(keyboard.Key.right)
        for key in (keyboard.Key.cmd, keyboard.Key.shift, keyboard.Key.ctrl):
            controller.release(key)
        deadline = time.monotonic() + 5
        while manager._linux_call(lambda: manager.native_window.pos().x()) == original_x and time.monotonic() < deadline:
            time.sleep(0.1)
        assert manager._linux_call(lambda: manager.native_window.pos().x()) == original_x + 20, 'Global shortcut did not dispatch exactly once'
        manager.set_ghost_mode(True)
        assert manager.is_ghost_mode
        manager.set_ghost_mode(False)
        assert not manager.is_ghost_mode
        manager.toggle_visibility()
        assert not manager._linux_call(lambda: manager.native_window.isVisible())
        manager.toggle_visibility()
        assert manager._linux_call(lambda: manager.native_window.isVisible())
        assert 'VeyraCue' in window.evaluate_js('document.title')
        captured = window._js_api.capture_screenshot()
        assert base64.b64decode(captured['data_url'].split(',')[1]).startswith(b'\x89PNG')
        window.evaluate_js('window.screenshotService.captureScreenshot().then(ok => window.testNativeScreenshot = ok)')
        deadline = time.monotonic() + 10
        while not window.evaluate_js('window.testNativeScreenshot === true') and time.monotonic() < deadline:
            time.sleep(0.1)
        assert window.evaluate_js('window.screenshotService.screenshotQueue.length') == 1
        result.update(desktop_loaded=True, window_controls=True, global_hotkeys=True, global_shortcut_dispatch=True, native_screenshot=True)
    except Exception as error:
        result['error'] = str(error)
    finally:
        Path('output').mkdir(exist_ok=True)
        Path('output/linux-runtime-check.json').write_text(json.dumps(result), encoding='utf-8')
        window.destroy()


try:
    main.webview.start(check_desktop, gui='qt')
finally:
    main.window_manager.window_manager.stop_hotkey_listener()
    main.asyncio_service_thread.stop()
print(json.dumps(result))
if result.get('error'):
    raise SystemExit(1)
