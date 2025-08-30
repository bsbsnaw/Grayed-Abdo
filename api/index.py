import logging
import calendar
from datetime import datetime, timedelta, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ExtBot
import os
import asyncio
from flask import Flask, request

# --- الإعدادات الأساسية ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# احصل على التوكن من متغيرات البيئة بدلاً من كتابته مباشرة في الكود
# سنقوم بتعيين هذا المتغير لاحقًا في لوحة تحكم Vercel
TOKEN = os.environ.get("BOT_TOKEN")

# في Vercel، المكان الوحيد المتاح للكتابة المؤقتة هو مجلد /tmp
# ملاحظة: الملفات في هذا المجلد قد تُمحى، هذا حل مؤقت وليس دائمًا
SUBSCRIBERS_FILE = "/tmp/subscribers.txt"

# --- نقطة المرجع لجريدة الشرق الأوسط (تبقى كما هي) ---
REFERENCE_DATE = date(2025, 8, 29)
REFERENCE_ISSUE_NUMBER = 17076


# --- دوال التعامل مع الذاكرة (تبقى كما هي) ---

def read_subscribers():
    """يقرأ قائمة المشتركين من الملف."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        return set()
    with open(SUBSCRIBERS_FILE, "r") as f:
        return set(int(line.strip()) for line in f if line.strip())


def add_subscriber(chat_id):
    """يضيف مشتركًا جديدًا إلى الملف."""
    subscribers = read_subscribers()
    subscribers.add(chat_id)
    with open(SUBSCRIBERS_FILE, "w") as f:
        for sub_id in subscribers:
            f.write(f"{sub_id}\n")


def remove_subscriber(chat_id):
    """يزيل مشتركًا من الملف."""
    subscribers = read_subscribers()
    subscribers.discard(chat_id)
    with open(SUBSCRIBERS_FILE, "w") as f:
        for sub_id in subscribers:
            f.write(f"{sub_id}\n")

# --- كل دوال الواجهات وجلب الروابط تبقى كما هي ---
def create_calendar(year, month, calendar_type):
    markup_list = []
    header_row = [InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore")]
    markup_list.append(header_row)
    days_of_week_row = [InlineKeyboardButton(day, callback_data="ignore") for day in
                        ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]]
    markup_list.append(days_of_week_row)
    for week in calendar.monthcalendar(year, month):
        week_row = [InlineKeyboardButton(str(day) if day != 0 else " ",
                                         callback_data=f"cal_day_{year}-{month}-{day}_{calendar_type}" if day != 0 else "ignore")
                    for day in week]
        markup_list.append(week_row)
    prev_month_data = f"cal_nav_{year}-{month}_prev_{calendar_type}"
    next_month_data = f"cal_nav_{year}-{month}_next_{calendar_type}"
    footer_row = [InlineKeyboardButton("<", callback_data=prev_month_data),
                  InlineKeyboardButton(">", callback_data=next_month_data)]
    markup_list.append(footer_row)
    return InlineKeyboardMarkup(markup_list)


def create_week_view(target_date, calendar_type):
    start_of_week = target_date - timedelta(days=(target_date.weekday() + 1) % 7)
    markup_list = []
    week_days = []
    day_names = ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"]
    for i in range(7):
        current_day = start_of_week + timedelta(days=i)
        day_text = f"{day_names[i]}\n{current_day.day}"
        callback_data = f"week_day_{current_day.strftime('%Y-%m-%d')}_{calendar_type}"
        week_days.append(InlineKeyboardButton(day_text, callback_data=callback_data))
    markup_list.append(week_days)
    prev_week_date = start_of_week - timedelta(weeks=1)
    next_week_date = start_of_week + timedelta(weeks=1)
    nav_row = [
        InlineKeyboardButton("<< الأسبوع السابق",
                             callback_data=f"week_nav_{prev_week_date.strftime('%Y-%m-%d')}_{calendar_type}"),
        InlineKeyboardButton("الأسبوع التالي >>",
                             callback_data=f"week_nav_{next_week_date.strftime('%Y-%m-%d')}_{calendar_type}")
    ]
    markup_list.append(nav_row)
    return InlineKeyboardMarkup(markup_list)


def get_albayan_pdf_link(selected_date: date):
    date_str = selected_date.strftime("%Y%m%d")
    return f"https://media.albayan.ae/AlbayanPDF/albayan{date_str}.pdf"


def get_aawsat_viewer_link_by_date(selected_date: date):
    delta = selected_date - REFERENCE_DATE
    new_issue_number = REFERENCE_ISSUE_NUMBER + delta.days
    return f"https://aawsat.com/files/pdf/issue{new_issue_number}/"


# --- كل معالجات الأوامر تبقى كما هي ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["الأسبوع (الشرق الأوسط)", "الأسبوع (البيان)"], ["التقويم (الشرق الأوسط)", "التقويم (البيان)"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("أهلًا بك! اختر الجريدة وطريقة العرض:", reply_markup=reply_markup)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    add_subscriber(chat_id)
    await update.message.reply_text("تم اشتراكك بنجاح!")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    remove_subscriber(chat_id)
    await update.message.reply_text("تم إلغاء اشتراكك.")

async def week_aawsat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اختر يومًا من الأسبوع (الشرق الأوسط):",
                                    reply_markup=create_week_view(date.today(), "aawsat"))

async def week_albayan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اختر يومًا من الأسبوع (البيان):",
                                    reply_markup=create_week_view(date.today(), "albayan"))

async def calendar_aawsat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    await update.message.reply_text("اختر تاريخًا (الشرق الأوسط):",
                                    reply_markup=create_calendar(now.year, now.month, "aawsat"))

async def calendar_albayan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    await update.message.reply_text("اختر تاريخًا (البيان):",
                                    reply_markup=create_calendar(now.year, now.month, "albayan"))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    # ... (باقي كود المعالج كما هو بدون تغيير)
    view_type = parts[0]
    action_type = parts[1]
    if view_type == 'week':
        calendar_type = parts[3]
        selected_date_str = parts[2]
        target_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        if action_type == 'day':
            await query.edit_message_text(text=f"تم اختيار: {target_date.strftime('%d %B, %Y')}\nجاري إنشاء الرابط...")
            link = get_aawsat_viewer_link_by_date(target_date) if calendar_type == 'aawsat' else get_albayan_pdf_link(
                target_date)
            await query.message.reply_text(f"تفضل الرابط:\n{link}")
        elif action_type == 'nav':
            await query.edit_message_reply_markup(reply_markup=create_week_view(target_date, calendar_type))
    elif view_type == 'cal':
        if action_type == 'day':
            calendar_type = parts[3]
            year, month, day = map(int, parts[2].split("-"))
            selected_date = date(year, month, day)
            await query.edit_message_text(
                text=f"تم اختيار: {selected_date.strftime('%d %B, %Y')}\nجاري إنشاء الرابط...")
            link = get_aawsat_viewer_link_by_date(selected_date) if calendar_type == 'aawsat' else get_albayan_pdf_link(
                selected_date)
            await query.message.reply_text(f"تفضل الرابط:\n{link}")
        elif action_type == 'nav':
            calendar_type = parts[4]
            year, month = map(int, parts[2].split("-"))
            direction = parts[3]
            current_date = datetime(year, month, 1)
            if direction == "prev":
                new_date = (current_date - timedelta(days=1)).replace(day=1)
            else:
                last_day = calendar.monthrange(year, month)[1]; new_date = (
                            current_date.replace(day=last_day) + timedelta(days=1))
            await query.edit_message_reply_markup(
                reply_markup=create_calendar(new_date.year, new_date.month, calendar_type))

# --- إعداد تطبيق البوت والمعالجات (Handlers) ---
bot_instance = ExtBot(token=TOKEN)
application = Application.builder().bot(bot_instance).build()

# تسجيل المعالجات كما في الكود الأصلي
application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('subscribe', subscribe))
application.add_handler(CommandHandler('unsubscribe', unsubscribe))
application.add_handler(MessageHandler(filters.Regex("^الأسبوع \(الشرق الأوسط\)$"), week_aawsat))
application.add_handler(MessageHandler(filters.Regex("^الأسبوع \(البيان\)$"), week_albayan))
application.add_handler(MessageHandler(filters.Regex("^التقويم \(الشرق الأوسط\)$"), calendar_aawsat))
application.add_handler(MessageHandler(filters.Regex("^التقويم \(البيان\)$"), calendar_albayan))
application.add_handler(CallbackQueryHandler(callback_handler))


# --- إعداد خادم الويب (Flask) لاستقبال الـ Webhook ---
# هذا هو الجزء الجديد الذي يجعل الكود يعمل على Vercel
app = Flask(__name__)

@app.route('/', methods=['POST']) # <<<=== تم التغيير هنا
def webhook():
    """هذه الدالة تستقبل التحديثات من تليجرام وتعالجها"""
    update_data = request.get_json(force=True)
    update = Update.de_json(data=update_data, bot=bot_instance)
    
    # نقوم بتشغيل معالجة التحديث بشكل غير متزامن
    asyncio.run(application.process_update(update))
    
    return 'OK', 200

# Vercel يبحث عن متغير اسمه 'app' لتشغيله كخادم ويب
# لم نعد بحاجة إلى دالة main() أو application.run_polling()

