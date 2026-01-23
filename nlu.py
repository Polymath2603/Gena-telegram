"""
Natural Language Understanding for detecting user intents
"""
import re
from enum import Enum
from typing import Optional, Tuple


class Intent(Enum):
    """User intents that can be detected from natural language"""
    CLEAR_HISTORY = "clear_history"
    SHOW_SETTINGS = "show_settings"
    SHOW_HELP = "show_help"
    CHANGE_PERSONA = "change_persona"
    CHANGE_MODEL = "change_model"
    NONE = "none"


class NLUEngine:
    """Natural Language Understanding engine for intent detection"""
    
    INTENT_PATTERNS = {
        Intent.CLEAR_HISTORY: [
            r'clear.*context',
            r'forget.*context',
            r'reset.*context',
            r'clear.*history',
            r'forget.*history',
            r'start.*fresh',
            r'new.*conversation'
        ],
        Intent.SHOW_SETTINGS: [
            r'show.*settings',
            r'open.*settings',
            r'^settings$',
            r'my.*settings',
            r'preferences'
        ],
        Intent.SHOW_HELP: [
            r'^help$',
            r'commands',
            r'what.*can.*do',
            r'how.*use'
        ],
        Intent.CHANGE_PERSONA: [
            r'change.*persona',
            r'switch.*persona',
            r'different.*persona',
            r'change.*personality'
        ],
        Intent.CHANGE_MODEL: [
            r'change.*model',
            r'switch.*model',
            r'use.*model'
        ]
    }
    
    @staticmethod
    def detect_intent(text: str) -> Tuple[Intent, Optional[str]]:
        """
        Detect intent from user text
        
        Returns:
            Tuple of (Intent, extra_data)
        """
        text = text.lower().strip()
        
        for intent, patterns in NLUEngine.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    extra = NLUEngine._extract_extra_info(text, intent)
                    return intent, extra
        
        return Intent.NONE, None
    
    @staticmethod
    def _extract_extra_info(text: str, intent: Intent) -> Optional[str]:
        """Extract additional information based on intent"""
        
        if intent == Intent.CHANGE_PERSONA:
            personas = ['friend', 'advisor', 'artist', 'scholar', 'coach', 'mystic']
            for persona in personas:
                if persona in text:
                    return persona
        
        elif intent == Intent.CHANGE_MODEL:
            models = ['flash', 'pro']
            for model in models:
                if model in text:
                    return model
        
        return None