// Run against a static repository server: python -m http.server 8019 --bind 127.0.0.1.
async (page) => {
    let saves = 0;
    let summaries = 0;
    const record = { session_id: 'test-session', started_at: '2026-10-30T08:00:00Z', status: 'completed', context: { mode: 'call' }, events: [{ type: 'transcript', speaker: 'interviewer', text: 'How do we ship this?' }, { type: 'answer', question: 'How do we ship this?', text: 'Start with a small release.' }] };
    await page.route('**/static/**', route => route.continue({ url: route.request().url().replace('/static/', '/web/') }));
    await page.route('**/api/**', async route => {
        const path = route.request().url().replace(/^https?:\/\/[^/]+/, '').split('?')[0];
        let status = 200;
        let body = {};
        if (path === '/api/config') body = { DEV_MODE: true };
        else if (path === '/api/ai-providers') body = [{ name: 'Test engine', models: ['test-model'] }];
        else if (path === '/api/ai-providers/full') body = [];
        else if (path === '/api/finalize-session') {
            if (++saves === 1) { status = 500; body = { detail: 'Disk full' }; }
            else body = { success: true, path: 'test-output/session.json', record };
            if (route.request().headers()['x-app-token'] !== 'test-token') throw new Error('Save missing authentication');
        } else if (path === '/api/sessions') body = [record];
        else if (path === '/api/sessions/test-session') body = record;
        else if (path.endsWith('/summary')) {
            if (++summaries === 1) { status = 503; body = { detail: 'Engine unavailable' }; }
            else body = { success: true, summary: 'Ship a small release first.' };
        }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto('http://127.0.0.1:8019/web/index.html');
    await page.waitForFunction(() => window.providerManager?.aiProviders.length && document.getElementById('ai-model-select').value);
    const result = await page.evaluate(async () => {
        window.__APP_TOKEN__ = 'test-token';
        const { stateManager, webSocketHandler, switchView, endInterview } = await import('/static/js/main.js');
        const assert = (condition, message) => { if (!condition) throw new Error(message); };
        document.getElementById('session-mode').value = 'call';
        document.getElementById('session-mode').dispatchEvent(new Event('change'));
        for (const id of ['user-name', 'user-company', 'user-role', 'user-resume']) assert(!document.getElementById(id).required, `${id} still required for call`);
        assert(stateManager.handleOnboarding(), 'Regular call requires interview details');
        const upload = document.getElementById('session-documents');
        const setFiles = files => { const data = new DataTransfer(); files.forEach(file => data.items.add(file)); upload.files = data.files; upload.dispatchEvent(new Event('change')); };
        setFiles([new File(['Release notes'], 'notes.md', { type: 'text/markdown' })]);
        await new Promise(resolve => setTimeout(resolve, 60));
        assert(stateManager.handleOnboarding() && stateManager.appState.onboardingData.documents[0].text === 'Release notes', 'Document not included in context');
        setFiles([new File(['a'.repeat(60001)], 'oversized.txt')]);
        await new Promise(resolve => setTimeout(resolve, 60));
        assert(!stateManager.documents.length && document.getElementById('session-documents-status').textContent.includes('limit'), 'Oversized document accepted');
        setFiles([new File(['binary'], 'resume.pdf')]);
        await new Promise(resolve => setTimeout(resolve, 60));
        assert(!stateManager.documents.length && !upload.value, 'Unsupported document accepted');
        switchView('live');
        window.liveInterviewUI.initialize();
        window.liveInterviewUI.setSessionStatus('starting');
        assert(document.getElementById('live-session-status').textContent.includes('Starting'), 'Premature listening status');
        const NativeSocket = window.WebSocket;
        class FakeSocket extends EventTarget {
            static OPEN = 1; static CLOSED = 3;
            constructor(url, protocols) {
                super(); this.readyState = 0; this.bufferedAmount = 0; this.sent = []; this.closes = 0;
                window.testSocketUrl = url; window.testSocketProtocols = protocols;
                setTimeout(() => { this.readyState = 1; this.dispatchEvent(new Event('open')); this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({ type: 'session_resumed', payload: { session_id: 'test-session' } }) })); }, 0);
            }
            send(data) { this.sent.push(data); }
            close() { this.closes++; this.readyState = 3; this.dispatchEvent(new Event('close')); }
        }
        window.WebSocket = FakeSocket;
        webSocketHandler.session_id = 'test-session';
        await webSocketHandler.connect();
        const socket = webSocketHandler.socket;
        assert(window.testSocketProtocols.join(',') === 'superassist,test-token' && !window.testSocketUrl.includes('test-token'), 'WebSocket token exposed in URL');
        assert(document.getElementById('live-session-status').textContent === 'Listening', 'Reconnect did not restore status');
        window.liveInterviewUI.updateMuteButton(true);
        window.liveInterviewUI.updatePauseButton(true);
        assert(document.getElementById('mute-btn').getAttribute('aria-pressed') === 'true' && document.getElementById('pause-btn').getAttribute('aria-pressed') === 'true', 'Pressed states missing');
        assert(getComputedStyle(document.querySelector('.mute-text'), '::after').content !== '"d"', 'Mutedd suffix remains');
        window.liveInterviewUI.handleMuteStateChange({ microphone: false, universal: false });
        const input = document.getElementById('chat-question');
        input.value = 'A follow-up';
        document.getElementById('chat-form').dispatchEvent(new Event('submit', { cancelable: true }));
        assert(document.querySelector('#chat-form button').disabled, 'Pending chat allows duplicate sends');
        window.dispatchEvent(new CustomEvent('superassist:answer-complete', { detail: { success: false } }));
        assert(input.value === 'A follow-up', 'Failed answer discarded chat draft');
        window.liveInterviewUI.startStreamingAIResponse({ question: 'How do we ship this?' });
        window.liveInterviewUI.appendStreamingChunk('Start with a small release.');
        window.liveInterviewUI.resetStreamingResponse();
        window.liveInterviewUI.appendStreamingChunk('Use a small rollout.');
        webSocketHandler.handleAiAnswerComplete({ success: true });
        assert(document.querySelector('.answer-question').textContent === 'How do we ship this?', 'Answer lost question');
        const size = document.getElementById('answer-font-size');
        size.value = '18'; size.dispatchEvent(new Event('change'));
        assert(getComputedStyle(document.querySelector('#conversation-stream .streaming-text')).fontSize === '18px', 'Text size control overridden');
        window.liveInterviewUI.addInterviewerQuestion('How do we ship this?', false);
        await endInterview();
        assert(document.body.dataset.view === 'completion' && document.getElementById('session-review-events').textContent.includes('How do we ship this?'), 'Failed save is not reviewable');
        assert(webSocketHandler.session_id === 'test-session' && socket.closes === 0, 'Failed save cleared session');
        assert(!document.getElementById('session-retry-save').hidden && document.getElementById('session-new-btn').disabled, 'Failed save allows data loss');
        await endInterview();
        assert(socket.closes === 1 && !webSocketHandler.session_id, 'Successful finalize did not disconnect');
        assert(document.getElementById('session-save-status').textContent.includes('test-output/session.json'), 'Saved path missing');
        assert(document.getElementById('session-retry-save').hidden && !document.getElementById('session-new-btn').disabled, 'Completed actions wrong');
        window.WebSocket = NativeSocket;
        return ['regular call', 'document context and limits', 'WS protocol authentication', 'truthful status', 'pressed states', 'draft retry', 'question association and fallback', 'text size', 'save failure preserved', 'finalize success'];
    });
    await page.getByRole('button', { name: 'Generate AI summary' }).click();
    await page.waitForFunction(() => document.getElementById('session-summary').textContent.includes('Engine unavailable'));
    await page.getByRole('button', { name: 'Generate AI summary' }).click();
    await page.waitForFunction(() => document.getElementById('session-summary').textContent === 'Ship a small release first.');
    await page.getByRole('button', { name: 'Session history' }).click();
    await page.getByRole('button', { name: /Regular call/ }).click();
    await page.waitForFunction(() => document.getElementById('session-review-events').textContent.includes('Start with a small release.'));
    await page.screenshot({ path: 'output/playwright/session-review.png' });
    await page.unroute('**/api/**');
    await page.unroute('**/static/**');
    return [...result, 'summary retry', 'history opens full record'];
}
