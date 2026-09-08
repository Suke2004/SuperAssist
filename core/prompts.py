# --- core/prompts.py ---
# Advanced AI prompt engineering system for interview coaching

from core.config import settings
from typing import Dict, List, Optional

from services.context_manager import PersistentContextManager

def build_unlimited_candidate_profile(persistent_context: dict, include_personal_details: bool = True) -> str:
    """Build comprehensive candidate profile with UNLIMITED content.

    include_personal_details=False omits the resume and job-description blocks
    (driven by PERSONALIZE_ANSWERS). Identity fields (name/company/role/focus)
    are always kept.
    """
    profile_parts = []
    
    if persistent_context.get('candidate_name'):
        profile_parts.append(f"Candidate Name: {persistent_context['candidate_name']}")
    
    if persistent_context.get('target_company'):
        profile_parts.append(f"Target Company: {persistent_context['target_company']}")
    
    if persistent_context.get('target_role'):
        profile_parts.append(f"Target Role: {persistent_context['target_role']}")
    
    if persistent_context.get('focus_areas'):
        focus_areas = ', '.join(persistent_context['focus_areas'])
        profile_parts.append(f"Interview Focus Areas: {focus_areas}")
    
    # UNLIMITED: Complete resume content
    if include_personal_details and persistent_context.get('complete_resume'):
        profile_parts.append(f"COMPLETE RESUME/BACKGROUND:\n{persistent_context['complete_resume']}")
    
    # UNLIMITED: Complete job description
    if include_personal_details and persistent_context.get('complete_job_description'):
        profile_parts.append(f"COMPLETE JOB DESCRIPTION/REQUIREMENTS:\n{persistent_context['complete_job_description']}")
    
    return "\n".join(profile_parts) + "\n" if profile_parts else ""

