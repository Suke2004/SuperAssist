"""Platform routing and desktop controls without cloud calls or real recording."""
import asyncio
import base64
import sys
import os
import shutil
import subprocess
import time
from array import array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import main
import window_manager
from api import session_manager
from services import desktop, portable_audio


@pytest.mark.parametrize('platform', ['darwin', 'linux'])
def test_outputs_exclude_physical_microphones_and_keep_ids(monkeypatch, platform):
    mic = SimpleNamespace(id='mic', name='Built-in microphone', isloopback=False)
    output = SimpleNamespace(id='headphones.monitor' if platform == 'linux' else '42',
                             name='Monitor of headphones' if platform == 'linux' else 'BlackHole 2ch',
                             isloopback=platform == 'linux')
    sc = MagicMock()
    sc.all_microphones.return_value = [mic, output]
    sc.default_speaker.return_value = SimpleNamespace(id='headphones')
    monkeypatch.setitem(sys.modules, 'soundcard', sc)
    monkeypatch.setattr(portable_audio, 'sys', SimpleNamespace(platform=platform))
    info = portable_audio.list_devices()
    assert info['available'] and info['default_id'] == output.id
    assert [d['id'] for d in info['microphones']] == ['mic']
    capture = portable_audio.PortableCapture(AsyncMock(), AsyncMock(), 'mic')
    with pytest.raises(RuntimeError, match='unavailable'):
        capture._open()
    capture.device_name = output.id
    capture._open()
    assert capture.sample_rate == 48000 and capture.channels == 1


def test_mac_without_routed_device_does_not_claim_to_capture_headphones(monkeypatch):
    sc = MagicMock()
    sc.all_microphones.return_value = [SimpleNamespace(id='mic', name='MacBook microphone')]
    monkeypatch.setitem(sys.modules, 'soundcard', sc)
    monkeypatch.setattr(portable_audio, 'sys', SimpleNamespace(platform='darwin'))
    info = portable_audio.list_devices()
    assert not info['available'] and not info['devices']
    assert 'BlackHole' in info['error']


def test_portable_pcm_downmix_clips_and_preserves_quiet_speech():
    np = pytest.importorskip('numpy')
    owner = portable_audio.PortableCapture(AsyncMock(), AsyncMock())
    owner._enqueue = MagicMock()
    owner.loop = SimpleNamespace(call_soon_threadsafe=lambda fn, pcm: fn(pcm))
    device = MagicMock()
    stream = portable_audio._RecorderStream(owner, device)
    frames = np.array([[1, 1], [-1, -1], [0.001, 0.001], [1, -1], [2, 2]], dtype='float32')

    # End the worker on its next check, after the first PCM block is delivered.
    recorder = device.recorder.return_value.__enter__.return_value
    recorder.record.side_effect = [frames]
    owner.loop.call_soon_threadsafe = lambda fn, pcm: (fn(pcm), stream.stop.set())
    stream._read()
    values = array('h', owner._enqueue.call_args.args[0]).tolist()
    assert values == [32767, -32767, 32, 0, 32767]
    recorder.record.assert_called_once_with(numframes=960)
    device.recorder.assert_called_once_with(samplerate=48000, blocksize=960)


def test_recorder_permission_failure_is_visible_and_closes_thread():
    pytest.importorskip('numpy')
    owner = portable_audio.PortableCapture(AsyncMock(), AsyncMock())
    device = MagicMock()
    device.recorder.side_effect = PermissionError('microphone permission denied')
    stream = portable_audio._RecorderStream(owner, device)
    with pytest.raises(RuntimeError, match='permission denied'):
        stream.start_stream()
    stream.close()
    assert not stream.thread.is_alive()


