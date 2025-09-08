import json
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8317337195:AAEKG5koGvaYJYyxZK_zglRY_pNadazLhoY"

# قائمة الكلمات المفتاحية
keywords = ["أريد مساعدة", "مساعدة", "أحتاج مساعدة", "help", "need help"]

# قالب رسالة المجموعة
group_reply_template = "✅ {user} طلب المساعدة! للتواصل: 0774440982"

# اسم ملف JSON لتخزين الطلبات
log_file = "help_requests.json"

# دالة لتسجيل الطلب في ملف JSON
def log_request(user, message_text):
    request_data = {
        "user": user,
        "message": message_text,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        # قراءة البيانات السابقة
        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []

    data.append(request_data)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبًا! هذا البوت يراقب طلبات المساعدة في المجموعة ويخزنها."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if any(keyword.lower() in text for keyword in keywords):
        user = update.message.from_user.full_name
        reply_text = group_reply_template.format(user=user)
        
        # إرسال الرسالة في المجموعة
        await update.message.reply_text(reply_text)
        
        # تسجيل الطلب في ملف JSON
        log_request(user, update.message.text)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    app.run_polling()
