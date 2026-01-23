from flask import Flask, request
from pymessenger.bot import Bot

app = Flask(__name__)

# Replace with your actual values
PAGE_ACCESS_TOKEN = "YOUR_PAGE_ACCESS_TOKEN_HERE"
VERIFY_TOKEN = "YOUR_VERIFY_TOKEN_HERE"

bot = Bot(PAGE_ACCESS_TOKEN)

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403

    if request.method == "POST":
        data = request.get_json()
        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    if "message" in event and "text" in event["message"]:
                        sender_id = event["sender"]["id"]
                        text = event["message"]["text"]
                        bot.send_text_message(sender_id, f"Echo: {text}")
        return "OK", 200

if __name__ == "__main__":
    app.run(port=5000)