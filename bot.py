from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime, time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# ===== 配置 =====
TOKEN = "8625047747:AAHDgZx5xl7LMk67s0nlzjbGHRogNTdAmtE"
SHEET_NAME = "1B CS Attendance"

EMPLOYEES = {
    "CS 1": {"name": "Avelyn", "start": "09:00"},
    "CS 2": {"name": "Sam", "start": "09:00"},
    "CS 3": {"name": "John", "start": "17:00"},
    "CS 4": {"name": "Terry", "start": "17:00"},
    "CS 5": {"name": "Anson", "start": "01:00"},
    "CS 6": {"name": "Nate", "start": "01:00"},
}

BREAK_LIMIT = 30

# ===== Google Sheet =====
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# 🔥 自动判断路径（Render / 本地）
if os.path.exists("/etc/secrets/credentials.json"):
    CREDS_FILE = "/etc/secrets/credentials.json"
else:
    CREDS_FILE = "credentials.json"

creds = ServiceAccountCredentials.from_json_keyfile_name(
    CREDS_FILE, scope
)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ===== 内存 =====
work_sessions = {}
break_sessions = {}
USER_CHAT_IDS = {}

# ===== 核心逻辑 =====
async def process(update: Update, action: str):
    user = update.effective_user.first_name
    user_id = str(update.effective_user.id)
    now = datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")

    emp = EMPLOYEES.get(user)
    emp_name = emp["name"] if emp else "Unknown"

    work_hours = ""
    status = ""

    if action == "On Duty":
        work_sessions[user_id] = now
        if emp:
            start = datetime.strptime(emp["start"], "%H:%M").time()
            status = "Late ❌" if now.time() > start else "On Time ✅"

    elif action == "Break":
        break_sessions[user_id] = now
        status = "Break Start"

    elif action == "Break Back":
        if user_id in break_sessions:
            mins = int((now - break_sessions.pop(user_id)).total_seconds() / 60)
            status = f"Break Over {mins} mins ❌" if mins > BREAK_LIMIT else f"Break OK {mins} mins ✅"

    elif action == "Off Duty":
        if user_id in work_sessions:
            hours = round((now - work_sessions.pop(user_id)).total_seconds() / 3600, 2)
            work_hours = f"{hours} hrs"

    # 写入 Google Sheet
    sheet.append_row([f"{user} {emp_name}", user_id, action, time_str, work_hours, status])

    await update.message.reply_text(
        f"👤 {user} {emp_name}\n"
        f"📌 {action} 成功\n"
        f"⏰ {time_str}\n"
        f"{status}"
    )

# ===== 指令 =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    USER_CHAT_IDS[user] = update.effective_chat.id
    await update.message.reply_text("系统启动成功 ✅\n使用：/work /end /rest /back")

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process(update, "On Duty")

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process(update, "Off Duty")

async def rest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process(update, "Break")

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process(update, "Break Back")

# ===== 报表 =====
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")

    result = "📊 今日报表\n\n"

    for r in records:
        if today in str(r.get("Time", "")):
            result += f"{r.get('Name')} | {r.get('Action')} | {r.get('Time')}\n"

    if result == "📊 今日报表\n\n":
        result += "暂无记录"

    await update.message.reply_text(result)

# ===== 主程序 =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("work", work))
app.add_handler(CommandHandler("end", end))
app.add_handler(CommandHandler("rest", rest))
app.add_handler(CommandHandler("back", back))
app.add_handler(CommandHandler("report", report))

print("BOT RUNNING...")
app.run_polling()

from flask import Flask
from threading import Thread

web = Flask(__name__)

@web.route("/")
def home():
    return "Bot is alive"

def run_web():
    web.run(host="0.0.0.0", port=10000)

Thread(target=run_web).start()
