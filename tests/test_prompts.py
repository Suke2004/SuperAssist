"""Tests for prompt builders: history slicing, truncation, language resolution."""

from core.config import settings
from core.prompts import (
    build_conversation_history_block,
    get_interview_answer_prompt,
    get_quick_response_prompt,
)
from services.context_manager import PersistentContextManager


def _make_context(resume="My resume text", languages=None, exchanges=0):
    ctx = PersistentContextManager()
    ctx.initialize_persistent_context({
        "name": "Jane Doe",
        "company": "Acme",
        "role": "Backend Engineer",
        "resume": resume,
        "objectives": "Build APIs",
        "focus": ["dsa"],
        "selectedLanguages": languages or ["python"],
    })
    for i in range(exchanges):
        ctx.add_conversation_exchange(
            interviewer_question=f"Question {i}?",
            ai_response=f"Answer {i} " + "detail " * 900,
        )
    return ctx


class TestHistorySlicing:
    def test_history_is_sliced_to_max(self):
        ctx = _make_context(exchanges=10)
        block = build_conversation_history_block(ctx.conversation_history)
        # Header must match the number actually printed (old bug: printed all)
        assert f"LAST {settings.MAX_CONVERSATION_HISTORY} EXCHANGE" in block
        # Older exchanges must NOT appear
        assert "Question 0?" not in block
        assert "Question 9?" in block

    def test_long_fields_are_truncated(self):
        ctx = _make_context(exchanges=1)
        block = build_conversation_history_block(ctx.conversation_history)
        assert "…[truncated]" in block


class TestPromptBuilders:
    def test_answer_prompt_includes_context_and_question(self):
        ctx = _make_context()
        prompt = get_interview_answer_prompt("Explain two sum", ctx)
        assert "Jane Doe" in prompt
        assert "Explain two sum" in prompt
        # Templates are embedded for routing
        assert "CODING / ALGORITHM / DSA" in prompt
        assert "SYSTEM DESIGN" in prompt
        assert "BEHAVIORAL" in prompt

    def test_personalization_toggle_removes_resume(self):
        ctx = _make_context(resume="SECRET-RESUME-MARKER")
        settings.PERSONALIZE_ANSWERS = False
        try:
            prompt = get_interview_answer_prompt("What is a heap?", ctx)
        finally:
            settings.PERSONALIZE_ANSWERS = True
        assert "SECRET-RESUME-MARKER" not in prompt

    def test_quick_prompt_works_with_partial_profile(self):
        ctx = PersistentContextManager()
        ctx.initialize_persistent_context({"name": "Solo Name"})
        prompt = get_quick_response_prompt("Why is quicksort O(n log n)?", ctx)
        assert "Solo Name" in prompt
        assert "Why is quicksort O(n log n)?" in prompt

    def test_none_context_manager_degrades_gracefully(self):
        prompt = get_interview_answer_prompt("Reverse a string", None)
        assert "Reverse a string" in prompt


class TestLanguageResolution:
    def test_cpp_selected(self):
        ctx = _make_context(languages=["C++"])
        assert ctx.get_primary_language() == "cpp"

    def test_unknown_language_without_substring_collision_defaults_to_python(self):
        # Note: get_primary_language falls back to substring matching, so a name
        # containing e.g. 'c' would map to 'c'. Use a collision-free fake name.
        ctx = _make_context(languages=["XYZZYlang"])
        assert ctx.get_primary_language() == "python"
