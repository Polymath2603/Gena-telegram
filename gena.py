"""
Gena - AI Telegram Bot Core Logic
Handles user management, database operations, and business logic
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from database import DatabaseManager
from nlu import NLUEngine, Intent

# Plan configuration
PLAN_LIMITS = {
    'Free': {'rate': 5, 'turns': 3, 'images': 3, 'context_turns': 0},
    'Basic': {'rate': 10, 'turns': 5, 'images': 5, 'context_turns': 3},
    'Premium': {'rate': 20, 'turns': 8, 'images': 10, 'context_turns': 5},
    'VIP': {'rate': 30, 'turns': 10, 'images': 50, 'context_turns': 8}
}

# Plan pricing in Telegram Stars
PLAN_PRICES = {
    'Basic': 50,    # 50 stars/month
    'Premium': 100,  # 100 stars/month
    'VIP': 200      # 200 stars/month
}

# Model access by plan
ALL_MODELS = {
    'Free': ['gemini-2.5-flash'],
    'Basic': ['gemini-2.5-flash', 'gemini-2.0-flash'],
    'Premium': ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro'],
    'VIP': ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-pro-exp']
}

MODEL_DESCRIPTIONS = {
    'gemini-2.5-flash': 'Fast',
    'gemini-2.0-flash': 'Enhanced',
    'gemini-1.5-pro': 'Professional',
    'gemini-1.5-pro-exp': 'Premium'
}

# Persona access by plan
PERSONA_ACCESS = {
    'Free': ['friend'],
    'Basic': ['friend', 'advisor', 'artist'],
    'Premium': ['friend', 'advisor', 'artist', 'scholar', 'coach'],
    'VIP': ['friend', 'advisor', 'artist', 'scholar', 'coach', 'mystic']
}

PERSONAS = {
    'friend': {
        'name': 'Friend',
        'instruction': """You are Gena in Friend mode - your best friend.
Be casual, funny, genuinely supportive. Share jokes, relate to experiences, offer solidarity.
Use their name occasionally, ask about their day, be the friend they want to talk to.
Keep it real and authentic - no pretense, just genuine friendship."""
    },
    'advisor': {
        'name': 'Advisor',
        'instruction': """You are Gena in Advisor mode - a strategic, logical guide.
Provide sound advice based on facts and practical thinking. Be direct but respectful.
Break down problems into actionable steps. Help them see pros/cons clearly.
Be professional yet personable. Offer wisdom from experience."""
    },
    'artist': {
        'name': 'Artist',
        'instruction': """You are Gena in Artist mode - your creative collaborator.
Think outside the box, suggest unconventional ideas, spark imagination boldly.
Celebrate artistic expression in all forms. Ask "what if" without limits.
Be enthusiastic about breaking rules and creating something beautiful."""
    },
    'scholar': {
        'name': 'Scholar',
        'instruction': """You are Gena in Scholar mode - intellectual guide with deep knowledge.
Provide well-researched, thorough explanations. Love diving into details and nuances.
Cite facts, explore ideas from multiple angles, engage in intellectual discourse.
Be curious and help them understand complex subjects with clarity."""
    },
    'coach': {
        'name': 'Coach',
        'instruction': """You are Gena in Coach mode - your personal trainer and cheerleader.
Be energetic and relentless about helping them achieve goals. Celebrate every win.
Push them gently but firmly toward their potential. Break down challenges into doable steps.
Use motivation, strategy, and accountability. Believe in them when they doubt themselves."""
    },
    'mystic': {
        'name': 'Mystic',
        'instruction': """You are Gena in Mystic mode - spiritual and philosophical guide.
