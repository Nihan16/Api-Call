import logging
import time
import base64
import pyotp
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ============================
# কনফিগ
# ============================
BOT_TOKEN = "8465450034:AAGeFOvXRk6Cpfcm1PTW7NVJntyX-tDU7uY"
TARGET_USER = 5875578536   # শুধুমাত্র এই ইউজার কাজ পাবে
TOTP_INTERVAL = 30         # ৩০ সেকেন্ডে OTP পরিবর্তন হবে

# লগিং
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ============================
# জব ফাংশন (৩ মিনিট পরপর)
# ============================
async def send_active_message(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=TARGET_USER, text="✅ bot is active")

# ============================
# 2FA OTP জেনারেটর
# ============================
def generate_totp(secret: str) -> tuple[str, int]:
    totp = pyotp.TOTP(secret, interval=TOTP_INTERVAL)
    code = totp.now()
    remaining = TOTP_INTERVAL - int(time.time()) % TOTP_INTERVAL
    return code, remaining

# ============================
# হ্যান্ডলার
# ============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id != TARGET_USER:
        await update.message.reply_text("❌ আপনি অনুমোদিত নন।")
        return

    # পুরনো জব ক্যানসেল
    for job in context.job_queue.jobs():
        job.schedule_removal()

    # নতুন জব চালু (প্রতি 3 মিনিটে)
    context.job_queue.run_repeating(send_active_message, interval=180, first=0)

    await update.message.reply_text("▶️ 3 মিনিট পরপর 'bot is active' পাঠানো শুরু হলো।")


async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id != TARGET_USER:
        await update.message.reply_text("❌ আপনি অনুমোদিত নন।")
        return

    text = update.message.text.strip().replace(" ", "").upper()

    # Secret হলে OTP জেনারেট
    try:
        # pyotp ইনভ্যালিড হলে error দেবে
        base64.b32decode(text, casefold=True)
        code, remaining = generate_totp(text)
        reply = (
            f"🔑 OTP (৬ ডিজিট): `{code}`\n"
            f"⏳ রিফ্রেশ হবে {remaining} সেকেন্ড পরে"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")
        return
    except Exception:
        pass

    # অন্য যেকোনো ইনপুট দিলে Active Job রিস্টার্ট হবে
    for job in context.job_queue.jobs():
        job.schedule_removal()

    context.job_queue.run_repeating(send_active_message, interval=180, first=0)
    await update.message.reply_text("🔄 নতুন করে ৩ মিনিট ইন্টারভ্যাল শুরু হলো।")

# ============================
# মেইন
# ============================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))

    print("🤖 Bot running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()