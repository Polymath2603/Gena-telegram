import os
import json
import base64
import asyncio
import mimetypes
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, AsyncIterator
from dotenv import load_dotenv
import httpx
import aiofiles
from personas import PERSONAS, get_available_personas, get_persona_instruction, get_persona_name
from database import DatabaseManager
from nlu import NLUEngine, Intent
from telegram import (
    Update, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    LabeledPrice,
    InputFile,
    InputMediaPhoto,
    InputMediaVideo,
    Message
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes
)

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
ADMIN_USER_IDS = [id.strip() for id in os.getenv('ADMIN_USER_IDS', '').split(',') if id.strip()]
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 5 * 1024 * 1024))  # 5MB
PROVIDER_TOKEN = os.getenv('PROVIDER_TOKEN', '')

# Validate environment variables
if not all([TELEGRAM_TOKEN, GEMINI_API_KEY, ADMIN_USER_IDS]):
    raise ValueError('Missing required environment variables (TELEGRAM_TOKEN, GEMINI_API_KEY, ADMIN_USER_IDS)')

# Gemini configuration - Plan-based model access
FREE_MODELS = ['gemini-2.5-flash']
GEMINI_MODEL = 'gemini-2.5-flash'

# All available models
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

# MIME types and extensions
ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
EXTENSION_TO_MIME = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
    '.heic': 'image/heic',
    '.heif': 'image/heif'
}

# Plan limits
PLAN_LIMITS = {
    'Free': {'rate': 5, 'turns': 3, 'images': 3},
    'Basic': {'rate': 10, 'turns': 5, 'images': 5},
    'Premium': {'rate': 20, 'turns': 8, 'images': 10},
    'VIP': {'rate': 30, 'turns': 10, 'images': 50}
}

# Default system instruction
DEFAULT_SYSTEM_INSTRUCTION = """You are Gena, a sweet and kind-hearted friend that people can trust for anything, anytime. 

Your core traits:
- Always supportive and encouraging (genuine, never cringey)
- Naturally funny and witty with good humor
- Genuinely helpful and eager to assist
- Warm and empathetic in your responses
- Positive and uplifting in your outlook
- Casual and friendly in your tone

Communication style:
- Use moderate emojis (occasional, not excessive)
- Keep responses concise and natural (1-4 sentences usually, but vary based on context)
- Ask follow-up questions sometimes to show genuine interest
- Remember and reference details from the conversation
- Use the user's name occasionally when it feels natural
- Offer helpful suggestions and advice when appropriate

Topics and boundaries:
- Avoid: explicit sexual content, violence/gore, dark humor, political/religious debates, controversial topics, illegal activities, self-harm discussion
- Instead, gently redirect to positive topics or offer supportive guidance

Be authentic, warm, and genuinely present in the conversation. Think of yourself as the friend people want to talk to."""

