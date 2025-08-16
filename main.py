import logging
import pyotp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "8465450034:AAGeFOvXRk6Cpfcm1PTW7NVJntyX-tDU7uY"

# 2FA Secret Name
SECRET_NAME = "My2FASecret"

# Inline keyboard with 2FA secret name
def get_keyboard():
    keyboard = [
        [InlineKeyboardButton(SECRET_NAME, callback_data='2fa_input')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Click the button below to generate your OTP:",
        reply_markup=get_keyboard()
    )

# Handle button click
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        f"Please send me your 2FA secret code for {SECRET_NAME}."
    )
    # Store in user_data that we're waiting for input
    context.user_data['awaiting_secret'] = True

# Handle user messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_secret'):
        secret = update.message.text.strip().replace(" ", "")
        try:
            totp = pyotp.TOTP(secret)
            otp = totp.now()
            await update.message.reply_text(f"Your OTP: `{otp}`", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text("Invalid 2FA secret. Please try again.")
        context.user_data['awaiting_secret'] = False
    else:
        await update.message.reply_text("Click the 2FA button below to start.", reply_markup=get_keyboard())

# Main function
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()