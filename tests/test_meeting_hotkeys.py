"""Meeting keys stay untouched; Windows owns only the app's exact chords."""
from threading import Event
from unittest.mock import MagicMock

import pytest
import main
import window_manager


HOTKEY_ACTIONS = [
    (ord('H'), 'toggle_visibility', ()), (ord('K'), 'toggle_ghost_mode', ()),
    (ord('M'), 'send_audio_command', ('toggle_mic_mute',)),
    (ord('U'), 'send_audio_command', ('toggle_universal_mute',)),
    (ord('G'), 'send_audio_command', ('toggle_answer_mode',)),
    (ord('V'), 'send_vision_command', ('toggle_vision_mode',)),
    (ord('S'), 'send_vision_command', ('capture_screenshot',)),
    (ord('P'), 'send_vision_command', ('process_screenshots',)),
    (ord('R'), 'send_vision_command', ('reset_screenshot_queue',)),
    (ord('Q'), 'send_preset_switch_signal', ('primary',)),
    (ord('W'), 'send_preset_switch_signal', ('secondary',)),
    (ord('E'), 'send_context_aware_command', ('auto_select_preset',)),
    (ord('T'), 'send_vision_switch_command', ('switch_vision_model',)),
    (ord('O'), 'send_interview_command', ('reset_interview',)),
    (ord('Y'), 'enable_proctoring_stealth_mode', ()),
    (0x70, 'send_transparency_command', ('transparent',)),
    (0x71, 'send_transparency_command', ('semi',)),
    (0x72, 'send_transparency_command', ('opaque',)),
    (0xDB, 'send_audio_command', ('decrease_transparency',)),
    (0xDD, 'send_audio_command', ('increase_transparency',)),
    (0x25, 'move_window', (-20, 0)), (0x27, 'move_window', (20, 0)),
    (0x26, 'move_window', (0, -20)), (0x28, 'move_window', (0, 20)),
    (0x21, '_start_continuous_scrolling', ()), (0x22, '_start_continuous_scrolling', ()),
]


@pytest.mark.parametrize('platform', ['win32', 'darwin', 'linux'])
@pytest.mark.parametrize('code,method,args', HOTKEY_ACTIONS)
def test_every_desktop_shortcut_runs_its_expected_action(monkeypatch, platform, code, method, args):
    manager = window_manager.WindowManager()
    manager.is_windows, manager.is_macos, manager.is_linux = platform == 'win32', platform == 'darwin', platform == 'linux'
    manager._run_windows_hotkeys = manager._run_unix_hotkeys = MagicMock()
    action = MagicMock()
    monkeypatch.setattr(manager, method, action)
    manager._start_hotkey_listener_thread()
    assert set(manager.shortcut_bindings) == {item[0] for item in HOTKEY_ACTIONS}
    for _ in range(2):
        manager.scrolling_up = manager.scrolling_down = False
        manager.shortcut_bindings[code]()
    assert action.call_count == 2
    action.assert_called_with(*args)


@pytest.mark.parametrize('command', ['toggle_mic_mute', 'toggle_universal_mute', 'toggle_vision_mode',
    'capture_screenshot', 'process_screenshots', 'reset_screenshot_queue', 'toggle_answer_mode',
    'switch_vision_model', 'reset_interview', 'decrease_transparency', 'increase_transparency'])
def test_global_commands_run_immediately_and_preserve_two_real_presses(monkeypatch, command):
    monitor = main.GlobalCommandMonitor()
    execute = MagicMock()
    monkeypatch.setattr(monitor, '_execute_browser_command', execute)
    payload = {'command': command, 'source': 'global_hotkey'}
    assert monitor._process_command(payload)
    assert monitor._process_command(payload)
    assert execute.call_count == 2
    assert monitor._process_command({**payload, 'source': 'remote'}) is False
    assert execute.call_count == 2


