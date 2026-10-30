import { apiRequest } from './session-api.js';

export class SessionReview {
    constructor(showView, socketHandler) {
        this.showView = showView;
        this.socketHandler = socketHandler;
        this.record = null;
        this.unsaved = false;
        document.getElementById('session-history-btn').addEventListener('click', () => this.showHistory());
        document.getElementById('session-retry-save').addEventListener('click', () => window.endInterview());
        document.getElementById('session-new-btn').addEventListener('click', () => {
            window.liveInterviewUI.clearConversation();
            document.getElementById('chat-question').value = '';
            this.record = null;
            this.showView('onboarding');
        });
        document.getElementById('session-summary-btn').addEventListener('click', () => this.generateSummary());
        document.getElementById('session-export-btn').addEventListener('click', async () => {
            const button = document.getElementById('session-export-btn');
            button.disabled = true;
            try {
                const result = await apiRequest('/api/export-transcript', { session_id: this.record.session_id });
                document.getElementById('session-save-status').textContent = `Transcript saved: ${result.path}`;
            } catch (error) { document.getElementById('session-save-status').textContent = error.message; }
            finally { button.disabled = false; }
        });
    }

    show(record, { unsaved = false, path = '', error = '' } = {}) {
        this.record = record;
        this.unsaved = unsaved;
        this.showView('completion');
        document.getElementById('session-review-title').textContent = unsaved ? 'Session stopped — save needs attention' : 'Session complete';
        document.getElementById('session-save-status').textContent = unsaved
            ? `Save failed: ${error}. Your conversation is available below. Retry before starting a new session.`
            : `Saved locally${path || record.path ? `: ${path || record.path}` : '.'}`;
        document.getElementById('session-retry-save').hidden = !unsaved;
        document.getElementById('session-new-btn').disabled = unsaved;
        document.getElementById('session-export-btn').disabled = unsaved;
        document.getElementById('session-summary-btn').disabled = unsaved;
        document.getElementById('session-summary').textContent = record.summary || 'Generate a summary with your selected AI engine when you are ready.';
        const events = document.getElementById('session-review-events');
        events.replaceChildren();
        for (const event of record.events || []) {
            const item = document.createElement('article');
            const label = document.createElement('strong');
            label.textContent = `${event.speaker || event.type || 'Conversation'}${event.timestamp ? ` · ${new Date(event.timestamp).toLocaleTimeString()}` : ''}`;
            const text = document.createElement('p');
            text.textContent = [event.question && `Question: ${event.question}`, event.text].filter(Boolean).join('\n');
            item.append(label, text);
            events.append(item);
        }
        if (!events.childElementCount) events.textContent = 'No conversation was recorded.';
        const draft = document.getElementById('chat-question').value.trim();
        document.getElementById('session-unsent-draft').textContent = draft ? `Unsent draft: ${draft}` : '';
    }

    async showHistory() {
        if (this.unsaved) { this.show(this.record, { unsaved: true, error: 'The previous save did not complete' }); return; }
        if (document.body.dataset.view === 'live') {
            window.liveInterviewUI.addMessage('End this session before opening history.', 'system-message');
            return;
        }
        this.showView('history');
        const list = document.getElementById('session-history-list');
        list.textContent = 'Loading saved sessions…';
        try {
            const result = await apiRequest('/api/sessions');
            list.replaceChildren();
            for (const session of Array.isArray(result) ? result : result.sessions || []) {
                const button = document.createElement('button');
                const context = session.context || {};
                button.textContent = `${context.mode === 'call' ? 'Regular call' : context.role || 'Interview'}${context.company ? ` · ${context.company}` : ''} · ${new Date(session.started_at).toLocaleString()} · ${session.status || 'saved'}`;
                button.addEventListener('click', async () => {
                    button.disabled = true;
                    try { this.show(await apiRequest(`/api/sessions/${encodeURIComponent(session.session_id)}`), { path: session.path }); }
                    catch (error) { button.textContent = `Could not open session: ${error.message}. Click to retry.`; }
                    finally { button.disabled = false; }
                });
                list.append(button);
            }
            if (!list.childElementCount) list.textContent = 'No saved sessions yet.';
        } catch (error) { list.textContent = `Could not load saved sessions: ${error.message}. Open History again to retry.`; }
    }

    async generateSummary() {
        const button = document.getElementById('session-summary-btn');
        const summary = document.getElementById('session-summary');
        button.disabled = true;
        summary.textContent = 'Generating summary…';
        try {
            const result = await apiRequest(`/api/sessions/${encodeURIComponent(this.record.session_id)}/summary`, {});
            this.record.summary = result.summary;
            summary.textContent = result.summary;
        } catch (error) { summary.textContent = `Summary unavailable: ${error.message}. Your saved conversation is still available. Retry when the engine is ready.`; }
        finally { button.disabled = this.unsaved; }
    }
}
