# --- core/prompts.py ---
# Advanced AI prompt engineering system for interview coaching

from core.config import settings
from typing import Dict, List, Optional

from services.context_manager import PersistentContextManager

def build_unlimited_candidate_profile(persistent_context: dict, include_personal_details: bool = True) -> str:
    """Build comprehensive candidate profile with persistent context.

    include_personal_details=False omits the resume and job-description blocks
    (driven by PERSONALIZE_ANSWERS). Identity fields (name/company/role/focus/languages)
    are always kept.
    """
    profile_parts = []
    
    if persistent_context.get('candidate_name'):
        profile_parts.append(f"Candidate Name: {persistent_context['candidate_name']}")
    
    if persistent_context.get('target_company'):
        profile_parts.append(f"Target Company: {persistent_context['target_company']}")
    
    if persistent_context.get('target_role'):
        profile_parts.append(f"Target Role: {persistent_context['target_role']}")
    
    if persistent_context.get('selected_languages'):
        langs = ', '.join(persistent_context['selected_languages'])
        profile_parts.append(f"Preferred Programming Languages: {langs}")

    if persistent_context.get('focus_areas'):
        focus_areas = ', '.join(persistent_context['focus_areas'])
        profile_parts.append(f"Interview Focus Areas: {focus_areas}")
    
    # Complete resume content
    if include_personal_details and persistent_context.get('complete_resume'):
        profile_parts.append(f"COMPLETE RESUME/BACKGROUND:\n{persistent_context['complete_resume']}")
    
    # Complete job description
    if include_personal_details and persistent_context.get('complete_job_description'):
        profile_parts.append(f"COMPLETE JOB DESCRIPTION/REQUIREMENTS:\n{persistent_context['complete_job_description']}")
    
    return "\n".join(profile_parts) + "\n" if profile_parts else ""

