import logging
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

from telegram.ext import Updater, CommandHandler

# ===== 配置 =====
TOKEN = "8625047747:AAHDgZx5xl7LMk67s0nlzjbGHRogNTdAmtE"
SHEET_NAME = "1B CS Attendance"

BREAK_LIMIT = 30

# ===== Google Sheet =====
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# 自动判断路径（Render / 本地）
import os

if os.path.exists("/etc/secrets/credentials.json"):
    CREDS_FILE = "/etc/secrets/credentials.json"
else:
    CREDS_FILE = "credentials.json"

creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ===== 内存 =====
work_sessions = {}
break_sessions = {}

# ===== Logging =====
logging.basicConfig(level=logging.INFO)

# ===== 功能 =====

def start(update, context):
    update.message.reply_text("Bot 已启动！\n/work 开始工作\n/end 下班\n/rest 休息\n/back 回来\n/report 查看记录")

def work(update, context):
    user = update.effective_user.first_name
    now = datetime.now()

    work_sessions[user] = now

    emp = EMPLOYEES.get(user)

    if not emp:
        cs = "CS ?"
        late = "❌"
    else:
        cs = emp["cs"]
        start_time = emp["start"]
        late = "❌" if now.strftime("%H:%M") > start_time else "✅"

    sheet.append_row([
        user, "", "On Duty",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        "", "Working"
    ])

    msg = f"""👤 {cs} {user}
━━━━━━━━━━━━━━━
📌 On Duty 成功
⏰ 时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
🟢 状态: 正常

Late {late}"""

    update.message.reply_text(msg)

def end(update, context):
    user = update.effective_user.first_name
    now = datetime.now()

    if user not in work_sessions:
        update.message.reply_text("❌ 还没上班")
        return

    start_time = work_sessions.pop(user)
    hours = round((now - start_time).total_seconds() / 3600, 2)

    sheet.append_row([
        user, "", "Off Duty",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        hours, "Ended"
    ])

    msg = f"""👤 {user}
━━━━━━━━━━━━━━━
📌 Off Duty 成功
⏰ 时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
🕒 工作: {hours} 小时"""

    update.message.reply_text(msg)

def rest(update, context):
    user = update.effective_user.first_name
    now = datetime.now()

    break_sessions[user] = now

    sheet.append_row([
        user, "", "Break Start",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        "", "Break"
    ])

    msg = f"""👤 {user}
━━━━━━━━━━━━━━━
☕ Break 成功
⏰ 时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
📍 状态: Break Start"""

    update.message.reply_text(msg)
    
def back(update, context):
    user = update.effective_user.first_name
    now = datetime.now()

    if user not in break_sessions:
        update.message.reply_text("❌ 没有休息记录")
        return

    start = break_sessions.pop(user)
    minutes = int((now - start).total_seconds() / 60)

    status = "正常" if minutes <= BREAK_LIMIT else "超时 ❌"

    sheet.append_row([
        user, "", "Break End",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        minutes, status
    ])

    msg = f"""👤 {user}
━━━━━━━━━━━━━━━
🔙 Break Back 成功
⏰ 时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
🕒 休息: {minutes} 分钟
✅ 状态: {status}"""

    update.message.reply_text(msg)
    
def report(update, context):
    records = sheet.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")

    result = "📊 今日记录\n\n"

    for r in records:
        if today in str(r.get("Time", "")):
            result += f"{r.get('Name')} | {r.get('Action')} | {r.get('Time')}\n"

    if result == "📊 今日记录\n\n":
        result += "暂无记录"

    update.message.reply_text(result)

# ===== Flask 防休眠（Render 必须）=====
from flask import Flask
from threading import Thread

web = Flask(__name__)

@web.route("/")
def home():
    return "Bot is alive"

def run_web():
    web.run(host="0.0.0.0", port=10000)

Thread(target=run_web).start()

# ===== 主程序 =====
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
