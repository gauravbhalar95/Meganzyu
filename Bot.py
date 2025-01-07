from flask import Flask, request
from mega import Mega
import telebot
import os

# Initialize Flask app
app = Flask(__name__)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 8443))  # Default to port 8443
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Webhook URL (set in environment)

# Initialize Telegram bot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Mega.nz instance
mega = Mega()
user_credentials = {}  # Dictionary to store user-specific credentials

# Webhook endpoint
@app.route(f"/webhook", methods=["POST"])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "OK", 200
    else:
        return "Unsupported Media Type", 415

# Start command to provide instructions
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "Welcome! To use the bot:\n1. Send your Mega.nz email and password in this format:\n   `/credentials email password`\n2. Send any file to upload it to Mega.nz in the folder 'my_mega_folder'."
    )

# Handle credentials input
@bot.message_handler(commands=['credentials'])
def set_credentials(message):
    try:
        # Parse the message text
        _, email, password = message.text.split(' ', 2)
        user_credentials[message.chat.id] = {"email": email, "password": password}
        bot.reply_to(message, "Credentials saved! You can now send files for upload.")
    except ValueError:
        bot.reply_to(message, "Invalid format. Use `/credentials email password`.")

# Handle file uploads
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def handle_file(message):
    chat_id = message.chat.id

    # Check if credentials are set
    if chat_id not in user_credentials:
        bot.reply_to(message, "Please set your Mega.nz credentials first using `/credentials email password`.")
        return

    try:
        # Login to Mega.nz with user credentials
        credentials = user_credentials[chat_id]
        mega_client = mega.login(credentials['email'], credentials['password'])

        # Create or find the folder "my_mega_folder"
        folder_name = "my_mega_folder"
        folder = mega_client.find(folder_name)
        if folder is None:
            folder = mega_client.create_folder(folder_name)

        # Determine the type of content and download it
        if message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name
        elif message.photo:
            file_id = message.photo[-1].file_id
            file_name = f"photo_{message.photo[-1].file_unique_id}.jpg"
        elif message.video:
            file_id = message.video.file_id
            file_name = message.video.file_name or f"video_{message.video.file_unique_id}.mp4"
        elif message.audio:
            file_id = message.audio.file_id
            file_name = message.audio.file_name or f"audio_{message.audio.file_unique_id}.mp3"
        else:
            bot.reply_to(message, "Unsupported file type.")
            return

        # Download the file from Telegram
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Save file locally
        with open(file_name, "wb") as new_file:
            new_file.write(downloaded_file)

        # Upload to Mega.nz
        uploaded_file = mega_client.upload(file_name, folder[0])
        mega_link = mega_client.get_upload_link(uploaded_file)

        # Reply with Mega.nz link
        bot.reply_to(message, f"File uploaded successfully to '{folder_name}'! Here's your link: {mega_link}")

        # Clean up local file
        os.remove(file_name)

    except Exception as e:
        bot.reply_to(message, f"An error occurred: {str(e)}")

# Fallback for unsupported messages
@bot.message_handler(func=lambda message: True)
def fallback(message):
    bot.reply_to(message, "Please use `/credentials email password` to set your Mega.nz credentials.")

# Start Flask server
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=PORT)