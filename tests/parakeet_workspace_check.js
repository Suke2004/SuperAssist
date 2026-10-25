// Run against the local app: playwright-cli run-code --filename tests/parakeet_workspace_check.js
async (page) => {
    await page.route('**/static/**', route => route.continue());
    await page.goto('http://127.0.0.1:8017/');
    await page.waitForFunction(() => document.getElementById('ai-model-select')?.value && document.getElementById('ai-secondary-model-select')?.value && document.getElementById('vision-model-select')?.value);
    const result = await page.evaluate(async () => {
        const { switchView, stateManager } = await import('/static/js/main.js');
        const assert = (condition, message) => { if (!condition) throw new Error(message); };
        assert(getComputedStyle(document.documentElement).colorScheme === 'dark', 'Dark theme missing');
        assert(getComputedStyle(document.getElementById('user-resume')).backgroundColor === 'rgb(24, 29, 37)', 'Setup input is not dark');
        assert(document.title === 'VeyraCue — Interview assistant', 'Application name was not updated');
        assert(!window.appState.aiProviders.some(p => p.hasUsableKey === false), 'Unconfigured provider offered');
        assert(document.getElementById('ai-provider-select').value, 'Missing primary provider');
        document.getElementById('user-name').value = 'Test candidate';
        document.getElementById('user-company').value = 'Example company';
        document.getElementById('user-role').value = 'Backend engineer';
        document.getElementById('user-resume').value = 'Built and maintained Python APIs.';
        document.getElementById('user-instructions').value = 'Keep answers concise.';
        assert(stateManager.handleOnboarding(), 'Onboarding validation failed');
        assert(stateManager.getState().onboardingData.instructions === 'Keep answers concise.', 'Instructions lost');
        switchView('live');
        window.liveInterviewUI.init();
        assert(getComputedStyle(document.querySelector('.workspace-sidebar')).display === 'none', 'Setup navigation covers interview overlay');
        const overlay = document.getElementById('live-view').getBoundingClientRect();
        assert(overlay.left === 0 && overlay.top === 0 && overlay.width === innerWidth, 'Interview overlay does not use the full window');
        const more = document.querySelector('.live-more');
        more.querySelector('summary').click();
        assert(more.open && document.getElementById('preset-indicator').closest('.live-more-menu'), 'Model details not in the secondary menu');
        more.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        assert(!more.open, 'Escape did not close secondary menu');
        const socket = { readyState: WebSocket.OPEN, sent: [], send(message) { this.sent.push(JSON.parse(message)); } };
        window.webSocketHandler.socket = socket;
        window.webSocketHandler.handleTranscriptUpdate({ transcript: 'How do you cache API results?', is_final: true, speaker_role: 'interviewer' });
        window.webSocketHandler.handleTranscriptUpdate({ transcript: 'I use Redis.', is_final: true, speaker_role: 'candidate' });
        assert(document.querySelectorAll('#transcript-stream .message').length === 2, 'Speaker transcripts misplaced');
        assert(document.querySelectorAll('#conversation-stream .message').length === 0, 'Transcript leaked into answers');
        window.webSocketHandler.handleAiProcessingStarted({ question: 'How do you cache API results?' });
        window.webSocketHandler.handleAiAnswerChunk({ chunk: 'Use Redis with a TTL.', chunk_type: 'content' });
        window.webSocketHandler.handleAiAnswerComplete({ answer: 'Use Redis with a TTL.', success: true });
        assert(document.getElementById('conversation-stream').textContent.includes('Use Redis'), 'Answer failed to render');
        document.getElementById('answer-btn').click();
        const toggle = document.getElementById('auto-answer-toggle');
        toggle.checked = false;
        toggle.dispatchEvent(new Event('change'));
        window.webSocketHandler.handleMessage({ type: 'auto_answer_status', payload: { enabled: false } });
        assert(!toggle.checked, 'Manual-answer status lost');
        document.getElementById('chat-question').value = 'What about cache invalidation?';
        document.getElementById('chat-form').dispatchEvent(new Event('submit', { cancelable: true }));
        assert(socket.sent.some(m => m.type === 'request_answer'), 'Answer button disconnected');
        assert(socket.sent.some(m => m.type === 'set_auto_answer' && m.payload.enabled === false), 'Auto answer button disconnected');
        assert(socket.sent.some(m => m.type === 'ask_question' && m.payload.question === 'What about cache invalidation?'), 'Chat form disconnected');
        window.liveInterviewUI.clearConversation();
        assert(!document.querySelector('#transcript-stream .message') && !document.querySelector('#conversation-stream .message'), 'Clear left transcript behind');
        return { checked: ['dark theme', 'application name', 'configured engines', 'instructions', 'full-window overlay', 'secondary menu', 'speaker routing', 'streamed answer', 'manual answer', 'auto answer', 'chat', 'clear'] };
    });
    for (const size of [{ width: 1000, height: 700 }, { width: 800, height: 600 }, { width: 640, height: 700 }, { width: 390, height: 844 }]) {
        await page.setViewportSize(size);
        const layout = await page.evaluate(() => {
            const rect = selector => document.querySelector(selector).getBoundingClientRect();
            return { header: rect('.live-header').height, answer: rect('.answers-panel').height,
                answerWidth: rect('.answers-panel').width, stream: rect('#conversation-stream').height,
                width: innerWidth, height: innerHeight, overflow: document.documentElement.scrollWidth > innerWidth,
                answerButton: rect('#answer-btn').width };
        });
        if (layout.header > 100 || layout.answer < layout.height * .55 || layout.stream < layout.height * .4 || layout.overflow || layout.answerButton > 100) {
            throw new Error(`Live answer space lost at ${size.width}px: ${JSON.stringify(layout)}`);
        }
        if (size.width > 760 && layout.answerWidth < size.width * .7) throw new Error('Transcript is larger than the answer area');
    }
    await page.setViewportSize({ width: 1000, height: 700 });
    await page.evaluate(() => {
        document.getElementById('live-session-title').textContent = 'Backend engineer at Example company';
        document.getElementById('session-timer').textContent = '00:37';
        document.getElementById('auto-answer-toggle').checked = true;
        window.webSocketHandler.handleTranscriptUpdate({ transcript: 'How would you handle a traffic spike without taking the service down?', is_final: true, speaker_role: 'interviewer' });
        const answer = 'I would start with the bottleneck, rather than scaling every layer at once.\n\n**First, protect the service.** Put request limits and timeouts at the edge, cache repeated reads, and queue work that does not need an immediate response.\n\n**Then scale the constrained layer.** Add stateless application instances, check database connection limits, and watch p95 latency and error rates.\n\n**Finally, validate recovery.** Run a load test with a realistic spike and verify the queue drains after traffic returns to normal.';
        window.webSocketHandler.handleAiProcessingStarted({ question: 'How would you handle a traffic spike?' });
        window.webSocketHandler.handleAiAnswerChunk({ chunk: answer, chunk_type: 'content' });
        window.webSocketHandler.handleAiAnswerComplete({ answer, success: true });
        window.liveInterviewUI.showActivity('Listening...');
        if (document.querySelector('.stealth-indicator-dot').textContent) throw new Error('Activity text replaced its status dot');
        if (document.querySelector('.stealth-indicator-text').textContent !== 'Listening...') throw new Error('Activity status was not updated');
        window.liveInterviewUI.showResumeScrollButton();
        if (!document.querySelector('.resume-scroll-btn').classList.contains('hidden')) throw new Error('Scroll control shown when the answer fits');
        const message = document.querySelector('#conversation-stream .message');
        if (getComputedStyle(message).opacity !== '1') throw new Error('Live answer is invisible before its animation completes');
        if (getComputedStyle(message.querySelector('p')).opacity !== '1') throw new Error('Answer text is dimmed by an animation');
        const luminance = color => {
            const rgb = color.match(/[\d.]+/g).slice(0, 3).map(Number).map(v => {
                const s = v / 255; return s <= .04045 ? s / 12.92 : ((s + .055) / 1.055) ** 2.4;
            });
            return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
        };
        const checkContrast = (selector, panel) => {
            const text = luminance(getComputedStyle(document.querySelector(selector)).color);
            const background = luminance(getComputedStyle(document.querySelector(panel)).backgroundColor);
            if ((Math.max(text, background) + .05) / (Math.min(text, background) + .05) < 4.5) throw new Error(`Low dark-theme contrast: ${selector}`);
        };
        checkContrast('#conversation-stream p', '.answers-panel');
        checkContrast('#conversation-stream strong', '.answers-panel');
        checkContrast('.auto-answer-toggle', '.answers-panel');
        checkContrast('#chat-question', '#chat-question');
        checkContrast('#answer-btn', '#answer-btn');
        checkContrast('#screenshot-btn', '#screenshot-btn');
    });
    await page.waitForFunction(() => document.getElementById('transcript-stream').textContent.includes('service down'), { timeout: 5000 });
    await page.screenshot({ path: 'output/playwright/veyracue-live.png' });
    await page.evaluate(async () => { const { switchView } = await import('/static/js/main.js'); switchView('onboarding'); });
    await page.setViewportSize({ width: 390, height: 844 });
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    if (!fits) throw new Error('Mobile layout overflows horizontally');
    await page.screenshot({ path: 'output/playwright/parakeet-mobile.png' });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: 'output/playwright/parakeet-setup.png' });
    await page.unroute('**/static/**');
    return result;
}
