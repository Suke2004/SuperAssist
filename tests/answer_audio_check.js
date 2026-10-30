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
        window.webSocketHandler.sendMessage = () => {};
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
    await page.evaluate(async () => {
        const ui = window.liveInterviewUI;
        ui.startStreamingAIResponse({ question: 'How would you scale the cache?' });
        ui.appendStreamingChunk('## Cache scaling\n\n' + Array.from({ length: 80 }, (_, i) => `Step ${i}: Distribute keys, bound memory, and handle invalidation.`).join('\n\n'));
        await new Promise(requestAnimationFrame);
        if (ui.pendingStreamingChunk || !ui.currentStreamingContent.textContent.includes('Step 79')) throw new Error('Streaming frame lost content');
        ui.resumeAutoScroll();
    });
    await page.locator('#conversation-stream').hover();
    await page.mouse.wheel(0, -30);
    await page.waitForFunction(() => window.liveInterviewUI.scrollState.userReadingMode);
    await page.evaluate(async () => {
        const ui = window.liveInterviewUI;
        const stream = ui.conversationStream;
        const readingPosition = stream.scrollTop;
        if (stream.scrollHeight - stream.clientHeight - readingPosition > 100) throw new Error('Check must start within the old auto-scroll threshold');
        const parser = ui.markdownParser;
        const original = parser.processChunk;
        let renders = 0;
        parser.processChunk = function(chunk) { renders++; return original.call(this, chunk); };
        try {
            for (let i = 0; i < 100; i++) ui.appendStreamingChunk(` token${i}`);
            await new Promise(requestAnimationFrame);
            if (renders !== 1) throw new Error(`Token burst caused ${renders} renders instead of one`);
            if (!ui.scrollState.userReadingMode || Math.abs(stream.scrollTop - readingPosition) > 1) throw new Error('Streaming interrupted reading near the bottom');
            ui.appendStreamingChunk('\n\nFinal words are preserved.');
            window.webSocketHandler.handleAiAnswerComplete({ success: true });
            if (ui.pendingStreamingChunk || ui.streamingFrame !== null) throw new Error('Completed answer left a pending frame');
            if (!stream.lastElementChild.textContent.includes('Final words are preserved.')) throw new Error('Final chunk was lost');
            if (Math.abs(stream.scrollTop - readingPosition) > 1) throw new Error('Finalization interrupted reading');
        } finally { parser.processChunk = original; }
        ui.startStreamingAIResponse({ question: 'Replacement answer' });
        ui.appendStreamingChunk('Discard this partial answer.');
        ui.resetStreamingResponse();
        ui.appendStreamingChunk('Keep this replacement.');
        window.webSocketHandler.handleAiAnswerComplete({ success: true });
        if (stream.lastElementChild.textContent.includes('Discard this') || !stream.lastElementChild.textContent.includes('Keep this replacement.')) throw new Error('Fallback mixed answers');
        ui.startStreamingAIResponse();
        ui.appendStreamingChunk('Discard after clearing.');
        ui.clearConversation();
        await new Promise(requestAnimationFrame);
        if (stream.childElementCount || ui.streamingFrame !== null) throw new Error('Cleared answer rendered later');
        ui.startStreamingAIResponse({ question: 'Explain caching' });
        ui.appendStreamingChunk('## Cache design\n\nKeep the database authoritative.\n\n```python\ncache.get(key)\n```');
        window.webSocketHandler.handleAiAnswerComplete({ success: true });
        for (const el of document.querySelectorAll('#live-view button, #live-view button *, #live-view summary, .resume-scroll-btn')) {
            if (getComputedStyle(el).cursor !== 'default') throw new Error('Interview control changes the cursor');
        }
        const send = document.querySelector('#chat-form button');
        send.disabled = true;
        if (getComputedStyle(send).cursor !== 'default') throw new Error('Disabled button changes the cursor');
        send.disabled = false;
    });
    await page.locator('#live-view summary').click();
    if (!await page.locator('#live-view details').evaluate(el => el.open)) throw new Error('More button no longer works');
    await page.locator('#live-view summary').click();
    await page.evaluate(() => { navigator.clipboard.writeText = async text => { window.testCopiedCode = text; }; });
    await page.locator('.copy-button').click();
    await page.waitForFunction(() => window.testCopiedCode === 'cache.get(key)');
    await page.evaluate(() => {
        if (document.querySelector('.copy-button').getBoundingClientRect().height < 24) throw new Error('Copy target is too small');
    });
    await page.screenshot({ path: 'output/playwright/veyracue-answer-scroll.png' });
    await page.setViewportSize({ width: 390, height: 700 });
    await page.evaluate(() => {
        const panel = document.querySelector('.answers-panel').getBoundingClientRect();
        if (panel.width > innerWidth || panel.bottom > innerHeight || panel.height < 200) throw new Error('Narrow answer pane overflows the viewport');
    });
    await page.screenshot({ path: 'output/playwright/veyracue-interview-mobile.png' });
    await page.unroute('**/static/**');
    return ['14px answers', 'compact headings', 'mouse wheel during generation', 'global scrolling', 'reading near bottom', 'one render per frame', 'final chunk', 'fallback reset', 'clear pending frame', 'arrow cursors', 'working More button', 'code copy', 'narrow layout', 'native capture without microphone', 'playback status'];
}
