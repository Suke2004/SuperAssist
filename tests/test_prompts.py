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


class TestHRQuestionDifferentiation:
    def test_is_hr_or_behavioral_question_detection(self):
        from core.prompts import is_hr_or_behavioral_question

        # Questions from exp.txt and common HR questions
        assert is_hr_or_behavioral_question("1. Tell me about you self") is True
        assert is_hr_or_behavioral_question("Tell me about yourself") is True
        assert is_hr_or_behavioral_question("2. Tell me about you internship") is True
        assert is_hr_or_behavioral_question("Tell me about your internship") is True
        assert is_hr_or_behavioral_question("3. tell me what value you bring to company") is True
        assert is_hr_or_behavioral_question("What value do you bring to our team?") is True
        assert is_hr_or_behavioral_question("Why should we hire you?") is True
        assert is_hr_or_behavioral_question("What are your greatest strengths and weaknesses?") is True
        assert is_hr_or_behavioral_question("Where do you see yourself in 5 years?") is True
        assert is_hr_or_behavioral_question("Tell me about a time you had a conflict with a teammate") is True

        # Coding and technical questions should NOT match HR
        assert is_hr_or_behavioral_question("Two sum problem") is False
        assert is_hr_or_behavioral_question("Given an array of integers nums and an integer target, return indices") is False
        assert is_hr_or_behavioral_question("Implement LRU Cache") is False
        assert is_hr_or_behavioral_question("Design Twitter system architecture") is False
        assert is_hr_or_behavioral_question("What is the difference between TCP and UDP?") is False

    def test_audio_hr_prompt_includes_negative_coding_constraints(self):
        ctx = _make_context()
        prompt = get_interview_answer_prompt("Tell me about you self", ctx)
        assert "DETECTED QUESTION INTENT: HR / BEHAVIORAL / PERSONAL / BACKGROUND QUESTION" in prompt
        assert "STRICTLY DO NOT write any code blocks" in prompt
        assert "STRICTLY DO NOT mention Big-O complexity" in prompt
        assert "FORMAT A: FOR HR / INTRODUCTORY / INTERNSHIP / VALUE PROPOSITION QUESTIONS" in prompt

    def test_audio_coding_prompt_retains_coding_structure(self):
        ctx = _make_context()
        prompt = get_interview_answer_prompt("Given an array of ints, find two that sum to target", ctx)
        assert "DETECTED QUESTION INTENT" not in prompt
        assert "FOR CODING / ALGORITHM / DSA QUESTIONS" in prompt
        assert "Optimal Solution" in prompt

    def test_vision_prompt_includes_hr_template_and_prohibitions(self):
        from services.vision_service import vision_service
        ctx = _make_context(resume="Experienced full-stack engineer with React and Python internships.")
        prompt = vision_service.generate_coding_analysis_prompt(["python"], context_manager=ctx)
        
        # Must include candidate profile
        assert "Jane Doe" in prompt
        assert "Experienced full-stack engineer" in prompt

        # Must include SECTION 1 for HR questions with strict code prohibitions
        assert "SECTION 1: HR / BEHAVIORAL / INTERVIEW QUESTION ANALYSIS & RESPONSE" in prompt
        assert "DO NOT write any code blocks!" in prompt
        assert "DO NOT mention Big-O Time/Space complexity!" in prompt
        assert "Key Internship & Project Highlights" in prompt
        assert "Value Proposition & Role Fit" in prompt

        # Must also still support coding and MCQ
        assert "SECTION 2: MULTIPLE CHOICE QUESTION (MCQ) ANALYSIS" in prompt
        assert "SECTION 3: CODING / DSA PROBLEM ANALYSIS & SOLUTION" in prompt

