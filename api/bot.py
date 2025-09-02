import logging
import random
import os
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from threading import Thread
import schedule
import time

app = Flask(__name__)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets setup
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)
assignment_sheet = client.open("VisionCourseSupport").worksheet("Assignments")
wins_sheet = client.open("VisionCourseSupport").worksheet("Wins")

# Configuration
TOKEN = os.environ.get('TOKEN', '8138720265:AAHtklkJUBfb8Z9haLJylvcNad56lWT-WiE')
ADMIN_ID = os.environ.get('ADMIN_ID', '8282761440')
GROUP_CHAT_ID = os.environ.get('GROUP_CHAT_ID', '-1003069423158')

# Telegram Dispatcher
dispatcher = Dispatcher(None, None, use_context=True)

# Handlers (add your handlers here, e.g., start, menu, etc.)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or str(update.effective_user.id)
    keyboard = [["Submit Assignment 📝", "Share Small Win 🎉"], ["Check Status 📊", "Grade (Admin) 🖊️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, welcome! Use the buttons! 🚀", reply_markup=reply_markup)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or str(update.effective_user.id)
    keyboard = [["Submit Assignment 📝", "Share Small Win 🎉"], ["Check Status 📊", "Grade (Admin) 🖊️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, choose an option! 🚀", reply_markup=reply_markup)

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or str(update.effective_user.id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, keyboard removed! Use /menu to bring it back. 😄", reply_markup=ReplyKeyboardRemove())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or str(update.effective_user.id)
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    mode = context.user_data.get('mode', '')

    if text == "Submit Assignment 📝":
        context.user_data['mode'] = 'submit_module'
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, enter module number (4, 7, or 10):")
    elif text == "Share Small Win 🎉":
        context.user_data['mode'] = 'small_win'
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, share your win (text/photo/video):")
    elif text == "Check Status 📊":
        try:
            records = assignment_sheet.get_all_records()
            user_submissions = [r for r in records if r['User'] == user]
            if user_submissions:
                response = f"@{user}, your progress:\n"
                for r in user_submissions:
                    response += f"Module {r['Module']}: {r['Status']} ({r['Grade']})\n"
            else:
                response = f"@{user}, no submissions yet. Submit one!"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        except Exception as e:
            logger.error(f"Status error: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching status. Try again! 😓")
    elif text == "Grade (Admin) 🖊️":
        if user_id != ADMIN_ID:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Only admins can grade! 😎")
            return
        context.user_data['mode'] = 'grade_details'
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, enter: @username <module> <grade> (e.g., @erioluwadan 10 9/10)")
    elif mode == 'submit_module':
        if text not in ['4', '7', '10']:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, only modules 4, 7, or 10! 😄")
            return
        context.user_data['mode'] = 'assignment'
        context.user_data['module'] = text
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, send Module {text} content (text/photo/video)! 🎥")
    elif mode == 'grade_details':
        if user_id != ADMIN_ID:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Only admins can grade! 😎")
            return
        try:
            parts = text.split()
            if len(parts) < 3:
                raise ValueError("Invalid format")
            target_user = parts[0].lstrip('@')
            module = parts[1]
            grade = " ".join(parts[2:])
            assignment_sheet.append_row([target_user, module, "Graded", "N/A", "N/A", grade, time.strftime('%Y-%m-%d')])
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, graded {target_user}'s Module {module} as {grade}! 🚀")
        except Exception as e:
            logger.error(f"Grade error: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Error grading. Try again! 😓")
        finally:
            context.user_data.pop('mode', None)
