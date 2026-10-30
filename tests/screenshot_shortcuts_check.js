// Run with playwright-cli run-code --filename tests/screenshot_shortcuts_check.js.
async (page) => {
    await page.addInitScript(() => {
        Object.defineProperty(navigator, 'platform', { configurable: true,
            value: new URL(location.href).searchParams.get('platform') || 'Win32' });
    });
    const results = [];
    for (const platform of ['Win32', 'MacIntel', 'Linux x86_64']) {
        await page.goto(`http://127.0.0.1:8017/?platform=${encodeURIComponent(platform)}`);
        await page.waitForFunction(() => document.getElementById('vision-model-select')?.value);
        const checked = await page.evaluate(async platform => {
            const { switchView, stateManager } = await import('/static/js/main.js');
            const { default: hotkeys } = await import('/static/js/hotkeys.js');
            switchView('live');
            hotkeys.setEnabled(true);
            const mac = platform === 'MacIntel';
            const dispatch = (code, shift = false, repeat = false) => {
                const event = new KeyboardEvent('keydown', { code, key: code.startsWith('Key') ? code.slice(3).toLowerCase() : code,
                    altKey: mac, ctrlKey: !mac, shiftKey: !mac || shift, metaKey: !mac,
                    bubbles: true, cancelable: true, repeat });
                document.getElementById('chat-question').dispatchEvent(event);
                return event.defaultPrevented;
            };
            const calls = [];
            window.pywebview = { api: { shortcut: async code => { calls.push(code); return true; }, stop_scrolling: async () => {} } };
            window.__nativeHotkeys = false;
            const mapping = [
                ['KeyH', 72], [mac ? 'KeyX' : 'KeyK', 75], ['KeyM', 77], ['KeyU', 85],
                ['KeyG', 71], ['KeyV', 86], ['KeyS', 83], ['KeyP', 80], ['KeyR', 82],
                ['KeyQ', 81], ['KeyW', 87], ['KeyE', 69], ['KeyT', 84], ['KeyO', 79],
                [mac ? 'KeyS' : 'KeyY', 89, mac],
                [mac ? 'Digit1' : 'F1', 112], [mac ? 'Digit2' : 'F2', 113], [mac ? 'Digit3' : 'F3', 114],
                ['BracketLeft', 219], ['BracketRight', 221],
                [mac ? 'Comma' : 'ArrowLeft', 37, mac], [mac ? 'Period' : 'ArrowRight', 39, mac],
                [mac ? 'KeyU' : 'ArrowUp', 38, mac], [mac ? 'KeyD' : 'ArrowDown', 40, mac],
                [mac ? 'Comma' : 'PageUp', 33], [mac ? 'Period' : 'PageDown', 34]
            ];
            for (const [code, expected, shift = false] of mapping) {
                if (!dispatch(code, shift) || calls.at(-1) !== expected) throw new Error(`Shortcut disconnected: ${code}`);
                const count = calls.length;
                dispatch(code, shift, true);
                if (calls.length !== count) throw new Error(`Held key repeated: ${code}`);
            }
            if (calls.length !== 26) throw new Error('Shortcut fired twice');
            window.__nativeHotkeys = true;
            window.__nativeHotkeyCodes = [77];
            if (dispatch('KeyM')) throw new Error('Registered native mute duplicated in browser');
            if (!dispatch('KeyU') || calls.at(-1) !== 85) throw new Error('Unregistered shortcut has no focused fallback');
            window.__nativeHotkeys = false;
            hotkeys.setEnabled(false);
            const disabledCount = calls.length;
            dispatch('KeyS');
            if (calls.length !== disabledCount) throw new Error('Disabled screenshot shortcut still fires');
            hotkeys.setEnabled(true);

            window.pywebview = undefined;
            const messages = [];
            window.sendSocketMessage = (type, payload) => { messages.push([type, payload]); return true; };
            window.wsHandler.sendMessage = window.sendSocketMessage;
            window.wsHandler.answerModeFull = undefined;
            if (!dispatch('KeyG') || window.wsHandler.answerModeFull !== false) throw new Error('First answer-mode press does not switch to hints');
            dispatch('KeyG');
            if (!window.wsHandler.answerModeFull || messages.length !== 2) throw new Error('Rapid answer-mode toggle lost');
            window.muteManager.setMicrophoneMute(false);
            window.muteManager.setUniversalMute(false);
            messages.length = 0;
            if (!dispatch('KeyM') || !window.muteManager.isMicrophoneMuted()) throw new Error('Focused microphone mute missing');
            dispatch('KeyM');
            if (window.muteManager.isMicrophoneMuted() || messages.length !== 2) throw new Error('Rapid mute presses lost or duplicated');
            dispatch('KeyU');
            if (!window.muteManager.isUniversallyMuted()) throw new Error('Focused pause missing');
            dispatch('KeyU');
            if (window.muteManager.isUniversallyMuted()) throw new Error('Rapid resume lost');
            stateManager.appState.selectedVisionProvider = { name: 'Test vision', model: 'test-model' };
            stateManager.appState.selectedSecondaryVisionProvider = { name: 'Test secondary', model: 'other-model' };
            window.muteManager.setUniversalMute(true);
            dispatch('KeyV');
            dispatch('KeyV');
            if (stateManager.appState.visionMode.isActive || !window.muteManager.isUniversallyMuted()) throw new Error('Vision toggle overrides manual pause');
            dispatch('KeyV');
            dispatch('KeyT');
            if (stateManager.appState.visionMode.currentVisionProvider !== 'secondary') throw new Error('Secondary vision shortcut disconnected');
            dispatch('KeyT');
            if (stateManager.appState.visionMode.currentVisionProvider !== 'primary') throw new Error('Rapid vision model toggle lost');
            dispatch('KeyV');
            window.muteManager.setUniversalMute(false);

            const canvas = document.createElement('canvas');
            canvas.width = 1200; canvas.height = 600;
            canvas.getContext('2d').fillRect(0, 0, 1200, 600);
            window.pywebview = { api: { capture_screenshot: async () => ({ data_url: canvas.toDataURL('image/png') }) } };
            navigator.mediaDevices.getDisplayMedia = async () => { throw new Error('Unexpected screen picker'); };
            window.open = () => { throw new Error('Unexpected image viewer'); };
            let processed = 0;
            const processQueue = window.screenshotService.processQueue.bind(window.screenshotService);
            window.screenshotService.processQueue = async () => { processed++; return true; };
            stateManager.lastScreenshotTime = 0;
            document.getElementById('screenshot-btn').click();
            while (window.screenshotService.isCapturing) await new Promise(resolve => setTimeout(resolve, 10));
            if (processed || window.screenshotService.screenshotQueue.length !== 1) throw new Error('Screenshot does not stay queued for review');
            if (window.muteManager.isUniversallyMuted()) throw new Error('Screenshot pauses audio');
            if (document.querySelectorAll('.screenshot-image').length !== 1) throw new Error('Queue thumbnail missing');
            document.querySelector('.screenshot-remove').click();
            if (window.screenshotService.screenshotQueue.length) throw new Error('Removing queued screenshot failed');
            stateManager.lastScreenshotTime = 0;
            if (!await window.captureScreenshot()) throw new Error('Capture after removal failed');
            document.getElementById('process-queue-btn').click();
            if (processed !== 1) throw new Error('Explicit Process button disconnected');
            window.pywebview = undefined;
            if (!dispatch('KeyR') || window.screenshotService.screenshotQueue.length) throw new Error('Clear queue shortcut disconnected');
            window.screenshotService.processQueue = processQueue;
            window.pywebview = { api: { capture_screenshot: async () => ({ data_url: canvas.toDataURL('image/png') }) } };
            stateManager.lastScreenshotTime = 0;
            await window.captureScreenshot();
            let finish;
            let requests = 0;
            const pending = new Promise(resolve => { finish = resolve; });
            window.screenshotService.sendToVisionAI = async () => { requests++; return pending; };
            const processing = processQueue();
            await processQueue();
            if (requests !== 1) throw new Error('Repeated Process shortcut sends duplicate requests');
            stateManager.lastScreenshotTime = 0;
            await window.captureScreenshot();
            const newest = window.screenshotService.screenshotQueue.at(-1).id;
            if (!document.getElementById('process-queue-btn').disabled) throw new Error('Adding a capture re-enables duplicate analysis');
            finish({ success: true });
            await processing;
            if (window.screenshotService.screenshotQueue.length !== 1 || window.screenshotService.screenshotQueue[0].id !== newest) throw new Error('Analysis cleared a newer capture');
            window.screenshotService.sendToVisionAI = async () => ({ success: false, error: 'Simulated provider failure' });
            await processQueue();
            if (window.screenshotService.isProcessing || window.screenshotService.screenshotQueue.length !== 1) throw new Error('Failed analysis loses queued capture or blocks retry');
            window.screenshotService.clearQueue();
            if (!document.getElementById('process-queue-btn').disabled) throw new Error('Empty queue Process remains enabled');
            return ['26 mappings', 'one action per press', 'held/disabled keys', 'native/focused deduplication',
                'mute/resume', 'answer/vision model toggles', 'manual pause preserved', 'quiet capture', 'queue removal', 'explicit analysis', 'single in-flight analysis', 'new captures preserved'];
        }, platform);
        results.push(`${platform}: ${checked.join(', ')}`);
    }
    return results;
}
