import os
import logging
from datetime import datetime, time
import pytz

from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# ===== TOKEN =====
TOKEN = os.environ.get("TOKEN")

# ===== 马来西亚时间 =====
tz = pytz.timezone("Asia/Kuala_Lumpur")

# ===== 员工 + 班次 =====
STAFF = {
    "CS 1": {"name": "AVELYN", "start": time(9, 0), "end": time(17, 0)},
    "CS 2": {"name": "SAM", "start": time(1, 0), "end": time(9, 0)},
    "CS 3": {"name": "JOHN", "start": time(17, 0), "end": time(1, 0)},
    "CS 4": {"name": "TERRY", "start": time(17, 0), "end": time(1, 0)},
    "CS 5": {"name": "ANSON", "start": time(1, 0), "end": time(9, 0)},
}

# ===== 状态 =====
work_sessions = {}
break_sessions = {}

logging.basicConfig(level=logging.INFO)

# ===== 菜单 =====
menu = ReplyKeyboardMarkup([
    ["🟢 On Duty", "🔴 Off Duty"],
    ["☕ Break", "✅ Back"],
], resize_keyboard=True)


# ===== 获取员工 =====
def get_staff(update):
    tg_name = update.effective_user.first_name

    if tg_name in STAFF:
        data = STAFF[tg_name]
        return tg_name, data["name"], data["start"], data["end"]

    return tg_name, "Unknown", None, None


# ===== 判断 Early / On Time / Late =====
def check_status(now, start_time):
    now_time = now.time()

    if now_time < start_time:
        return "Early 🟡"
    elif now_time == start_time:
        return "On Time ✅"
    else:
        return "Late ❌"


# ===== Start =====
def start(update, context):
    update.message.reply_text("系统已启动 ✅\n请选择操作👇", reply_markup=menu)


# ===== On Duty =====
def work(update, context):
    now = datetime.now(tz)
    user_id = update.effective_user.id

    staff, name, start_time, end_time = get_staff(update)

    if start_time is None:
        update.message.reply_text("❌ 未注册员工")
        return

    if user_id in work_sessions:
        update.message.reply_text("❌ 你已经在上班")
        return

    status = check_status(now, start_time)

    work_sessions[user_id] = now

    update.message.reply_text(
        f"""👤 {staff} {name}
🟢 On Duty 成功
🕒 班次: {start_time.strftime("%H:%M")} - {end_time.strftime("%H:%M")}
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
{status}"""
    )


# ===== Off Duty =====
def end(update, context):
    now = datetime.now(tz)
    user_id = update.effective_user.id

    staff, name, _, _ = get_staff(update)

    if user_id not in work_sessions:
        update.message.reply_text("❌ 你还没上班")
        return

    start_time = work_sessions.pop(user_id)
    hours = round((now - start_time).total_seconds() / 3600, 2)

    update.message.reply_text(
        f"""👤 {staff} {name}
🔴 Off Duty 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
🕒 工作: {hours} 小时"""
    )


# ===== Break =====
def rest(update, context):
    now = datetime.now(tz)
    user_id = update.effective_user.id

    staff, name, _, _ = get_staff(update)

    break_sessions[user_id] = now

    update.message.reply_text(
        f"""👤 {staff} {name}
☕ Break 开始
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}"""
    )


# ===== Back =====
def back(update, context):
    now = datetime.now(tz)
    user_id = update.effective_user.id

    staff, name, _, _ = get_staff(update)

    if user_id not in break_sessions:
        update.message.reply_text("❌ 没有在休息")
        return

    start = break_sessions.pop(user_id)

    seconds = int((now - start).total_seconds())
    minutes = seconds // 60

    status = "OK ✅" if minutes <= 30 else "Overtime ❌"

    update.message.reply_text(
        f"""👤 {staff} {name}
✅ Break Back 成功
⏰ 时间: {now.strftime("%Y-%m-%d %H:%M:%S")}
☕ 休息: {minutes} 分钟 ({seconds} 秒)
{status}"""
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


# ===== 启动 =====
updater = Updater(TOKEN, use_context=True)
updater.bot.delete_webhook()

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text, handle_message))

print("BOT RUNNING...")
updater.start_polling()
updater.idle()
