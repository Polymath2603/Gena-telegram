# 🤖 Gena - AI Telegram Bot

A powerful, multi-persona AI chatbot for Telegram with image support, conversation memory, and flexible subscription plans.

## ✨ Features

- **🧠 Multiple AI Personas**: Switch between Friend, Advisor, Artist, Scholar, Coach, and Mystic
- **🖼️ Image Support**: Send images with questions for visual analysis
- **💭 Conversation Memory**: Context-aware responses based on chat history
- **⚡ Rate Limiting**: Fair usage with tier-based limits
- **📊 Admin Dashboard**: Analytics and usage statistics
- **💳 Telegram Stars Payment**: Seamless in-app subscription upgrades
- **🔒 Safety Controls**: Built-in content filtering and moderation

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Google Gemini API Key (from [Google AI Studio](https://makersuite.google.com/app/apikey))

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/gena-bot.git
cd gena-bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
TELEGRAM_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
ADMIN_USER_IDS=your_telegram_user_id
```

4. **Run the bot**
```bash
python telebot.py
```

## 📋 Plans & Pricing

| Plan | Price | Messages/min | Images/day | Context | Personas | Models |
|------|-------|--------------|------------|---------|----------|--------|
| **Free** | $0 | 5 | 3 | 0 turns | 1 | 1 |
| **Basic** | 50⭐/mo | 10 | 5 | 3 turns | 3 | 2 |
| **Premium** | 100⭐/mo | 20 | 10 | 5 turns | 5 | 3 |
| **VIP** | 200⭐/mo | 30 | 50 | 8 turns | 6 | 4 |

## 🎭 Personas

- **Friend** - Casual, supportive companion
- **Advisor** - Strategic, logical guide
- **Artist** - Creative, experimental visionary
- **Scholar** - Academic, detail-oriented expert
- **Coach** - Motivational, goal-focused trainer
- **Mystic** - Spiritual, philosophical seeker

## 📝 Commands

- `/start` - Initialize the bot
- `/help` - Show help message
- `/settings` - Configure bot settings
- `/clear` - Forget conversation context
- `/admin` - Admin dashboard (admin only)

## 🧩 Natural Language Commands

The bot understands natural language:
- "clear my context"
- "show settings"
- "change persona to advisor"
- "what's my plan"

## 🏗️ Project Structure

```
gena-bot/
├── telebot.py           # Telegram bot interface
├── gena.py              # Core business logic
├── database.py          # Database operations
├── nlu.py               # Natural language understanding
├── admin_dashboard.py   # Analytics dashboard
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── README.md           # This file
└── data/               # Data directory (auto-created)
    ├── errors/         # Error logs
    └── gena.db         # SQLite database
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_TOKEN` | Bot token from @BotFather | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `ADMIN_USER_IDS` | Comma-separated admin IDs | Yes |
| `MAX_FILE_SIZE` | Max image size (default: 5MB) | No |

### Database Schema

The bot uses SQLite with the following tables:
- `users` - User information
- `plans` - Subscription plans
- `settings` - User preferences
- `usage` - Rate limiting data
- `message_history` - Conversation logs
- `safety_settings` - Content moderation rules

## 🛡️ Safety & Moderation

Built-in safety controls:
- Content filtering for harassment, hate speech, explicit content
- Rate limiting per plan tier
- Image upload limits
- Context length restrictions

## 📊 Admin Dashboard

Access analytics with `/admin`:
- Total users and messages
- Plan distribution
- Popular personas
- Daily activity charts
- Top users by activity

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🐛 Troubleshooting

### Common Issues

**Bot doesn't respond**
- Check if `TELEGRAM_TOKEN` is correct
- Verify bot is running (`python telebot.py`)
- Check logs in `data/errors/errors.json`

**API errors**
- Verify `GEMINI_API_KEY` is valid
- Check API quota limits
- Review safety settings

**Database errors**
- Delete `data/gena.db` to reset
- Check file permissions
- Verify SQLite installation

## 📞 Support

- Create an issue on GitHub
- Contact via Telegram: [@yourusername](https://t.me/yourusername)
- Email: your.email@example.com

## 🙏 Acknowledgments

- Built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- Powered by [Google Gemini API](https://ai.google.dev/)
- Inspired by the AI community

---

Made with ❤️ by [Your Name]