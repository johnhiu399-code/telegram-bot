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

# ===== TIMEZONE =====
tz = pytz.timezone("Asia/Kuala_Lumpur")

# ===== LOG =====
logging.basicConfig(level=logging.INFO)

# ===== MEMORY =====
work_sessions = {}
break_sessions = {}

# ===== MENU =====
menu = ReplyKeyboardMarkup(
    [
        ["🟢 On Duty", "🔴 Off Duty"],
        ["☕ Break", "✅ Back"]
    ],
    resize_keyboard=True
)

# ===== GOOGLE SHEET =====
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials.json",
    scope
)

client = gspread.authorize(creds)

sheet = client.open("CS Attendance").sheet1

# ===== GET STAFF =====
def get_staff(update):

    tg_name = update.effective_user.full_name.strip()

    # 统一空格
    tg_name = " ".join(tg_name.split())

    return tg_name, tg_name


# ===== SHIFT SYSTEM =====
def get_shift(staff):

    staff = staff.strip()

    # ===== 9AM - 5PM =====
    if staff == "CS 1 (Avelyn)":
        return {
            "start": time(9, 0),
            "end": time(17, 0),
            "shift": "9:00AM - 5:00PM"
        }

    elif staff == "CS 2 (Ed)":
        return {
            "start": time(9, 0),
            "end": time(17, 0),
            "shift": "9:00AM - 5:00PM"
        }

    # ===== 5PM - 1AM =====
    elif staff == "CS 3 (John)":
        return {
            "start": time(17, 0),
            "end": time(1, 0),
            "shift": "5:00PM - 1:00AM"
        }

    elif staff == "CS 4 (Terry)":
        return {
            "start": time(17, 0),
            "end": time(1, 0),
            "shift": "5:00PM - 1:00AM"
        }

    # ===== 1AM - 9AM =====
    elif staff == "CS 5 (Sam)":
        return {
            "start": time(1, 0),
            "end": time(9, 0),
            "shift": "1:00AM - 9:00AM"
        }

    return None


# ===== CHECK LATE =====
def check_late(now, start_time):

    current = now.time()

    if current > start_time:
        return "Late ❌"

    return "On Time ✅"


# ===== LOG SHEET =====
def log_sheet(staff, name, action, now, value="", status=""):

    try:
        row = [
            staff,
            name,
            action,
            now.strftime("%Y-%m-%d %H:%M:%S"),
            value,
            status
        ]

        sheet.append_row(row)

    except Exception as e:
        print("SHEET ERROR =", e)


# ===== START =====
def start(update, context):

    update.message.reply_text(
        "1BCS打卡系统启动 ✅\n请选择操作👇",
        reply_markup=menu
    )


# ===== WORK =====
def work(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    print("WORK STAFF =", repr(staff))

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

    log_sheet(staff, name, "On Duty", now, "", status)

    update.message.reply_text(
        f"""👤 {staff}
🟢 On Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
📋 班次: {shift_name}
{status}"""
    )


# ===== END =====
def end(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    print("END STAFF =", repr(staff))

    if staff not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    start_work = work_sessions[staff]

    seconds = int((now - start_work).total_seconds())

    hours = round(seconds / 3600, 2)

    del work_sessions[staff]

    log_sheet(staff, name, "Off Duty", now, hours)

    update.message.reply_text(
        f"""👤 {staff}
🔴 Off Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 工作: {hours} 小时"""
    )


# ===== BREAK =====
def rest(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    if staff not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    break_sessions[staff] = now

    log_sheet(staff, name, "Break", now)

    update.message.reply_text(
        f"""👤 {staff}
☕ Break 开始
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}"""
    )


# ===== BACK =====
def back(update, context):

    now = datetime.now(tz)

    staff, name = get_staff(update)

    if staff not in break_sessions:
        update.message.reply_text("❌ 你没有在休息")
        return

    start_break = break_sessions[staff]

    seconds = int((now - start_break).total_seconds())

    minutes = seconds // 60

    del break_sessions[staff]

    log_sheet(staff, name, "Break Back", now, f"{minutes} 分钟")

    update.message.reply_text(
        f"""👤 {staff}
✅ Break Back 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
☕ 休息: {minutes} 分钟 ({seconds} 秒)"""
    )


# ===== HANDLE BUTTON =====
def handle_message(update, context):

    text = update.message.text.strip()

    print("BUTTON =", text)

    if "On Duty" in text:
        work(update, context)

    elif "Off Duty" in text:
        end(update, context)

    elif "Break" in text and "Back" not in text:
        rest(update, context)

    elif "Back" in text:
        back(update, context)


# ===== RUN =====
updater = Updater(TOKEN, use_context=True)

updater.bot.delete_webhook()

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("work", work))
dp.add_handler(CommandHandler("end", end))
dp.add_handler(CommandHandler("rest", rest))
dp.add_handler(CommandHandler("back", back))

dp.add_handler(MessageHandler(Filters.text, handle_message))

print("BOT PRO+ RUNNING")

updater.start_polling()
updater.idle()