def get_interview_answer_prompt(question: str, context_manager: PersistentContextManager) -> str:
    """
    Generate AI prompt with guaranteed persistent context + recent conversation history.
    NO TOKEN LIMITS - includes complete resume and job description.
    """
    
    complete_context = context_manager.get_complete_context()
    persistent_context = complete_context['persistent']
    conversation_history = complete_context['conversation_history']
    
    prompt_parts = []
    
    # System role instructions
    prompt_parts.append("""You are an expert interview coach providing real-time assistance during a live job interview.
Your goal is to help the candidate give the best possible answer to the interviewer's question.

COMPREHENSIVE TECHNICAL INTERVIEW GUIDELINES:

FOR CODING/ALGORITHM QUESTIONS:
- Start with brief problem understanding and clarification
- Provide intuitive explanation of the approach first
- Give at least 2 different solutions when applicable (brute force → optimized)
- Write clean, working code in the EXACT programming language specified
- Include time and space complexity analysis for each approach
- Explain the thought process and why you chose each approach
- Add comments in code for clarity
- Mention edge cases and how to handle them

FOR DATA STRUCTURES & ALGORITHMS (DSA):
- Explain which data structure/algorithm fits best and why
- Discuss trade-offs between different approaches
- Provide complexity analysis (Big O notation)
- Include implementation details and optimizations
- Mention real-world applications where this would be useful

FOR SYSTEM DESIGN QUESTIONS:
- Start with requirements gathering and clarification
- Design high-level architecture first, then dive into components
- Discuss scalability, reliability, and performance considerations
- Choose appropriate databases, caching strategies, load balancing
- Address bottlenecks and how to handle them
- Include technology stack recommendations with justifications
- Discuss monitoring, logging, and deployment strategies

FOR TECHNICAL Q&A/CONCEPTS:
- Provide clear, precise definitions
- Explain use cases and practical applications
- Compare with alternatives (pros/cons)
- Give real-world examples from your experience
- Mention best practices and common pitfalls
- Include relevant technologies and frameworks

FOR API DESIGN QUESTIONS:
- Follow RESTful principles and industry standards
- Design proper URL structure and HTTP methods
- Include request/response examples with JSON schemas
- Discuss authentication, authorization, and security
- Address versioning, rate limiting, and error handling
- Consider scalability and performance optimizations

FOR FRONTEND/BACKEND TECHNICAL QUESTIONS:
- Mention specific frameworks, libraries, and tools
- Discuss performance optimizations and best practices
- Include code examples when relevant
- Address cross-browser compatibility, responsive design (frontend)
- Discuss security, databases, and architecture patterns (backend)

GENERAL APPROACH:
- Always be authentic and use real experiences from the candidate's background
- Structure answers clearly with logical flow
- Be concise but comprehensive - avoid unnecessary fluff
- Show depth of knowledge while remaining practical
- Demonstrate problem-solving thinking process""")
    
    # PERSISTENT CANDIDATE CONTEXT - Always present, never removed
    prompt_parts.append("=" * 100)
    prompt_parts.append("🔒 PERSISTENT CANDIDATE CONTEXT (ALWAYS PRESENT - NEVER REMOVED):")
    prompt_parts.append(build_unlimited_candidate_profile(persistent_context, settings.PERSONALIZE_ANSWERS))
    prompt_parts.append("=" * 100)
    
    # Recent conversation history (limited to MAX_CONVERSATION_HISTORY exchanges)
    if settings.INCLUDE_CONVERSATION_HISTORY and conversation_history:
        prompt_parts.append(f"📝 RECENT CONVERSATION HISTORY (LAST {settings.MAX_CONVERSATION_HISTORY} EXCHANGES FOR CONTEXT):")
        for i, exchange in enumerate(conversation_history, 1):
            if exchange.get('interviewer_question'):
                prompt_parts.append(f"Exchange {i} - INTERVIEWER: {exchange['interviewer_question']}")
            if exchange.get('candidate_response'):
                prompt_parts.append(f"           ↳ CANDIDATE: {exchange['candidate_response']}")
            if exchange.get('ai_response'):
                # Include full AI response for complete context
                ai_response = exchange['ai_response']
                prompt_parts.append(f"           ↳ AI ASSISTANT: {ai_response}")
            prompt_parts.append("")
        prompt_parts.append("=" * 100)
    
    # Current question to answer
    prompt_parts.append("🎯 CURRENT QUESTION TO ANSWER:")
    prompt_parts.append(f'"{question}"')
    
    # Enhanced Instructions with comprehensive markdown formatting
    prompt_parts.append("""
🎯 RESPONSE INSTRUCTIONS:
- FOCUS ONLY ON THE CURRENT QUESTION ABOVE
- Use the COMPLETE candidate background from the persistent context only if required (full resume and job description)
- The conversation history is for context only - don't re-answer previous questions
- Be authentic and specific using the candidate's REAL experience and projects
- Write as if you ARE the candidate speaking directly to the interviewer

📝 MANDATORY STRUCTURED MARKDOWN FORMATTING:
- You MUST format your response using proper markdown structure. Choose the appropriate template based on question type:
- IMPORTANT: Do not include ```markdown``` in your response anywhere as it breaks the formatting.
═══════════════════════════════════════════════════════════════════════════════════════

🔧 **FOR CODING/ALGORITHM/DSA QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD:**
> "[2-3 clear conversational sentences explaining intuition and strategy directly to the interviewer: e.g. 'We can solve this using two pointers in O(N) time and O(1) space. We initialize pointers at both boundaries and advance inward based on the condition. Let me implement this now.']"

### ⚡ Optimal Solution ([Core Technique Name])
- **Time Complexity:** O(...) — [1-line rationale]
- **Space Complexity:** O(...) — [1-line rationale]
- **Core Pattern:** [e.g. Two Pointers / Sliding Window / Monotonic Stack / Dynamic Programming]

```language
// Production-ready implementation in candidate's target language
// Professional, natural comments (NO emojis or AI-like headers inside code blocks)
// Clean naming and direct edge-case handling
```

### 🔍 Key Edge Cases & Interview Follow-ups
- **Edge Cases:** [2-3 quick bullets to mention aloud to the interviewer: e.g. empty input, single element, duplicates]
- **Trade-off vs Naive:** [1-2 sentences comparing with brute force and why this optimal approach was selected]

═══════════════════════════════════════════════════════════════════════════════════════

🏗️ **FOR SYSTEM DESIGN QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD:**
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

═══════════════════════════════════════════════════════════════════════════════════════

🎯 **FOR BEHAVIORAL/EXPERIENCE QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD:**
> "[2 direct conversational sentences summarizing the situation and high-impact result: e.g. 'At my previous role, we faced a critical production latency spike right before a major release. I led the root cause investigation, optimized our database indexing, and cut latency by 65%. Here is how it unfolded.']"

### 📊 Situation-Action-Result (SAR)
- **Situation:** [1-2 concise bullets on the challenge, stakes, and team context]
- **Action:** [2-3 clear bullets on what I specifically spearheaded, technical decisions made, and stakeholder alignment]
- **Result:** [Quantifiable metric, business outcome, or recognition: e.g. 40% speedup, zero downtime, customer satisfaction]
- **Key Takeaway:** [1 sentence on the lasting lesson or leadership insight applied to future work]

═══════════════════════════════════════════════════════════════════════════════════════

🔍 **FOR TECHNICAL CONCEPT/KNOWLEDGE QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD:**
> "[1-2 concise sentences delivering the exact definition and primary real-world advantage: e.g. 'A Trie is a tree-like data structure used for efficient prefix retrieval in O(L) time where L is word length, making it optimal for autocomplete and dictionary searches compared to hash tables.']"

### 💡 Core Concept & Working
- **Definition:** [Precise, authoritative explanation without fluff]
- **Under the Hood:** [How memory/pointers or execution works under the hood]

### ⚖️ Trade-offs & Production Usage
- **When to Use:** [Scenarios where it outperforms alternatives]
- **Drawbacks:** [Memory overhead, CPU penalty, or edge constraints]
- **Comparison:** [1 line contrasting against standard alternative]

═══════════════════════════════════════════════════════════════════════════════════════

💼 **FOR GENERAL/SIMPLE QUESTIONS:**

> **💬 WHAT TO SAY OUT LOUD:**
> "[1-2 direct, confident sentences directly answering the question.]"

- **Core Answer:** [Direct factual answer]
- **Key Details:** [2-3 bullet points with practical context]
- **Real-world Example:** [1-line tie back to practical experience]

═══════════════════════════════════════════════════════════════════════════════════════

**CRITICAL FORMATTING RULES:**
1. **Always lead EVERY answer with the `> **💬 WHAT TO SAY OUT LOUD:**` block** so the candidate can start speaking immediately within the first 2 seconds.
2. **Provide only the optimal production solution directly** (no duplicate brute-force code blocks).
3. **NEVER use emojis inside code blocks or code comments** — keep code looking 100% human-written, clean, and production-grade.
4. **Use bullet points and bold keywords** for sub-second scanning while maintaining webcam eye contact.
5. **Keep responses tight, punchy, and concise** — eliminate academic fluff and lengthy essays so answers stream in seconds.

ALWAYS choose the most appropriate template above and format your response accordingly.

**COMPLETE STRUCTURED MARKDOWN ANSWER TO THE CURRENT QUESTION:**""")
    
    return "\n".join(prompt_parts)

