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
sheet = client.open("CS Attendance").sheet1

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)

# =========================
# MEMORY
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
SHIFT_CONFIG = {

    # 9AM - 5PM
    "CS 1 (Avelyn)": {
        "start": time(9, 0),
        "end": time(17, 0),
        "label": "9:00AM - 5:00PM"
    },

    "CS 2 (Ed)": {
        "start": time(9, 0),
        "end": time(17, 0),
        "label": "9:00AM - 5:00PM"
    },

    # 5PM - 1AM
    "CS 3 (John)": {
        "start": time(17, 0),
        "end": time(1, 0),
        "label": "5:00PM - 1:00AM"
    },

    "CS 4 (Terry)": {
        "start": time(17, 0),
        "end": time(1, 0),
        "label": "5:00PM - 1:00AM"
    },

    # 1AM - 9AM
    "CS 5 (Sam)": {
        "start": time(1, 0),
        "end": time(9, 0),
        "label": "1:00AM - 9:00AM"
    }
}

# =========================
# GET STAFF NAME
# =========================
def get_staff(update):

    tg_name = update.effective_user.full_name.strip()

    tg_name = " ".join(tg_name.split())

    return tg_name

# =========================
# GET SHIFT
# =========================
def get_shift(staff):

    return SHIFT_CONFIG.get(staff)

# =========================
# CHECK LATE
# =========================
def is_late(now, start_time):

    shift_start = now.replace(
        hour=start_time.hour,
        minute=start_time.minute,
        second=0,
        microsecond=0
    )

    # Allow 5 mins grace
    grace = shift_start + timedelta(minutes=5)

    if now > grace:
        return "Late ❌"

    return "On Time ✅"

# =========================
# GOOGLE SHEET LOG
# =========================
def log_sheet(staff, action, now, duration="", status=""):

    try:

        sheet.append_row([
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            staff,
            action,
            duration,
            status
        ])

    except Exception as e:

        print("SHEET ERROR =", e)

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

    staff = get_staff(update)

    print("WORK STAFF =", repr(staff))

    if staff in work_sessions:

        update.message.reply_text(
            "❌ 你已经在 On Duty 了"
        )

        return

    shift = get_shift(staff)

    if not shift:

        update.message.reply_text(
            "❌ 找不到你的班次，请联系管理员"
        )

        return

    status_text = is_late(
        now,
        shift["start"]
    )

    work_sessions[staff] = now

    log_sheet(
        staff,
        "On Duty",
        now,
        "",
        status_text
    )

    msg = (
        f"👤 {staff}\n\n"
        f"🟢 On Duty 成功\n"
        f"⏰ 时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🏢 班次: {shift['label']}\n"
        f"{status_text}"
    )

    update.message.reply_text(msg)

# =========================
# OFF DUTY
# =========================
def end(update, context):

    now = datetime.now(tz)

    staff = get_staff(update)

    print("END STAFF =", repr(staff))

    if staff not in work_sessions:

        update.message.reply_text(
            "❌ 你还没上班"
        )

        return

    start_time = work_sessions.pop(staff)

    worked = now - start_time

    hours = round(
        worked.total_seconds() / 3600,
        2
    )

    log_sheet(
        staff,
        "Off Duty",
        now,
        f"{hours} Hour(s)"
    )

    msg = (
        f"👤 {staff}\n\n"
        f"🔴 Off Duty 成功\n"
        f"⏰ 时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏳ 工作: {hours} Hour(s)"
    )

    update.message.reply_text(msg)

# =========================
# BREAK
# =========================
def rest(update, context):

    now = datetime.now(tz)

    staff = get_staff(update)

    if staff not in work_sessions:

        update.message.reply_text(
            "❌ 你还没上班"
        )

        return

    break_sessions[staff] = now

    log_sheet(
        staff,
        "Break",
        now
    )

    update.message.reply_text(
        f"☕ {staff}\n\nBreak 开始"
    )

# =========================
# BACK
# =========================
def back(update, context):

    now = datetime.now(tz)

    staff = get_staff(update)

    if staff not in break_sessions:

        update.message.reply_text(
            "❌ 你没有在 Break"
        )

        return

    start_break = break_sessions.pop(staff)

    duration = now - start_break

    mins = round(
        duration.total_seconds() / 60,
        1
    )

    log_sheet(
        staff,
        "Back",
        now,
        f"{mins} Minutes"
    )

    update.message.reply_text(
        f"✅ {staff}\n\nBreak 结束\n☕ {mins} 分钟"
    )

# =========================
# HANDLE BUTTONS
# =========================
def handle_message(update, context):

    text = update.message.text.strip()

    print("BUTTON =", text)

    if text in ["🟢 On Duty", "/work"]:

        work(update, context)

    elif text in ["🔴 Off Duty", "/end"]:

        end(update, context)

    elif text in ["☕ Break", "/rest"]:

        rest(update, context)

    elif text in ["✅ Back", "/back"]:

        back(update, context)

# =========================
# TELEGRAM BOT
# =========================
updater = Updater(
    TOKEN,
    use_context=True
)

updater.bot.delete_webhook(
    drop_pending_updates=True
)

dp = updater.dispatcher

dp.add_handler(
    CommandHandler(
        "start",
        start
    )
)

dp.add_handler(
    MessageHandler(
        Filters.text,
        handle_message
    )
)

# =========================
# FLASK WEB SERVER
# =========================
app = Flask(__name__)

@app.route('/')
def home():

    return "BOT RUNNING"

def run_web():

    app.run(
        host='0.0.0.0',
        port=int(
            os.environ.get(
                "PORT",
                10000
            )
        )
    )

Thread(
    target=run_web
).start()

# =========================
# START BOT
# =========================
print("BOT PRO+ RUNNING")

updater.start_polling()

updater.idle()