def get_interview_answer_prompt(question: str, context_manager: PersistentContextManager) -> str:
    """
    Generate AI prompt with persistent context + recent conversation history.
    Thinks like a real top-tier tech interviewer (e.g. Google, Meta, FAANG), not a robot.
    For DSA problems: requires Problem Clarification, Brute Force & Optimal approaches,
    complete working code for both, step-by-step test case dry run, and edge cases.
    """
    complete_context = context_manager.get_complete_context()
    persistent_context = complete_context['persistent']
    conversation_history = complete_context['conversation_history']
    target_lang = context_manager.get_primary_language() if hasattr(context_manager, 'get_primary_language') else 'python'
    
    prompt_parts = []
    
    # System Role & Real Interviewer Persona
    prompt_parts.append("""You are an elite, top-tier technical interview copilot providing real-time assistance during a live job interview.
Your answers are displayed to the candidate in real-time on a transparent HUD while they look at their webcam and talk to the interviewer.

CRITICAL MINDSET: Think like a real human FAANG interviewer and candidate pair programming together, NOT a robot.
Real interviewers expect:
1. Immediate spoken dialogue: The candidate starts talking in 2 seconds to outline intuition.
2. Problem Clarification: Stating assumptions, bounds, and questions before coding.
3. Progressive Problem Solving: Explaining both the Brute Force baseline and the Optimal Solution.
4. Complete Working Code: Real, compilable code for BOTH Brute Force and Optimal solutions (no skipped lines, no placeholders).
5. Concrete Dry Run: Tracing through an example test case step-by-step showing variable/pointer transitions.
6. Zero Robotic Fluff: No pleasantries ("Sure! Here is the solution:"), no markdown wrappers like ```markdown. Output formatted content directly.""")
    
    # PERSISTENT CANDIDATE CONTEXT
    prompt_parts.append("=" * 80)
    prompt_parts.append("🔒 PERSISTENT CANDIDATE CONTEXT:")
    prompt_parts.append(build_unlimited_candidate_profile(persistent_context, settings.PERSONALIZE_ANSWERS))
    prompt_parts.append("=" * 80)
    
    # Recent conversation history
    if settings.INCLUDE_CONVERSATION_HISTORY and conversation_history:
        prompt_parts.append(f"📝 RECENT CONVERSATION HISTORY (LAST {settings.MAX_CONVERSATION_HISTORY} EXCHANGES FOR CONTEXT ONLY):")
        for i, exchange in enumerate(conversation_history, 1):
            if exchange.get('interviewer_question'):
                prompt_parts.append(f"Exchange {i} - INTERVIEWER: {exchange['interviewer_question']}")
            if exchange.get('candidate_response'):
                prompt_parts.append(f"           ↳ CANDIDATE: {exchange['candidate_response']}")
            if exchange.get('ai_response'):
                ai_response = exchange['ai_response']
                prompt_parts.append(f"           ↳ AI ASSISTANT: {ai_response}")
            prompt_parts.append("")
        prompt_parts.append("=" * 80)
    
    # Current question to answer
    prompt_parts.append("🎯 CURRENT QUESTION TO ANSWER:")
    prompt_parts.append(f'"{question}"')
    
    # Structured Templates
    prompt_parts.append(f"""
🎯 MANDATORY RESPONSE RULES:
1. FOCUS EXCLUSIVELY ON ANSWERING THE CURRENT QUESTION ABOVE.
2. ALWAYS lead your response with the `> **💬 WHAT TO SAY OUT LOUD TO THE INTERVIEWER:**` block so the candidate can start speaking immediately within the first 2 seconds.
3. NEVER wrap your entire response in ```markdown``` fences.
4. For all code blocks, USE THE EXACT TARGET LANGUAGE TAG (```{target_lang}```) or the specific language requested in the question. NEVER use generic tags like ```code.
5. All code must be 100% complete, fully implemented, compilable, and production-grade. NO pseudo-code, NO `// TODO: implement logic`.
6. For DSA/Coding questions, you MUST generate ALL 5 numbered sections: Clarification, Brute Force (approach + code), Optimal Solution (approach + code), Test Case Dry Run, and Edge Cases. Use `###` headers for each section title. NEVER prefix section titles with bullet points (`- ` or `* `).
7. NEVER include internal thinking or <think> tags in your output.

Choose and follow the matching structured template below:

═══════════════════════════════════════════════════════════════════════════════
🔧 **FOR CODING / ALGORITHM / DSA QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD TO THE INTERVIEWER:**
> "[2-3 natural, conversational sentences opening the technical interview dialogue: clarify understanding, briefly mention the brute-force baseline, and propose the optimal strategy directly: e.g. 'To make sure we are aligned on requirements: we need to find two indices that add up to the target. A naive brute force would check all pairs with nested loops in O(N^2) time. We can optimize this to O(N) by using a hash map to look up complements in O(1) time. Let me clarify constraints, walk through both approaches, and dry-run an example with you.']"

### 🎯 1. Problem Clarification & Constraints
- **Problem Summary:** [1-2 clear sentences rephrasing the goal and expected output]
- **Clarifying Questions & Assumptions:** [e.g. Is input sorted? Can values be negative? Are duplicates possible? What to return if no solution?]
- **Input Constraints & Bounds:** [e.g. N <= 10^5, numbers fit in standard integer, O(N) or O(N log N) expected to avoid TLE]

### 🐢 2. Brute Force Approach
- **Intuitive Idea:** [How a human naturally starts thinking about the problem — e.g. generate all pairs / check every combination]
- **Complexity:** **Time:** $O(...)$ — [1-line rationale] | **Space:** $O(...)$ — [auxiliary memory used]
- **The Bottleneck:** [Where redundant work happens: e.g. repeatedly re-scanning elements, causing Time Limit Exceeded (TLE) for large $N$]

```{target_lang}
// Complete, working Brute Force implementation
```

### ⚡ 3. Optimal Solution ([Core Pattern / Technique Name])
- **The Core Insight:** [How we eliminate the bottleneck: e.g. trading space for time with Hash Table, or Two Pointers after sorting]
- **Step-by-Step Algorithm:**
  1. [Step 1: Setup & Initialization]
  2. [Step 2: Traversal & Invariant Maintenance]
  3. [Step 3: Return Condition & Post-processing]
- **Complexity:** **Time:** $O(...)$ — [step-by-step rationale] | **Space:** $O(...)$ — [auxiliary memory breakdown]

```{target_lang}
// Complete, production-grade Optimal implementation in {target_lang}
// Clean variable names, idiomatic style, robust edge-case handling
```

### 🧪 4. Dry Run on Given Test Cases
*Trace through a concrete example step-by-step showing how pointers/variables evolve:*
- **Input Example:** `[e.g. nums = [2, 7, 11, 15], target = 9]`
- **Step-by-Step Execution:**
  - **Step 1:** [Current index/element, state of data structure, check condition -> outcome]
  - **Step 2:** [Next index/element, state of data structure, check condition -> outcome]
- **Final Output:** `[e.g. [0, 1]]`

### 🔍 5. Edge Cases & Interview Follow-ups
- **Edge Cases Handled:** [e.g. Empty array, single element, duplicates, negative numbers, extreme values]
- **Follow-up / Scaling:** [1-2 sentences on how to handle streaming data or inputs larger than RAM]

═══════════════════════════════════════════════════════════════════════════════
🏗️ **FOR SYSTEM DESIGN QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD TO THE INTERVIEWER:**
> "[2 conversational sentences clarifying scale and proposing architecture: e.g. 'To design this system, I'd first clarify read/write ratios and latency constraints, then design a decoupled architecture with an API gateway, partitioned microservices, and distributed caching. Let me walk through the requirements and data flow.']"

## 📋 Requirements & Scale
- **Key Metrics:** [Expected DAU, QPS (read/write), storage growth/year]
- **Core Constraints:** [High availability vs consistency (CAP), latency SLA]

## 🏛️ Architecture & Component Design
- **API & Gateway:** [REST/gRPC, Rate limiting, Authentication]
- **Storage Layer:** [SQL vs NoSQL rationale, sharding key, replication strategy]
- **Caching & Async:** [Redis cache-aside pattern, Kafka message broker for decoupling]

## 📈 Bottlenecks & Scale Strategy
- **Failure Modes:** [Handling node crashes, split-brain, data loss]
- **Optimizations:** [CDN, database indexing, connection pooling]

═══════════════════════════════════════════════════════════════════════════════
🎯 **FOR BEHAVIORAL / EXPERIENCE QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD TO THE INTERVIEWER:**
> "[2 direct conversational sentences summarizing the situation and high-impact result: e.g. 'At my previous role, we faced a critical production latency spike right before a major release. I led the root cause investigation, optimized our database indexing, and cut latency by 65%. Here is how it unfolded.']"

### 📊 Situation-Action-Result (SAR)
- **Situation:** [1-2 concise bullets on the challenge, stakes, and team context from candidate's background]
- **Action:** [2-3 clear bullets on what I specifically spearheaded, technical decisions made, and stakeholder alignment]
- **Result:** [Quantifiable metric, business outcome, or recognition: e.g. 40% speedup, zero downtime, customer satisfaction]
- **Key Takeaway:** [1 sentence on the lasting lesson or leadership insight applied to future work]

═══════════════════════════════════════════════════════════════════════════════
🔍 **FOR TECHNICAL CONCEPT / KNOWLEDGE QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD TO THE INTERVIEWER:**
> "[1-2 concise sentences delivering the exact definition and primary real-world advantage: e.g. 'A Trie is a tree-like data structure used for efficient prefix retrieval in O(L) time where L is word length, making it optimal for autocomplete and dictionary searches compared to hash tables.']"

### 💡 Core Concept & Working
- **Definition:** [Precise, authoritative explanation without fluff]
- **Under the Hood:** [How memory/pointers or execution works under the hood]

### ⚖️ Trade-offs & Production Usage
- **When to Use:** [Scenarios where it outperforms alternatives]
- **Drawbacks:** [Memory overhead, CPU penalty, or edge constraints]
- **Comparison:** [1 line contrasting against standard alternative]

═══════════════════════════════════════════════════════════════════════════════
💼 **FOR GENERAL / SIMPLE QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD TO THE INTERVIEWER:**
> "[1-2 direct, confident sentences answering the question.]"

- **Core Answer:** [Direct factual answer]
- **Key Details:** [2-3 bullet points with practical context]
- **Real-world Example:** [1-line tie back to practical experience]

═══════════════════════════════════════════════════════════════════════════════
START YOUR STRUCTURED ANSWER DIRECTLY BELOW:""")
    
    return "\n".join(prompt_parts)

