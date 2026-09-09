from datetime import datetime
from core.config import settings
import re

def filter_thinking_content(content: str) -> str:
    """Filter out thinking content enclosed in <think> tags from AI responses."""
    if not content or not isinstance(content, str):
        return content
    
    # Remove content between <think> and </think> tags (case insensitive, multiline)
    thinking_regex = r'<think\s*>[\s\S]*?</think\s*>'
    filtered_content = re.sub(thinking_regex, '', content, flags=re.IGNORECASE)
    
    # Clean up any extra whitespace or newlines left behind
    filtered_content = re.sub(r'\n\s*\n\s*\n', '\n\n', filtered_content).strip()
    
    return filtered_content

class PersistentContextManager:
    """
    Manages persistent candidate context that is ALWAYS present in AI prompts.
    No token limits - includes complete resume and job description.
    """
    
    def __init__(self):
        self.persistent_context = {
            'candidate_name': '',
            'target_company': '',
            'target_role': '',
            'complete_resume': '',        # UNLIMITED - Full resume
            'complete_job_description': '',  # UNLIMITED - Full job description
            'focus_areas': [],
            'selected_languages': [],
            'additional_context': {},
            'created_at': None
        }
        self.conversation_history = []  # Limited to MAX_CONVERSATION_HISTORY exchanges
        self.is_initialized = False
    
    def initialize_persistent_context(self, onboarding_data: dict):
        """Initialize persistent context from onboarding data - called once per interview"""
        languages = onboarding_data.get('selectedLanguages', []) or onboarding_data.get('selected_languages', [])
        if isinstance(languages, str):
            languages = [languages]
            
        self.persistent_context.update({
            'candidate_name': onboarding_data.get('name', ''),
            'target_company': onboarding_data.get('company', ''),
            'target_role': onboarding_data.get('role', ''),
            'complete_resume': onboarding_data.get('resume', ''),  # FULL CONTENT
            'complete_job_description': onboarding_data.get('objectives', ''),  # FULL CONTENT
            'focus_areas': onboarding_data.get('focus', []),
            'selected_languages': languages,
            'created_at': datetime.now().isoformat()
        })
        self.is_initialized = True
        print(f"✅ Persistent context initialized with full resume ({len(self.persistent_context['complete_resume'])} chars), languages: {languages}")
    
    def add_conversation_exchange(self, interviewer_question: str = None, candidate_response: str = None, ai_response: str = None):
        """Add conversation exchange - deduplicating questions and limited to MAX_CONVERSATION_HISTORY most recent"""
        
        # Filter thinking content from AI response
        filtered_ai_response = filter_thinking_content(ai_response) if ai_response else ai_response
        
        # If we are only getting an AI response, update the last exchange.
        if interviewer_question is None and ai_response and self.conversation_history:
            self.conversation_history[-1]['ai_response'] = filtered_ai_response
            return
        # If we are only getting a candidate response, add it to the last exchange.
        elif interviewer_question is None and candidate_response and self.conversation_history:
            self.conversation_history[-1]['candidate_response'] = candidate_response
            return
        
        # If the last exchange was for the EXACT SAME question (e.g. retry or fallback), update it instead of duplicating
        if interviewer_question and self.conversation_history and self.conversation_history[-1].get('interviewer_question') == interviewer_question:
            if candidate_response:
                self.conversation_history[-1]['candidate_response'] = candidate_response
            if filtered_ai_response:
                self.conversation_history[-1]['ai_response'] = filtered_ai_response
            return

        exchange = {
            'interviewer_question': interviewer_question,
            'candidate_response': candidate_response,
            'ai_response': filtered_ai_response,
            'timestamp': datetime.now().isoformat()
        }
        self.conversation_history.append(exchange)

        # Keep only last MAX_CONVERSATION_HISTORY exchanges
        max_history = getattr(settings, 'MAX_CONVERSATION_HISTORY', 5) or 5
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]
    
    def add_ai_response(self, ai_response: str, response_type: str = "normal"):
        """Add AI response to conversation history"""
        # Prefix vision analysis responses to distinguish them
        if response_type == "vision":
            ai_response = f"[VISION ANALYSIS] {ai_response}"
        
        # Filter out thinking content
        filtered_ai_response = filter_thinking_content(ai_response)
        
        # Add to the last exchange if it exists, otherwise create a new one
        if self.conversation_history:
            self.conversation_history[-1]['ai_response'] = filtered_ai_response
        else:
            # Create a new exchange with just the AI response
            exchange = {
                'interviewer_question': None,
                'candidate_response': None,
                'ai_response': filtered_ai_response,
                'timestamp': datetime.now().isoformat()
            }
            self.conversation_history.append(exchange)
        
        # Keep only last MAX_CONVERSATION_HISTORY exchanges
        max_history = settings.MAX_CONVERSATION_HISTORY
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]
        
        print(f"✅ AI response added to conversation history (type: {response_type}, total exchanges: {len(self.conversation_history)})")
    
    def get_complete_context(self) -> dict:
        """Return complete context - persistent + conversation history"""
        return {
            'persistent': self.persistent_context,
            'conversation_history': self.conversation_history,
            'context_stats': {
                'resume_length': len(self.persistent_context['complete_resume']),
                'job_desc_length': len(self.persistent_context['complete_job_description']),
                'conversation_exchanges': len(self.conversation_history),
                'is_initialized': self.is_initialized
            }
        }
    
    def get_primary_language(self) -> str:
        """
        Resolve the candidate's primary programming language identifier for markdown code fences.
        Returns a normalized tag (e.g. 'cpp', 'python', 'java', 'javascript', 'typescript', 'go', 'rust').
        """
        # 1. Check explicitly selected languages
        selected = self.persistent_context.get('selected_languages', [])
        candidates = []
        if isinstance(selected, list):
            candidates.extend(selected)
        elif isinstance(selected, str):
            candidates.append(selected)

        # 2. Check focus areas
        focus = self.persistent_context.get('focus_areas', [])
        if isinstance(focus, list):
            candidates.extend(focus)

        # Normalize lookup map
        lang_map = {
            'c++': 'cpp',
            'cpp': 'cpp',
            'python': 'python',
            'py': 'python',
            'java': 'java',
            'javascript': 'javascript',
            'js': 'javascript',
            'typescript': 'typescript',
            'ts': 'typescript',
            'go': 'go',
            'golang': 'go',
            'rust': 'rust',
            'rs': 'rust',
            'c#': 'csharp',
            'csharp': 'csharp',
            'cs': 'csharp',
            'c': 'c',
            'sql': 'sql',
            'ruby': 'ruby',
            'swift': 'swift',
            'kotlin': 'kotlin'
        }

        for item in candidates:
            if not item or not isinstance(item, str):
                continue
            cleaned = item.strip().lower()
            if cleaned in lang_map:
                return lang_map[cleaned]
            for key, val in lang_map.items():
                if key in cleaned:
                    return val

        # Fallback default for technical interviews
        return 'python'

    def ensure_context_available(self) -> bool:
        """Verify persistent context is available, defaulting gracefully if not explicitly initialized."""
        if not self.is_initialized:
            self.is_initialized = True
        if not self.persistent_context.get('candidate_name'):
            self.persistent_context['candidate_name'] = 'Candidate'
        return True

    def reset_conversation_history(self):
        """Resets the conversation history."""
        self.conversation_history = []
        print("🔄 Conversation history reset")