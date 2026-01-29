"""
Gena - AI Telegram Bot Core Logic
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from database import DatabaseManager
from nlu import NLUEngine
from personas import get_available_personas, get_persona_instruction, get_persona_name

# Plan configuration
PLAN_LIMITS = {
    'Free': {'rate': 5, 'turns': 3, 'images': 3, 'context_turns': 3, 'custom_instruction': False},
    'Basic': {'rate': 10, 'turns': 5, 'images': 5, 'context_turns': 5, 'custom_instruction': False},
    'Premium': {'rate': 20, 'turns': 8, 'images': 10, 'context_turns': 8, 'custom_instruction': True},
    'VIP': {'rate': 30, 'turns': 10, 'images': 20, 'context_turns': 10, 'custom_instruction': True}
}

PLAN_PRICES = {
    'Basic': 50,
    'Premium': 100,
    'VIP': 200
}

ALL_MODELS = {
    'Free': ['gemini-2.5-flash'],
    'Basic': ['gemini-2.5-flash', 'gemini-2.0-flash'],
    'Premium': ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro'],
    'VIP': ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-pro-exp']
}

MODEL_DESCRIPTIONS = {
    'gemini-2.5-flash': 'Fast ⚡',
    'gemini-2.0-flash': 'Enhanced 🚀',
    'gemini-1.5-pro': 'Pro 💎',
    'gemini-1.5-pro-exp': 'Premium 👑'
}

DEFAULT_SAFETY_SETTINGS = [
    {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
    {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
    {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
    {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'}
]


class GenaCore:
    """Core business logic"""
    
    def __init__(self, db_path: str = 'data/database.db'):
        self.db = DatabaseManager(db_path)
        self._initialize_safety_settings()
    
    def _initialize_safety_settings(self):
        if not self.db.get_safety_settings():
            self.db.set_safety_settings(DEFAULT_SAFETY_SETTINGS)
    
    def initialize_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> None:
        """Initialize or update user record with separate name fields"""
        self.db.init_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
    )
    
    def get_user_info(self, user_id: int) -> Dict:
        return self.db.get_user_info(user_id)
    
    def get_user_plan(self, user_id: int) -> str:
        return self.db.get_user_plan(user_id)
    
    def upgrade_plan(self, user_id: int, plan: str, duration_days: int = 30) -> bool:
        if plan not in PLAN_LIMITS:
            return False
        
        expiration = None
        if plan != 'Free':
            expiration = (datetime.now() + timedelta(days=duration_days)).isoformat()
        
        self.db.set_user_plan(user_id, plan, expiration)
        return True
    
    def cancel_subscription(self, user_id: int) -> None:
        self.db.set_user_plan(user_id, 'Free', None)
    
    def get_plan_expiration(self, user_id: int) -> Optional[str]:
        return self.db.get_plan_expiration(user_id)
    
    def get_settings(self, user_id: int) -> Dict:
        return self.db.get_settings(user_id)
    
    def update_settings(self, user_id: int, **kwargs) -> None:
        self.db.update_settings(user_id, **kwargs)
    
    def get_available_models(self, plan: str) -> List[str]:
        return ALL_MODELS.get(plan, ALL_MODELS['Free'])
    
    def get_available_personas(self, plan: str) -> List[str]:
        return get_available_personas(plan)
    
    def get_persona_instruction(self, persona_key: str) -> str:
        return get_persona_instruction(persona_key)
    
    def get_persona_name(self, persona_key: str) -> str:
        return get_persona_name(persona_key)
    
    def has_custom_instruction(self, user_id: int) -> bool:
        plan = self.get_user_plan(user_id)
        return PLAN_LIMITS[plan]['custom_instruction']
    
    def build_system_instruction(self, user_id: int, persona_key: str) -> str:
        """Build complete system instruction with persona + custom instruction"""
        user_info = self.get_user_info(user_id)
        first_name = user_info.get('first_name') or 'friend'
        
        # Base persona instruction
        instruction = get_persona_instruction(persona_key)
        
        # Add name context - use first name only
        instruction += f"\n\nThe user's first name is {first_name}. Use this name naturally in conversation (not too often, just when it feels right)."
        
        # Add custom instruction if available
        if self.has_custom_instruction(user_id):
            settings = self.get_settings(user_id)
            custom = settings.get('customInstruction', '').strip()
            if custom:
                instruction += f"\n\nAdditional user preferences:\n{custom}"
        
        return instruction
    
    def check_rate_limit(self, user_id: int) -> bool:
        plan = self.get_user_plan(user_id)
        usage = self.db.get_usage(user_id)
        
        current_minute = datetime.now().strftime('%Y-%m-%d %H:%M')
        rate_data = usage['rateLimit']
        
        if rate_data['minute'] != current_minute:
            self.db.update_usage(user_id, rate_minute=current_minute, rate_count=1)
            return True
        else:
            count = rate_data['count'] + 1
            self.db.update_usage(user_id, rate_count=count)
            return count <= PLAN_LIMITS[plan]['rate']
    
    def check_image_limit(self, user_id: int) -> bool:
        plan = self.get_user_plan(user_id)
        usage = self.db.get_usage(user_id)
        
        current_day = datetime.now().strftime('%Y-%m-%d')
        image_data = usage['imageLimit']
        
        if image_data['resetTime'] != current_day:
            self.db.update_usage(user_id, image_count=1, image_reset=current_day)
            return True
        else:
            count = image_data['count'] + 1
            self.db.update_usage(user_id, image_count=count)
            return count <= PLAN_LIMITS[plan]['images']
    
    def add_message(self, user_id: int, role: str, content: str, media_id: int = None) -> None:
        self.db.add_message(user_id, role, content, media_id)
    
    def add_media(self, user_id: int, file_id: str, file_path: str, mime_type: str, file_size: int) -> int:
        return self.db.add_media(user_id, file_id, file_path, mime_type, file_size)
    
    def get_context_history(self, user_id: int) -> List[Dict]:
        plan = self.get_user_plan(user_id)
        context_turns = PLAN_LIMITS[plan]['context_turns']
        
        if context_turns == 0:
            return []
        
        return self.db.get_history(user_id, limit=context_turns)
    
    def get_full_history(self, user_id: int, limit: int = 100) -> List[Dict]:
        return self.db.get_history(user_id, limit=limit)
    
    def forget_context(self, user_id: int) -> None:
        pass  # Context is automatically limited by plan
    
    def detect_intent(self, text: str) -> tuple:
        return NLUEngine.detect_intent(text)
    
    def get_safety_settings(self) -> List[Dict]:
        return self.db.get_safety_settings()
    
    def get_plan_info(self, plan: str) -> Dict:
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
        info = self.get_plan_info(plan)
        limits = info['limits']
        
        details = f"💬 Messages: *{limits['rate']}/minute*\n"
        details += f"🖼 Images: *{limits['images']}/day*\n"
        details += f"💭 Context: *{limits['context_turns']} turns*\n"
        details += f"🤖 Models: *{len(info['models'])}*\n"
        details += f"👤 Personas: *{len(info['personas'])}*\n"
        
        if limits['custom_instruction']:
            details += f"✏️ Custom Instructions: *Yes*\n"
        
        if info['price'] > 0:
            details += f"\n⭐ *{info['price']} stars/month*"
        else:
            details += f"\n✨ *Free Forever*"
        
        return details