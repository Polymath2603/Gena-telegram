# Gena 🤖

> Telegram bot powered by Google Gemini AI. Intelligent conversations, image analysis, and customizable personas.

**Status:** Active development 🟢

A Telegram bot that uses Google Gemini for intelligent conversations, image analysis, and customizable personas with tiered subscription plans.

## Features
- 💬 Chat with Gemini directly on Telegram
- 🖼 Vision support — send images and ask questions about them
- 🎭 Custom personas via `/settings` (Buddy, Wise, Creative, Geeky, Hype, Chill, Sarcastic, Coach)
- 🗑 `/clear` to reset conversation context
- ⚙️ Customizable behavior settings & model selection
- ⭐ Telegram Stars subscription payments (Basic / Premium / VIP)
- 👑 Admin dashboard with `/admin` (analytics, user management, backups)

## Setup
1. Set `GEMINI_API_KEY` and `TELEGRAM_BOT_TOKEN` in `.env`
2. Run: `python src/telebot.py`

See [SETUP.md](SETUP.md) for detailed instructions.

## Structure
```
gena/
├── src/
│   ├── telebot.py        # Telegram bot interface
│   ├── gena.py           # Core logic & plan configuration
│   ├── database.py       # SQLite database manager
│   ├── nlu.py            # Natural language intent detection
│   ├── personas.py       # Persona definitions & access control
│   ├── admin_dashboard.py# Admin analytics & reporting
│   └── fix_database.py   # Database migration tool
├── data/                 # Database, media, error logs
├── PRIVACY_POLICY.md
├── SETUP.md
└── LICENSE
```

## Support

If you find this useful, consider supporting:

| Token | Address / Method |
|---|---|
| PayPal | `paypal.com/ncp/payment/W78F6W4TXZ4CS` |
| Binance | UID `1011264323` |
| Bybit | UID `467077834` |
| BTC | `15kPSKNLEgVH6Jy3RtNaT2mPsxTMS6MAEp` |
| SOL | `EWcxGVtbohy8CdFLb2HNUqSHdecRiWKLywgMLwsXByhn` |
| LTC | via Binance UID `1011264323` |
| TON | via Bybit UID `467077834` |
| TRC20 (USDT) | `TMW5uSDN6sMUBNirMoqY1icpsfa7GhPZfK` |
| BEP20/ERC20 | `0x7a8887c2ac3e596f6170c9e28b44e6b6d025c854` |
