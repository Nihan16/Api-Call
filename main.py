import logging
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# আপনার বট টোকেন বসান
BOT_TOKEN = "8386739525:AAGkPaoULHOtrWLUYotmYRpzDjodz0jwV6M"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Facebook UID চেক ফাংশন
def check_facebook_uid(uid):
    url = f"https://www.facebook.com/profile.php?id={uid}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if "this content isn't available" in r.text.lower():
            return "Dead"
        elif r.status_code == 200:
            return "Live"
        else:
            return "Dead"
    except:
        return "Error"

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 হ্যালো! আমাকে ফেসবুক UID লিস্ট পাঠাও, আমি Live বা Dead বলে দেব।")

# UID চেক এবং আলাদা করে আউটপুট
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uids = [line.strip() for line in text.split("\n") if line.strip().isdigit()]

    if not uids:
        await update.message.reply_text("❌ অনুগ্রহ করে শুধু UID নাম্বার পাঠান (প্রতিটি লাইনে একটি করে)।")
        return

    live_list = []
    dead_list = []
    error_list = []

    for uid in uids:
        status = check_facebook_uid(uid)
        if status == "Live":
            live_list.append(uid)
        elif status == "Dead":
            dead_list.append(uid)
        else:
            error_list.append(uid)
        await asyncio.sleep(0.2)  # Async delay

    # আউটপুট মেসেজ তৈরি
    messages = []

    if live_list:
        messages.append("✅ **Live UIDs:**\n" + "\n".join(live_list))
    if dead_list:
        messages.append("❌ **Dead UIDs:**\n" + "\n".join(dead_list))
    if error_list:
        messages.append("⚠️ **Error UIDs:**\n" + "\n".join(error_list))

    # ব্যাচে পাঠানো
    for msg in messages:
        if len(msg) > 4000:
            parts = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
            for p in parts:
                await update.message.reply_text(p, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")

# বট চালানো
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()