def get_quick_response_prompt(question: str, context_manager: PersistentContextManager) -> str:
    """
    Generates a quick, simple prompt for basic questions with essential context.
    Uses the persistent context manager to access full candidate data.
    """
    if not context_manager or not context_manager.ensure_context_available():
        return f"""Interview question: "{question}"

📝 FORMATTING REQUIREMENT:
Format your response in clear markdown structure:

## 🎯 [Brief Topic Summary]
[Your main answer here]

### 💡 Key Points
- Important detail 1
- Important detail 2
- Supporting context

Give a brief, professional answer.

**STRUCTURED ANSWER:**"""
    
    persistent_context = context_manager.get_complete_context()['persistent']
    
    # Build basic profile from persistent context
    profile_parts = []
    name = persistent_context.get('candidate_name', '')
    role = persistent_context.get('target_role', '')
    company = persistent_context.get('target_company', '')
    resume = persistent_context.get('complete_resume', '')

    if name and role and company:
        profile_parts.append(f"You are {name}, applying for {role} at {company}.")
    
    # Include key resume highlights (a snippet for quick reference)
    if resume and settings.PERSONALIZE_ANSWERS:
        resume_preview = resume[:1200] + "..." if len(resume) > 1200 else resume
        profile_parts.append(f"Key background highlights: {resume_preview}")
    
    profile_context = "\n".join(profile_parts) if profile_parts else ""
    
    return f"""🎯 CURRENT INTERVIEW QUESTION TO ANSWER:
"{question}"

CANDIDATE PROFILE:
{profile_context}

🎯 INSTRUCTIONS:
Give a professional, brief answer to the CURRENT QUESTION above. Draw from your actual background and projects. Be specific and authentic.

📝 MANDATORY FORMATTING REQUIREMENT:
Format your response using clear markdown structure for easy reading:

## 🎯 [Brief Answer Summary]
[Your main response to the question]

### 💡 Key Details
- **Important Point 1:** Brief explanation
- **Important Point 2:** Supporting detail  
- **Relevant Experience:** Quick example from your background

### 🔗 Why This Matters
Brief connection to the role or how this demonstrates your fit.

**STRUCTURED BRIEF ANSWER:**"""

# Removed manual question categorization - AI now handles this intelligently