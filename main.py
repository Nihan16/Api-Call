import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    JobQueue,
)
from collections import defaultdict
import asyncio
import os
import pyotp

# বট টোকেন (আপনার বটফাদার থেকে প্রাপ্ত টোকেন এখানে বসান)
TOKEN = "8465450034:AAGeFOvXRk6Cpfcm1PTW7NVJntyX-tDU7uY"

# নির্দিষ্ট ইউজার আইডি যারা বট ব্যবহার করতে পারবে
ALLOWED_USER_IDS = [6945456838, 1607112738, 5875578536]

# ফেসবুক প্রোফাইল লিঙ্ক খুঁজে বের করার জন্য রেগুলার এক্সপ্রেশন
FACEBOOK_PROFILE_URL_PATTERN = r"(https:\/\/www\.facebook\.com\/profile\.php\?id=\d{14})"
FACEBOOK_ID_PATTERN = re.compile(r"id=(\d{14})")

# 2FA সিক্রেট কী খুঁজে বের করার জন্য রেগুলার এক্সপ্রেশন (32 অক্ষরের)
TOTP_SECRET_PATTERN = re.compile(r"^[A-Z2-7]{32}$")
# নতুন 2FA সিক্রেট কী প্যাটার্ন: 8টি গ্রুপে 4টি করে অক্ষর, স্পেস দিয়ে আলাদা
NEW_TOTP_SECRET_PATTERN = re.compile(r"([A-Z0-9]{4}\s){7}[A-Z0-9]{4}")

# ব্যবহারকারী অনুসারে মেসেজ আইডি ট্র্যাক করার জন্য ডিকশনারি
user_message_ids = defaultdict(list)
bot_response_message_ids = defaultdict(list)
# নতুন ডিকশনারি: প্রতিটি ফেসবুক আইডির জন্য বটের পাঠানো মেসেজ আইডি সংরক্ষণ করবে
facebook_id_to_message_id = defaultdict(list)

# লগিং সেটআপ করা
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """বট স্টার্ট করলে এই মেসেজটি দেখাবে।"""
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text(
            "দুঃখিত! আপনি এই বট ব্যবহার করার অনুমতিপ্রাপ্ত নন।"
        )
        logger.info(f"Unauthorized access attempt by user ID: {user_id}")
        return

    start_message = await update.message.reply_text(
        "👋 আমি প্রস্তুত! আমাকে Facebook Profile Link অথবা ৩২ অক্ষরের 2FA সিক্রেট কী মেসেজ পাঠান। আমি ফরম্যাট অনুযায়ী আউটপুট দেব।"
    )
    bot_response_message_ids[user_id].append(start_message.message_id)
    logger.info(f"User {user_id} started the bot.")

async def delete_message_after_delay(chat_id: int, message_id: int, delay: int):
    """নির্দিষ্ট সময় পর একটি মেসেজ ডিলিট করে।"""
    await asyncio.sleep(delay)
    try:
        application_instance = Application.builder().token(TOKEN).build()
        await application_instance.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Successfully deleted message {message_id} in chat {chat_id}.")
    except Exception as e:
        logger.error(f"Failed to delete message {message_id} in chat {chat_id}: {e}")

async def send_all_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ব্যবহারকারীকে তার ইনপুট থেকে পাওয়া সমস্ত আইডি দেখায়।"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text(
            "দুঃখিত! আপনি এই বট ব্যবহার করার অনুমতিপ্রাপ্ত নন।"
        )
        return

    logger.info(f"User {user_id} requested /uid command.")

    extracted_ids_per_user = context.user_data.get('extracted_ids', [])

    if extracted_ids_per_user:
        unique_ids = sorted(list(set(extracted_ids_per_user)))
        response_text = "আপনার দেওয়া মেসেজ থেকে পাওয়া **সকল আইডি**:\n" + "\n".join(unique_ids)
    else:
        response_text = "আপনার দেওয়া মেসেজ থেকে কোনো আইডি পাওয়া যায়নি।"

    response_message = await update.message.reply_text(response_text, parse_mode='Markdown')
    bot_response_message_ids[user_id].append(response_message.message_id)

    # নতুন কোড: 20 সেকেন্ড পর মেসেজটি ডিলিট করে
    asyncio.create_task(delete_message_after_delay(chat_id=chat_id, message_id=response_message.message_id, delay=20))
    asyncio.create_task(delete_message_after_delay(chat_id=chat_id, message_id=update.message.message_id, delay=20))


