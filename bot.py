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

# ===== 员工名单（必须有）=====
# ===== 员工 =====
STAFF = {
    "CS 1": "AVELYN",
    "CS 2": "SAM",
    "CS 3": "JOHN",
    "CS 4": "TERRY",
    "CS 5": "ANSON",
    "CS 6": "NATE"
}

# ===== 班次 =====
SHIFT = {
    "CS 1": (9, 17),
    "CS 2": (9, 17),
    "CS 3": (17, 1),
    "CS 4": (17, 1),
    "CS 5": (1, 9),
    "CS 6": (1, 9),
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
    user_id = update.effective_user.id   # ✅ 放这里

    if user_id not in USER_MAP:
        update.message.reply_text("❌ 未注册员工")
        return

    staff_id, name = USER_MAP[user_id]

    now = datetime.now()
    
    # 找员工编号
    staff_id = None
    for k in STAFF:
        if k in user:
            staff_id = k
            break

    if not staff_id:
        update.message.reply_text("❌ 无法识别员工，请用 CS1/CS2 名字")
        return

    name = STAFF[staff_id]

    # ===== 判断班次 =====
    start_hour, end_hour = SHIFT[staff_id]
    current_hour = now.hour

    # 跨天班（17 → 1）
    if start_hour > end_hour:
        if current_hour >= start_hour or current_hour < end_hour:
            shift_ok = True
        else:
            shift_ok = False
    else:
        shift_ok = start_hour <= current_hour < end_hour

    # ===== 判断迟到 =====
    late = now.hour > start_hour or (now.hour == start_hour and now.minute > 0)

    status = "Late ❌" if late else "On Time ✅"

    work_sessions[staff_id] = now

    # ===== 写入Sheet =====
    sheet.append_row([
        staff_id,
        name,
        "Work Start",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        "",
        status
    ])

    # ===== 输出 =====
    msg = f"""👤 {staff_id} {name}
📌 On Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
{status}"""

    update.message.reply_text(msg)

# 🔴 下班
def end(update, context):
    user_id = update.effective_user.id

    if user_id not in USER_MAP:
        update.message.reply_text("❌ 未注册员工")
        return

    staff_id, name = USER_MAP[user_id]
    now = datetime.now()

    if staff_id not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    start_time = work_sessions.pop(staff_id)
    hours = round((now - start_time).total_seconds() / 3600, 2)

    sheet.append_row([
        staff_id,
        name,
        "Work End",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        hours,
        "Ended"
    ])

    msg = f"""👤 {staff_id} {name}
🔴 Off Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 工作: {hours} 小时"""

    update.message.reply_text(msg)
    
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
