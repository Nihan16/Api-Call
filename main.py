import logging
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from bs4 import BeautifulSoup
import time

BOT_TOKEN = "8386739525:AAGkPaoULHOtrWLUYotmYRpzDjodz0jwV6M"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Facebook UID চেক (আপডেট করা লজিক)
async def check_facebook_uid_async(uid, client):
    url = f"https://www.facebook.com/profile.php?id={uid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    try:
        r = await client.get(url, headers=headers, timeout=10)
        html_text = r.text.lower()
        soup = BeautifulSoup(r.text, 'html.parser')

        # HTTP স্ট্যাটাস কোড দিয়ে চেক
        if r.status_code in [404, 405, 400]:
            return uid, "Dead"

        # og:image ডেড চেক
        og_image_tag = soup.find('meta', {'property': 'og:image'})
        if og_image_tag:
            img_url = og_image_tag.get('content', '')
            if "static.xx.fbcdn.net/rsrc.php" in img_url and "yO/r/Yp-d8W5y8v3.png" in img_url:
                return uid, "Dead"

        # ডেড কন্টেন্ট কিওয়ার্ড চেক
        dead_keywords = [
            "this content isn't available", 
            "page not found",
            "the link you followed may be broken",
            "আপনি যে পেজটি খুঁজছেন তা পাওয়া যায়নি",
            "content unavailable",
            "profile not available"
        ]
        if any(keyword in html_text for keyword in dead_keywords):
            return uid, "Dead"

        # প্রোফাইল টাইটেল/নাম না থাকলে ডেড
        og_title_tag = soup.find("meta", property="og:title")
        if not og_title_tag or not og_title_tag.get("content", "").strip():
            return uid, "Dead"

        # সব চেক পাস করলে Live
        return uid, "Live"

    except httpx.RequestError as e:
        logging.error(f"Error checking UID {uid}: {e}")
        return uid, "Error"
    except Exception as e:
        logging.error(f"Unexpected error for UID {uid}: {e}")
        return uid, "Error"

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 হ্যালো! আমাকে ফেসবুক UID লিস্ট পাঠাও, আমি Live বা Dead বলে দেব।")

# UID চেক
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uids = [line.strip() for line in text.split("\n") if line.strip().isdigit()]

    if not uids:
        await update.message.reply_text("❌ অনুগ্রহ করে শুধু UID নাম্বার পাঠান (প্রতিটি লাইনে একটি করে)।")
        return

    live_list, dead_list, error_list = [], [], []
    await update.message.reply_text(f"⏳ {len(uids)}টি UID চেকিং শুরু হয়েছে... দয়া করে অপেক্ষা করুন।")
    
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        tasks = [check_facebook_uid_async(uid, client) for uid in uids]
        results = await asyncio.gather(*tasks)

    for uid, status in results:
        if status == "Live":
            live_list.append(uid)
        elif status == "Dead":
            dead_list.append(uid)
        else:
            error_list.append(uid)
    
    end_time = time.time()
    total_time = end_time - start_time
    context.user_data['live_uids'] = live_list

    # ফলাফল প্রদর্শন
    if dead_list:
        if live_list:
            live_text = "✅ **Live UIDs:**\n" + "\n".join(live_list)
            await update.message.reply_text(live_text, parse_mode="Markdown")
        dead_text = "❌ **Dead UIDs:**\n" + "`" + "`\n`".join(dead_list) + "`"
        await update.message.reply_text(dead_text, parse_mode="Markdown")
    else:
        if live_list:
            live_only_text = f"✅ সবগুলো UID লাইভ রয়েছে ({len(live_list)}টি):\n" + "\n".join(live_list)
            await update.message.reply_text(live_only_text, parse_mode="Markdown")

    if error_list:
        error_text = "⚠️ **Error UIDs:**\n" + "\n".join(error_list)
        await update.message.reply_text(error_text, parse_mode="Markdown")

    if live_list:
        refresh_button = [[InlineKeyboardButton("Refresh Live UIDs", callback_data="refresh")]]
        reply_markup = InlineKeyboardMarkup(refresh_button)
        await update.message.reply_text(
            f"চেক করতে মোট সময় লেগেছে: **{total_time:.2f}** সেকেন্ড।",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# রিফ্রেশ বাটন
async def refresh_uids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    live_uids_to_check = context.user_data.get('live_uids', [])

    if not live_uids_to_check:
        await query.edit_message_text("আগের কোনো লাইভ UID পাওয়া যায়নি। নতুন করে তালিকা পাঠান।")
        return

    await query.edit_message_text(f"⏳ {len(live_uids_to_check)}টি লাইভ UID পুনরায় চেকিং শুরু হয়েছে...")

    newly_dead_uids, current_live_uids = [], []
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        tasks = [check_facebook_uid_async(uid, client) for uid in live_uids_to_check]
        results = await asyncio.gather(*tasks)

    for uid, status in results:
        if status == "Dead":
            newly_dead_uids.append(uid)
        elif status == "Live":
            current_live_uids.append(uid)

    end_time = time.time()
    total_time = end_time - start_time
    context.user_data['live_uids'] = current_live_uids

    output_message = ""
    if newly_dead_uids:
        output_message += "⚠️ **নতুন করে ডেড হওয়া UID-গুলো:**\n" + "`" + "`\n`".join(newly_dead_uids) + "`\n\n"
    if current_live_uids:
        output_message += f"✅ **বর্তমানে লাইভ UID-গুলো ({len(current_live_uids)}টি):**\n" + "\n".join(current_live_uids) + "\n\n"
    if not output_message:
        output_message = "কোনো UID লাইভ পাওয়া যায়নি।"

    output_message += f"রিফ্রেশ করতে মোট সময় লেগেছে: **{total_time:.2f}** সেকেন্ড।"
    
    refresh_button = [[InlineKeyboardButton("Refresh Live UIDs", callback_data="refresh")]]
    reply_markup = InlineKeyboardMarkup(refresh_button)

    await query.edit_message_text(output_message, reply_markup=reply_markup, parse_mode="Markdown")

# বট চালানো
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(refresh_uids))
    app.run_polling()
