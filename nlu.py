"""Natural Language Understanding for detecting user intents."""
import re
from enum import Enum
from typing import Optional, Tuple

class Intent(Enum):
    """User intents that can be detected from natural language."""
    CLEAR_HISTORY = "clear_history"
    SHOW_SETTINGS = "show_settings"
    SHOW_HELP = "show_help"
    CHANGE_PERSONA = "change_persona"
    CHANGE_MODEL = "change_model"
    SHOW_PLAN = "show_plan"
    UPGRADE_PLAN = "upgrade_plan"
    FEEDBACK = "feedback"
    START = "start"
    NONE = "none"

class NLUEngine:
    """Natural Language Understanding engine for intent detection."""
    
    # Intent patterns - maps regex patterns to intents
    INTENT_PATTERNS = {
        Intent.CLEAR_HISTORY: [
            r'clear.*history',
            r'delete.*history',
            r'reset.*conversation',
            r'start.*fresh',
            r'new.*conversation',
            r'wipe.*chat',
            r'forget.*history'
        ],
        Intent.SHOW_SETTINGS: [
            r'show.*settings',
            r'open.*settings',
            r'settings',
            r'my.*settings',
            r'configure',
            r'preferences'
        ],
        Intent.SHOW_HELP: [
            r'help',
            r'commands',
            r'what.*can.*do',
            r'help.*me',
            r'how.*use',
            r'instructions'
        ],
        Intent.CHANGE_PERSONA: [
            r'change.*persona',
            r'switch.*persona',
            r'different.*persona',
            r'be.*like',
            r'change.*personality',
            r'act.*like',
            r'pretend.*be'
        ],
        Intent.CHANGE_MODEL: [
            r'change.*model',
            r'switch.*model',
            r'different.*model',
            r'use.*model'
        ],
        Intent.SHOW_PLAN: [
            r'show.*plan',
            r'my.*plan',
            r'current.*plan',
            r'what.*plan',
            r'plan.*info',
            r'subscription'
        ],
        Intent.UPGRADE_PLAN: [
            r'upgrade',
            r'premium',
            r'better.*plan',
            r'get.*premium',
            r'subscribe'
        ],
        Intent.FEEDBACK: [
            r'feedback',
            r'report.*issue',
            r'bug',
            r'problem',
            r'issue.*report',
            r'suggestion'
        ],
        Intent.START: [
            r'start',
            r'begin',
            r'hello',
            r'hi'
        ]
    }
    
    @staticmethod
    def detect_intent(text: str) -> Tuple[Intent, Optional[str]]:
        """
        Detect intent from user text.
        
        Returns:
            Tuple of (Intent, extra_data)
            extra_data can be persona name, model name, etc.
        """
        text = text.lower().strip()
        
        # Try to match patterns
        for intent, patterns in NLUEngine.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    # Extract additional info if possible
                    extra = NLUEngine._extract_extra_info(text, intent)
                    return intent, extra
        
        return Intent.NONE, None
    
    @staticmethod
    def _extract_extra_info(text: str, intent: Intent) -> Optional[str]:
        """Extract additional information from text based on intent."""
        
        if intent == Intent.CHANGE_PERSONA:
            # Try to extract persona name
            personas = ['friend', 'mentor', 'therapist', 'writer', 'tech', 'romantic', 'creative', 'analyst', 'coach']
            for persona in personas:
                if persona in text:
                    return persona
        
        elif intent == Intent.CHANGE_MODEL:
            # Try to extract model name
            models = ['flash', 'pro', 'vision', 'pro-exp']
            for model in models:
                if model in text:
                    return model
        
        elif intent == Intent.UPGRADE_PLAN:
            # Try to extract plan name
            plans = ['basic', 'premium', 'vip']
            for plan in plans:
                if plan in text:
                    return plan.capitalize()
        
        return None
    
    @staticmethod
    def should_use_nl_command(text: str) -> bool:
        """Check if text is a natural language command (not just chat)."""
        intent, _ = NLUEngine.detect_intent(text)
        return intent != Intent.NONE
