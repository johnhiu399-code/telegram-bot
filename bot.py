from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from datetime import datetime, time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ===== 配置 =====
TOKEN = "8625047747:AAHDgZx5xl7LMk67s0nlzjbGHRogNTdAmtE"
SHEET_NAME = "1B CS Attendance"

EMPLOYEES = {
    "CS 1": {"name": "Avelyn", "start": "09:00"},
    "CS 2": {"name": "Sam", "start": "09:00"},
    "CS 3": {"name": "John", "start": "17:00"},
    "CS 4": {"name": "Terry", "start": "17:00"},
    "CS 5": {"name": "Anson", "start": "01:00"},
    "CS 6": {"name": "Nate", "start": "01:00"},
}

BREAK_LIMIT = 30

# ===== Google Sheet =====
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ===== 内存 =====
work_sessions = {}
break_sessions = {}
USER_CHAT_IDS = {}

# ===== 共用函数 =====
async def process(update: Update, action: str):
    user = update.effective_user.first_name
    user_id = str(update.effective_user.id)
    now = datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")

    emp = EMPLOYEES.get(user)
    emp_name = emp["name"] if emp else "Unknown"

    work_hours = ""
    status = ""

    # 上班
    if action == "On Duty":
        work_sessions[user_id] = now
        if emp:
            start = datetime.strptime(emp["start"], "%H:%M").time()
            status = "Late ❌" if now.time() > start else "On Time ✅"

    # 休息开始
    elif action == "Break":
        break_sessions[user_id] = now
        status = "Break Start"

    # 休息结束
    elif action == "Break Back":
        if user_id in break_sessions:
            mins = int((now - break_sessions.pop(user_id)).total_seconds() / 60)
            status = f"Break Over {mins} mins ❌" if mins > BREAK_LIMIT else f"Break OK {mins} mins ✅"

    # 下班
    elif action == "Off Duty":
        if user_id in work_sessions:
            hours = round((now - work_sessions.pop(user_id)).total_seconds() / 3600, 2)
            work_hours = f"{hours} hrs"

    # 写入 Google Sheet
    sheet.append_row([f"{user} {emp_name}", user_id, action, time_str, work_hours, status])

    # 回复
    await update.message.reply_text(
        f"👤 {user} {emp_name}\n"
        f"📌 {action} 成功\n"
        f"⏰ 时间: {time_str}\n"
        f"{status}"
    )

# ===== 指令 =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    USER_CHAT_IDS[user] = update.effective_chat.id
    await update.message.reply_text("系统已启动，用指令打卡：/work /end /rest /back")

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process(update, "On Duty")

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process(update, "Off Duty")

async def rest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process(update, "Break")

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process(update, "Break Back")

# ===== 报表 =====
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")

    result = "📊 今日报表\n\n"

    for r in records:
        name = r.get("Name")
        action = r.get("Action")
        time_val = r.get("Time")

        if not name or not action or not time_val:
            continue

        if today in str(time_val):
            result += f"{name} | {action} | {time_val}\n"

    if result == "📊 今日报表\n\n":
        result += "暂无记录"

    await update.message.reply_text(result)

# ===== 自动提醒 =====
async def check_no_checkin(context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")

    checked = set()

    for r in records:
        if today in str(r.get("Time")) and r.get("Action") == "On Duty":
            checked.add(r.get("Name").split()[0])

    for user in EMPLOYEES:
        if user not in checked:
            chat_id = USER_CHAT_IDS.get(user)
            if chat_id:
                await context.bot.send_message(chat_id, "⚠️ 你还没有打卡上班！")

# ===== 主程序 =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("work", work))
app.add_handler(CommandHandler("end", end))
app.add_handler(CommandHandler("rest", rest))
app.add_handler(CommandHandler("back", back))
app.add_handler(CommandHandler("report", report))

# 定时任务
job_queue = app.job_queue
job_queue.run_daily(check_no_checkin, time(hour=9, minute=15))

print("BOT COMMAND SYSTEM RUNNING...")
app.run_polling()