async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ব্যবহারকারীর এবং বটের সমস্ত পূর্ববর্তী মেসেজ মুছে ফেলে।"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text(
            "দুঃখিত! আপনি এই বট ব্যবহার করার অনুমতিপ্রাপ্ত নন।"
        )
        return

    logger.info(f"User {user_id} requested /clear command.")

    for msg_id in user_message_ids[user_id]:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            logger.info(f"Deleted user message {msg_id} in chat {chat_id}.")
        except Exception as e:
            logger.warning(f"Could not delete user message {msg_id} in chat {chat_id}: {e}")
    user_message_ids[user_id].clear()

    for msg_id in bot_response_message_ids[user_id]:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            logger.info(f"Deleted bot response message {msg_id} in chat {chat_id}.")
        except Exception as e:
            logger.warning(f"Could not delete bot response message {msg_id} in chat {chat_id}: {e}")
    bot_response_message_ids[user_id].clear()

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
        logger.info(f"Deleted /clear command message {update.message.message_id} from user {user_id}.")
    except Exception as e:
        logger.warning(f"Could not delete /clear command message {update.message.message_id}: {e}")

    context.user_data['extracted_ids'] = []
    
    # Facebook ID থেকে মেসেজ আইডি ডিকশনারি খালি করা
    facebook_id_to_message_id.clear()

    confirmation_message = await update.message.reply_text("সমস্ত চ্যাট মুছে ফেলা হয়েছে। আপনি এখন নতুন করে শুরু করতে পারেন।")
    bot_response_message_ids[user_id].append(confirmation_message.message_id)

# নতুন ডিলিট ফাংশন
async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ইনলাইন বাটনে ক্লিক করলে মেসেজগুলো মুছে ফেলে।"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    current_message_id = query.message.message_id
    
    # কলব্যাক ডেটা থেকে পূর্ববর্তী মেসেজ আইডির তালিকা পেতে
    message_ids_str = query.data.replace('delete_', '')
    message_ids = [int(mid) for mid in message_ids_str.split(',') if mid.isdigit()]
    
    message_ids.append(current_message_id)

    # সব মেসেজ ডিলিট করা
    for msg_id in set(message_ids):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            logger.info(f"Deleted message {msg_id} by inline button in chat {chat_id}.")
        except Exception as e:
            logger.warning(f"Failed to delete message {msg_id} by inline button: {e}")

