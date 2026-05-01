import logging
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# ===== TOKEN =====
TOKEN = os.environ.get("TOKEN")

# ===== Google Sheet =====
SHEET_NAME = "1B CS Attendance"

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

if os.path.exists("/etc/secrets/credentials.json"):
    CREDS_FILE = "/etc/secrets/credentials.json"
else:
    CREDS_FILE = "credentials.json"

creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ===== 员工（改这里的 ID）=====
EMPLOYEES = {
    "CS 1": {"name": "Avelyn", "start": "09:00"},
    "CS 2": {"name": "Sam", "start": "09:00"},
    "CS 3": {"name": "John", "start": "17:00"},
    "CS 4": {"name": "Terry", "start": "17:00"},
    "CS 5": {"name": "Anson", "start": "01:00"},
    "CS 6": {"name": "Nate", "start": "01:00"},
}

BREAK_LIMIT = 30

# ===== 内存 =====
work_sessions = {}
break_sessions = {}

logging.basicConfig(level=logging.INFO)

# ===== 按钮 =====
keyboard = [
    ["🟢 On Duty", "🔴 Off Duty"],
    ["☕ Break", "✅ Back"],
    ["📊 Report"]
]
markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===== 工具 =====
def get_staff(update):
    user_id = update.effective_user.id
    return STAFF.get(user_id, {"name": "Unknown", "start": "09:00"})

def is_late(now, start_time_str):
    start_time = datetime.strptime(start_time_str, "%H:%M").time()
    return now.time() > start_time

# ===== 功能 =====

def start(update, context):
    update.message.reply_text(
        "系统已启动 ✅\n请选择操作👇",
        reply_markup=markup
    )

# 🟢 上班
def work(update, context):
    try:
        staff = get_staff(update)
        user = staff["name"]
        start_time = staff["start"]

        now = datetime.now()

        work_sessions[user] = now

        late = "Late ❌" if is_late(now, start_time) else "On Time ✅"
        shift = f"{start_time} Shift"

        sheet.append_row([
            user,
            "Work Start",
            now.strftime("%Y-%m-%d %H:%M:%S"),
            shift,
            late
        ])

        msg = f"""👤 {user}
📌 On Duty 成功
🕒 班次: {shift}
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
{late}"""

        update.message.reply_text(msg)

    except Exception as e:
        update.message.reply_text(f"❌ Error: {e}")

# 🔴 下班
def end(update, context):
    staff = get_staff(update)
    user = staff["name"]
    now = datetime.now()

    if user not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    start_time = work_sessions.pop(user)
    hours = round((now - start_time).total_seconds() / 3600, 2)

    sheet.append_row([
        user,
        "Work End",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        hours
    ])

    update.message.reply_text(f"""👤 {user}
📌 Off Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 工作: {hours} 小时""")

# ☕ 休息
def rest(update, context):
    staff = get_staff(update)
    user = staff["name"]
    now = datetime.now()

    break_sessions[user] = now

    update.message.reply_text(f"""👤 {user}
☕ Break 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}""")

# ✅ 回来
def back(update, context):
    staff = get_staff(update)
    user = staff["name"]
    now = datetime.now()

    if user not in break_sessions:
        update.message.reply_text("❌ 你没有在休息")
        return

    start = break_sessions.pop(user)
    minutes = int((now - start).total_seconds() / 60)

    status = "OK ✅" if minutes <= BREAK_LIMIT else "Overtime ❌"

    update.message.reply_text(f"""👤 {user}
✅ Break Back 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 休息: {minutes} 分钟
{status}""")

# 📊 报表
def report(update, context):
    records = sheet.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")

    result = "📊 今日记录\n\n"

    for r in records:
        if today in str(r.values()):
            result += f"{r}\n"

    update.message.reply_text(result or "暂无记录")

# ===== 按钮控制 =====
def handle_message(update, context):
    text = update.message.text

    if text == "🟢 On Duty":
        work(update, context)
    elif text == "🔴 Off Duty":
        end(update, context)
    elif text == "☕ Break":
        rest(update, context)
    elif text == "✅ Back":
        back(update, context)
    elif text == "📊 Report":
        report(update, context)

# ===== Flask 防休眠 =====
from flask import Flask
from threading import Thread

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is alive"

def run_web():
    app_web.run(host="0.0.0.0", port=10000)

# ===== 主程序 =====
if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()

    updater = Updater(TOKEN, use_context=True)
    updater.bot.delete_webhook()

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    print("BOT RUNNING...")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()
