import os
import logging
from datetime import datetime, time, timedelta
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

# ===== 内存 =====
work_sessions = {}
break_sessions = {}

logging.basicConfig(level=logging.INFO)

# ===== 菜单 =====
menu = ReplyKeyboardMarkup(
    [["🟢 On Duty", "🔴 Off Duty"],
     ["☕ Break", "✅ Back"]],
    resize_keyboard=True
)

# ===== 解析名字（CS 3 (John)）=====
def get_staff(update):
    tg_name = update.effective_user.first_name.strip()

    if "(" in tg_name and ")" in tg_name:
        try:
            staff = tg_name.split("(")[0].strip()
            name = tg_name.split("(")[1].replace(")", "").strip()
        except:
            staff = tg_name
            name = tg_name
    else:
        staff = tg_name
        name = tg_name

    return staff, name

# ===== 班次 =====
def get_shift(staff):
    if staff == "CS 1":
        return time(9, 0)
    elif staff in ["CS 3", "CS 4"]:
        return time(17, 0)
    elif staff == "CS 5":
        return time(1, 0)
    return None

# ===== Late 判断（已修复跨天）=====
def check_late(now, start_time):
    if not start_time:
        return "Unknown"

    start_dt = now.replace(
        hour=start_time.hour,
        minute=start_time.minute,
        second=0,
        microsecond=0
    )

    # 晚班（17:00 → 次日）
    if start_time.hour == 17:
        if now.hour < 12:
            start_dt -= timedelta(days=1)

    # 凌晨班（1:00）
    if start_time.hour == 1:
        if now.hour >= 9:
            start_dt -= timedelta(days=1)

    return "On Time ✅" if now <= start_dt else "Late ❌"

# ===== Start =====
def start(update, context):
    update.message.reply_text("1B打卡系统已启动 ✅ 请选择", reply_markup=menu)

# ===== 上班 =====
def work(update, context):
    now = datetime.now(tz)
    staff, name = get_staff(update)

    if staff in work_sessions:
        update.message.reply_text("❌ 已经在上班了")
        return

    start_time = get_shift(staff)
    status = check_late(now, start_time)

    work_sessions[staff] = now

    update.message.reply_text(
        f"""👤 {staff} ({name})
🟢 On Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
{status}"""
    )

# ===== 下班 =====
def end(update, context):
    now = datetime.now(tz)
    staff, name = get_staff(update)

    if staff not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    start_time = work_sessions.pop(staff)
    hours = round((now - start_time).total_seconds() / 3600, 2)

    update.message.reply_text(
        f"""👤 {staff} ({name})
🔴 Off Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 工作: {hours} 小时"""
    )

# ===== 休息 =====
def rest(update, context):
    now = datetime.now(tz)
    staff, name = get_staff(update)

    if staff in break_sessions:
        update.message.reply_text("❌ 已在休息中")
        return

    break_sessions[staff] = now

    update.message.reply_text(
        f"""👤 {staff} ({name})
☕ Break 开始
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}"""
    )

# ===== 回来 =====
def back(update, context):
    now = datetime.now(tz)
    staff, name = get_staff(update)

    if staff not in break_sessions:
        update.message.reply_text("❌ 没有在休息")
        return

    start = break_sessions.pop(staff)
    seconds = int((now - start).total_seconds())
    minutes = seconds // 60

    update.message.reply_text(
        f"""👤 {staff} ({name})
✅ Break Back 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
☕ 休息: {minutes} 分钟 ({seconds} 秒)"""
    )

# ===== 按钮处理 =====
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

# ===== Flask 防 Render 睡觉 =====
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web).start()

# ===== 启动 =====
updater = Updater(TOKEN, use_context=True)
updater.bot.delete_webhook()

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text, handle_message))

print("🔥 BOT RUNNING")
updater.start_polling()
updater.idle()
