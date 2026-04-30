import logging
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

from telegram.ext import Updater, CommandHandler

# ===== 配置 =====
TOKEN = "8625047747:AAHDgZx5xl7LMk67s0nlzjbGHRogNTdAmtE"
SHEET_NAME = "IB CS Attendance"

EMPLOYEES = {
    "CS 1": {"name": "Avelyn", "start": "09:00"},
    "CS 2": {"name": "Sam", "start": "09:00"},
    "CS 3": {"name": "John", "start": "17:00"},
    "CS 4": {"name": "Terry", "start": "17:00"},
}

# ===== Google Sheet =====
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Render / 本地路径判断
if os.path.exists("/etc/secrets/credentials.json"):
    CREDS_FILE = "/etc/secrets/credentials.json"
else:
    CREDS_FILE = "credentials.json"

creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ===== 内存 =====
work_sessions = {}
rest_sessions = {}

# ===== Logging =====
logging.basicConfig(level=logging.INFO)

# ===== 工具函数 =====
def find_employee(user):
    for key, val in EMPLOYEES.items():
        if val["name"].lower() == user.lower():
            return key, val
    return None, None

def is_late(now, start_time):
    return "❌" if now.strftime("%H:%M") > start_time else "✅"

# ===== 指令 =====

def start(update, context):
    update.message.reply_text("👋 欢迎使用 CS Attendance Bot")

def work(update, context):
    user = update.effective_user.first_name
    user_id = str(update.effective_user.id)
    now = datetime.now()

    cs_id, emp = find_employee(user)
    if not emp:
        update.message.reply_text("❌ 未注册员工")
        return

    late = is_late(now, emp["start"])
    work_sessions[user_id] = now

    sheet.append_row([user, "On Duty", now.strftime("%Y-%m-%d %H:%M:%S")])

    msg = f"""👤 {cs_id} {emp['name']}
📌 On Duty 成功
⏰ {now.strftime('%Y-%m-%d %H:%M:%S')}
Late {late}"""

    update.message.reply_text(msg)

def end(update, context):
    user = update.effective_user.first_name
    user_id = str(update.effective_user.id)
    now = datetime.now()

    start_time = work_sessions.get(user_id)
    if not start_time:
        update.message.reply_text("❌ 没有上班记录")
        return

    duration = now - start_time
    hours = round(duration.total_seconds() / 3600, 2)

    sheet.append_row([user, "Off Duty", now.strftime("%Y-%m-%d %H:%M:%S")])

    msg = f"""📌 下班成功
👤 {user}
⏰ {now.strftime('%Y-%m-%d %H:%M:%S')}
🕒 工作时间：{hours} 小时"""

    update.message.reply_text(msg)

def rest(update, context):
    user_id = str(update.effective_user.id)
    now = datetime.now()

    rest_sessions[user_id] = now

    update.message.reply_text(f"""☕ 休息开始
⏰ {now.strftime('%H:%M:%S')}""")

def back(update, context):
    user_id = str(update.effective_user.id)
    now = datetime.now()

    rest_start = rest_sessions.get(user_id)
    if not rest_start:
        update.message.reply_text("❌ 没有休息记录")
        return

    duration = now - rest_start
    mins = int(duration.total_seconds() / 60)

    update.message.reply_text(f"""🔙 已返回工作
🕒 休息时间：{mins} 分钟""")

def report(update, context):
    records = sheet.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")

    result = "📊 今日报表\n\n"

    for r in records:
        if today in str(r.get("Time", "")):
            result += f"{r.get('Name')} | {r.get('Action')} | {r.get('Time')}\n"

    if result.strip() == "📊 今日报表":
        result += "暂无记录"

    update.message.reply_text(result)

# ===== 启动 =====
updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("work", work))
dp.add_handler(CommandHandler("end", end))
dp.add_handler(CommandHandler("rest", rest))
dp.add_handler(CommandHandler("back", back))
dp.add_handler(CommandHandler("report", report))

print("BOT RUNNING...")
updater.start_polling()
updater.idle()
