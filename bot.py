from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8625047747:AAHDgZx5xl7LMk67s0nlzjbGHRogNTdAmtE"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is working!")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.run_polling()
