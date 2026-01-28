"""
Gena - Telegram Bot Interface (Fixed for compatibility)
"""
import os
import base64
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
import httpx
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    PreCheckoutQueryHandler, filters, ContextTypes
)
from gena import GenaCore, PLAN_PRICES, MODEL_DESCRIPTIONS
from admin_dashboard import AdminDashboard

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv('ADMIN_USER_IDS', '').split(',') if id.strip()]

if not all([TELEGRAM_TOKEN, GEMINI_API_KEY]):
    raise ValueError('Missing TELEGRAM_TOKEN or GEMINI_API_KEY')

ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']


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
                'maxOutputTokens': 2048
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
                if e.response.status_code == 429:
                    raise Exception("⏱ API rate limit reached. Please try again in a moment.")
                elif e.response.status_code == 400:
                    raise Exception("❌ Invalid request. Please try a different message.")
                elif e.response.status_code == 500:
                    raise Exception("❌ API service error. Please try again later.")
                else:
                    raise Exception("❌ API error. Please try again.")


class GenaBot:
    """Main Telegram bot"""
    
    def __init__(self):
        # Build application with proper configuration
        self.app = (
            Application.builder()
            .token(TELEGRAM_TOKEN)
            .build()
        )
        self.core = GenaCore()
        self.gemini = GeminiAPI(GEMINI_API_KEY)
        self.media_dir = Path.cwd() / 'data' / 'media'
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._setup_handlers()
    
    def _setup_handlers(self):
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
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
        
        user = update.effective_user
        self.core.initialize_user(user.id, user.username, user.full_name)
        plan = self.core.get_user_plan(user.id)
        
        welcome = (
            f"👋 *Welcome to Gena!*\n\n"
            f"Your AI companion with:\n"
            f"• 💬 Text & Image support\n"
            f"• 🎭 Multiple personalities\n"
            f"• 💭 Conversation memory\n"
            f"• 📋 Plan: *{plan}*\n\n"
            f"Use /help to see all commands! ✨"
        )
        
        await update.message.reply_text(welcome, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "*🤖 Gena Bot Commands*\n\n"
            "📍 /start - Initialize bot\n"
            "❓ /help - Show this message\n"
            "⚙️ /settings - View/change settings\n"
            "🗑️ /clear - Forget conversation context\n\n"
            "*💬 Natural Language:*\n"
            "• 'clear my context'\n"
            "• 'show settings'\n"
            "• 'change persona to advisor'\n\n"
            "Send text or images to chat! 🚀"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        await self._show_settings_menu(update.message, user_id)
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
        
        keyboard = [[
            InlineKeyboardButton("✅ Yes", callback_data="clear_confirm"),
            InlineKeyboardButton("❌ No", callback_data="clear_cancel")
        ]]
        
        await update.message.reply_text(
            "⚠️ *Forget conversation context?*\n\n"
            "(History preserved for reference) 📚",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ Not authorized")
            return
        
        args = context.args if context.args else []
        
        dashboard = AdminDashboard(self.core.db)
        
        if not args:
            report = dashboard.generate_report()
            await update.message.reply_text(f"```\n{report}\n```", parse_mode='Markdown')
        elif args[0] == 'users':
            count = self.core.db.get_total_users()
            await update.message.reply_text(f"📊 Total users: *{count}*", parse_mode='Markdown')
        elif args[0] == 'messages':
            count = self.core.db.get_total_messages()
            await update.message.reply_text(f"💬 Total messages: *{count}*", parse_mode='Markdown')
        elif args[0] == 'export':
            filepath = f"data/analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            if dashboard.export_analytics(filepath):
                await update.message.reply_text(f"✅ Exported to `{filepath}`", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Export failed")
        else:
            await update.message.reply_text(
                "*Admin Commands:*\n"
                "/admin - Full report\n"
                "/admin users - User count\n"
                "/admin messages - Message count\n"
                "/admin export - Export analytics",
                parse_mode='Markdown'
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
        
        user = update.effective_user
        user_id = user.id
        self.core.initialize_user(user_id, user.username, user.full_name)
        
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
        
        if not self.core.check_rate_limit(user_id):
            await update.message.reply_text("⏱ Rate limit exceeded. Wait a minute! 😊")
            return
        
        try:
            parts = []
            text = update.message.text or update.message.caption
            media_id = None
            
            if text:
                parts.append({'text': text})
            
            if update.message.photo:
                if not self.core.check_image_limit(user_id):
                    await update.message.reply_text("🖼 Daily image limit reached! Upgrade for more! 🚀")
                    return
                
                photo = update.message.photo[-1]
                file = await photo.get_file()
                
                user_media_dir = self.media_dir / str(user_id)
                user_media_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                file_ext = Path(file.file_path).suffix or '.jpg'
                file_name = f"{timestamp}_{photo.file_id[:10]}{file_ext}"
                file_path = user_media_dir / file_name
                
                await file.download_to_drive(file_path)
                
                mime_type = mimetypes.guess_type(str(file_path))[0] or 'image/jpeg'
                media_id = self.core.add_media(user_id, photo.file_id, str(file_path), mime_type, photo.file_size)
                
                file_data = await file.download_as_bytearray()
                parts.append({
                    'inlineData': {
                        'data': base64.b64encode(file_data).decode(),
                        'mimeType': mime_type
                    }
                })
            
            if not parts:
                await update.message.reply_text("Please send text or an image! 📝")
                return
            
            settings = self.core.get_settings(user_id)
            model = settings.get('model', 'gemini-2.5-flash')
            persona = settings.get('current_persona', 'friend')
            
            system_instruction = self.core.build_system_instruction(user_id, persona)
            history = self.core.get_context_history(user_id)
            
            contents = []
            for entry in history:
                if entry['role'] == 'user':
                    contents.append({'role': 'user', 'parts': [{'text': entry['content']}]})
                else:
                    contents.append({'role': 'model', 'parts': [{'text': entry['content']}]})
            
            contents.append({'role': 'user', 'parts': parts})
            
            safety_settings = self.core.get_safety_settings()
            response = await self.gemini.generate_content(
                model=model,
                contents=contents,
                system_instruction=system_instruction,
                safety_settings=safety_settings
            )
            
            response_text = self._extract_response_text(response)
            
            if not response_text:
                await update.message.reply_text("❌ No response received")
                return
            
            user_text = text if text else "[Image]"
            self.core.add_message(user_id, 'user', user_text, media_id)
            self.core.add_message(user_id, 'assistant', response_text)
            
            for chunk in self._split_message(response_text):
                await update.message.reply_text(
                    chunk, 
                    parse_mode='Markdown',
                    reply_to_message_id=update.message.message_id
                )
        
        except Exception as e:
            await self._log_error(user_id, e)
            error_msg = str(e)
            if not error_msg.startswith(('⏱', '❌')):
                error_msg = "❌ Something went wrong. Try again! 🔄"
            await update.message.reply_text(error_msg)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if not query.from_user:
            return
        
        user_id = query.from_user.id
        data = query.data
        
        if data == "clear_confirm":
            self.core.forget_context(user_id)
            await query.message.edit_text("✅ Context forgotten! (History preserved) 📚", parse_mode='Markdown')
        
        elif data == "clear_cancel":
            await query.message.edit_text("👍 Context kept!")
        
        elif data == "settings_back":
            await self._show_settings_menu(query.message, user_id, edit=True)
        
        elif data == "settings_model":
            await self._show_model_menu(query.message, user_id)
        
        elif data == "settings_persona":
            await self._show_persona_menu(query.message, user_id)
        
        elif data == "settings_plan":
            await self._show_plan_menu(query.message, user_id)
        
        elif data == "settings_custom":
            await self._show_custom_instruction(query.message, user_id)
        
        elif data.startswith("model_"):
            model = data.split("_", 1)[1]
            self.core.update_settings(user_id, model=model)
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="settings_back")]]
            await query.message.edit_text(
                f"✅ Model changed to *{model}*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("persona_"):
            persona = data.split("_", 1)[1]
            plan = self.core.get_user_plan(user_id)
            available = self.core.get_available_personas(plan)
            
            if persona in available:
                instruction = self.core.get_persona_instruction(persona)
                self.core.update_settings(user_id, current_persona=persona, systemInstruction=instruction)
                
                name = self.core.get_persona_name(persona)
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="settings_back")]]
                await query.message.edit_text(
                    f"✅ Persona changed to *{name}*",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await query.answer("❌ Persona not available", show_alert=True)
        
        elif data.startswith("upgrade_"):
            plan = data.split("_")[1].capitalize()
            await self._send_invoice(query.from_user.id, plan)
            await query.answer("⭐ Invoice sent!")
        
        elif data == "cancel_subscription":
            keyboard = [[
                InlineKeyboardButton("✅ Yes", callback_data="cancel_confirm"),
                InlineKeyboardButton("❌ No", callback_data="settings_plan")
            ]]
            await query.message.edit_text(
                "⚠️ *Cancel subscription?*\n\nDowngrade to Free plan.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "cancel_confirm":
            self.core.cancel_subscription(user_id)
            await query.message.edit_text("✅ Subscription cancelled. Downgraded to Free.")
    
    async def handle_pre_checkout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.pre_checkout_query
        
        try:
            import json
            payload = json.loads(query.invoice_payload)
            plan = payload.get('plan')
            
            if plan not in PLAN_PRICES:
                await query.answer(ok=False, error_message="Invalid plan")
                return
            
            await query.answer(ok=True)
            
            if query.from_user:
                self.core.upgrade_plan(query.from_user.id, plan, duration_days=30)
        
        except Exception as e:
            await query.answer(ok=False, error_message="Payment error")
    
    async def _show_settings_menu(self, message: Message, user_id: int, edit: bool = False):
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
            [InlineKeyboardButton("📋 Your Plan", callback_data="settings_plan")]
        ]
        
        if self.core.has_custom_instruction(user_id):
            keyboard.insert(1, [InlineKeyboardButton("✏️ Custom Instructions", callback_data="settings_custom")])
        
        if edit:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    async def _show_model_menu(self, message: Message, user_id: int):
        plan = self.core.get_user_plan(user_id)
        available = self.core.get_available_models(plan)
        settings = self.core.get_settings(user_id)
        current = settings.get('model', 'gemini-2.5-flash')
        
        keyboard = []
        for model in available:
            desc = MODEL_DESCRIPTIONS.get(model, 'Standard')
            check = "✓ " if current == model else ""
            keyboard.append([InlineKeyboardButton(f"{check}{desc}", callback_data=f"model_{model}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
        
        await message.edit_text(
            f"*🤖 Select Model*\n\nCurrent: `{current}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _show_persona_menu(self, message: Message, user_id: int):
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
                    row.append(InlineKeyboardButton(f"{check}{name}", callback_data=f"persona_{persona}"))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
        
        current_name = self.core.get_persona_name(current)
        await message.edit_text(
            f"*👤 Select Persona*\n\nCurrent: `{current_name}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _show_plan_menu(self, message: Message, user_id: int):
        plan = self.core.get_user_plan(user_id)
        expiration = self.core.get_plan_expiration(user_id)
        
        text = f"*📋 Your Plan: {plan}*\n\n{self.core.format_plan_details(plan)}"
        
        if expiration:
            exp_date = datetime.fromisoformat(expiration).strftime('%Y-%m-%d')
            text += f"\n\n📅 Expires: *{exp_date}*"
        
        keyboard = []
        
        if plan != 'VIP':
            for upgrade_plan in ['Basic', 'Premium', 'VIP']:
                if upgrade_plan == plan:
                    continue
                price = PLAN_PRICES.get(upgrade_plan, 0)
                if price == 0:
                    continue
                keyboard.append([InlineKeyboardButton(
                    f"⬆️ {upgrade_plan} ({price}⭐/mo)",
                    callback_data=f"upgrade_{upgrade_plan.lower()}"
                )])
        
        if plan != 'Free':
            keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_subscription")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    async def _show_custom_instruction(self, message: Message, user_id: int):
        settings = self.core.get_settings(user_id)
        custom = settings.get('customInstruction', '').strip()
        
        text = (
            "*✏️ Custom Instructions*\n\n"
            "Add your own preferences to customize Gena's behavior!\n\n"
        )
        
        if custom:
            text += f"*Current:*\n`{custom}`\n\n"
        else:
            text += "_No custom instructions set_\n\n"
        
        text += "To update, send me your instructions starting with `/custom`\n"
        text += "Example: `/custom Be more formal and technical`"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="settings_back")]]
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    def _extract_response_text(self, response: Dict) -> str:
        text = ""
        if 'candidates' in response and response['candidates']:
            candidate = response['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                for part in candidate['content']['parts']:
                    if 'text' in part:
                        text += part['text']
        return text.strip()
    
    def _split_message(self, text: str, max_len: int = 4096) -> List[str]:
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
        import json
        
        price = PLAN_PRICES.get(plan, 0)
        if price == 0:
            return
        
        title = f"{plan} Plan"
        description = f"1 month subscription to Gena {plan} Plan"
        payload = json.dumps({'plan': plan, 'duration': 30})
        
        prices = [LabeledPrice(f"{plan} Monthly", price)]
        
        await self.app.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices
        )
    
    async def _log_error(self, user_id: int, error: Exception):
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
            json.dump(errors[-100:], f, indent=2)
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        print(f"Error: {context.error}")
    
    def run(self):
        """Start the bot with proper configuration"""
        print("🚀 Gena bot started!")
        try:
            self.app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
        except Exception as e:
            print(f"❌ Bot error: {e}")


if __name__ == '__main__':
    bot = GenaBot()
    bot.run()