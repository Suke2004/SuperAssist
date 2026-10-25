// Verify the answer pane and native startup without granting microphone permission.
async (page) => {
    await page.route('**/static/**', route => route.continue());
    await page.setViewportSize({ width: 1000, height: 700 });
    await page.goto('http://127.0.0.1:8017/');
    await page.waitForFunction(() => document.getElementById('vision-model-select')?.value);
    await page.evaluate(() => {
        navigator.mediaDevices.getUserMedia = async () => { throw new Error('No microphone access'); };
        window.testShareRequests = 0;
        navigator.mediaDevices.getDisplayMedia = async () => { window.testShareRequests++; throw new Error('Unexpected share'); };
        window.webSocketHandler.connect = async () => { window.testBackendConnected = true; };
        window.providerManager.runPreFlightChecks = async () => {
            document.querySelectorAll('.check-item').forEach(check => {
                if (!check.id.startsWith('check-mic-')) window.webSocketHandler.updateCheckStatus(check, 'success', 'Test service ready');
            });
            window.providerManager.checkAllSystemsGo();
        };
        window.webSocketHandler.startInterview = async microphoneAvailable => { window.testMicrophoneAvailable = microphoneAvailable; };
        document.getElementById('user-name').value = 'Test candidate';
        document.getElementById('user-company').value = 'Example';
        document.getElementById('user-role').value = 'Engineer';
        document.getElementById('user-resume').value = 'Builds APIs';
    });
    await page.getByRole('button', { name: 'Continue to audio setup' }).click();
    await page.waitForFunction(() => window.testBackendConnected);
    await page.evaluate(async () => {
        if (!document.getElementById('mic-select').disabled || document.getElementById('audio-capture-mode').value !== 'native') throw new Error('Missing microphone did not select system-only startup');
        if (document.getElementById('start-interview-button').disabled) throw new Error('Native capture still requires microphone permission');
        const { startInterview } = await import('/static/js/main.js');
        await startInterview();
        if (window.testMicrophoneAvailable !== false || window.testShareRequests) throw new Error('Native startup requested a microphone or screen share');
        window.webSocketHandler.updateAudioHealth('System audio', { status: 'receiving', detail: 'Test headphones' });
        if (!document.getElementById('audio-health').textContent.includes('audio detected (Test headphones)')) throw new Error('Actual playback status is missing');
        const answer = '# Cache design\n\n> A short spoken answer.\n\n' + Array.from({ length: 90 }, (_, i) => `Paragraph ${i}: Keep the database authoritative, explain the consistency trade-off, and handle invalidation races.`).join('\n\n');
        window.webSocketHandler.handleAiProcessingStarted({ question: 'Explain caching' });
        window.webSocketHandler.handleAiAnswerComplete({ answer, success: true });
        const stream = document.getElementById('conversation-stream');
        if (getComputedStyle(stream.querySelector('.streaming-text')).fontSize !== '14px') throw new Error('Desktop answer text is too large');
        if (parseFloat(getComputedStyle(stream.querySelector('h1')).fontSize) > 17) throw new Error('Answer heading is too large');
        if (stream.scrollHeight <= stream.clientHeight) throw new Error('Long answer does not overflow its scroll pane');
        stream.scrollTop = 0;
    });
    await page.locator('#conversation-stream').hover();
    await page.mouse.wheel(0, 600);
    await page.waitForFunction(() => document.getElementById('conversation-stream').scrollTop > 100);
    await page.mouse.wheel(0, -150);
    await page.waitForFunction(() => window.liveInterviewUI.scrollState.userReadingMode);
    await page.evaluate(() => {
        const stream = document.getElementById('conversation-stream');
        const before = stream.scrollTop;
        window.liveInterviewUI.scrollAnswers(-120);
        if (stream.scrollTop >= before || !window.liveInterviewUI.scrollState.userReadingMode) throw new Error('Global scroll cannot move the answer');
        const reading = stream.scrollTop;
        window.liveInterviewUI.scrollToBottom();
        if (stream.scrollTop !== reading) throw new Error('Automatic updates interrupted reading');
        window.liveInterviewUI.resumeAutoScroll();
        if (stream.scrollHeight - stream.clientHeight - stream.scrollTop > 2) throw new Error('Jump to latest failed');
    });
    await page.screenshot({ path: 'output/playwright/veyracue-answer-scroll.png' });
    await page.unroute('**/static/**');
    return ['14px answers', 'compact headings', 'mouse wheel', 'global scrolling', 'reading position', 'native capture without microphone', 'playback status'];
}
