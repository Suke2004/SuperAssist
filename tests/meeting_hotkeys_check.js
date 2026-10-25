// Run with playwright-cli run-code --filename tests/meeting_hotkeys_check.js.
async (page) => {
    await page.route('**/static/**', route => route.continue());
    await page.goto('http://127.0.0.1:8017/');
    await page.waitForFunction(() => window.wsHandler && window.liveInterviewUI);
    const result = await page.evaluate(async () => {
        const { default: hotkeys, isAppShortcut } = await import('/static/js/hotkeys.js');
        const { switchView } = await import('/static/js/main.js');
        switchView('live');
        hotkeys.setEnabled(true);
        const calls = [];
        window.wsHandler.toggleAnswerMode = () => { calls.push('mode'); return true; };
        hotkeys.decreaseTransparency = () => calls.push('opacity');
        const dispatch = options => {
            const event = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...options });
            document.body.dispatchEvent(event);
            return event.defaultPrevented;
        };
        for (const key of ['h', 'u', 'v', 's', 'g', '[']) {
            if (dispatch({ key, altKey: true })) throw new Error(`Old meeting Alt+${key} intercepted`);
        }
        if (dispatch({ key: 'g', ctrlKey: true, shiftKey: true })) throw new Error('Ordinary Ctrl+Shift key intercepted');
        if (calls.length) throw new Error('Legacy shortcut still triggered an app action');
        const modifiers = { ctrlKey: true, shiftKey: true, metaKey: true };
        if (!isAppShortcut(new KeyboardEvent('keydown', { key: 'g', ...modifiers }))) throw new Error('New Windows chord not recognized');
        if (!dispatch({ key: 'g', ...modifiers })) throw new Error('New answer mode shortcut disconnected');
        dispatch({ key: 'g', repeat: true, ...modifiers });
        if (!dispatch({ key: '{', code: 'BracketLeft', ...modifiers })) throw new Error('Shifted bracket shortcut disconnected');
        if (calls.join(',') !== 'mode,opacity') throw new Error('Shortcut repeated or fired twice');
        hotkeys.setEnabled(false);
        if (dispatch({ key: 'g', ...modifiers })) throw new Error('Disabled shortcuts still consume keys');
        if (!document.getElementById('pause-btn').title.includes('Ctrl+Shift+Win+U')) throw new Error('Live shortcut hint stale');
        if (document.querySelector('.commands-grid').textContent.includes('Alt/')) throw new Error('Help still advertises old shortcuts');
        switchView('onboarding');
        return ['meeting chords untouched', 'exact Windows modifiers', 'single action', 'shifted bracket', 'disabled state', 'updated help'];
    });
    await page.unroute('**/static/**');
    return result;
}
