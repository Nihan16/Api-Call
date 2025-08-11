import logging
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from bs4 import BeautifulSoup

# Replace with your bot token
BOT_TOKEN = "8386739525:AAGkPaoULHOtrWLUYotmYRpzDjodz0jwV6M"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Facebook UID check function (updated)
def check_facebook_uid(uid):
    url = f"https://www.facebook.com/profile.php?id={uid}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        
        # Check for specific status codes
        if r.status_code == 404:
            return "Dead"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # A more robust check: look for specific tags that exist on live profiles
        # For example, a meta tag with 'content="profile"'
        meta_tags = soup.find_all('meta', {'property': 'og:type'})
        for tag in meta_tags:
            if tag.get('content') == 'profile':
                return "Live"
        
        # If the profile type meta tag is not found, it's likely a dead link
        return "Dead"

    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking UID {uid}: {e}")
        return "Error"
    except Exception as e:
        logging.error(f"An unexpected error occurred for UID {uid}: {e}")
        return "Error"

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 হ্যালো! আমাকে ফেসবুক UID লিস্ট পাঠাও, আমি Live বা Dead বলে দেব।")

# UID check and output
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uids = [line.strip() for line in text.split("\n") if line.strip().isdigit()]

    if not uids:
        await update.message.reply_text("❌ অনুগ্রহ করে শুধু UID নাম্বার পাঠান (প্রতিটি লাইনে একটি করে)।")
        return

    live_list = []
    dead_list = []
    error_list = []

    await update.message.reply_text("⏳ চেকিং শুরু হয়েছে... দয়া করে অপেক্ষা করুন।")

    for uid in uids:
        status = check_facebook_uid(uid)
        if status == "Live":
            live_list.append(uid)
        elif status == "Dead":
            dead_list.append(uid)
        else:
            error_list.append(uid)
        await asyncio.sleep(0.5)

    messages = []
    
    if live_list:
        messages.append("✅ **Live UIDs:**\n" + "\n".join(live_list))
    if dead_list:
        messages.append("❌ **Dead UIDs:**\n" + "\n".join(dead_list))
    if error_list:
        messages.append("⚠️ **Error UIDs:**\n" + "\n".join(error_list))

    if not messages:
        await update.message.reply_text("কোনো UID পাওয়া যায়নি বা সবগুলোতে সমস্যা হয়েছে।")
        return

    for msg in messages:
        if len(msg) > 4096:
            parts = [msg[i:i+4096] for i in range(0, len(msg), 4096)]
            for p in parts:
                await update.message.reply_text(p, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")

# Run the bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()
    
