from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import re

# আপনার বট টোকেন এখানে দিন
TOKEN = "8386739525:AAGkPaoULHOtrWLUYotmYRpzDjodz0jwV6M"

# সোর্স গ্রুপ এবং বটের আইডি
SOURCE_CHAT_ID = -1002776669757
SOURCE_BOT_ID = 8338117097

# এই ডিকশনারিতে ব্যবহারকারীর চ্যাট আইডি এবং তাদের দেওয়া ফোন নম্বর সংরক্ষণ করা হবে
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start কমান্ডের জন্য হ্যান্ডলার"""
    user_id = update.effective_user.id
    user_data[user_id] = {"target_phone": None}
    await update.message.reply_text(
        "স্বাগতম! আপনি যে নম্বরের OTP পেতে চান সেটি আমাকে মেসেজ বক্সে পাঠান।\n"
        "উদাহরণ: 93726556"
    )

async def set_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """মেসেজ থেকে ফোন নম্বর নেওয়ার জন্য হ্যান্ডলার"""
    user_id = update.effective_user.id
    phone_number = update.message.text.strip()
    
    # ফোন নম্বরটি একটি বৈধ ফরম্যাটে আছে কিনা তা যাচাই করা
    if re.match(r"^\d{8,12}$", phone_number): # আপনার দেশের ফোন নম্বরের ফরম্যাট অনুযায়ী রেগুলার এক্সপ্রেশনটি পরিবর্তন করতে পারেন
        user_data[user_id]["target_phone"] = phone_number
        await update.message.reply_text(
            f"ঠিক আছে! আমি এখন এই নম্বরের OTP খুঁজছি: {phone_number}\n"
            "OTP পেলে আমি আপনাকে জানিয়ে দেব।"
        )
    else:
        await update.message.reply_text(
            "এটি একটি বৈধ ফোন নম্বর নয়। অনুগ্রহ করে সঠিক ফোন নম্বরটি পাঠান।"
        )


async def forward_otp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """সোর্স গ্রুপ থেকে OTP খুঁজে ফরোয়ার্ড করার জন্য হ্যান্ডলার"""
    message = update.effective_message

    # মেসেজটি সঠিক বট এবং গ্রুপ থেকে এসেছে কিনা তা যাচাই করা
    if message.from_user.id == SOURCE_BOT_ID and message.chat.id == SOURCE_CHAT_ID:
        
        message_text = message.text
        
        # প্রতিটি ব্যবহারকারীর জন্য তাদের সেট করা ফোন নম্বরটি খুঁজে বের করা
        for user_id, data in user_data.items():
            target_phone = data["target_phone"]
            if target_phone:
                
                # রেগুলার এক্সপ্রেশন ব্যবহার করে মেসেজে ফোন নম্বর এবং কোড খুঁজে বের করা
                # আপনার দেওয়া ফরম্যাট অনুযায়ী প্যাটার্নটি তৈরি করা হয়েছে
                # প্যাটার্ন: 🌐 Country : ... ☎ Number : ... 🔐 Code : ...
                pattern = r"☎ Number : .*?" + re.escape(target_phone) + r".*\n.*🔐 Code : (\d+)"
                match = re.search(pattern, message_text, re.DOTALL)

                if match:
                    extracted_code = match.group(1)
                    
                    # যদি কোডটি পাওয়া যায়, তাহলে ব্যবহারকারীকে ফরোয়ার্ড করা
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"আপনার নম্বরের ({target_phone}) OTP কোডটি হলো: {extracted_code}"
                    )
                    
                    # একবার কোড ফরোয়ার্ড করার পর নম্বরটি রিসেট করা
                    user_data[user_id]["target_phone"] = None
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="OTP ফরোয়ার্ড করা হয়েছে। আপনি যদি অন্য কোনো নম্বরের জন্য OTP পেতে চান, তাহলে নতুন নম্বরটি পাঠান।"
                    )
                    break # লুপ থেকে বের হয়ে যাওয়া কারণ কোড পাওয়া গেছে

def main() -> None:
    """বট চালু করার জন্য প্রধান ফাংশন"""
    application = Application.builder().token(TOKEN).build()

    # কমান্ড হ্যান্ডলার
    application.add_handler(CommandHandler("start", start))
    
    # মেসেজ হ্যান্ডলার
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_phone_number))
    
    # সোর্স গ্রুপ থেকে আসা মেসেজ হ্যান্ডলার
    application.add_handler(MessageHandler(filters.UpdateType.MESSAGES, forward_otp, block=False))
    
    # বট চালু করা
    print("বটটি চালু হয়েছে। আপনার মেসেজ বক্সে ফোন নম্বর পাঠিয়ে চেষ্টা করুন।")
    application.run_polling(allowed_updates=[Update.MESSAGE, Update.CHANNEL_POST])

if __name__ == "__main__":
    main()