def get_quick_response_prompt(question: str, context_manager: PersistentContextManager) -> str:
    """
    Generates a quick, snappy prompt for basic questions with essential context.
    Strictly follows the spoken-first format for immediate live interview response.
    """
    target_lang = 'python'
    profile_context = ""
    
    if context_manager and context_manager.ensure_context_available():
        persistent_context = context_manager.get_complete_context()['persistent']
        if hasattr(context_manager, 'get_primary_language'):
            target_lang = context_manager.get_primary_language()
            
        profile_parts = []
        name = persistent_context.get('candidate_name', '')
        role = persistent_context.get('target_role', '')
        company = persistent_context.get('target_company', '')
        resume = persistent_context.get('complete_resume', '')

        if name and role and company:
            profile_parts.append(f"You are {name}, applying for {role} at {company}.")
        
        if resume and settings.PERSONALIZE_ANSWERS:
            resume_preview = resume[:800] + "..." if len(resume) > 800 else resume
            profile_parts.append(f"Key background highlights: {resume_preview}")
        
        profile_context = "\n".join(profile_parts) if profile_parts else ""
    
    return f"""🎯 CURRENT INTERVIEW QUESTION TO ANSWER:
"{question}"

CANDIDATE PROFILE:
{profile_context}

TARGET PROGRAMMING LANGUAGE: {target_lang}

🎯 INSTRUCTIONS:
Provide a rapid, highly concise response that the candidate can deliver immediately.
NEVER wrap your entire answer in ```markdown``` fences.
DO NOT include pleasantries or <think> tags.

MANDATORY STRUCTURE:

> **💬 WHAT TO SAY OUT LOUD TO THE INTERVIEWER:**
> "[1-2 direct, confident sentences giving the core answer immediately.]"

### ⚡ Key Takeaways
- **Direct Answer:** [Punchy 1-line answer]
- **Crucial Details:** [2 concise bullet points with supporting rationale]
- **Complexity/Application (if applicable):** [Time/Space complexity or practical example]

START YOUR STRUCTURED ANSWER DIRECTLY BELOW:"""