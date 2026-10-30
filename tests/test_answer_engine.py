"""Answer-engine regressions with local streams and no provider requests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import llm_service
from services.context_manager import PersistentContextManager
from core.prompts import get_interview_answer_prompt, get_quick_response_prompt


class ScriptedStream:
    def __init__(self, items):
        self.items = iter(items)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = next(self.items, None)
        if item is None:
            raise StopAsyncIteration
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            delay, item = item
            await asyncio.sleep(delay)
        return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=item))])

    async def close(self):
        self.closed = True


def make_manager(monkeypatch, results, keys=1):
    created = []
    create = AsyncMock(side_effect=results)

    def client_factory(**kwargs):
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock())
        created.append((kwargs, client))
        return client

    monkeypatch.setattr(llm_service, 'AsyncOpenAI', client_factory)
    monkeypatch.setattr(llm_service.app_metrics, 'provider_error', lambda *args: None)
    monkeypatch.setattr(llm_service.app_metrics, 'inc', lambda *args: None)
    manager = llm_service.LLMManager('Test', 'https://test.invalid', 'key-0', 'test-model', api_keys=[f'key-{i}' for i in range(keys)])
    manager.set_context_manager(PersistentContextManager())
    return manager, created, create


@pytest.mark.asyncio
async def test_key_retry_resets_partial_output_and_disables_sdk_retries(monkeypatch):
    failed = ScriptedStream(['obsolete draft', ConnectionError('connection dropped')])
    good = ScriptedStream(['finished answer'])
    manager, clients, create = make_manager(monkeypatch, [failed, good], keys=2)
    chunks = []

    async def callback(text, kind):
        chunks.append((text, kind))

    answer, info = await manager.get_ai_answer('What is a heap?', callback)
    assert answer == 'finished answer' and info['success']
    assert chunks == [('obsolete draft', 'chunk'), ('', 'reset'), ('finished answer', 'chunk')]
    assert all(kwargs['max_retries'] == 0 for kwargs, _ in clients)
    clients[0][1].close.assert_awaited_once()
    assert failed.closed and good.closed and create.await_count == 2
    assert info['duration_ms'] >= info['ttft_ms'] >= 0
    assert manager.context_manager.conversation_history[-1]['ai_response'] == 'finished answer'


@pytest.mark.asyncio
@pytest.mark.parametrize('result', [ScriptedStream([]), ScriptedStream([' ', '\n']), SimpleNamespace(choices=[]), SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])])
async def test_empty_provider_answer_never_counts_as_success(monkeypatch, result):
    manager, _, _ = make_manager(monkeypatch, [result])
    callback = AsyncMock() if isinstance(result, ScriptedStream) else None
    answer, info = await manager.get_ai_answer('Explain caching', callback)
    assert info['error'] == 'non_retryable_error' and 'empty answer' in answer
    assert not manager.context_manager.conversation_history


@pytest.mark.asyncio
async def test_empty_primary_stream_can_fall_back(monkeypatch):
    primary, _, _ = make_manager(monkeypatch, [ScriptedStream([])])
    secondary = SimpleNamespace(get_ai_answer=AsyncMock(return_value=('fallback', {'success': True})), get_status=lambda: {}, is_healthy=True)
    multi = llm_service.MultiLLMManager()
    multi.providers = {'primary': primary, 'secondary': secondary}
    multi.fallback_order = ['primary', 'secondary']
    multi.presets = {key: {'provider': key, 'model': 'test', 'description': key, 'priority': 1} for key in multi.providers}
    callback = AsyncMock()
    answer, info = await multi.get_ai_answer('Explain caching', callback)
    assert answer == 'fallback' and info['fallback_used']
    callback.assert_awaited_once_with('', 'reset')


@pytest.mark.asyncio
@pytest.mark.parametrize('first', [[], [' ', '\n']])
async def test_first_meaningful_token_has_a_deadline(monkeypatch, first):
    stream = ScriptedStream(first + [(10, 'too late')])
    manager, _, _ = make_manager(monkeypatch, [stream])
    monkeypatch.setattr(llm_service, 'FIRST_TOKEN_TIMEOUT_SECONDS', 0.02)
    monkeypatch.setattr(llm_service, 'ANSWER_TIMEOUT_SECONDS', 1)
    answer, info = await asyncio.wait_for(manager.get_ai_answer('What is caching?', AsyncMock()), 0.5)
    assert info['error'] == 'all_keys_failed' and stream.closed
    assert not manager.context_manager.conversation_history


@pytest.mark.asyncio
async def test_first_token_deadline_includes_waiting_for_stream_creation(monkeypatch):
    manager, _, create = make_manager(monkeypatch, [])

    async def hung(**kwargs):
        await asyncio.sleep(10)

    create.side_effect = hung
    monkeypatch.setattr(llm_service, 'FIRST_TOKEN_TIMEOUT_SECONDS', 0.02)
    monkeypatch.setattr(llm_service, 'ANSWER_TIMEOUT_SECONDS', 1)
    answer, info = await asyncio.wait_for(manager.get_ai_answer('What is caching?', AsyncMock()), 0.5)
    assert info['error'] == 'all_keys_failed' and create.await_count == 1
    assert not manager.context_manager.conversation_history


@pytest.mark.asyncio
async def test_provider_deadline_bounds_midstream_and_key_retries(monkeypatch):
    stream = ScriptedStream(['first', (10, 'too late')])
    manager, _, create = make_manager(monkeypatch, [stream], keys=2)
    monkeypatch.setattr(llm_service, 'ANSWER_TIMEOUT_SECONDS', 0.02)
    answer, info = await asyncio.wait_for(manager.get_ai_answer('What is caching?', AsyncMock()), 0.5)
    assert info['error'] == 'all_keys_failed' and info['attempts'] == 1
    assert stream.closed and create.await_count == 1


@pytest.mark.asyncio
async def test_cancelled_stream_does_not_persist_partial_answer_or_retry(monkeypatch):
    stream = ScriptedStream(['partial', 'rest'])
    manager, _, create = make_manager(monkeypatch, [stream], keys=2)
    with pytest.raises(asyncio.CancelledError):
        await manager.get_ai_answer('What is caching?', AsyncMock(return_value=False))
    assert stream.closed and create.await_count == 1
    assert not manager.context_manager.conversation_history


@pytest.mark.asyncio
async def test_overall_deadline_stops_before_fallback(monkeypatch):
    async def hung(*args, **kwargs):
        await asyncio.sleep(10)

    primary = SimpleNamespace(get_ai_answer=AsyncMock(side_effect=hung))
    secondary = SimpleNamespace(get_ai_answer=AsyncMock())
    multi = llm_service.MultiLLMManager()
    multi.providers = {'primary': primary, 'secondary': secondary}
    multi.fallback_order = ['primary', 'secondary']
    monkeypatch.setattr(llm_service, 'ALL_PROVIDERS_TIMEOUT_SECONDS', 0.02)
    answer, info = await asyncio.wait_for(multi.get_ai_answer('q'), 0.5)
    assert info['error'] == 'answer_timeout'
    secondary.get_ai_answer.assert_not_called()


@pytest.mark.parametrize('question, category', [('What is Redis?', 'CONCEPT'), ('Tell me about yourself', 'BEHAVIORAL'), ('Implement LRU cache', 'CODING'), ('Design a news feed', 'SYSTEM_DESIGN')])
def test_short_new_questions_keep_their_own_route(question, category):
    context = PersistentContextManager()
    context.add_conversation_exchange('Explain binary search', ai_response='Prior answer')
    assert f'ROUTING DECISION (already made by the application): {category}' in get_interview_answer_prompt(question, context)
    assert f'ROUTING: {category}' in get_quick_response_prompt(question, context)
    assert 'FOLLOW-UP / VARIANT TEMPLATE' not in get_interview_answer_prompt(question, context)


@pytest.mark.parametrize('question', ['why?', 'What about duplicates?', 'Can you optimize this?', 'Explain that'])
def test_explicit_followups_keep_delta_route(question):
    context = PersistentContextManager()
    context.add_conversation_exchange('Implement binary search', ai_response='Prior answer')
    assert 'FOLLOW-UP / VARIANT TEMPLATE' in get_interview_answer_prompt(question, context)


def test_candidate_segments_append_and_old_candidate_facts_remain_bounded(monkeypatch):
    monkeypatch.setattr(llm_service.settings, 'MAX_CONVERSATION_HISTORY', 2)
    context = PersistentContextManager()
    context.add_conversation_exchange('first question', ai_response='UNVERIFIED_ASSISTANT_CLAIM')
    context.add_conversation_exchange(candidate_response='I led the payments migration.')
    context.add_conversation_exchange(candidate_response='It cut latency by 20 percent.')
    assert context.conversation_history[-1]['candidate_response'] == 'I led the payments migration. It cut latency by 20 percent.'
    for index in range(12):
        context.add_conversation_exchange(f'question {index}', candidate_response='Candidate fact ' + 'detail ' * 100, ai_response='UNVERIFIED_ASSISTANT_CLAIM')
    memory = context.persistent_context['candidate_fact_memory']
    assert len(context.conversation_history) == 2 and len(memory) == 8
    assert all(len(fact['text']) <= 600 and fact['source_id'].startswith('candidate:') for fact in memory)
    assert 'UNVERIFIED_ASSISTANT_CLAIM' not in str(memory)
    context.reset_conversation_history()
    assert not context.persistent_context['candidate_fact_memory']


@pytest.mark.parametrize('builder', [get_interview_answer_prompt, get_quick_response_prompt])
def test_evicted_candidate_excerpt_still_grounds_later_answers(monkeypatch, builder):
    monkeypatch.setattr(llm_service.settings, 'MAX_CONVERSATION_HISTORY', 2)
    context = PersistentContextManager()
    context.add_conversation_exchange('Your previous work?', candidate_response='I built a Rust optimizer.', ai_response='Invented employer claim')
    context.add_conversation_exchange('Question two')
    context.add_conversation_exchange('Question three')
    prompt = builder('Describe your Rust optimizer work', context)
    assert 'I built a Rust optimizer.' in prompt and '[candidate:1:1]' in prompt
    assert 'Invented employer claim' not in prompt


@pytest.mark.parametrize('builder', [get_interview_answer_prompt, get_quick_response_prompt])
def test_question_retrieves_tail_evidence_from_full_sources(builder):
    context = PersistentContextManager()
    context.initialize_persistent_context({
        'resume': 'General engineering background. ' * 300 + '\nLed the payments fraud migration at Acme.',
        'objectives': 'General role requirements. ' * 300 + '\nPayments fraud ownership is essential.',
        'documents': [{'name': 'Launch notes', 'text': 'General launch information. ' * 300 + '\nPayments fraud migration deadline is November 12.'}],
    })
    prompt = builder('Discuss the payments fraud migration', context)
    assert 'Led the payments fraud migration at Acme.' in prompt
    assert 'Payments fraud ownership is essential.' in prompt
    assert 'migration deadline is November 12.' in prompt
    assert '[resume:' in prompt and '[job_description:' in prompt and '[document_1:' in prompt
    assert len(prompt) < 15000


@pytest.mark.parametrize('builder', [get_interview_answer_prompt, get_quick_response_prompt])
def test_regular_call_uses_reference_documents_without_interview_rubrics(builder):
    context = PersistentContextManager()
    context.initialize_persistent_context({'session_mode': 'regular', 'documents': [{'name': 'Plan', 'text': 'The rollout deadline is November 12.'}]})
    prompt = builder('When is the rollout deadline?', context)
    assert 'live call copilot' in prompt and '[document_1:' in prompt
    assert 'The rollout deadline is November 12.' in prompt
    assert 'WHAT TO SAY OUT LOUD TO THE INTERVIEWER' not in prompt
    assert 'BEHAVIORAL / HR / RESUME TEMPLATE' not in prompt


@pytest.mark.parametrize('documents', ['bad', [{'name': 'Bad'}], [{'name': 'Bad', 'text': 42}]])
def test_documents_validate_before_mutating_context(documents):
    context = PersistentContextManager()
    with pytest.raises(ValueError, match='Documents'):
        context.initialize_persistent_context({'documents': documents})
    assert not context.is_initialized and context.persistent_context['documents'] == []
