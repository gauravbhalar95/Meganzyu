import os
import logging
from flask import Flask, request
import telebot
from mega import Mega

# Environment Variables
API_TOKEN = os.getenv('API_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Public URL for the bot
TEMP_FOLDER = "temp"

# Initialize bot and Mega
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
mega_client = None
user_target_folder = {}

# Logging configuration
logging.basicConfig(level=logging.DEBUG)

# Command to log in to Mega.nz
@bot.message_handler(commands=['meganz'])
def handle_mega_login(message):
    global mega_client
    args = message.text.split(maxsplit=2)

    try:
        if len(args) == 1:
            mega_client = Mega().login()
            bot.reply_to(message, "Logged in to Mega.nz anonymously!")
        elif len(args) == 3:
            email, password = args[1], args[2]
            mega_client = Mega().login(email, password)
            bot.reply_to(message, "Successfully logged in to Mega.nz!")
        else:
            bot.reply_to(message, "Usage: /meganz <username> <password>")
    except Exception as e:
        bot.reply_to(message, f"Login failed: {str(e)}")

# Command to list folders
@bot.message_handler(commands=['listfolders'])
def list_folders(message):
    global mega_client
    if mega_client is None:
        bot.reply_to(message, "Please log in first using /meganz <username> <password>.")
        return

    try:
        folders = mega_client.get_folders()
        folder_names = [f['a']['n'] for f in folders.values() if 'a' in f and 'n' in f['a']]
        if not folder_names:
            bot.reply_to(message, "No folders found. Use the Mega.nz web interface to create folders.")
        else:
            folder_list = "\n".join(f"{idx + 1}. {name}" for idx, name in enumerate(folder_names))
            bot.reply_to(message, f"Available folders:\n{folder_list}\n\nReply with the folder number to select it.")
    except Exception as e:
        bot.reply_to(message, f"Failed to retrieve folders: {str(e)}")

# Set target folder based on user reply
@bot.message_handler(func=lambda message: message.text.isdigit())
def set_target_folder(message):
    global mega_client, user_target_folder
    if mega_client is None:
        bot.reply_to(message, "Please log in first using /meganz <username> <password>.")
        return

    try:
        folders = mega_client.get_folders()
        folder_names = [f['a']['n'] for f in folders.values() if 'a' in f and 'n' in f['a']]
        folder_index = int(message.text) - 1

        if 0 <= folder_index < len(folder_names):
            user_target_folder[message.chat.id] = folder_names[folder_index]
            bot.reply_to(message, f"Target folder set to: {folder_names[folder_index]}")
        else:
            bot.reply_to(message, "Invalid folder number. Please try again.")
    except Exception as e:
        bot.reply_to(message, f"Error setting folder: {str(e)}")

# Handle any file upload
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def handle_file_upload(message):
    global mega_client, user_target_folder
    if mega_client is None:
        bot.reply_to(message, "Please log in first using /meganz <username> <password>.")
        return

    if message.chat.id not in user_target_folder:
        bot.reply_to(message, "Please set a target folder using /listfolders.")
        return

    target_folder = user_target_folder[message.chat.id]

    try:
        # Determine file type and download
        file_info = None
        file_name = None
        if message.content_type == 'document':
            file_info = bot.get_file(message.document.file_id)
            file_name = message.document.file_name
        elif message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            file_name = "photo.jpg"
        elif message.content_type == 'video':
            file_info = bot.get_file(message.video.file_id)
            file_name = message.video.file_name
        elif message.content_type == 'audio':
            file_info = bot.get_file(message.audio.file_id)
            file_name = message.audio.file_name

        # Create temp folder if not exists
        if not os.path.exists(TEMP_FOLDER):
            os.makedirs(TEMP_FOLDER)

        # Save file locally
        file_path = os.path.join(TEMP_FOLDER, file_name)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Upload to Mega.nz
        bot.reply_to(message, "Uploading the file to Mega.nz...")
        public_link = upload_to_mega(file_path, target_folder)
        bot.reply_to(message, f"File uploaded successfully! Public link: {public_link}")

        # Cleanup
        os.remove(file_path)
    except Exception as e:
        logging.error("Error during file upload", exc_info=True)
        bot.reply_to(message, f"File upload failed: {str(e)}")

# Upload file to Mega.nz
def upload_to_mega(file_path, folder_name):
    try:
        # Find or create the target folder
        folders = mega_client.find(folder_name)
        folder = folders[0] if folders else mega_client.create_folder(folder_name)

        # Upload file
        file = mega_client.upload(file_path, folder)
        return mega_client.get_upload_link(file)
    except Exception as e:
        logging.error("Error uploading to Mega.nz", exc_info=True)
        raise

# Flask app for webhook
app = Flask(__name__)

@app.route('/' + API_TOKEN, methods=['POST'])
def bot_webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route('/')
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + '/' + API_TOKEN, timeout=60)
    return "Webhook set", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)
