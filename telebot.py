"""
Gena - Telegram Bot Interface
Handles all Telegram interactions and API calls
"""
import os
import base64
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Union
from dotenv import load_dotenv
import httpx
from telegram import (
    Update, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
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
from gena import GenaCore, PLAN_PRICES

# Load environment
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv('ADMIN_USER_IDS', '').split(',') if id.strip()]

if not all([TELEGRAM_TOKEN, GEMINI_API_KEY]):
    raise ValueError('Missing TELEGRAM_TOKEN or GEMINI_API_KEY')

# Media configuration
ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


class GeminiAPI:
    """Gemini API client"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
    
    async def generate_content(
        self, 
        model: str,
        contents: List[Dict],
        system_instruction: str = None,
        safety_settings: List[Dict] = None
    ) -> Dict:
        """Generate content from Gemini API"""
        url = f"{self.base_url}/{model}:generateContent"
        params = {'key': self.api_key}
        
        request_body = {
            'contents': contents,
            'generationConfig': {
                'temperature': 0.7,
                'topK': 40,
                'topP': 0.95,
                'maxOutputTokens': 1024
            }
        }
        
        if system_instruction:
            request_body['system_instruction'] = {
                'parts': [{'text': system_instruction}]
            }
        
        if safety_settings:
            valid_settings = [
                s for s in safety_settings 
                if isinstance(s, dict) and 'category' in s and 'threshold' in s
            ]
            if valid_settings:
                request_body['safetySettings'] = valid_settings
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, params=params, json=request_body)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_msg = e.response.text
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', error_msg)
                except:
                    pass
                raise Exception(f"Gemini API Error ({e.response.status_code}): {error_msg}")


class GenaBot:
    """Main Telegram bot class"""
    
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.core = GenaCore()
        self.gemini = GeminiAPI(GEMINI_API_KEY)
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup all command and message handlers"""
        self.app.add_handler(CommandHandler('start', self.start_command))
        self.app.add_handler(CommandHandler('help', self.help_command))
        self.app.add_handler(CommandHandler('settings', self.settings_command))
        self.app.add_handler(CommandHandler('clear', self.clear_command))
        self.app.add_handler(CommandHandler('admin', self.admin_command))
        
        self.app.add_handler(MessageHandler(
            filters.PHOTO | filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))
        
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(PreCheckoutQueryHandler(self.handle_pre_checkout))
        
        self.app.add_error_handler(self.error_handler)
    
    # Command Handlers
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        self.core.initialize_user(user_id)
        plan = self.core.get_user_plan(user_id)
        
        welcome = (
            f"👋 *Welcome to Gena!*\n\n"
            f"Your AI companion with:\n"
            f"• Text & Image support\n"
            f"• Multiple personalities\n"
            f"• Conversation memory\n"
            f"• Your plan: *{plan}*\n\n"
            f"Use /help to see all commands"
        )
        
        await update.message.reply_text(welcome, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "*Gena Bot Commands*\n\n"
            "/start - Initialize bot\n"
            "/help - Show this message\n"
            "/settings - View/change settings\n"
            "/clear - Forget conversation context\n\n"
            "*Natural Language:*\n"
            "You can also say:\n"
            "• 'clear my context'\n"
            "• 'show settings'\n"
            "• 'change persona to advisor'\n\n"
            "Send text or images to chat!"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        await self._show_settings_menu(update.message, user_id)
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        if not update.effective_user:
            return
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, forget", callback_data="clear_confirm"),
                InlineKeyboardButton("❌ No, keep", callback_data="clear_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ Forget conversation context?\n"
            "(Chat history will be preserved)",
            reply_markup=reply_markup
        )
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ Not authorized")
            return
        
        from admin_dashboard import AdminDashboard
        dashboard = AdminDashboard(self.core.db)
        report = dashboard.generate_report()
        
        await update.message.reply_text(f"```\n{report}\n```", parse_mode='Markdown')
    
    # Message Handler
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        self.core.initialize_user(user_id)
        
        # Check for NLU commands
        if update.message.text:
            intent, extra = self.core.detect_intent(update.message.text)
            
            if intent.value == 'clear_history':
                await self.clear_command(update, context)
                return
            elif intent.value == 'show_settings':
                await self._show_settings_menu(update.message, user_id)
                return
            elif intent.value == 'show_help':
                await self.help_command(update, context)
                return
        
        # Rate limit check
        if not self.core.check_rate_limit(user_id):
            await update.message.reply_text(
                "⏱ Rate limit exceeded. Please wait a minute."
            )
            return
        
        try:
            # Build message parts
            parts = []
            
            # Add text
            text = update.message.text or update.message.caption
            if text:
                parts.append({'text': text})
            
            # Add images
            if update.message.photo:
                if not self.core.check_image_limit(user_id):
                    await update.message.reply_text(
                        "🖼 Daily image limit reached. Upgrade for more!"
                    )
                    return
                
                media = await self._process_images(update.message.photo)
                parts.extend(media)
            
            if not parts:
                await update.message.reply_text("Please send text or an image.")
                return
            
            # Get settings
            settings = self.core.get_settings(user_id)
            model = settings.get('model', 'gemini-2.5-flash')
            persona = settings.get('current_persona', 'friend')
            
            # Get system instruction
            system_instruction = self.core.get_persona_instruction(persona)
            
            # Get context history
            history = self.core.get_context_history(user_id)
            
            # Build contents
            contents = []
            for entry in history:
                contents.append({
                    'role': 'user',
                    'parts': [{'text': entry['user']}]
                })
                contents.append({
                    'role': 'model',
                    'parts': [{'text': entry['bot']}]
                })
            
            # Add current message
            contents.append({
                'role': 'user',
                'parts': parts
            })
            
            # Get safety settings
            safety_settings = self.core.get_safety_settings()
            
            # Call Gemini API
            response = await self.gemini.generate_content(
                model=model,
                contents=contents,
                system_instruction=system_instruction,
                safety_settings=safety_settings
            )
            
            # Extract response text
            response_text = self._extract_response_text(response)
            
            if not response_text:
                await update.message.reply_text("❌ No response from API")
                return
            
            # Save to history
            user_text = text if text else "[Image]"
            self.core.add_to_history(user_id, user_text, response_text)
            
            # Send response
            for chunk in self._split_message(response_text):
                await update.message.reply_text(chunk)
        
        except Exception as e:
            await self._log_error(user_id, e)
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    # Callback Handler
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        if not query.from_user:
            return
        
        user_id = query.from_user.id
        data = query.data
        
        # Clear context
        if data == "clear_confirm":
            self.core.forget_context(user_id)
            await query.message.edit_text("✅ Context forgotten! (History preserved)")
        
        elif data == "clear_cancel":
            await query.message.edit_text("👍 Context kept")
        
        # Settings navigation
        elif data == "settings_back":
            await self._show_settings_menu(query.message, user_id, edit=True)
        
        elif data == "settings_model":
            await self._show_model_menu(query.message, user_id)
        
        elif data == "settings_persona":
            await self._show_persona_menu(query.message, user_id)
        
        elif data == "settings_plan":
            await self._show_plan_menu(query.message, user_id)
        
        # Model selection
        elif data.startswith("model_"):
            model = data.split("_", 1)[1]
            self.core.update_settings(user_id, model=model)
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="settings_back")]]
            await query.message.edit_text(
                f"✅ Model changed to *{model}*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        # Persona selection
        elif data.startswith("persona_"):
            persona = data.split("_", 1)[1]
            plan = self.core.get_user_plan(user_id)
            available = self.core.get_available_personas(plan)
            
            if persona in available:
                instruction = self.core.get_persona_instruction(persona)
                self.core.update_settings(
                    user_id, 
                    current_persona=persona,
                    systemInstruction=instruction
                )
                
                name = self.core.get_persona_name(persona)
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="settings_back")]]
                await query.message.edit_text(
                    f"✅ Persona changed to *{name}*",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await query.answer("❌ Persona not available", show_alert=True)
        
        # Plan upgrade
        elif data.startswith("upgrade_"):
            plan = data.split("_")[1].capitalize()
            await self._send_invoice(query.from_user.id, plan)
            await query.message.edit_text(f"⭐️ Invoice sent for {plan} plan!")
        
        # Cancel subscription
        elif data == "cancel_subscription":
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes, cancel", callback_data="cancel_confirm"),
                    InlineKeyboardButton("❌ No, keep", callback_data="settings_plan")
                ]
            ]
            await query.message.edit_text(
                "⚠️ Cancel subscription?\n"
                "You'll be downgraded to Free plan.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data == "cancel_confirm":
            self.core.cancel_subscription(user_id)
            await query.message.edit_text("✅ Subscription cancelled. Downgraded to Free.")
    
    # Payment Handler
    async def handle_pre_checkout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pre-checkout query"""
        query = update.pre_checkout_query
        
        try:
            import json
            payload = json.loads(query.invoice_payload)
            plan = payload.get('plan')
            
            if plan not in PLAN_PRICES:
                await query.answer(ok=False, error_message="Invalid plan")
                return
            
            await query.answer(ok=True)
            
            # Upgrade user
            if query.from_user:
                self.core.upgrade_plan(query.from_user.id, plan, duration_days=30)
        
        except Exception as e:
            await query.answer(ok=False, error_message=str(e))
    
    # UI Builders
    async def _show_settings_menu(self, message: Message, user_id: int, edit: bool = False):
        """Show settings menu"""
        settings = self.core.get_settings(user_id)
        plan = self.core.get_user_plan(user_id)
        persona = self.core.get_persona_name(settings.get('current_persona', 'friend'))
        
        text = (
            f"*⚙️ Settings*\n\n"
            f"🤖 Model: `{settings.get('model', 'gemini-2.5-flash')}`\n"
            f"👤 Persona: `{persona}`\n"
            f"📋 Plan: `{plan}`"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🤖 Model", callback_data="settings_model"),
                InlineKeyboardButton("👤 Persona", callback_data="settings_persona")
            ],
            [
                InlineKeyboardButton("📋 Your Plan", callback_data="settings_plan")
            ]
        ]
        
        if edit:
            await message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def _show_model_menu(self, message: Message, user_id: int):
        """Show model selection menu"""
        plan = self.core.get_user_plan(user_id)
        available = self.core.get_available_models(plan)
        settings = self.core.get_settings(user_id)
        current = settings.get('model', 'gemini-2.5-flash')
        
        keyboard = []
        for model in available:
            from gena import MODEL_DESCRIPTIONS
            desc = MODEL_DESCRIPTIONS.get(model, 'Standard')
            check = "✓ " if current == model else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"{check}{model} ({desc})",
                    callback_data=f"model_{model}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
        
        await message.edit_text(
            f"*🤖 Select Model*\n\nCurrent: `{current}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _show_persona_menu(self, message: Message, user_id: int):
        """Show persona selection menu"""
        plan = self.core.get_user_plan(user_id)
        available = self.core.get_available_personas(plan)
        settings = self.core.get_settings(user_id)
        current = settings.get('current_persona', 'friend')
        
        keyboard = []
        for i in range(0, len(available), 2):
            row = []
            for j in range(2):
                if i + j < len(available):
                    persona = available[i + j]
                    name = self.core.get_persona_name(persona)
                    check = "✓ " if persona == current else ""
                    row.append(InlineKeyboardButton(
                        f"{check}{name}",
                        callback_data=f"persona_{persona}"
                    ))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
        
        current_name = self.core.get_persona_name(current)
        await message.edit_text(
            f"*👤 Select Persona*\n\nCurrent: `{current_name}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _show_plan_menu(self, message: Message, user_id: int):
        """Show plan management menu"""
        plan = self.core.get_user_plan(user_id)
        expiration = self.core.get_plan_expiration(user_id)
        
        text = f"*📋 Your Plan: {plan}*\n\n"
        text += self.core.format_plan_details(plan)
        
        if expiration:
            exp_date = datetime.fromisoformat(expiration).strftime('%Y-%m-%d')
            text += f"\n\n📅 Expires: {exp_date}"
        
        keyboard = []
        
        # Show upgrade options
        if plan != 'VIP':
            upgrade_plans = ['Basic', 'Premium', 'VIP']
            for upgrade_plan in upgrade_plans:
                if upgrade_plan != plan:
                    price = PLAN_PRICES.get(upgrade_plan, 0)
                    keyboard.append([
                        InlineKeyboardButton(
                            f"⬆️ Upgrade to {upgrade_plan} ({price} ⭐️/mo)",
                            callback_data=f"upgrade_{upgrade_plan.lower()}"
                        )
                    ])
        
        # Show cancel option for paid plans
        if plan != 'Free':
            keyboard.append([
                InlineKeyboardButton(
                    "❌ Cancel Subscription",
                    callback_data="cancel_subscription"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
        
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # Utilities
    async def _process_images(self, photos: List) -> List[Dict]:
        """Process photo files to base64"""
        result = []
        for photo in photos:
            file = await photo.get_file()
            file_data = await file.download_as_bytearray()
            mime_type = mimetypes.guess_type(file.file_path)[0]
            
            if mime_type and mime_type in ALLOWED_MIME_TYPES:
                result.append({
                    'inlineData': {
                        'data': base64.b64encode(file_data).decode(),
                        'mimeType': mime_type
                    }
                })
        return result
    
    def _extract_response_text(self, response: Dict) -> str:
        """Extract text from Gemini API response"""
        text = ""
        if 'candidates' in response and response['candidates']:
            candidate = response['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                for part in candidate['content']['parts']:
                    if 'text' in part:
                        text += part['text']
        return text
    
    def _split_message(self, text: str, max_len: int = 4096) -> List[str]:
        """Split long messages"""
        if len(text) <= max_len:
            return [text]
        
        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break
            
            split = text.rfind('\n', 0, max_len)
            if split == -1:
                split = text.rfind(' ', 0, max_len)
            if split == -1:
                split = max_len
            
            chunks.append(text[:split])
            text = text[split:].lstrip()
        
        return chunks
    
    async def _send_invoice(self, user_id: int, plan: str):
        """Send Telegram Stars invoice"""
        import json
        
        price = PLAN_PRICES.get(plan, 0)
        if price == 0:
            return
        
        title = f"{plan} Plan"
        description = f"1 month subscription to Gena {plan} Plan"
        payload = json.dumps({'plan': plan, 'duration': 30})
        currency = "XTR"  # Telegram Stars
        
        from telegram import LabeledPrice
        prices = [LabeledPrice(f"{plan} Monthly", price)]
        
        await self.app.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",  # Empty for Telegram Stars
            currency=currency,
            prices=prices
        )
    
    async def _log_error(self, user_id: int, error: Exception):
        """Log error to file"""
        error_dir = Path.cwd() / 'data' / 'errors'
        error_dir.mkdir(parents=True, exist_ok=True)
        
        import json
        import traceback
        
        error_data = {
            'user_id': user_id,
            'error': str(error),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }
        
        error_file = error_dir / 'errors.json'
        errors = []
        
        if error_file.exists():
            try:
                with open(error_file, 'r') as f:
                    errors = json.load(f)
            except:
                pass
        
        errors.append(error_data)
        
        with open(error_file, 'w') as f:
            json.dump(errors[-100:], f, indent=2)  # Keep last 100 errors
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler"""
        print(f"Error: {context.error}")
    
    def run(self):
        """Start the bot"""
        print("🚀 Gena bot started!")
        self.app.run_polling()


if __name__ == '__main__':
    bot = GenaBot()
    bot.run()