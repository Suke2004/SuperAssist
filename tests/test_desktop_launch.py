"""Desktop startup and the hidden launcher, without opening an interview session."""
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import main
from api import websocket as websocket_api
from services import native_audio


def test_desktop_window_starts_on_top(monkeypatch):
    create = MagicMock()
    monkeypatch.setattr(main.webview, 'create_window', create)
    main.setup_webview_window()
    assert create.call_args.args[0] == main.APP_WINDOW_TITLE
    assert create.call_args.kwargs['on_top'] is True
    assert create.call_args.kwargs['background_color'] == '#101318'
    assert create.call_args.args[1].startswith('http://127.0.0.1:')


def test_interview_can_remain_interactive_and_click_through_is_explicit():
    manager = main.window_manager.WindowManager()
    manager.hwnd = 1
    manager.native_window = MagicMock()
    manager.set_ghost_mode = MagicMock()
    manager.hide_from_taskbar = MagicMock()
    manager.set_always_on_top = MagicMock()
    manager.set_transparency = MagicMock()
    assert manager.enable_proctoring_stealth_mode(click_through=False)
    manager.set_ghost_mode.assert_called_with(False)
    assert manager.enable_proctoring_stealth_mode()
    manager.set_ghost_mode.assert_called_with(True)


def test_new_desktop_name_preserves_configured_title(monkeypatch):
    assert main._default_title == 'VeyraCue'
    manager = main.window_manager.window_manager
    find = MagicMock(return_value=123)
    monkeypatch.setattr(main.window_manager, 'IS_MACOS', False)
    monkeypatch.setattr(manager, 'find_window_by_title', find)
    monkeypatch.delenv('WINDOW_TITLE', raising=False)
    assert main.window_manager.find_aura_window()
    find.assert_called_with('VeyraCue')
    monkeypatch.setenv('WINDOW_TITLE', 'My interview overlay')
    assert main.window_manager.find_aura_window()
    find.assert_called_with('My interview overlay')


@pytest.mark.parametrize('failed', [False, True])
def test_desktop_start_selects_webview2_and_reports_fatal_errors(monkeypatch, failed):
    services = MagicMock()
    start = MagicMock(side_effect=RuntimeError('WebView2 unavailable') if failed else None)
    monkeypatch.setattr(main, 'asyncio_service_thread', services)
    monkeypatch.setattr(main, 'setup_webview_window', MagicMock())
    monkeypatch.setattr(main.webview, 'start', start)
    monkeypatch.setattr(main.window_manager.window_manager, 'stop_hotkey_listener', MagicMock())
    monkeypatch.setattr(main.app_metrics, 'load_from_disk', MagicMock())
    if failed:
        with pytest.raises(RuntimeError, match='WebView2 unavailable'):
            main.main()
    else:
        main.main()
    assert start.call_args.kwargs['gui'] == ('edgechromium' if sys.platform == 'win32' else 'qt' if sys.platform == 'linux' else None)
    services.stop.assert_called_once()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows Script Host launcher')
def test_silent_launcher_uses_own_folder_and_writes_log(tmp_path):
    folder = tmp_path / 'Desktop & interview app'
    folder.mkdir()
    shutil.copy2(Path(main.__file__).with_name('silent_run.vbs'), folder / 'silent_run.vbs')
    (folder / 'run.bat').write_text('@echo off\necho desktop-started %1\necho "%CD%"\nexit /b 0\n')
    launched = subprocess.run(['cscript.exe', '//nologo', str(folder / 'silent_run.vbs')],
                              cwd=tmp_path, capture_output=True, timeout=15)
    assert launched.returncode == 0, launched.stderr.decode(errors='replace')
    log = (folder / 'output' / 'desktop-launch.log').read_text()
    assert 'desktop-started --silent' in log
    assert str(folder) in log


@pytest.mark.asyncio
async def test_desktop_shutdown_closes_every_session_even_when_one_fails(monkeypatch):
    first = MagicMock(cleanup=AsyncMock(side_effect=OSError('device removed')))
    second = MagicMock(cleanup=AsyncMock())
    manager = MagicMock(active_sessions={'first': first, 'second': second})
    monkeypatch.setattr(main, 'session_manager', manager)
    monkeypatch.setattr(main.command_monitor, 'stop_monitoring', AsyncMock())
    monkeypatch.setattr(main.uvicorn_server, 'stop', AsyncMock())
    monkeypatch.setattr(main.app_metrics, 'save_to_disk', MagicMock())
    await main.AsyncioServiceThread()._cleanup_async_services()
    first.cleanup.assert_awaited_once()
    second.cleanup.assert_awaited_once()
    assert [call.args[0] for call in manager.remove_session.call_args_list] == ['first', 'second']


def test_audio_callback_stops_when_its_event_loop_is_closed(monkeypatch):
    monkeypatch.setattr(native_audio, 'pa', MagicMock(paComplete=1, paContinue=0, paInputOverflow=2))
    capture = native_audio.NativeLoopback(AsyncMock(), AsyncMock())
    capture.loop = MagicMock()
    capture.loop.call_soon_threadsafe.side_effect = RuntimeError('Event loop is closed')
    assert capture._callback(b'pcm', 1, {}, 0) == (None, 1)
    assert capture.stopped


@pytest.mark.asyncio
async def test_desktop_socket_disconnect_is_handled_without_receiving_twice(monkeypatch):
    socket = MagicMock(headers={'x-app-token': websocket_api.APP_SESSION_TOKEN}, accept=AsyncMock(), receive=AsyncMock(return_value={
        'type': 'websocket.disconnect', 'code': 1000}))
    session = MagicMock(session_id='desktop-test', _send_json=AsyncMock())
    manager = MagicMock()
    manager.create_session.return_value = session
    monkeypatch.setattr(websocket_api, 'session_manager', manager)
    await websocket_api.websocket_endpoint(socket, session_id=None)
    socket.receive.assert_awaited_once()
    manager.schedule_delayed_cleanup.assert_called_once_with('desktop-test', websocket_api.DISCONNECT_GRACE_SECONDS)
