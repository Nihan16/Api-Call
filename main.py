import logging
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# আপনার বট টোকেন বসান
BOT_TOKEN = "8386739525:AAGkPaoULHOtrWLUYotmYRpzDjodz0jwV6M"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# থ্রেড পুল ইনিশিয়ালাইজ করা
executor = ThreadPoolExecutor(max_workers=10) # 10টি থ্রেড দিয়ে একবারে 10টি UID চেক করা হবে

# Facebook UID চেক ফাংশন (আপডেট করা)
def check_facebook_uid(uid):
    url = f"https://www.facebook.com/profile.php?id={uid}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code == 404:
            return "Dead"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        og_image_tag = soup.find('meta', {'property': 'og:image'})
        
        if og_image_tag and "https://static.xx.fbcdn.net/rsrc.php/v3/yO/r/Yp-d8W5y8v3.png" in og_image_tag['content']:
            return "Dead"
        elif og_image_tag and "https://static.xx.fbcdn.net/rsrc.php/v3/yO/r/Yp-d8W5y8v3.png" not in og_image_tag['content']:
            return "Live"
        else:
            return "Dead"

    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking UID {uid}: {e}")
        return "Error"
    except Exception as e:
        logging.error(f"An unexpected error occurred for UID {uid}: {e}")
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

    await update.message.reply_text(f"⏳ {len(uids)}টি UID চেকিং শুরু হয়েছে... দয়া করে অপেক্ষা করুন।")

    live_list = []
    dead_list = []
    error_list = []

    # মাল্টি-থ্রেডিং ব্যবহার করে UID চেক করা
    loop = asyncio.get_event_loop()
    futures = [loop.run_in_executor(executor, check_facebook_uid, uid) for uid in uids]
    
    # সকল UID চেক শেষ হওয়া পর্যন্ত অপেক্ষা করা
    results = await asyncio.gather(*futures)

    for uid, status in zip(uids, results):
        if status == "Live":
            live_list.append(uid)
        elif status == "Dead":
            dead_list.append(uid)
        else:
            error_list.append(uid)
    
    # আউটপুট মেসেজ তৈরি
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

# বট চালানো
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()
    