@pytest.mark.asyncio
@pytest.mark.parametrize('platform', ['darwin', 'linux'])
async def test_unix_session_uses_two_independent_native_sources(monkeypatch, platform):
    session = session_manager.InterviewSession('portable')
    session.audio_capture_mode, session.audio_input = 'native', 'microphone-id'
    captures = [MagicMock(open=AsyncMock(), sample_rate=48000) for _ in range(2)]
    factory = MagicMock(side_effect=captures)
    managers = [MagicMock(start=AsyncMock(), send_audio=AsyncMock(), finish=AsyncMock()) for _ in range(2)]
    monkeypatch.setattr(session_manager, 'sys', SimpleNamespace(platform=platform))
    monkeypatch.setattr(portable_audio, 'PortableCapture', factory)
    monkeypatch.setattr(session_manager, 'DeepgramManager', MagicMock(side_effect=managers))
    monkeypatch.setattr(session_manager, 'MultiLLMManager', MagicMock())
    monkeypatch.setattr(session_manager.VisionService, 'set_context_manager', MagicMock())
    monkeypatch.setattr(session_manager.VisionService, 'load_vision_providers', MagicMock())
    await session.initialize_managers({}, None, None, None, {})
    assert factory.call_args_list[1].kwargs == {'microphone': True}
    assert factory.call_args_list[1].args[2] == 'microphone-id'
    await session._send_native_audio(b'\x01\x00')
    await session._send_native_microphone_audio(b'\x02\x00')
    managers[0].send_audio.assert_awaited_once_with(b'\x01\x00')
    managers[1].send_audio.assert_awaited_once_with(b'\x02\x00')
    session.state['is_muted'] = True
    await session._send_native_microphone_audio(b'private')
    assert managers[1].send_audio.await_count == 1
    session.state['is_universally_muted'] = True
    await session._send_native_audio(b'private')
    assert managers[0].send_audio.await_count == 1


@pytest.mark.asyncio
async def test_unix_pause_clears_both_capture_queues_and_cleanup_closes_both():
    session = session_manager.InterviewSession('portable-pause')
    captures = [MagicMock(queue=asyncio.Queue(), finish=AsyncMock()) for _ in range(2)]
    session.native_audio, session.native_microphone = captures
    session._send_json = AsyncMock()
    for capture in captures:
        capture.queue.put_nowait(b'private')
    await session.handle_config_update({'isUniversallyMuted': True})
    assert all(capture.paused and capture.queue.empty() for capture in captures)
    await session.handle_config_update({'is_muted': True})
    await session.handle_config_update({'isUniversallyMuted': False})
    assert not captures[0].paused and captures[1].paused
    await session.cleanup()
    for capture in captures:
        capture.finish.assert_awaited_once()


@pytest.mark.parametrize('platform,gui', [('win32', 'edgechromium'), ('darwin', None), ('linux', 'qt')])
def test_renderer_selection_preserves_windows(monkeypatch, platform, gui):
    start = MagicMock()
    monkeypatch.setattr(main, 'sys', SimpleNamespace(platform=platform))
    monkeypatch.setattr(main, 'setup_webview_window', MagicMock())
    monkeypatch.setattr(main, 'asyncio_service_thread', MagicMock())
    monkeypatch.setattr(main.webview, 'start', start)
    monkeypatch.setattr(main.app_metrics, 'load_from_disk', MagicMock())
    monkeypatch.setattr(main.window_manager.window_manager, 'stop_hotkey_listener', MagicMock())
    main.main()
    assert start.call_args.kwargs['gui'] == gui


@pytest.mark.parametrize('mac', [False, True])
def test_unix_hotkeys_are_exact_and_mac_option_symbols_use_physical_keys(monkeypatch, mac):
    if window_manager.keyboard is None:
        pytest.skip('pynput backend unavailable; focused shortcut tests cover this case')
    keyboard = window_manager.keyboard
    manager = window_manager.WindowManager()
    manager.is_windows, manager.is_macos, manager.is_linux = False, mac, not mac
    monkeypatch.setenv('XDG_SESSION_TYPE', 'x11')
    monkeypatch.setattr(manager, '_check_macos_accessibility_permission', lambda: True)
    monkeypatch.setattr(window_manager.webview, 'windows', [])
    callbacks = {}
    listener = MagicMock(canonical=lambda key: keyboard.KeyCode.from_char(key.char.lower())
                         if getattr(key, 'char', None) else key)
    key = SimpleNamespace(char='©', vk=5) if mac else keyboard.KeyCode.from_char('g')
    if mac:
        key = keyboard.KeyCode.from_char('©', vk=5)

    def join():
        modifiers = [keyboard.Key.alt] if mac else [keyboard.Key.ctrl, keyboard.Key.shift, keyboard.Key.cmd]
        for modifier in modifiers:
            callbacks['on_press'](modifier)
        callbacks['on_press'](key)
        callbacks['on_press'](key)
        callbacks['on_release'](key)
        extra = keyboard.Key.ctrl if mac else keyboard.Key.alt
        callbacks['on_press'](extra)
        callbacks['on_press'](key)
        callbacks['on_release'](key)
        callbacks['on_release'](extra)
        if not mac:
            callbacks['on_press'](keyboard.Key.right.value)
            callbacks['on_release'](keyboard.Key.right.value)

    listener.join.side_effect = join
    monkeypatch.setattr(keyboard, 'Listener', lambda **kwargs: (callbacks.update(kwargs), listener)[1])
    action = MagicMock()
    move = MagicMock()
    manager._run_unix_hotkeys({ord('G'): action, 0x27: move})
    action.assert_called_once()
    if not mac:
        move.assert_called_once()
    assert not manager.global_hotkeys_active


