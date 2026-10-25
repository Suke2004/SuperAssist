"""Meeting keys stay untouched; Windows owns only the app's exact chords."""
from threading import Event
from unittest.mock import MagicMock

import pytest
import window_manager


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
    manager._run_windows_hotkeys({ord('H'): first, ord('M'): second})
    assert [call.args for call in system.RegisterHotKey.call_args_list] == [
        (None, 1, 0x400E, ord('H')), (None, 2, 0x400E, ord('M'))]
    first.assert_not_called()
    second.assert_called_once()
    system.UnregisterHotKey.assert_called_once_with(None, 2)
    assert not manager.scrolling_up and not manager.scrolling_down


@pytest.mark.skipif(not window_manager.IS_WINDOWS, reason='Windows hotkey registration')
def test_shutdown_signals_native_hotkey_loop(monkeypatch):
    manager = window_manager.WindowManager()
    manager._hotkey_stop = Event()
    manager.stop_hotkey_listener()
    assert manager._hotkey_stop.is_set()
