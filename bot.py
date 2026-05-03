import os
import logging
from datetime import datetime, time
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# ===== TOKEN =====
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    print("❌ TOKEN missing")
    exit()

# ===== 时区 =====
tz = pytz.timezone("Asia/Kuala_Lumpur")

# ===== 员工 =====
STAFF = {
    "CS 1": {"name": "AVELYN", "start": time(9, 0)},
    "CS 3": {"name": "JOHN", "start": time(17, 0)},
    "CS 4": {"name": "TERRY", "start": time(17, 0)},
    "CS 2": {"name": "SAM", "start": time(1, 0)},
    "CS 5": {"name": "ANSON", "start": time(1, 0)},
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
sheet = client.open("1B CS Attendance").sheet1

# ===== 内存 =====
work_sessions = {}
break_sessions = {}

logging.basicConfig(level=logging.INFO)

# ===== Menu =====
menu = ReplyKeyboardMarkup(
    [["🟢 On Duty", "🔴 Off Duty"],
     ["☕ Break", "✅ Back"]],
    resize_keyboard=True
)

# ===== 获取员工 =====
def get_staff(update):
    tg_name = update.effective_user.first_name

    if tg_name in STAFF:
        data = STAFF[tg_name]
        return tg_name, data["name"], data["start"]

    return tg_name, "Unknown", None

# ===== Late 判断 =====
def check_late(now, start_time):
    start_dt = now.replace(hour=start_time.hour, minute=0, second=0)

    if start_time.hour > now.hour:
        start_dt = start_dt.replace(day=now.day - 1)

    return "On Time ✅" if now <= start_dt else "Late ❌"

# ===== 写入 Sheet =====
def log_sheet(name, staff, action, now, value="", status=""):
    sheet.append_row([
        name,
        staff,
        action,
        now.strftime("%Y-%m-%d %H:%M:%S"),
        value,
        status
    ])

# ===== Start =====
def start(update, context):
    update.message.reply_text("1B打卡系统已启动 ✅，请选择👇🏻", reply_markup=menu)

# ===== On Duty =====
def work(update, context):
    now = datetime.now(tz)
    staff, name, start_time = get_staff(update)

    if staff in work_sessions:
        update.message.reply_text("❌ 已经在上班了")
        return

    status = check_late(now, start_time)
    work_sessions[staff] = now

    log_sheet(name, staff, "On Duty", now, "", status)

    update.message.reply_text(
        f"""👤 {staff} {name}
🟢 On Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
{status}"""
    )

# ===== Off Duty =====
def end(update, context):
    now = datetime.now(tz)
    staff, name, _ = get_staff(update)

    if staff not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    start_time = work_sessions.pop(staff)
    hours = round((now - start_time).total_seconds() / 3600, 2)

    log_sheet(name, staff, "Off Duty", now, hours, "Ended")

    update.message.reply_text(
        f"""👤 {staff} {name}
🔴 Off Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 工作: {hours} 小时"""
    )

# ===== Break =====
def rest(update, context):
    now = datetime.now(tz)
    staff, name, _ = get_staff(update)

    if staff in break_sessions:
        update.message.reply_text("❌ 已经在休息中")
        return

    break_sessions[staff] = now

    log_sheet(name, staff, "Break Start", now)

    update.message.reply_text(
        f"""👤 {staff} {name}
☕ Break 开始
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}"""
    )

# ===== Back =====
def back(update, context):
    now = datetime.now(tz)
    staff, name, _ = get_staff(update)

    if staff not in break_sessions:
        update.message.reply_text("❌ 没有在休息")
        return

    start = break_sessions.pop(staff)
    seconds = int((now - start).total_seconds())
    minutes = seconds // 60

    log_sheet(name, staff, "Break End", now, minutes, "OK")

    update.message.reply_text(
        f"""👤 {staff} {name}
✅ Break Back 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
☕ 休息: {minutes} 分钟 ({seconds} 秒)"""
    )

# ===== Report =====
def report(update, context):
    records = sheet.get_all_records()
    today = datetime.now(tz).strftime("%Y-%m-%d")

    result = "📊 今日记录\n\n"

    for r in records:
        if today in str(r.get("Time", "")):
            result += f"{r.get('Name')} | {r.get('Action')} | {r.get('Time')}\n"

    update.message.reply_text(result if result else "暂无记录")

# ===== Message =====
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

# ===== Flask =====
from flask import Flask
from threading import Thread

web = Flask(__name__)

@web.route("/")
def home():
    return "Bot is alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)

Thread(target=run_web).start()

# ===== Run =====
updater = Updater(TOKEN, use_context=True)
updater.bot.delete_webhook()

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("report", report))
dp.add_handler(MessageHandler(Filters.text, handle_message))

print("🔥 BOT PRO+ RUNNING")
updater.start_polling()
updater.idle()