# Safety settings
DEFAULT_SAFETY_SETTINGS = [
    {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
    {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
    {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
    {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'}
]

# Error messages
ERROR_MESSAGES = {
    'RATE_LIMIT_EXCEEDED': 'You have exceeded your rate limit. Please try again later.',
    'IMAGE_LIMIT_EXCEEDED': 'You have reached your daily image limit.',
    'INVALID_MODEL': f"Invalid model selected. Available models: {', '.join(FREE_MODELS)}",
    'NOT_AUTHORIZED': 'You are not authorized to use this command.'
}

class UserManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def get_user_dir(self, user_id: int) -> Path:
        return self.base_dir / 'data' / 'users' / str(user_id)

    async def read_json_file(self, file_path: Path) -> dict:
        try:
            async with aiofiles.open(file_path, 'r') as f:
                return json.loads(await f.read())
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            print(f"Error reading {file_path}: {e}")
            return None

    async def write_json_file(self, file_path: Path, data: dict) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, 'w') as f:
            await f.write(json.dumps(data, indent=2))

    async def append_to_json_file(self, file_path: Path, item: dict) -> None:
        data = await self.read_json_file(file_path) or []
        if not isinstance(data, list):
            data = []
        data.append(item)
        await self.write_json_file(file_path, data)

    async def init_user_data(self, user_id: int) -> None:
        user_dir = self.get_user_dir(user_id)
        files = {
            'plan.json': {'plan': 'Free', 'expiration': None},
            'settings.json': {'model': 'gemini-2.5-flash', 'current_persona': 'friend', 'systemInstruction': DEFAULT_SYSTEM_INSTRUCTION},
            'usage.json': {
                'rateLimit': {'minute': '', 'count': 0},
                'imageLimit': {'count': 0, 'resetTime': ''},
                'videoLimit': {'count': 0, 'resetTime': ''}
            },
            'history.json': []
        }
        
        for filename, default_data in files.items():
            file_path = user_dir / filename
            if not file_path.exists():
                await self.write_json_file(file_path, default_data)

    async def get_user_plan(self, user_id: int) -> str:
        user_dir = self.get_user_dir(user_id)
        plan_file = user_dir / 'plan.json'
        plan_data = await self.read_json_file(plan_file) or {'plan': 'Free', 'expiration': None}
        
        if plan_data['expiration'] and datetime.fromisoformat(plan_data['expiration']) < datetime.now():
            plan_data = {'plan': 'Free', 'expiration': None}
            await self.write_json_file(plan_file, plan_data)
        
        return plan_data['plan']

class GeminiAPI:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.client = httpx.AsyncClient()

    async def generate_content(self, prompt: dict, stream: bool = False, safety_settings: list = None, system_instruction: str = None) -> dict:
        endpoint = 'streamGenerateContent' if stream else 'generateContent'
        url = f"{self.base_url}/{self.model}:{endpoint}"
        params = {'key': self.api_key}
        
        # Check if prompt has full contents (with history) or just parts
        if 'contents' in prompt:
            contents = prompt.get('contents', [])
            if not contents:
                raise ValueError("Contents cannot be empty")
        else:
            # Get parts from prompt (single message)
            parts = prompt.get('parts', [])
            if not parts:
                raise ValueError("Message parts cannot be empty")
            contents = [{
                'parts': parts,
                'role': 'user'
            }]
        
        # Build request body with proper structure
        request_body = {
            'contents': contents,
            'generationConfig': {
                'temperature': 0.5,  # Lower for more consistent, factual responses
                'topK': 40,
                'topP': 0.95,
                'maxOutputTokens': 1024  # Shorter responses by default
            }
        }
        
        # Add system instruction if provided
        if system_instruction:
            request_body['system_instruction'] = {
                'parts': [{'text': system_instruction}]
            }
        
        # Add safety settings only if provided and valid
        if safety_settings and isinstance(safety_settings, list) and len(safety_settings) > 0:
            # Validate safety settings have required fields
            valid_settings = []
            for setting in safety_settings:
                if isinstance(setting, dict) and 'category' in setting and 'threshold' in setting:
                    valid_settings.append(setting)
            if valid_settings:
                request_body['safetySettings'] = valid_settings
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, params=params, json=request_body)
                
                if response.status_code == 429:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Rate limited')
                    raise Exception(f"API Rate Limited (429): {error_msg}")
                
                response.raise_for_status()
                
                return response.json()
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                try:
                    error_data = json.loads(error_text)
                    error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                except:
                    error_msg = error_text
                print(f"API Error {e.response.status_code}: {error_msg}")
                raise Exception(f"Gemini API Error {e.response.status_code}: {error_msg}")

class Gena:
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        print(f"Error: {context.error}")
    async def handle_pre_checkout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.pre_checkout_query
        
        try:
            # Extract plan info from payload
            payload = json.loads(query.invoice_payload)
            plan = payload.get('plan')
            duration = payload.get('duration', 30)  # Default 30 days
            
            if not plan or plan not in PLAN_LIMITS:
                await query.answer(ok=False, error_message="Invalid plan selected.")
                return
                
            # Approve the transaction
            await query.answer(ok=True)
            
            if not query.from_user:
                return
                
            # Update user's plan after successful payment
            user_id = query.from_user.id
            
            # Update plan in database
            expiration = (datetime.now() + timedelta(days=duration)).isoformat()
            self.db.set_user_plan(user_id, plan, expiration)
            
        except Exception as e:
            print(f"Pre-checkout error: {e}")
            await query.answer(ok=False, error_message="An error occurred processing your payment.")
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        
        if not query.from_user:
            return
            
        user_id = query.from_user.id
        data = query.data
        
        if data == "clear_confirm":
            # Clear conversation history from database
            self.db.clear_history(user_id)
            await query.message.edit_text("🗑️ Conversation history cleared successfully!")
            
        elif data == "clear_cancel":
            await query.message.edit_text("👍 Conversation history kept intact.")
            
        elif data.startswith("persona_"):
            persona_key = data.split("_", 1)[1]
            plan = self.db.get_user_plan(user_id)
            available_personas = get_available_personas(plan)
            
            if persona_key in available_personas:
                # Update in database
                system_instruction = get_persona_instruction(persona_key)
                self.db.update_settings(user_id, current_persona=persona_key, systemInstruction=system_instruction)
                
                # Show success with back button
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="settings_back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text(
                    f"✅ Persona changed to *{get_persona_name(persona_key)}*!",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.answer("❌ This persona is not available for your plan.", show_alert=True)
            
        elif data == "settings_back":
            # Rebuild and show settings menu
            settings = self.db.get_settings(user_id)
            plan = self.db.get_user_plan(user_id)
            current_persona = settings.get('current_persona', 'friend')
            persona_name = get_persona_name(current_persona)
            
            keyboard = [
                [
                    InlineKeyboardButton("🤖 Model", callback_data="settings_model"),
                    InlineKeyboardButton("📋 Plan", callback_data="settings_plan")
                ],
                [
                    InlineKeyboardButton("👤 Persona", callback_data="settings_persona")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            settings_text = (
                "*Current Settings*\n\n"
                f"🤖 Model: `{settings.get('model', GEMINI_MODEL)}`\n"
                f"📋 Plan: `{plan}`\n"
                f"👤 Persona: `{persona_name}`\n\n"
                "Click a button below to modify settings:"
            )
            await query.message.edit_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')
        
        elif data.startswith("settings_"):
            setting = data.split("_")[1]
            if setting == "model":
                await self.show_model_settings(query.message, user_id)
            elif setting == "plan":
                await self.plan_command(None, None, user_id, query.message)
            elif setting == "persona":
                await self.show_persona_settings(query.message, user_id)
        
        elif data.startswith("model_"):
            model = data.split("_", 1)[1]
            # Update in database
            self.db.update_settings(user_id, model=model)
            
            # Show success with back button
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="settings_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                f"✅ Model changed to `{model}`!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
                
        elif data.startswith("upgrade_"):
            plan = data.split("_")[1].upper()
            await self.handle_plan_upgrade(query.message, user_id, plan)
            
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user:
            return
            
        user_id = update.effective_user.id
        user_dir = self.user_manager.get_user_dir(user_id)
        history_file = user_dir / 'history.json'
        
        # Create confirmation keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, clear", callback_data="clear_confirm"),
                InlineKeyboardButton("❌ No, keep", callback_data="clear_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ Are you sure you want to clear your conversation history?\n"
            "This action cannot be undone.",
            reply_markup=reply_markup
        )
    async def plan_command(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None, user_id: int = None, message: Message = None) -> None:
        """Handle plan command - can be called from both commands and callbacks."""
        # Handle both command (with Update) and callback (with user_id + message)
        if user_id is None:
            if not update or not update.effective_user:
                return
            user_id = update.effective_user.id
            message = update.message
        
        current_plan = self.db.get_user_plan(user_id)
        
        # Define plan details including prices
        plans = {
            'Basic': {
                'price': 499,  # $4.99
                'description': (
                    "• 10 messages/minute\n"
                    "• 5 message history\n"
                    "• 5 images/day\n"
                    "• Custom model selection\n"
                    "• 3 personas\n"
                    "• Basic customization"
                )
            },
            'Premium': {
                'price': 999,  # $9.99
                'description': (
                    "• 20 messages/minute\n"
                    "• 8 message history\n"
                    "• 10 images/day\n"
                    "• All models access\n"
                    "• 6 personas\n"
                    "• Full customization"
                )
            },
            'VIP': {
                'price': 1999,  # $19.99
                'description': (
                    "• 30 messages/minute\n"
                    "• 10 message history\n"
                    "• 50 images/day\n"
                    "• All 9 personas\n"
                    "• Priority support\n"
                    "• Exclusive features"
                )
            }
        }
        
        # Create inline keyboard for upgrades
        keyboard = []
        for plan_name, details in plans.items():
            if plan_name != current_plan:
                button_text = f"Upgrade to {plan_name} (${details['price']/100:.2f}/month)"
                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f"upgrade_{plan_name.lower()}"
                )])
        
        # Show current plan details
        plan_text = (
            f"*Your Current Plan: {current_plan}*\n\n"
            f"Daily Limits:\n"
            f"• Messages: {PLAN_LIMITS[current_plan]['rate']}/minute\n"
            f"• History: {PLAN_LIMITS[current_plan]['turns']} messages\n"
            f"• Images: {PLAN_LIMITS[current_plan]['images']}/day\n\n"
        )
        
        if current_plan != 'VIP':
            plan_text += "Available Upgrades:"
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            plan_text += "🌟 You're on our highest plan!"
            reply_markup = None
        
        # Handle both Message (from callback) and Update (from command)
        if message:
            await message.edit_text(plan_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                plan_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    async def show_persona_settings(self, message: Message, user_id: int) -> None:
        """Display persona selection menu with back button."""
        plan = self.db.get_user_plan(user_id)
        available_personas = get_available_personas(plan)
        
        if not available_personas:
            await message.edit_text(
                "⚠️ No personas available for your plan.\n"
                "Use /plan to upgrade your subscription."
            )
            return
        
        settings = self.db.get_settings(user_id)
        current_persona = settings.get('current_persona', 'friend')
        
        # Create keyboard with 2 buttons per row
        keyboard = []
        for i in range(0, len(available_personas), 2):
            row = []
            for j in range(2):
                if i + j < len(available_personas):
                    persona_key = available_personas[i + j]
                    persona_name = get_persona_name(persona_key)
                    button_text = f"✓ {persona_name}" if persona_key == current_persona else persona_name
                    row.append(InlineKeyboardButton(
                        button_text,
                        callback_data=f"persona_{persona_key}"
                    ))
            if row:
                keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        personas_text = "*👤 Persona Selection*\n\n"
        for persona_key in available_personas:
            personas_text += f"• {get_persona_name(persona_key)}\n"
        personas_text += f"\n*Currently Using:* {get_persona_name(current_persona)}"
        
        await message.edit_text(personas_text, reply_markup=reply_markup, parse_mode='Markdown')
    

    async def show_model_settings(self, message: Message, user_id: int) -> None:
        """Display model selection menu with plan-based access."""
        plan = self.db.get_user_plan(user_id)
        available_models = ALL_MODELS.get(plan, ALL_MODELS['Free'])
        
        settings = self.db.get_settings(user_id)
        current_model = settings.get('model', GEMINI_MODEL)
        
        keyboard = []
        for model in available_models:
            label = f"{model} ({MODEL_DESCRIPTIONS.get(model, 'Standard')})"
            checkmark = "✓ " if current_model == model else ""
            keyboard.append([InlineKeyboardButton(
                f"{checkmark}{label}",
                callback_data=f"model_{model}"
            )])
        
        # Add upgrade button if not VIP
        if plan != 'VIP':
            keyboard.append([InlineKeyboardButton("📈 Upgrade for more models", callback_data="settings_back")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        models_text = (
            f"*🤖 Model Selection ({plan} Plan)*\n\n"
            + "\n".join([f"• {m} ({MODEL_DESCRIPTIONS.get(m, 'Standard')})" for m in available_models])
            + f"\n\nCurrent: `{current_model}`\n\nSelect a model for your responses:"
        )
        await message.edit_text(models_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def settings_command(self, update: Union[Update, Message], context: ContextTypes.DEFAULT_TYPE = None) -> None:
        """Handle settings command - can be called from both commands and callbacks."""
        # Handle both Update (from command) and Message (from callback)
        if isinstance(update, Message):
            message = update
            # Try to get user_id from message.from_user if available
            if not message.from_user:
                return
            user_id = message.from_user.id
        else:
            if not update.effective_user:
                return
            message = update.message
            user_id = update.effective_user.id
        
        # Get settings and plan from database
        settings = self.db.get_settings(user_id)
        plan = self.db.get_user_plan(user_id)
        
        keyboard = [
            [
                InlineKeyboardButton("🤖 Model", callback_data="settings_model"),
                InlineKeyboardButton("📋 Plan", callback_data="settings_plan")
            ],
            [
                InlineKeyboardButton("👤 Persona", callback_data="settings_persona")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_persona = settings.get('current_persona', 'friend')
        persona_name = get_persona_name(current_persona)
        
        settings_text = (
            "*Current Settings*\n\n"
            f"🤖 Model: `{settings.get('model', GEMINI_MODEL)}`\n"
            f"📋 Plan: `{plan}`\n"
            f"👤 Persona: `{persona_name}`\n\n"
            "Click a button below to modify settings:"
        )
        
        # Handle both Update.message and direct Message object
        if isinstance(update, Message):
            await message.edit_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await message.reply_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = (
            "*Gena Bot Help*\n\n"
            "/start - Start the bot and initialize your data\n"
            "/help - Show this help message\n"
            "/settings - View or change your settings (model, system instruction, etc.)\n"
            "/plan - View or upgrade your plan\n"
            "/clear - Clear your conversation history\n\n"
            "*Natural Language Commands:*\n"
            "Try saying things like:\n"
            "• 'clear my history'\n"
            "• 'show settings'\n"
            "• 'change persona to friend'\n"
            "• 'what plan am I on'\n\n"
            "You can send text and images.\n"
            "Some features require a paid plan."
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Admin command - show dashboard stats."""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        
        # Check if user is admin
        if str(user_id) not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        from admin_dashboard import AdminDashboard
        
        dashboard = AdminDashboard(self.db)
        report = dashboard.generate_report()
        
        await update.message.reply_text(f"```\n{report}\n```", parse_mode='Markdown')
    
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.user_manager = UserManager(Path.cwd())
        self.db = DatabaseManager('gena.db')
        
        # Migrate from JSON to SQLite if needed
        try:
            self.db.migrate_from_json(Path.cwd())
        except Exception as e:
            print(f"Migration error (non-blocking): {e}")
        
        self.gemini_api = GeminiAPI(GEMINI_API_KEY, GEMINI_MODEL)
        self.setup_handlers()

    def setup_handlers(self):
        # Command handlers
        self.app.add_handler(CommandHandler('start', self.start_command))
        self.app.add_handler(CommandHandler('help', self.help_command))
        self.app.add_handler(CommandHandler('settings', self.settings_command))
        self.app.add_handler(CommandHandler('plan', self.plan_command))
        self.app.add_handler(CommandHandler('clear', self.clear_command))
        self.app.add_handler(CommandHandler('admin', self.admin_command))

        # Message handlers
        self.app.add_handler(MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))

        # Callback query handler
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

        # Payment handlers
        self.app.add_handler(PreCheckoutQueryHandler(self.handle_pre_checkout))

        # Error handler
        self.app.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user:
            return
            
        user_id = update.effective_user.id
        # Initialize user in database
        self.db.init_user(user_id)
        plan = self.db.get_user_plan(user_id)
        
        welcome_text = (
            f"👋 Welcome! I'm Gena, your AI companion with:\n"
            f"• Multimodal support (text + images)\n"
            f"• Conversation memory ({PLAN_LIMITS[plan]['turns']} turns)\n"
            f"• Custom personas (Basic+)\n"
            f"• Your plan: {plan}\n\n"
            f"Try sending an image with a question or use /help for commands."
        )
        
        await update.message.reply_text(welcome_text)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user:
            return

        user_id = update.effective_user.id
        
        # Initialize user in database if needed
        self.db.init_user(user_id)
        plan = self.db.get_user_plan(user_id)
        
        # Check for natural language commands
        if update.message.text:
            intent, extra = NLUEngine.detect_intent(update.message.text)
            
            if intent == Intent.CLEAR_HISTORY:
                # Show confirmation
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Yes, clear", callback_data="clear_confirm"),
                        InlineKeyboardButton("❌ No, keep", callback_data="clear_cancel")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "⚠️ Clear your conversation history?",
                    reply_markup=reply_markup
                )
                return
            
            elif intent == Intent.SHOW_SETTINGS:
                await self.settings_command(update.message, context)
                return
            
            elif intent == Intent.SHOW_HELP:
                await self.help_command(update, context)
                return
            
            elif intent == Intent.SHOW_PLAN:
                await self.plan_command(update, context)
                return

        # Rate limit check
        if not await self.check_rate_limit(user_id, plan):
            await update.message.reply_text(ERROR_MESSAGES['RATE_LIMIT_EXCEEDED'])
            return

        try:
            # Process message
            message_parts = []
            
            # Handle text
            if update.message.text or update.message.caption:
                text = update.message.text or update.message.caption
                message_parts.append({'text': text})

            # Handle images only (videos removed)
            if update.message.photo:
                media_files = update.message.photo

                if not await self.check_media_limit(user_id, plan, 'image'):
                    await update.message.reply_text(ERROR_MESSAGES['IMAGE_LIMIT_EXCEEDED'])
                    return

                processed_media = await self.process_media(media_files)
                message_parts.extend(processed_media)

            # Validate that we have at least one part
            if not message_parts:
                await update.message.reply_text("Please send a message or image.")
                return

            # Get response from Gemini
            # Initialize user in database if needed
            self.db.init_user(user_id)
            
            # Get settings from database
            settings = self.db.get_settings(user_id)
            
            # Get the current persona and its system instruction
            current_persona = settings.get('current_persona', 'friend')
            plan = self.db.get_user_plan(user_id)
            available_personas = get_available_personas(plan)
            
            # If persona is not available, fall back to friend
            if current_persona not in available_personas:
                current_persona = 'friend'
                self.db.update_settings(user_id, current_persona=current_persona)
            
            system_instruction = get_persona_instruction(current_persona)
            
            # Load safety settings from database
            safety_settings_data = self.db.get_safety_settings() or DEFAULT_SAFETY_SETTINGS
            
            # Get conversation history based on plan limits
            history_limit = PLAN_LIMITS[plan]['turns']
            history = self.db.get_history(user_id, limit=history_limit)
            
            # Build contents with history as previous turns
            contents = []
            for hist_entry in history:
                # Add previous user message
                contents.append({
                    'role': 'user',
                    'parts': [{'text': hist_entry['user']}]
                })
                # Add previous bot response
                contents.append({
                    'role': 'model',
                    'parts': [{'text': hist_entry['bot']}]
                })
            
            # Add current message
            contents.append({
                'role': 'user',
                'parts': message_parts
            })
            
            response = await self.gemini_api.generate_content(
                {'contents': contents}, 
                safety_settings=safety_settings_data,
                system_instruction=system_instruction
            )

            # Parse response
            full_text = ""
            if isinstance(response, dict):
                if 'candidates' in response and response['candidates']:
                    candidate = response['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        for part in candidate['content']['parts']:
                            if 'text' in part:
                                full_text += part['text']
            
            if not full_text:
                await update.message.reply_text("No response received from API.")
                return

            # Extract text from message_parts for history
            user_message_for_history = ""
            for part in message_parts:
                if 'text' in part:
                    user_message_for_history += part['text']
            if not user_message_for_history:
                user_message_for_history = "[Image]"
            
            # Save to database history
            self.db.add_to_history(user_id, user_message_for_history, full_text)

            # Send response
            for message_chunk in self.split_message(full_text):
                await update.message.reply_text(
                    message_chunk,
                    parse_mode=None,  # Don't use MarkdownV2 to avoid escaping issues
                )

        except Exception as e:
            await self.log_error(user_id, e)
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def handle_plan_upgrade(self, message: Message, user_id: int, plan: str) -> None:
        if plan not in PLAN_LIMITS:
            await message.edit_text("❌ Invalid plan selected.")
            return
            
        prices = {
            'Free': 0,          # Free plan
            'Basic': 499,       # $4.99
            'Premium': 999,     # $9.99
            'VIP': 1999         # $19.99
        }
        
        # Check if PROVIDER_TOKEN is set for payments
        if not PROVIDER_TOKEN or PROVIDER_TOKEN == '0':
            price_display = f"${prices[plan]/100:.2f}/month" if prices[plan] > 0 else "Free"
            await message.edit_text(
                f"✅ Demo: {plan} Plan selected!\n\n"
                f"Pricing: {price_display}\n\n"
                f"Note: Payment integration coming soon. For now, plan upgraded for demo."
            )
            # Demo upgrade in database
            self.db.set_user_plan(user_id, plan, expiration=None)
            return
        
        if prices[plan] == 0:
            await message.edit_text(f"✅ {plan} plan is already free!")
            return
        
        title = f"Upgrade to {plan} Plan"
        description = f"Monthly subscription to Gena {plan} Plan"
        payload = json.dumps({'plan': plan, 'duration': 30})
        currency = "USD"
        prices_list = [LabeledPrice(f"{plan} Plan Monthly", prices[plan])]
        
        await self.app.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency=currency,
            prices=prices_list
        )

    async def check_rate_limit(self, user_id: int, plan: str) -> bool:
        user_dir = self.user_manager.get_user_dir(user_id)
        usage_file = user_dir / 'usage.json'
        usage = await self.user_manager.read_json_file(usage_file) or {
            'rateLimit': {'minute': '', 'count': 0}
        }
        
        current_minute = datetime.now().strftime('%Y-%m-%d %H:%M')
        if usage['rateLimit']['minute'] != current_minute:
            usage['rateLimit'] = {'minute': current_minute, 'count': 1}
        else:
            usage['rateLimit']['count'] += 1
            
        await self.user_manager.write_json_file(usage_file, usage)
        return usage['rateLimit']['count'] <= PLAN_LIMITS[plan]['rate']

    async def check_media_limit(self, user_id: int, plan: str, media_type: str) -> bool:
        user_dir = self.user_manager.get_user_dir(user_id)
        usage_file = user_dir / 'usage.json'
        usage = await self.user_manager.read_json_file(usage_file) or {
            'imageLimit': {'count': 0, 'resetTime': ''},
            'videoLimit': {'count': 0, 'resetTime': ''}
        }
        
        limit_key = f'{media_type}Limit'
        current_day = datetime.now().strftime('%Y-%m-%d')
        
        if usage[limit_key]['resetTime'] != current_day:
            usage[limit_key] = {'count': 1, 'resetTime': current_day}
        else:
            usage[limit_key]['count'] += 1
            
        await self.user_manager.write_json_file(usage_file, usage)
        return usage[limit_key]['count'] <= PLAN_LIMITS[plan][f'{media_type}s']

    async def process_media(self, media_files: List[Union[InputMediaPhoto, InputMediaVideo]]) -> List[dict]:
        result = []
        for media in media_files:
            file = await media.get_file()
            file_data = await file.download_as_bytearray()
            mime_type = mimetypes.guess_type(file.file_path)[0]
            
            if not mime_type or mime_type not in ALLOWED_MIME_TYPES:
                continue
                
            result.append({
                'inlineData': {
                    'data': base64.b64encode(file_data).decode(),
                    'mimeType': mime_type
                }
            })
        return result

    async def log_error(self, user_id: int, error: Exception) -> None:
        error_dir = Path.cwd() / 'data' / 'errors'
        error_dir.mkdir(parents=True, exist_ok=True)
        error_data = {
            'user_id': user_id,
            'error': str(error),
            'traceback': str(error.__traceback__),
            'timestamp': datetime.now().isoformat()
        }
        await self.user_manager.append_to_json_file(error_dir / 'errors.json', error_data)

    def split_message(self, text: str, max_length: int = 4096) -> List[str]:
        """Split a message into chunks that fit Telegram's message size limit."""
        if len(text) <= max_length:
            return [text]
            
        chunks = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break
                
            split_index = text.rfind('\n', 0, max_length)
            if split_index == -1:
                split_index = text.rfind(' ', 0, max_length)
            if split_index == -1:
                split_index = max_length
                
            chunks.append(text[:split_index])
            text = text[split_index:].lstrip()
            
        return chunks

    def run(self):
        """Start the bot."""
        print("🚀 Enhanced Gena bot ready!")
        self.app.run_polling()

if __name__ == '__main__':
    bot = Gena()
    bot.run()