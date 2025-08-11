import logging
import requests
import asyncio
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from bs4 import BeautifulSoup

# আপনার বট টোকেন বসান
BOT_TOKEN = "8386739525:AAGkPaoULHOtrWLUYotmYRpzDjodz0jwV6M"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Facebook UID চেক ফাংশন
def check_facebook_uid(uid):
    url = f"https://www.facebook.com/profile.php?id={uid}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code == 404:
            return "Dead"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        og_type_tag = soup.find('meta', {'property': 'og:type'})
        og_image_tag = soup.find('meta', {'property': 'og:image'})
        
        if og_type_tag and og_type_tag.get('content') == 'profile':
            return "Live"
        elif og_image_tag and "https://static.xx.fbcdn.net/rsrc.php/v3/yO/r/Yp-d8W5y8v3.png" in og_image_tag.get('content', ''):
            return "Dead"
        elif "this content isn't available" in r.text.lower():
            return "Dead"
        else:
            return "Live"

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

    # এখানে একটি একটি করে UID চেক করা হচ্ছে
    for uid in uids:
        status = check_facebook_uid(uid)
        if status == "Live":
            live_list.append(uid)
        elif status == "Dead":
            dead_list.append(uid)
        else:
            error_list.append(uid)
        await asyncio.sleep(0.01) # 0.01 সেকেন্ডের ডিলে যোগ করা হয়েছে

    messages = []
    
    if live_list:
        live_uids_text = "\n".join(live_list)
        messages.append(f"✅ **Live UIDs:**\n{live_uids_text}")
        
        callback_data = {
            'action': 'refresh',
            'uids': live_list
        }
        keyboard = [[InlineKeyboardButton("🔄 Refresh Live UIDs", callback_data=json.dumps(callback_data))]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    if dead_list:
        monospaced_dead_uids = [f"`{uid}`" for uid in dead_list]
        messages.append("❌ **Dead UIDs:**\n" + "\n".join(monospaced_dead_uids))

    if error_list:
        messages.append("⚠️ **Error UIDs:**\n" + "\n".join(error_list))

    if not messages:
        await update.message.reply_text("কোনো UID পাওয়া যায়নি বা সবগুলোতে সমস্যা হয়েছে।")
        return

    for i, msg in enumerate(messages):
        if i == len(messages) - 1 and 'reply_markup' in locals():
            await update.message.reply_text(msg, parse_mode="MarkdownV2", reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode="MarkdownV2")

# ইনলাইন বাটন হ্যান্ডেল করার জন্য নতুন ফাংশন
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = json.loads(query.data)
    action = data.get('action')
    uids = data.get('uids')

    if action == 'refresh' and uids:
        await query.edit_message_text("⏳ রিফ্রেশ করা হচ্ছে... দয়া করে অপেক্ষা করুন।")

        newly_dead_uids = []
        newly_live_uids = []

        # এখানেও একটি একটি করে UID চেক করা হচ্ছে
        for uid in uids:
            status = check_facebook_uid(uid)
            if status == "Dead":
                newly_dead_uids.append(uid)
            else:
                newly_live_uids.append(uid)
            await asyncio.sleep(0.01) # 0.01 সেকেন্ডের ডিলে

        response_message = ""
        if newly_dead_uids:
            monospaced_dead_uids = [f"`{uid}`" for uid in newly_dead_uids]
            response_message += "❌ **নতুন ডেড UIDs:**\n" + "\n".join(monospaced_dead_uids)
        
        response_message += f"\n\n✅ এখনও **{len(newly_live_uids)}**টি UID লাইভ আছে।"
        
        callback_data_new = {
            'action': 'refresh',
            'uids': newly_live_uids
        }
        keyboard = [[InlineKeyboardButton("🔄 Refresh Live UIDs", callback_data=json.dumps(callback_data_new))]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if response_message:
            await query.edit_message_text(response_message, parse_mode="MarkdownV2", reply_markup=reply_markup)
        else:
            await query.edit_message_text("সবগুলো UID এখনো লাইভ আছে।", reply_markup=reply_markup)

# বট চালানো
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    app.run_polling()
        