def test_wayland_leaves_global_shortcuts_off(monkeypatch):
    manager = window_manager.WindowManager()
    manager.is_windows, manager.is_macos, manager.is_linux = False, False, True
    monkeypatch.setenv('XDG_SESSION_TYPE', 'wayland')
    listener = MagicMock()
    if window_manager.keyboard is not None:
        monkeypatch.setattr(window_manager.keyboard, 'Listener', listener)
    manager._run_unix_hotkeys({})
    listener.assert_not_called()
    assert not manager.global_hotkeys_active


def test_mac_screenshot_is_temporary_and_respects_permission(monkeypatch):
    monkeypatch.setattr(desktop.DesktopAPI, '_is_local', lambda self: True)
    monkeypatch.setattr(desktop, 'sys', SimpleNamespace(platform='darwin'))
    quartz = SimpleNamespace(CGPreflightScreenCaptureAccess=lambda: True, CGRequestScreenCaptureAccess=MagicMock())
    monkeypatch.setitem(sys.modules, 'Quartz', quartz)
    paths = []

    def capture(args, **kwargs):
        path = Path(args[-1])
        paths.append(path)
        path.write_bytes(b'png-test-data')

    monkeypatch.setattr(desktop.subprocess, 'run', capture)
    result = desktop.DesktopAPI().capture_screenshot()
    assert base64.b64decode(result['data_url'].split(',')[1]) == b'png-test-data'
    assert not paths[0].exists()
    quartz.CGPreflightScreenCaptureAccess = lambda: False
    assert 'permission' in desktop.DesktopAPI().capture_screenshot()['error']
    quartz.CGRequestScreenCaptureAccess.assert_called_once()


def test_wayland_screenshot_uses_explicit_upload(monkeypatch):
    monkeypatch.setattr(desktop.DesktopAPI, '_is_local', lambda self: True)
    monkeypatch.setattr(desktop, 'sys', SimpleNamespace(platform='linux'))
    monkeypatch.setenv('XDG_SESSION_TYPE', 'wayland')
    assert desktop.DesktopAPI().capture_screenshot() == {'upload_required': True}


def test_native_bridge_rejects_remote_pages_and_unbound_calls():
    api = desktop.DesktopAPI()
    assert not api.shortcut(ord('O'))
    api._window = MagicMock(get_current_url=MagicMock(return_value='https://example.com/'))
    api._origin = ('http', '127.0.0.1', 8000)
    assert 'local app' in api.capture_screenshot()['error']
    api._window.get_current_url.return_value = 'http://127.0.0.1:8000/?view=live'
    assert api._is_local()


def test_linux_reshowing_window_does_not_duplicate_setup_or_listeners(monkeypatch):
    window = MagicMock()
    shown_event = window.events.shown
    manager = MagicMock()
    monkeypatch.setattr(main, 'sys', SimpleNamespace(platform='linux'))
    monkeypatch.setattr(main.webview, 'create_window', MagicMock(return_value=window))
    monkeypatch.setattr(main.window_manager, 'window_manager', manager)
    monkeypatch.setattr(main.window_manager, 'find_aura_window', lambda: True)
    monkeypatch.setattr(main.window_manager, 'set_app_always_on_top', lambda enabled: True)
    monkeypatch.setattr(main.window_manager, 'apply_capture_protection', lambda window: False)
    monkeypatch.setattr(main.time, 'sleep', lambda seconds: None)
    main.setup_webview_window()
    shown = shown_event.__iadd__.call_args.args[0]
    shown()
    shown()
    manager.set_native_window.assert_called_once()
    manager.start_hotkey_listener.assert_called_once()