async def handle_message_with_id_storage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ব্যবহারকারীর মেসেজ প্রক্রিয়া করে।"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_text = update.message.text.strip()
    response_sent = False

    if user_id not in ALLOWED_USER_IDS:
        return

    user_message_ids[user_id].append(update.message.message_id)
    logger.info(f"User {user_id} sent message: '{message_text}' (ID: {update.message.message_id})")

    # ১. যদি কোনো 2FA কী না পাওয়া যায়, তবে Facebook ID খোঁজা হবে
    extracted_ids = context.user_data.get('extracted_ids', [])
    full_url_match = re.search(FACEBOOK_PROFILE_URL_PATTERN, message_text)

    if full_url_match:
        found_link = full_url_match.group(0)
        id_match = FACEBOOK_ID_PATTERN.search(found_link)

        if id_match:
            extracted_id = id_match.group(1)
            
            if extracted_id in facebook_id_to_message_id:
                previous_message_ids = facebook_id_to_message_id[extracted_id]
                response_text = f"এই আইডিটি (`{extracted_id}`) পূর্বে ব্যবহৃত হয়েছে। নিচে তার মেসেজটি দেওয়া হলো:"
                
                # ইনলাইন বাটন মেসেজটি আগে পাঠানো
                all_ids_to_delete = previous_message_ids
                keyboard = [
                    [InlineKeyboardButton("Delete", callback_data=f"delete_{','.join(map(str, all_ids_to_delete))}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                response_message_inline = await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode='Markdown')
                bot_response_message_ids[user_id].append(response_message_inline.message_id)

                # তারপর ফরোয়ার্ড করা মেসেজটি পাঠানো
                forwarded_message = await context.bot.forward_message(chat_id=chat_id, from_chat_id=chat_id, message_id=previous_message_ids[0])
                bot_response_message_ids[user_id].append(forwarded_message.message_id)
                facebook_id_to_message_id[extracted_id].append(response_message_inline.message_id) # নতুন মেসেজ আইডি যুক্ত করা
                facebook_id_to_message_id[extracted_id].append(forwarded_message.message_id) # নতুন মেসেজ আইডি যুক্ত করা

            else:
                if extracted_id not in extracted_ids:
                    extracted_ids.append(extracted_id)
                context.user_data['extracted_ids'] = extracted_ids
                if user_id == 1607112738:
                    formatted_message_text = f"{message_text}*"
                else:
                    formatted_message_text = message_text
                response_text = (
                    f"{found_link}\n\n"
                    f"👉  `{formatted_message_text}`"
                )
                response_message = await update.message.reply_text(response_text, parse_mode='Markdown')
                logger.info(f"Found link for user {user_id}: {found_link}. Stored ID: {extracted_id}.")
                if response_message:
                    facebook_id_to_message_id[extracted_id].append(response_message.message_id)
        
        if 'response_message' in locals():
            asyncio.create_task(delete_message_after_delay(
                chat_id=chat_id,
                message_id=update.message.message_id,
                delay=15
            ))
            logger.info(f"Scheduled deletion of user message {update.message.message_id} from user {user_id}.")
        response_sent = True

    # ২. নতুন ফরম্যাট অনুযায়ী 32-character string খোঁজা
    new_secret_match = NEW_TOTP_SECRET_PATTERN.search(message_text.upper())
    if new_secret_match:
        secret = new_secret_match.group(0).replace(" ", "")
        try:
            totp = pyotp.TOTP(secret)
            code = totp.now()
            otp_message = f"""
            🔐→→→→ আপনার OTP:

            👉→→     👉   `{code}`  👈

            →→→→           ↑↑↑↑↑

            ⚠️ ৩০ সেকেন্ডের মধ্যে ব্যবহার করুন।
            """
            response_message = await update.message.reply_text(otp_message, parse_mode="Markdown")
            if response_message:
                asyncio.create_task(delete_message_after_delay(chat_id=chat_id, message_id=update.message.message_id, delay=10))
                asyncio.create_task(delete_message_after_delay(chat_id=chat_id, message_id=response_message.message_id, delay=10))
                bot_response_message_ids[user_id].append(response_message.message_id)
            logger.info(f"Generated and sent OTP for user {user_id} from new format.")
            response_sent = True
        except Exception:
            response_message = await update.message.reply_text("❌ ভুল 2FA Secret Code!")
            if response_message:
                bot_response_message_ids[user_id].append(response_message.message_id)
            logger.error(f"Failed to generate OTP for user {user_id} with new format.")
            response_sent = True

    # ৩. পুরনো ফরম্যাট (TOTP_SECRET_PATTERN) খোঁজা হবে
    elif TOTP_SECRET_PATTERN.search(message_text.replace(" ", "").upper()):
        secret = TOTP_SECRET_PATTERN.search(message_text.replace(" ", "").upper()).group(0)
        try:
            totp = pyotp.TOTP(secret)
            code = totp.now()
            otp_message = f"""
            🔐→→→→ আপনার OTP:

            👉→→     👉   `{code}`  👈

            →→→→           ↑↑↑↑↑

            ⚠️ ৩০ সেকেন্ডের মধ্যে ব্যবহার করুন।
            """
            response_message = await update.message.reply_text(otp_message, parse_mode="Markdown")
            if response_message:
                asyncio.create_task(delete_message_after_delay(chat_id=chat_id, message_id=update.message.message_id, delay=10))
                asyncio.create_task(delete_message_after_delay(chat_id=chat_id, message_id=response_message.message_id, delay=10))
                bot_response_message_ids[user_id].append(response_message.message_id)
            logger.info(f"Generated and sent OTP for user {user_id} from old format.")
            response_sent = True
        except Exception:
            response_message = await update.message.reply_text("❌ ভুল 2FA Secret Code!")
            if response_message:
                bot_response_message_ids[user_id].append(response_message.message_id)
            logger.error(f"Failed to generate OTP for user {user_id} with old format.")
            response_sent = True

    # যদি কোনো প্যাটার্নই না পাওয়া যায়
    if not response_sent:
        response_message = await update.message.reply_text(
            "আপনার মেসেজে কোনো নির্দিষ্ট ফেসবুক প্রোফাইল আইডি অথবা 2FA সিক্রেট কী খুঁজে পাইনি।"
        )
        logger.info(f"No ID or 2FA key found in message from user {user_id}.")
        if response_message:
            asyncio.create_task(delete_message_after_delay(
                chat_id=chat_id,
                message_id=update.message.message_id,
                delay=15
            ))
            asyncio.create_task(delete_message_after_delay(
                chat_id=chat_id,
                message_id=response_message.message_id,
                delay=15
            ))
            bot_response_message_ids[user_id].append(response_message.message_id)

async def send_scheduled_messages(context: ContextTypes.DEFAULT_TYPE):
    """
    নির্দিষ্ট ইউজারকে প্রতি 3 মিনিট 30 সেকেন্ডে একটি মেসেজ পাঠায় যাতে বট স্লিপ না করে।
    """
    # এখানে আপনার টার্গেট ইউজার আইডি দিন
    target_user_id = 5875578536
    
    # একটি ছোট মেসেজ যা বটকে সচল রাখবে
    message_text = "Bot is active! 🚀"
    
    try:
        await context.bot.send_message(chat_id=target_user_id, text=message_text)
        logger.info(f"Keep-alive message sent to user {target_user_id}.")
    except Exception as e:
        logger.error(f"Failed to send keep-alive message to {target_user_id}: {e}")

def main():
    """বট শুরু করার প্রধান ফাংশন।"""
    application = Application.builder().token(TOKEN).build()
    
    # JobQueue ইনস্ট্যান্স তৈরি করে Application এর সাথে যুক্ত করা
    job_queue_instance = application.job_queue
    
    # কমান্ড হ্যান্ডলার যোগ করা
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("uid", send_all_ids))
    application.add_handler(CommandHandler("clear", clear_chat))

    # মেসেজ হ্যান্ডলার যোগ করা
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_with_id_storage))
    
    # ইনলাইন বাটন কলব্যাক হ্যান্ডলার যোগ করা
    application.add_handler(CallbackQueryHandler(delete_message))
    
    # নতুন কোড: ব্যাকগ্রাউন্ডে মেসেজ পাঠানোর টাস্ক শুরু করা
    # প্রতি 3 মিনিট 30 সেকেন্ড (210 সেকেন্ড) পর পর send_scheduled_messages ফাংশনটি চলবে
    job_queue_instance.run_repeating(send_scheduled_messages, interval=210, first=210)

    # বট পোলিং শুরু করা
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot started polling.")

if __name__ == "__main__":
    main()