def test_global_toggle_is_not_replayed_when_dispatch_fails(monkeypatch):
    window = MagicMock()
    window.run_js.side_effect = RuntimeError('window closed after dispatch')
    monkeypatch.setattr(main.webview, 'windows', [window])
    main.GlobalCommandMonitor()._execute_browser_command('window.toggleMicMute();')
    window.run_js.assert_called_once()
    window.evaluate_js.assert_not_called()


@pytest.mark.skipif(not window_manager.IS_WINDOWS, reason='Windows hotkey registration')
def test_windows_shortcuts_have_no_alt_aliases_and_keep_action_mapping(monkeypatch):
    manager = window_manager.WindowManager()
    manager._run_windows_hotkeys = MagicMock()
    manager.toggle_visibility = MagicMock()
    manager.send_audio_command = MagicMock()
    manager.move_window = MagicMock()
    legacy = MagicMock()
    monkeypatch.setattr(window_manager.keyboard, 'GlobalHotKeys', legacy)
    manager._start_hotkey_listener_thread()
    bindings = manager._run_windows_hotkeys.call_args.args[0]
    assert len(bindings) == 26 and not {ord('Z'), ord('X'), ord('1'), ord('2'), ord('3')} & bindings.keys()
    assert {ord('H'), ord('K'), ord('M'), ord('U'), ord('Y'), 0x70, 0x71, 0x72, 0x21, 0x22, 0xDB, 0xDD} <= bindings.keys()
    bindings[ord('H')]()
    manager.toggle_visibility.assert_called_once()
    bindings[ord('M')]()
    manager.send_audio_command.assert_called_with('toggle_mic_mute')
    bindings[ord('G')]()
    manager.send_audio_command.assert_called_with('toggle_answer_mode')
    bindings[0x26]()
    manager.move_window.assert_called_with(0, -20)
    legacy.assert_not_called()


@pytest.mark.skipif(not window_manager.IS_WINDOWS, reason='Windows hotkey registration')
def test_exact_registration_leaves_occupied_shortcut_and_cleans_up(monkeypatch):
    manager = window_manager.WindowManager()
    manager._hotkey_stop = MagicMock()
    manager._hotkey_stop.is_set.side_effect = [False, True]
    manager.scrolling_up = manager.scrolling_down = True
    system = MagicMock()
    system.RegisterHotKey.side_effect = [False, True]
    first, second = MagicMock(), MagicMock()
    delivered = iter([1, 2, None])

    def peek(pointer, *args):
        hotkey_id = next(delivered)
        if hotkey_id is None:
            return 0
        pointer._obj.wParam = hotkey_id
        return 1

    system.PeekMessageW.side_effect = peek
    system.GetAsyncKeyState.return_value = 0
    monkeypatch.setattr(window_manager, '_user32', system)
    browser = MagicMock()
    monkeypatch.setattr(window_manager.webview, 'windows', [browser])
    manager._run_windows_hotkeys({ord('H'): first, ord('M'): second})
    assert [call.args for call in system.RegisterHotKey.call_args_list] == [
        (None, 1, 0x400E, ord('H')), (None, 2, 0x400E, ord('M'))]
    first.assert_not_called()
    second.assert_called_once()
    system.UnregisterHotKey.assert_called_once_with(None, 2)
    assert not manager.scrolling_up and not manager.scrolling_down
    assert browser.run_js.call_args_list[0].args == ('window.__nativeHotkeys = true; window.__nativeHotkeyCodes = [77];',)
    assert browser.run_js.call_args_list[-1].args == ('window.__nativeHotkeys = false; window.__nativeHotkeyCodes = [];',)
    assert not manager.global_hotkeys_active and not manager.registered_hotkeys


@pytest.mark.skipif(not window_manager.IS_WINDOWS, reason='Windows hotkey registration')
def test_shutdown_signals_native_hotkey_loop(monkeypatch):
    manager = window_manager.WindowManager()
    manager._hotkey_stop = Event()
    manager.stop_hotkey_listener()
    assert manager._hotkey_stop.is_set()