@pytest.mark.asyncio
async def test_denied_native_microphone_does_not_stop_meeting_capture(monkeypatch):
    session = session_manager.InterviewSession('mic-denied')
    session.native_audio = MagicMock(start=AsyncMock(), finish=AsyncMock())
    microphone = MagicMock(start=AsyncMock(side_effect=PermissionError('denied')), finish=AsyncMock())
    microphone_stt = MagicMock(finish=AsyncMock())
    session.native_microphone, session.mic_stt_manager = microphone, microphone_stt
    session.initialize_managers = AsyncMock()
    session._send_json = AsyncMock(return_value=True)
    session._report_provider_health = AsyncMock()
    monkeypatch.setattr(window_manager.window_manager, 'enable_proctoring_stealth_mode', MagicMock())
    await session.handle_start_interview({'audioCaptureMode': 'native'})
    session.native_audio.start.assert_awaited_once()
    microphone.finish.assert_awaited_once()
    microphone_stt.finish.assert_awaited_once()
    assert session.native_microphone is None and session.mic_stt_manager is None
    session._send_json.assert_any_await('interview_started', {'audio_capture_mode': 'native'})
    await session.cleanup()


@pytest.mark.skipif(os.name != 'posix', reason='Native Unix shell launcher')
def test_unix_launcher_uses_own_directory_and_preserves_windows_venv(tmp_path):
    folder = tmp_path / 'VeyraCue with spaces'
    folder.mkdir()
    shutil.copy2(Path(main.__file__).with_name('run.sh'), folder / 'run.sh')
    shutil.copy2(Path(main.__file__).with_name('silent_run.sh'), folder / 'silent_run.sh')
    uv = folder / 'tools' / 'uv'
    uv.parent.mkdir()
    uv.write_text('#!/usr/bin/env bash\nprintf "uv-called %s\\n" "$*"\nexit "${TEST_UV_EXIT:-0}"\n')
    uv.chmod(0o755)
    python = folder / '.venv' / 'bin' / 'python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/usr/bin/env bash\nif [[ "$1" == -c ]]; then exit 0; fi\nprintf "desktop-started %s\\n%s\\n" "$1" "$PWD"\n')
    python.chmod(0o755)
    windows_config = folder / 'venv' / 'pyvenv.cfg'
    windows_config.parent.mkdir()
    windows_config.write_text('existing Windows environment')
    env = {**os.environ, 'DISPLAY': ':99', 'PATH': f'{uv.parent}{os.pathsep}{os.environ["PATH"]}'}
    launched = subprocess.run(['bash', str(folder / 'run.sh')], cwd=tmp_path,
                              env=env, capture_output=True, text=True, timeout=10)
    assert launched.returncode == 0, launched.stderr
    assert 'desktop-started main.py' in launched.stdout and str(folder) in launched.stdout
    assert 'sync --locked --no-dev --managed-python --python 3.12' in launched.stdout
    launched = subprocess.run(['bash', str(folder / 'run.sh'), '--update'], cwd=tmp_path,
                              env=env, capture_output=True, text=True, timeout=10)
    assert launched.returncode == 0 and '--reinstall' in launched.stdout
    launched = subprocess.run(['bash', str(folder / 'silent_run.sh')], cwd=tmp_path,
                              env=env, capture_output=True, text=True, timeout=10)
    assert launched.returncode == 0 and not launched.stdout
    log = folder / 'output' / 'desktop-launch.log'
    deadline = time.monotonic() + 5
    while (not log.exists() or 'desktop-started main.py' not in log.read_text()) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert 'desktop-started main.py' in log.read_text()
    assert windows_config.read_text() == 'existing Windows environment'
    launched = subprocess.run(['bash', str(folder / 'run.sh')], cwd=tmp_path,
                              env={**env, 'TEST_UV_EXIT': '7'}, capture_output=True, text=True, timeout=10)
    assert launched.returncode == 7 and 'desktop-started' not in launched.stdout
    if sys.platform == 'linux':
        launched = subprocess.run(['bash', str(folder / 'run.sh')], cwd=tmp_path,
                                  env={**env, 'DISPLAY': '', 'WAYLAND_DISPLAY': ''}, capture_output=True, text=True, timeout=10)
        assert launched.returncode != 0 and 'graphical Linux desktop' in launched.stderr
