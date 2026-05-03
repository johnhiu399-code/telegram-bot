import os
import logging
from datetime import datetime, time
import pytz

from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# ===== TOKEN =====
TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    print("❌ TOKEN missing")
    exit()

# ===== 时区（马来西亚）=====
tz = pytz.timezone("Asia/Kuala_Lumpur")

# ===== 员工 & 班次 =====
STAFF = {
    "CS 1": {"name": "AVELYN", "start": time(9, 0), "end": time(17, 0)},
    "CS 3": {"name": "JOHN", "start": time(17, 0), "end": time(1, 0)},
    "CS 4": {"name": "TERRY", "start": time(17, 0), "end": time(1, 0)},
    "CS 2": {"name": "SAM", "start": time(1, 0), "end": time(9, 0)},
    "CS 5": {"name": "ANSON", "start": time(1, 0), "end": time(9, 0)},
}

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

# ===== 判断迟到 =====
def check_late(now, start_time):
    if not start_time:
        return "Unknown"

    start_dt = now.replace(hour=start_time.hour, minute=start_time.minute, second=0)

    # 跨天班（例如 17:00-1:00）
    if start_time.hour > now.hour:
        start_dt = start_dt.replace(day=now.day - 1)

    if now <= start_dt:
        return "On Time ✅"
    else:
        return "Late ❌"

# ===== Start =====
def start(update, context):
    update.message.reply_text(
        "1BCS打卡系统已启动 ✅\n请选择操作👇",
        reply_markup=menu
    )

# ===== 上班 =====
def work(update, context):
    now = datetime.now(tz)
    staff, name, start_time = get_staff(update)

    status = check_late(now, start_time)

    work_sessions[staff] = now

    update.message.reply_text(
        f"""👤 {staff} {name}
🟢 On Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
{status}"""
    )

# ===== 下班 =====
def end(update, context):
    now = datetime.now(tz)
    staff, name, _ = get_staff(update)

    if staff not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    start_time = work_sessions.pop(staff)
    hours = round((now - start_time).total_seconds() / 3600, 2)

    update.message.reply_text(
        f"""👤 {staff} {name}
🔴 Off Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 工作: {hours} 小时"""
    )

# ===== 休息 =====
def rest(update, context):
    now = datetime.now(tz)
    staff, name, _ = get_staff(update)

    break_sessions[staff] = now

    update.message.reply_text(
        f"""👤 {staff} {name}
☕ Break 开始
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}"""
    )

# ===== 回来 =====
def back(update, context):
    now = datetime.now(tz)
    staff, name, _ = get_staff(update)

    if staff not in break_sessions:
        update.message.reply_text("❌ 你没有在休息")
        return

    start = break_sessions.pop(staff)
    seconds = int((now - start).total_seconds())
    minutes = seconds // 60

    update.message.reply_text(
        f"""👤 {staff} {name}
✅ Break Back 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
☕ 休息: {minutes} 分钟 ({seconds} 秒)"""
    )

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

# ===== Flask 防休眠 =====
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

# ===== 启动 =====
updater = Updater(TOKEN, use_context=True)
updater.bot.delete_webhook()

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text, handle_message))

print("BOT RUNNING...")
updater.start_polling()
updater.idle()
