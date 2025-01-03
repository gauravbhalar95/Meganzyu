import os
import subprocess
from flask import Flask, request
import telebot

# Environment variables
API_TOKEN = os.getenv("API_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# Flask app
app = Flask(__name__)

# Helper functions
def execute_mega_command(command):
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise Exception(e.stderr.strip())

def get_folders():
    try:
        output = execute_mega_command(["megacl", "ls"])
        folders = [line.split()[-1] for line in output.splitlines() if "<DIR>" in line]
        return folders
    except Exception as e:
        return []

# Bot handlers for file upload
@bot.message_handler(content_types=["document", "photo", "video", "audio", "voice", "sticker", "animation"])
def handle_file_upload(message):
    # Detect file type
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    elif message.photo:
        file_id = message.photo[-1].file_id  # Get the highest resolution photo
        file_name = f"{message.date}_{message.chat.id}.jpg"
    elif message.video:
        file_id = message.video.file_id
        file_name = f"{message.date}_{message.chat.id}.mp4"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = f"{message.date}_{message.chat.id}.mp3"
    else:
        file_id = None
        file_name = None

    if file_id:
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path

        try:
            # Download the file from Telegram
            downloaded_file = bot.download_file(file_path)
            with open(file_name, "wb") as new_file:
                new_file.write(downloaded_file)

            # Get folders from Mega.nz
            folders = get_folders()
            if not folders:
                bot.reply_to(message, "No folders found in Mega.nz. Uploading to root.")
                execute_mega_command(["megacl", "put", file_name])
            else:
                # Send folder list to user
                markup = telebot.types.InlineKeyboardMarkup()
                for folder in folders:
                    markup.add(telebot.types.InlineKeyboardButton(folder, callback_data=f"upload:{file_name}:{folder}"))
                bot.reply_to(message, "Choose a folder to upload:", reply_markup=markup)

        except Exception as e:
            bot.reply_to(message, f"Error: {str(e)}")

# Bot callback handler for folder selection
@bot.callback_query_handler(func=lambda call: call.data.startswith("upload"))
def handle_folder_selection(call):
    try:
        _, file_name, folder = call.data.split(":")
        # Change directory to selected folder in Mega.nz
        execute_mega_command(["megacl", "cd", folder])
        # Upload the file to the selected folder
        execute_mega_command(["megacl", "put", file_name])
        # Share and get the public link for the uploaded file
        link = execute_mega_command(["megacl", "share", "--link", file_name])
        bot.send_message(call.message.chat.id, f"Uploaded to Mega.nz in folder '{folder}': {link}")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Failed to upload: {str(e)}")

# Webhook handling
@app.route(f"/{API_TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route("/")
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{API_TOKEN}")
    return "Webhook set!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)