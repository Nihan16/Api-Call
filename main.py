import logging
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from bs4 import BeautifulSoup
import time

# আপনার বট টোকেন বসান
BOT_TOKEN = "8386739525:AAGkPaoULHOtrWLUYotmYRpzDjodz0jwV6M"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Facebook UID চেক ফাংশন (অ্যাসিঙ্ক্রোনাস)
async def check_facebook_uid_async(uid, client):
    url = f"https://www.facebook.com/profile.php?id={uid}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    try:
        r = await client.get(url, headers=headers, timeout=5)
        
        # HTTP 404 error চেক করা
        if r.status_code == 404:
            return uid, "Dead"
        
        soup = BeautifulSoup(r.text, 'html.parser')

        # মেটা ট্যাগ বা নির্দিষ্ট টেক্সট দিয়ে ডেড প্রোফাইল চেক করা
        # এখানে og:image এর নতুন URL এবং কিছু ডেড প্রোফাইলের জন্য নির্দিষ্ট টেক্সট যোগ করা হয়েছে।
        
        # নতুন ডিফল্ট প্রোফাইল পিকচার URL
        default_profile_pic_urls = [
            "https://static.xx.fbcdn.net/rsrc.php/v3/yO/r/Yp-d8W5y8v3.png",
            "https://static.xx.fbcdn.net/rsrc.php/v3/yK/r/kH6s468L6jP.png" # একটি নতুন সম্ভাব্য ডিফল্ট URL
        ]
        
        og_image_tag = soup.find('meta', {'property': 'og:image'})
        
        if og_image_tag and any(url in og_image_tag.get('content', '') for url in default_profile_pic_urls):
            return uid, "Dead"
        
        # কিছু নির্দিষ্ট কিওয়ার্ড যা ডেড প্রোফাইলে দেখা যায়
        dead_keywords = [
            "Content not found", 
            "The link you followed may be broken", 
            "This content is no longer available",
            "This Page Isn't Available"
        ]
        
        if any(keyword in r.text for keyword in dead_keywords):
            return uid, "Dead"
        
        # যদি উপরের কোনো শর্তই না মেলে, তবে এটি লাইভ হিসেবে ধরা হবে।
        # এখানে আমরা og:type 'profile' দিয়েও নিশ্চিত হতে পারি।
        og_type_tag = soup.find('meta', {'property': 'og:type'})
        if og_type_tag and og_type_tag.get('content') == 'profile':
            return uid, "Live"
        
        # সবশেষে, যদি কোনো কিছুই খুঁজে না পাওয়া যায়, এটি সম্ভবত ডেড।
        return uid, "Dead"

    except httpx.RequestError as e:
        logging.error(f"Error checking UID {uid}: {e}")
        return uid, "Error"
    except Exception as e:
        logging.error(f"An unexpected error occurred for UID {uid}: {e}")
        return uid, "Error"

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 হ্যালো! আমাকে ফেসবুক UID লিস্ট পাঠাও, আমি Live বা Dead বলে দেব।")

# UID চেক এবং আলাদা করে আউটপুট
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # ডুপ্লিকেট UID অপসারণ
    uids_list = [line.strip() for line in text.split("\n") if line.strip().isdigit()]
    uids = list(dict.fromkeys(uids_list)) # ডুপ্লিকেট বাদ দিতে এই লাইনটি যোগ করা হয়েছে

    if not uids:
        await update.message.reply_text("❌ অনুগ্রহ করে শুধু UID নাম্বার পাঠান (প্রতিটি লাইনে একটি করে)।")
        return

    await update.message.reply_text(f"⏳ {len(uids)}টি UID চেকিং শুরু হয়েছে... দয়া করে অপেক্ষা করুন।")
    
    context.user_data['live_uids'] = []
    live_list, dead_list, error_list = [], [], []
    
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

    messages = []
    if live_list:
        live_text = "✅ **Live UIDs:**\n" + "\n".join(live_list)
        messages.append(live_text)
    
    if dead_list:
        dead_text = "❌ **Dead UIDs:**\n" + "`" + "`\n`".join(dead_list) + "`"
        messages.append(dead_text)

    if error_list:
        error_text = "⚠️ **Error UIDs:**\n" + "\n".join(error_list)
        messages.append(error_text)

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
    
    if live_list:
        refresh_button = [[InlineKeyboardButton("Refresh Live UIDs", callback_data="refresh")]]
        reply_markup = InlineKeyboardMarkup(refresh_button)
        await update.message.reply_text(f"চেক করতে মোট সময় লেগেছে: **{total_time:.2f}** সেকেন্ড।\n", reply_markup=reply_markup, parse_mode="Markdown")

# রিফ্রেশ বাটনে ক্লিক করলে
async def refresh_uids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    live_uids_to_check = context.user_data.get('live_uids', [])

    if not live_uids_to_check:
        await query.edit_message_text("আগের কোনো লাইভ UID পাওয়া যায়নি। নতুন করে তালিকা পাঠান।")
        return

    await query.edit_message_text(f"⏳ {len(live_uids_to_check)}টি লাইভ UID পুনরায় চেকিং শুরু হয়েছে...", parse_mode="Markdown")

    newly_dead_uids = []
    current_live_uids = []

    start_time = time.time()

    async with httpx.AsyncClient() as client:
        tasks = [check_facebook_uid_async(uid, client) for uid in live_uids_to_check]
        results = await asyncio.gather(*tasks)

    for uid, status in results:
        if status == "Dead":
            newly_dead_uids.append(uid)
        else:
            current_live_uids.append(uid)
            
    end_time = time.time()
    total_time = end_time - start_time
    
    context.user_data['live_uids'] = current_live_uids

    output_message = ""
    if newly_dead_uids:
        output_message += "⚠️ **নতুন করে ডেড হওয়া UID-গুলো:**\n" + "`" + "`\n`".join(newly_dead_uids) + "`" + "\n\n"
    
    output_message += f"বর্তমানে **{len(current_live_uids)}**টি UID লাইভ আছে।\n"
    output_message += f"রিফ্রেশ করতে মোট সময় লেগেছে: **{total_time:.2f}** সেকেন্ড।"

    refresh_button = [[InlineKeyboardButton("Refresh Live UIDs", callback_data="refresh")]]
    reply_markup = InlineKeyboardMarkup(refresh_button)

    await query.edit_message_text(output_message, parse_mode="Markdown", reply_markup=reply_markup)

# বট চালানো
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(refresh_uids))

    app.run_polling()
    
