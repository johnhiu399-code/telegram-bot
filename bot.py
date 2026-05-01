import logging
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# ===== TOKEN =====
TOKEN = os.environ.get("TOKEN")

SHEET_NAME = "1B CS Attendance"
BREAK_LIMIT = 30

# ===== 班次 =====
SHIFT = {
    "CS 1": (9, 17),
    "CS 2": (9, 17),
    "CS 3": (17, 1),
    "CS 4": (17, 1),
    "CS 5": (1, 9),
    "CS 6": (1, 9),
}

# ===== 名字映射 =====
NAME_MAP = {
    "CS 1": "AVELYN",
    "CS 2": "SAM",
    "CS 3": "JOHN",
    "CS 4": "TERRY",
    "CS 5": "ANSON",
    "CS 6": "NATE",
}

# ===== Google Sheet =====
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

# ===== 内存 =====
work_sessions = {}
break_sessions = {}

logging.basicConfig(level=logging.INFO)

# ===== 获取员工 =====
def get_staff(update):
    staff = update.effective_user.first_name.strip().upper()

    if staff not in SHIFT:
        return None, None

    name = NAME_MAP.get(staff, "UNKNOWN")
    return staff, name

# ===== START =====
def start(update, context):
    update.message.reply_text(
        "系统已启动 ✅\n"
        "/work 上班\n"
        "/end 下班\n"
        "/rest 休息\n"
        "/back 回来"
    )

# ===== WORK =====
def work(update, context):
    staff, name = get_staff(update)
    now = datetime.now()

    if not staff:
        update.message.reply_text("❌ 请把名字改成 CS 1 / CS 2...")
        return

    if staff in work_sessions:
        update.message.reply_text("⚠️ 已在上班中")
        return

    work_sessions[staff] = now

    start_hour, _ = SHIFT[staff]

    late = now.hour > start_hour or (now.hour == start_hour and now.minute > 0)
    status = "Late ❌" if late else "On Time ✅"

    sheet.append_row([
        staff,
        name,
        "Work Start",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        "",
        status
    ])

    update.message.reply_text(
        f"""👤 {staff} {name}
🟢 On Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
{status}"""
    )

# ===== END =====
def end(update, context):
    staff, name = get_staff(update)
    now = datetime.now()

    if not staff:
        update.message.reply_text("❌ 未识别员工")
        return

    if staff not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    start_time = work_sessions.pop(staff)
    hours = round((now - start_time).total_seconds() / 3600, 2)

    sheet.append_row([
        staff,
        name,
        "Work End",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        hours,
        "Ended"
    ])

    update.message.reply_text(
        f"""👤 {staff} {name}
🔴 Off Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 工作: {hours} 小时"""
    )

# ===== REST =====
def rest(update, context):
    staff, name = get_staff(update)
    now = datetime.now()

    if not staff:
        update.message.reply_text("❌ 未识别员工")
        return

    break_sessions[staff] = now

    sheet.append_row([
        staff,
        name,
        "Break Start",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        "",
        "Break"
    ])

    update.message.reply_text(f"☕ {staff} {name}\nBreak 开始")

# ===== BACK =====
def back(update, context):
    staff, name = get_staff(update)
    now = datetime.now()

    if not staff:
        update.message.reply_text("❌ 未识别员工")
        return

    if staff not in break_sessions:
        update.message.reply_text("❌ 没在休息")
        return

    start = break_sessions.pop(staff)
    minutes = int((now - start).total_seconds() / 60)

    status = "OK ✅" if minutes <= BREAK_LIMIT else "Overtime ❌"

    sheet.append_row([
        staff,
        name,
        "Break End",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        minutes,
        status
    ])

    update.message.reply_text(
        f"""👤 {staff} {name}
✅ Break Back 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
☕ 休息: {minutes} 分钟
{status}"""
    )

# ===== 按钮识别 =====
def handle_message(update, context):
    text = update.message.text.lower()

    if "on duty" in text:
        work(update, context)
    elif "off duty" in text:
        end(update, context)
    elif "break" in text and "back" not in text:
        rest(update, context)
    elif "back" in text:
        back(update, context)

# ===== Flask =====
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
updater.bot.delete_webhook()

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("work", work))
dp.add_handler(CommandHandler("end", end))
dp.add_handler(CommandHandler("rest", rest))
dp.add_handler(CommandHandler("back", back))

dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

print("BOT RUNNING...")
updater.start_polling()
updater.idle()
