# 🚀 Gena Bot - Complete Setup Guide

This guide will walk you through setting up Gena bot from scratch.

## 📋 Prerequisites

Before you begin, ensure you have:
- Python 3.8 or higher installed
- A Telegram account
- Internet connection
- Basic command line knowledge

## Step 1: Get Your Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Start a chat and send `/newbot`
3. Follow the prompts to:
   - Choose a name for your bot (e.g., "My Gena Bot")
   - Choose a username ending in 'bot' (e.g., "my_gena_bot")
4. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. **Important**: Keep this token secret!

## Step 2: Get Your Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated API key
5. **Important**: This key gives access to paid services - keep it secure!

## Step 3: Find Your Telegram User ID

### Method 1: Using @userinfobot
1. Search for [@userinfobot](https://t.me/userinfobot) in Telegram
2. Start the bot
3. It will reply with your user ID (a number like `123456789`)

### Method 2: Using @raw_info_bot
1. Search for [@raw_info_bot](https://t.me/raw_info_bot)
2. Start the bot and forward any message to it
3. Look for the `from.id` field in the response

## Step 4: Install the Bot

### Clone the Repository
```bash
git clone https://github.com/yourusername/gena-bot.git
cd gena-bot
```

### Create Virtual Environment (Recommended)
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

## Step 5: Configure Environment Variables

1. **Copy the example file**
```bash
# On Windows
copy .env.example .env

# On macOS/Linux
cp .env.example .env
```

2. **Edit the .env file**

Open `.env` in a text editor and fill in your values:

```env
# Your bot token from BotFather
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Your Gemini API key from Google AI Studio
GEMINI_API_KEY=AIzaSyD...your...key...here

# Your Telegram user ID (for admin access)
ADMIN_USER_IDS=123456789

# Optional: Maximum file size (default 5MB)
MAX_FILE_SIZE=5242880
```

3. **Multiple Admins** (Optional)

To add multiple admin users, separate IDs with commas:
```env
ADMIN_USER_IDS=123456789,987654321,555666777
```

## Step 6: Test the Bot

### Start the Bot
```bash
python telebot.py
```

You should see:
```
🚀 Gena bot started!
```

### Test in Telegram
1. Open Telegram
2. Search for your bot username (e.g., `@my_gena_bot`)
3. Send `/start`
4. You should receive a welcome message!

## Step 7: Common Setup Issues

### Issue: "Module not found"
**Solution**: Ensure you installed dependencies
```bash
pip install -r requirements.txt
```

### Issue: "Invalid token"
**Solution**: 
- Double-check your `TELEGRAM_TOKEN` in `.env`
- Ensure there are no extra spaces
- Make sure you copied the complete token from BotFather

### Issue: "API key invalid"
**Solution**:
- Verify your `GEMINI_API_KEY` in `.env`
- Ensure the API key is active in Google AI Studio
- Check if you have API quota remaining

### Issue: Bot doesn't respond
**Solution**:
1. Check if the bot is running (`python telebot.py`)
2. Verify the bot username is correct
3. Make sure you sent `/start` first
4. Check `data/errors/errors.json` for error logs

## Step 8: Enable Telegram Stars Payments (Optional)

To enable subscription payments:

1. Message [@BotFather](https://t.me/botfather)
2. Send `/mybots`
3. Select your bot
4. Select "Payments"
5. Select "Telegram Stars"
6. Confirm the integration

**Note**: Leave `provider_token` empty in the code for Telegram Stars.

## Step 9: Running in Production

### Using systemd (Linux)

1. Create service file: `/etc/systemd/system/gena-bot.service`
```ini
[Unit]
Description=Gena Telegram Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/gena-bot
Environment=PATH=/path/to/gena-bot/venv/bin
ExecStart=/path/to/gena-bot/venv/bin/python telebot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

2. Enable and start:
```bash
sudo systemctl enable gena-bot
sudo systemctl start gena-bot
sudo systemctl status gena-bot
```

### Using screen (Simple)

```bash
screen -S gena
python telebot.py
# Press Ctrl+A then D to detach
```

To reattach:
```bash
screen -r gena
```

### Using Docker (Advanced)

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "telebot.py"]
```

Build and run:
```bash
docker build -t gena-bot .
docker run -d --name gena --env-file .env gena-bot
```

## Step 10: Monitoring

### Check Logs
```bash
# View error logs
cat data/errors/errors.json

# Real-time monitoring (if using systemd)
sudo journalctl -u gena-bot -f
```

### Admin Dashboard
Send `/admin` to your bot to see:
- Total users
- Plan distribution
- Message statistics
- Popular personas
- Activity charts

## 📊 Database Backup

Regular backups are important:

```bash
# Backup database
cp data/gena.db backups/gena-$(date +%Y%m%d).db

# Automated backup (Linux cron)
0 2 * * * cp /path/to/gena-bot/data/gena.db /path/to/backups/gena-$(date +\%Y\%m\%d).db
```

## 🔐 Security Best Practices

1. **Never commit `.env` to git**
   - Already in `.gitignore`
   - Use environment variables in production

2. **Restrict admin access**
   - Only add trusted user IDs to `ADMIN_USER_IDS`
   - Regularly review admin list

3. **Keep dependencies updated**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

4. **Monitor API usage**
   - Check Gemini API quota regularly
   - Set up billing alerts in Google Cloud

5. **Regular backups**
   - Backup database weekly
   - Store backups securely off-server

## 🆘 Getting Help

If you encounter issues:

1. Check `data/errors/errors.json` for error details
2. Review this setup guide carefully
3. Search existing GitHub issues
4. Create a new issue with:
   - Error message
   - Steps to reproduce
   - System information
   - Relevant logs (remove sensitive data!)

## 🎉 You're Done!

Your Gena bot should now be running! Test all features:
- ✅ Send text messages
- ✅ Send images with questions
- ✅ Try `/settings` to change personas
- ✅ Test `/clear` to reset context
- ✅ Use natural language commands

Enjoy your AI companion! 🤖