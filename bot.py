import os
import logging
from datetime import datetime, time, timedelta
import pytz

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from flask import Flask
from threading import Thread

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters
)

# =========================================
# TOKEN
# =========================================

TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    print("❌ TOKEN missing")
    exit()

# =========================================
# TIMEZONE
# =========================================

tz = pytz.timezone("Asia/Kuala_Lumpur")

# =========================================
# GOOGLE SHEET
# =========================================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

CREDS_FILE = "/etc/secrets/credentials.json"

creds = ServiceAccountCredentials.from_json_keyfile_name(
    CREDS_FILE,
    scope
)

client = gspread.authorize(creds)

sheet = client.open("1B CS Attendance Official").sheet1

# =========================================
# LOGGING
# =========================================

logging.basicConfig(level=logging.INFO)

# =========================================
# MENU BUTTON
# =========================================

menu = ReplyKeyboardMarkup(
    [
        ["🟢 On Duty", "🔴 Off Duty"],
        ["☕ Break", "✅ Back"]
    ],
    resize_keyboard=True
)

# =========================================
# MEMORY
# =========================================

work_sessions = {}
break_sessions = {}

# =========================================
# STAFF NAME
# Telegram Name:
# CS 1 (Avelyn)
# =========================================

def get_staff(update):

    tg_name = update.effective_user.full_name.strip()

    if "(" in tg_name and ")" in tg_name:

        try:

            part1, part2 = tg_name.split("(", 1)

            staff = part1.strip().upper()

            name = part2.replace(")", "").strip()

        except:

            staff = tg_name
            name = tg_name

    else:

        staff = tg_name
        name = tg_name

    return staff, name

# =========================================
# SHIFT SYSTEM
# =========================================

def get_shift(staff):

    # ===== 9AM - 5PM =====
    if staff in [
        "CS AVELYN",
        "CS JAC"
    ]:

        return {
            "start": time(9, 0),
            "end": time(17, 0),
            "shift": "9:00AM - 5:00PM"
        }

    # ===== 5PM - 1AM =====
    elif staff in [
        "CS JOHN",
        "CS JANNY",
        "CS ETHAN"
    ]:

        return {
            "start": time(17, 0),
            "end": time(1, 0),
            "shift": "5:00PM - 1:00AM"
        }

    # ===== 1AM - 9AM =====
    elif staff in [
        "CS TERRY"
    ]:

        return {
            "start": time(1, 0),
            "end": time(9, 0),
            "shift": "1:00AM - 9:00AM"
        }

    return None

# =========================================
# LATE CHECK
# =========================================

def check_late(now, start_time):

    start_dt = now.replace(
        hour=start_time.hour,
        minute=start_time.minute,
        second=0,
        microsecond=0
    )

    # 晚班跨天
    if start_time.hour == 17 and now.hour < 12:
        start_dt -= timedelta(days=1)

    # 凌晨班跨天
    if start_time.hour == 1 and now.hour >= 9:
        start_dt -= timedelta(days=1)

    if now <= start_dt:
        return "On Time ✅"
    else:
        return "Late ❌"

# =========================================
# GOOGLE SHEET LOG
# =========================================

def log_sheet(staff, name, action, now, value="", status=""):

    sheet.append_row([
        staff,
        name,
        action,
        now.strftime("%Y-%m-%d %H:%M:%S"),
        value,
        status
    ])

# =========================================
# START
# =========================================

def start(update, context):

    update.message.reply_text(
        "1B打卡系统已启动 ✅\n请选择操作👇",
        reply_markup=menu
    )

# =========================================
# HIDE BUTTON
# =========================================

def hide(update, context):

    update.message.reply_text(
        "✅ Button Hidden",
        reply_markup=ReplyKeyboardRemove()
    )

# =========================================
# ON DUTY
# =========================================

def work(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    shift_data = get_shift(staff)

    if not shift_data:

        update.message.reply_text(
            "❌ 找不到你的班次"
        )

        return

    start_time = shift_data["start"]

    shift_name = shift_data["shift"]

    status = check_late(now, start_time)

    if staff in work_sessions:

        update.message.reply_text(
            "❌ 已经在上班了",
            reply_markup=menu
        )

        return

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
        f"""👤 {staff} ({name})
🟢 On Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
📋 班次: {shift_name}
{status}""",
        reply_markup=menu
    )

# =========================================
# OFF DUTY
# =========================================

def end(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    if staff not in work_sessions:

        update.message.reply_text(
            "❌ 你还没上班",
            reply_markup=menu
        )

        return

    start_time = work_sessions.pop(staff)

    hours = round(
        (now - start_time).total_seconds() / 3600,
        2
    )

    log_sheet(
        staff,
        name,
        "Off Duty",
        now,
        hours,
        "Ended"
    )

    update.message.reply_text(
        f"""👤 {staff} ({name})
🔴 Off Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 工作: {hours} 小时""",
        reply_markup=menu
    )

# =========================================
# BREAK
# =========================================

def rest(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    if staff in break_sessions:

        update.message.reply_text(
            "❌ 已经在休息中",
            reply_markup=menu
        )

        return

    break_sessions[staff] = now

    log_sheet(
        staff,
        name,
        "Break Start",
        now
    )

    update.message.reply_text(
        f"""👤 {staff} ({name})
☕ Break 开始
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}""",
        reply_markup=menu
    )

# =========================================
# BREAK BACK
# =========================================

def back(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    if staff not in break_sessions:

        update.message.reply_text(
            "❌ 没有在休息",
            reply_markup=menu
        )

        return

    start_break = break_sessions.pop(staff)

    seconds = int(
        (now - start_break).total_seconds()
    )

    minutes = seconds // 60

    log_sheet(
        staff,
        name,
        "Break End",
        now,
        minutes,
        "OK"
    )

    update.message.reply_text(
        f"""👤 {staff} ({name})
✅ Break Back 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
☕ 休息: {minutes} 分钟 ({seconds} 秒)""",
        reply_markup=menu
    )

# =========================================
# BUTTON HANDLER
# =========================================

def handle_message(update, context):

    text = update.message.text.strip()

    # ===== 按钮 =====

    if "On Duty" in text:

        work(update, context)

    elif "Off Duty" in text:

        end(update, context)

    elif text == "☕ Break":

        rest(update, context)

    elif text == "✅ Back":

        back(update, context)

    # ===== 指令 =====

    elif text == "/work":

        work(update, context)

    elif text == "/end":

        end(update, context)

    elif text == "/rest":

        rest(update, context)

    elif text == "/back":

        back(update, context)

    # ❌ 不再乱回复
    else:
        return

# =========================================
# KEEP RENDER ALIVE
# =========================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot alive"

def run_web():

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )

Thread(target=run_web).start()

# =========================================
# TELEGRAM START
# =========================================

updater = Updater(
    TOKEN,
    use_context=True
)

updater.bot.delete_webhook()

dp = updater.dispatcher

# COMMAND
dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("work", work))
dp.add_handler(CommandHandler("end", end))
dp.add_handler(CommandHandler("rest", rest))
dp.add_handler(CommandHandler("back", back))
dp.add_handler(CommandHandler("hide", hide))

# BUTTON
dp.add_handler(
    MessageHandler(
        Filters.text,
        handle_message
    )
)

print("🔥 1B CS Attendance Bot Running")

updater.start_polling()
updater.idle()
