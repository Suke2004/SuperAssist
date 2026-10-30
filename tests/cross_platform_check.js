// Run through playwright-cli against the local validation server.
async (page) => {
    await page.route('**/static/**', route => route.continue());
    await page.addInitScript(() => {
        Object.defineProperty(navigator, 'platform', { configurable: true,
            value: new URL(location.href).searchParams.get('platform') || 'Win32' });
    });
    const passed = [];
    for (const platform of ['Win32', 'MacIntel', 'Linux x86_64']) {
        const mac = platform === 'MacIntel';
        const linux = platform.startsWith('Linux');
        await page.route('**/api/audio-outputs', route => route.fulfill({ json: {
            available: true, native_microphone: true, platform: mac ? 'darwin' : linux ? 'linux' : 'win32',
            label: mac ? 'macOS routed audio' : linux ? 'Linux system audio' : 'Windows direct audio', default: 'Meeting output',
            devices: [{ id: 'meeting-output', name: 'Meeting output' }],
            microphones: [{ id: 'physical-mic', name: 'Physical microphone' }]
        } }));
        await page.goto(`http://127.0.0.1:8017/?platform=${encodeURIComponent(platform)}`);
        await page.waitForFunction(() => document.getElementById('vision-model-select')?.value);
        await page.evaluate(() => {
            navigator.mediaDevices.getUserMedia = async () => { throw new Error('Unexpected browser microphone request'); };
            navigator.mediaDevices.getDisplayMedia = async () => { throw new Error('Unexpected browser sharing request'); };
            const canvas = document.createElement('canvas');
            canvas.width = 4000; canvas.height = 2000;
            canvas.getContext('2d').fillRect(0, 0, 4000, 2000);
            window.testShortcutCalls = [];
            window.pywebview = { api: {
                capabilities: async () => ({ global_hotkeys: false }),
                shortcut: async code => window.testShortcutCalls.push(code),
                stop_scrolling: async () => window.testShortcutCalls.push('stop'),
                capture_screenshot: async () => ({ data_url: canvas.toDataURL('image/png') })
            } };
            window.__nativeHotkeys = false;
            window.webSocketHandler.connect = async () => { window.testConnected = true; };
            window.providerManager.runPreFlightChecks = async () => {
                document.querySelectorAll('.check-item').forEach(check => {
                    if (!check.id.startsWith('check-mic-')) window.webSocketHandler.updateCheckStatus(check, 'success', 'Ready');
                });
                window.providerManager.checkAllSystemsGo();
            };
            window.webSocketHandler.sendMessage = (type, payload) => {
                if (type === 'start_interview') {
                    window.testStartupPayload = payload;
                    window.webSocketHandler.pendingStart.resolve({ audio_capture_mode: 'native' });
                }
            };
            document.getElementById('user-name').value = 'Platform test';
            document.getElementById('user-company').value = 'Example';
            document.getElementById('user-role').value = 'Engineer';
            document.getElementById('user-resume').value = 'Builds APIs';
        });
        await page.getByRole('button', { name: 'Continue to audio setup' }).click();
        await page.waitForFunction(() => window.testConnected && !document.getElementById('start-interview-button').disabled);
        await page.evaluate(async ({ mac, linux }) => {
            const { startInterview } = await import('/static/js/main.js');
            const { default: hotkeys } = await import('/static/js/hotkeys.js');
            window.wsHandler.answerModeFull = false;
            await startInterview();
            if (window.wsHandler.answerModeFull !== true) throw new Error('New interview keeps the previous answer mode');
            if (!window.testStartupPayload.microphoneAvailable || window.testStartupPayload.audioInput !== 'physical-mic') throw new Error('Native microphone selection disconnected');
            if (window.testStartupPayload.audioCaptureMode !== 'native') throw new Error('Native output startup disconnected');
            if (!document.getElementById('pause-btn').title.includes(mac ? 'Option+U' : linux ? 'Ctrl+Shift+Super+U' : 'Ctrl+Shift+Win+U')) throw new Error('Platform shortcut hint incorrect');
            hotkeys.setEnabled(true);
            const options = mac ? { altKey: true, key: '©', code: 'KeyG' }
                : { ctrlKey: true, shiftKey: true, metaKey: true, key: 'g', code: 'KeyG' };
            const event = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...options });
            document.body.dispatchEvent(event);
            if (!event.defaultPrevented || window.testShortcutCalls.join(',') !== '71') throw new Error('Focused shortcut did not dispatch exactly once');
            window.__nativeHotkeys = true;
            document.body.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...options }));
            if (window.testShortcutCalls.join(',') !== '71') throw new Error('Native shortcut duplicated by browser');
            if (!await window.screenshotService.captureScreenshot()) throw new Error('Native screenshot not captured');
            const queued = window.screenshotService.screenshotQueue[0];
            const image = await createImageBitmap(queued.blob);
            if (image.width !== 2560 || image.height !== 1280) throw new Error('Native screenshot size cap lost');
            image.close();
        }, { mac, linux });
        passed.push(`${platform}: native audio/microphone, shortcuts, screenshots`);
        await page.unroute('**/api/audio-outputs');
    }
    await page.unroute('**/static/**');
    await page.goto('http://127.0.0.1:8017/');
    return passed;
}