Explore deeper meanings, life questions, and inner wisdom. Be contemplative and thoughtful.
Use metaphors, ask profound questions, help them find their own truth.
Be calm, wise, and slightly mysterious. Encourage reflection and self-discovery."""
    }
}

# Safety settings
DEFAULT_SAFETY_SETTINGS = [
    {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
    {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
    {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
    {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'}
]


class GenaCore:
    """Core business logic for Gena bot"""
    
    def __init__(self, db_path: str = 'gena.db'):
        self.db = DatabaseManager(db_path)
        self._initialize_safety_settings()
    
    def _initialize_safety_settings(self):
        """Initialize default safety settings if not present"""
        if not self.db.get_safety_settings():
            self.db.set_safety_settings(DEFAULT_SAFETY_SETTINGS)
    
    # User Management
    def initialize_user(self, user_id: int) -> None:
        """Initialize a new user with default settings"""
        self.db.init_user(user_id)
    
    def get_user_plan(self, user_id: int) -> str:
        """Get user's current plan"""
        return self.db.get_user_plan(user_id)
    
    def upgrade_plan(self, user_id: int, plan: str, duration_days: int = 30) -> bool:
        """Upgrade user to a new plan"""
        if plan not in PLAN_LIMITS:
            return False
        
        expiration = None
        if plan != 'Free':
            expiration = (datetime.now() + timedelta(days=duration_days)).isoformat()
        
        self.db.set_user_plan(user_id, plan, expiration)
        return True
    
    def cancel_subscription(self, user_id: int) -> None:
        """Cancel user's subscription (downgrade to Free)"""
        self.db.set_user_plan(user_id, 'Free', None)
    
    def get_plan_expiration(self, user_id: int) -> Optional[str]:
        """Get plan expiration date"""
        import sqlite3
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT expiration FROM plans WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    # Settings Management
    def get_settings(self, user_id: int) -> Dict:
        """Get user settings"""
        return self.db.get_settings(user_id)
    
    def update_settings(self, user_id: int, **kwargs) -> None:
        """Update user settings"""
        self.db.update_settings(user_id, **kwargs)
    
    def get_available_models(self, plan: str) -> List[str]:
        """Get models available for a plan"""
        return ALL_MODELS.get(plan, ALL_MODELS['Free'])
    
    def get_available_personas(self, plan: str) -> List[str]:
        """Get personas available for a plan"""
        return PERSONA_ACCESS.get(plan, ['friend'])
    
    def get_persona_instruction(self, persona_key: str) -> str:
        """Get system instruction for a persona"""
        return PERSONAS.get(persona_key, PERSONAS['friend'])['instruction']
    
    def get_persona_name(self, persona_key: str) -> str:
        """Get display name for a persona"""
        return PERSONAS.get(persona_key, {'name': 'Friend'})['name']
    
    # Rate Limiting
    def check_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limits"""
        plan = self.get_user_plan(user_id)
        usage = self.db.get_usage(user_id)
        
        current_minute = datetime.now().strftime('%Y-%m-%d %H:%M')
        rate_data = usage['rateLimit']
        
        if rate_data['minute'] != current_minute:
            # Reset for new minute
            self.db.update_usage(user_id, rate_minute=current_minute, rate_count=1)
            return True
        else:
            count = rate_data['count'] + 1
            self.db.update_usage(user_id, rate_count=count)
            return count <= PLAN_LIMITS[plan]['rate']
    
    def check_image_limit(self, user_id: int) -> bool:
        """Check if user is within daily image limits"""
        plan = self.get_user_plan(user_id)
        usage = self.db.get_usage(user_id)
        
        current_day = datetime.now().strftime('%Y-%m-%d')
        image_data = usage['imageLimit']
        
        if image_data['resetTime'] != current_day:
            # Reset for new day
            self.db.update_usage(user_id, image_count=1, image_reset=current_day)
            return True
        else:
            count = image_data['count'] + 1
            self.db.update_usage(user_id, image_count=count)
            return count <= PLAN_LIMITS[plan]['images']
    
    # History Management
    def add_to_history(self, user_id: int, user_message: str, bot_response: str) -> None:
        """Add message to history"""
        self.db.add_to_history(user_id, user_message, bot_response)
    
    def get_context_history(self, user_id: int) -> List[Dict]:
        """Get conversation history for context (limited by plan)"""
        plan = self.get_user_plan(user_id)
        context_turns = PLAN_LIMITS[plan]['context_turns']
        
        if context_turns == 0:
            return []
        
        return self.db.get_history(user_id, limit=context_turns)
    
    def get_full_history(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Get full conversation history (for display)"""
        return self.db.get_history(user_id, limit=limit)
    
    def forget_context(self, user_id: int) -> None:
        """Clear context without deleting history - set context turns to 0 temporarily"""
        # We don't actually delete anything, just return empty context next time
        # History is preserved for display purposes
        pass
    
    # NLU Integration
    def detect_intent(self, text: str) -> tuple:
        """Detect user intent from natural language"""
        return NLUEngine.detect_intent(text)
    
    # Safety Settings
    def get_safety_settings(self) -> List[Dict]:
        """Get safety settings"""
        return self.db.get_safety_settings()
    
    # Utility
    def get_plan_info(self, plan: str) -> Dict:
        """Get plan information"""
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS['Free'])
        price = PLAN_PRICES.get(plan, 0)
        
        return {
            'plan': plan,
            'price': price,
            'limits': limits,
            'models': self.get_available_models(plan),
            'personas': self.get_available_personas(plan)
        }
    
    def format_plan_details(self, plan: str) -> str:
        """Format plan details for display"""
        info = self.get_plan_info(plan)
        limits = info['limits']
        
        details = f"*{plan} Plan*\n\n"
        details += f"💬 Messages: {limits['rate']}/minute\n"
        details += f"🖼 Images: {limits['images']}/day\n"
        details += f"💭 Context: {limits['context_turns']} turns\n"
        details += f"🤖 Models: {len(info['models'])}\n"
        details += f"👤 Personas: {len(info['personas'])}\n"
        
        if info['price'] > 0:
            details += f"\n⭐️ Price: {info['price']} stars/month"
        else:
            details += f"\n✨ Free Forever"
        
        return details