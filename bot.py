import os
import logging
from datetime import datetime, time, timedelta

import pytz
import gspread

from oauth2client.service_account import ServiceAccountCredentials

from telegram import ReplyKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters
)

from flask import Flask
from threading import Thread

# =========================
# TOKEN
# =========================
TOKEN = os.environ.get("TOKEN")

# =========================
# TIMEZONE
# =========================
tz = pytz.timezone("Asia/Kuala_Lumpur")

# =========================
# GOOGLE SHEET
# =========================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials.json",
    scope
)

client = gspread.authorize(creds)

# 改成你的 Google Sheet 名字
sheet = client.open("1B CS Attendance").sheet1

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)

# =========================
# SESSION STORAGE
# =========================
work_sessions = {}
break_sessions = {}

# =========================
# BUTTON MENU
# =========================
menu = ReplyKeyboardMarkup(
    [
        ["🟢 On Duty", "🔴 Off Duty"],
        ["☕ Break", "✅ Back"]
    ],
    resize_keyboard=True
)

# =========================
# SHIFT SYSTEM
# =========================
def get_shift(staff):

    # 9AM - 5PM
    if staff in [
        "CS 1 (Avelyn)",
        "CS 2 (Ed)"
    ]:
        return {
            "start": time(9, 0),
            "end": time(17, 0),
            "shift": "9:00AM - 5:00PM"
        }

    # 5PM - 1AM
    elif staff in [
        "CS 3 (John)",
        "CS 4 (Terry)"
    ]:
        return {
            "start": time(17, 0),
            "end": time(1, 0),
            "shift": "5:00PM - 1:00AM"
        }

    # 1AM - 9AM
    elif staff in [
        "CS 5 (Sam)"
    ]:
        return {
            "start": time(1, 0),
            "end": time(9, 0),
            "shift": "1:00AM - 9:00AM"
        }

    return None

# =========================
# GET STAFF NAME
# =========================
def get_staff(update):

    tg_name = update.effective_user.full_name.strip()

    return tg_name, tg_name

# =========================
# CHECK LATE
# =========================
def check_late(now, start_time):

    shift_start = now.replace(
        hour=start_time.hour,
        minute=start_time.minute,
        second=0,
        microsecond=0
    )

    # allow 5 mins grace
    grace = shift_start + timedelta(minutes=5)

    if now > grace:
        return "Late ❌"

    return "On Time ✅"

# =========================
# LOG TO GOOGLE SHEET
# =========================
def log_sheet(staff, name, action, now, duration, status):

    sheet.append_row([
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        staff,
        name,
        action,
        duration,
        status
    ])

# =========================
# START
# =========================
def start(update, context):

    update.message.reply_text(
        "1BCS打卡系统启动 ✅\n请选择操作👇",
        reply_markup=menu
    )

# =========================
# ON DUTY
# =========================
def work(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    shift_data = get_shift(staff)

    if not shift_data:
        update.message.reply_text("❌ 找不到你的班次")
        return

    if staff in work_sessions:
        update.message.reply_text("❌ 已经在上班了")
        return

    start_time = shift_data["start"]
    shift_name = shift_data["shift"]

    status = check_late(now, start_time)

    work_sessions[staff] = now

    log_sheet(
        staff,
        name,
        "On Duty",
        now,
        "",
        status
    )

    update.message.reply_text(
        f"""
👤 {staff}

🟢 On Duty 成功

🕒 时间:
{now.strftime("%Y-%m-%d %H:%M:%S")}

🏢 班次:
{shift_name}

📌 {status}
"""
    )

# =========================
# OFF DUTY
# =========================
def end(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    if staff not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    start_work = work_sessions[staff]

    worked = now - start_work

    hours = round(worked.total_seconds() / 3600, 2)

    log_sheet(
        staff,
        name,
        "Off Duty",
        now,
        f"{hours} Hours",
        ""
    )

    del work_sessions[staff]

    update.message.reply_text(
        f"""
👤 {staff}

🔴 Off Duty 成功

🕒 时间:
{now.strftime("%Y-%m-%d %H:%M:%S")}

⏱ 工作:
{hours} 小时
"""
    )

# =========================
# BREAK
# =========================
def rest(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    if staff not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    break_sessions[staff] = now

    log_sheet(
        staff,
        name,
        "Break",
        now,
        "",
        ""
    )

    update.message.reply_text(
        f"""
☕ {staff}

Break 开始
"""
    )

# =========================
# BACK
# =========================
def back(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    if staff not in break_sessions:
        update.message.reply_text("❌ 你没有在 Break")
        return

    start_break = break_sessions[staff]

    duration = now - start_break

    mins = round(duration.total_seconds() / 60, 1)

    log_sheet(
        staff,
        name,
        "Back",
        now,
        f"{mins} Minutes",
        ""
    )

    del break_sessions[staff]

    update.message.reply_text(
        f"""
✅ {staff}

Back 成功

☕ Break:
{mins} 分钟
"""
    )

# =========================
# HANDLE BUTTONS
# =========================
def handle_message(update, context):

    text = update.message.text

    if text in ["🟢 On Duty", "/work"]:
        work(update, context)

    elif text in ["🔴 Off Duty", "/end"]:
        end(update, context)

    elif text in ["☕ Break", "/rest"]:
        rest(update, context)

    elif text in ["✅ Back", "/back"]:
        back(update, context)

# =========================
# FLASK WEB
# =========================
app = Flask(__name__)

@app.route('/')
def home():
    return "BOT RUNNING"

def run_web():
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get("PORT", 10000))
    )

Thread(target=run_web).start()

# =========================
# START BOT
# =========================
updater = Updater(TOKEN, use_context=True)

updater.bot.delete_webhook(drop_pending_updates=True)

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))

dp.add_handler(
    MessageHandler(
        Filters.text,
        handle_message
    )
)

print("BOT PRO+ RUNNING")

updater.start_polling()

updater.idle()
