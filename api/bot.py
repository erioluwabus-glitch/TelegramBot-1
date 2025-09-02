import logging
import random
import os
import time
from flask import Flask, request, jsonify
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64
import schedule

app = Flask(__name__)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets setup
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(base64.b64decode(os.environ.get('CREDENTIALS_JSON')), scope)
client = gspread.authorize(creds)
assignment_sheet = client.open("VisionCourseSupport").worksheet("Assignments")
wins_sheet = client.open("VisionCourseSupport").worksheet("Wins")

# Configuration
TOKEN = os.environ.get('TOKEN', '8138720265:AAGvACO_aPmvcJDpY3ugyM3AV1cmZUJ4RTU')
ADMIN_ID = os.environ.get('ADMIN_ID', '7109534825')
GROUP_CHAT_ID = os.environ.get('GROUP_CHAT_ID', '-1003036481382')
VALID_MODULES = ['4', '7', '10']
ENCOURAGEMENTS = ["Crushing it! 🚀", "Shining bright! 🌟", "On fire! 🔥", "Next-level! 💪"]

# Initialize Application
application = Application.builder().token(TOKEN).build()

# Handlers
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
        if text not in VALID_MODULES:
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

  async def handle_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
      user = update.effective_user.username or str(update.effective_user.id)
      content_type = "Text" if update.message.text else "Video" if update.message.video else "Photo" if update.message.photo else "Link"
      content = update.message.text or "Media/Link"
      encouragement = random.choice(ENCOURAGEMENTS)
      mode = context.user_data.get('mode', '')
      if mode == 'assignment':
          module = context.user_data.get('module', 'Unknown')
          status = "Submitted"
          grade = "Auto-Graded: 8/10 - Nailed it!" if content_type == "Video" else "Auto-Graded: 6/10 - Video submissions score higher!"
          try:
              if content_type in ["Video", "Photo"]:
                  file_id = update.message.video.file_id if content_type == "Video" else update.message.photo[-1].file_id
                  sent_message = await context.bot.send_message(GROUP_CHAT_ID, f"{content_type} from @{user} for Module {module}")
                  message_id = sent_message.message_id
                  content = f"telegram:{GROUP_CHAT_ID}:{message_id}"
                  if content_type == "Video":
                      await context.bot.send_video(GROUP_CHAT_ID, file_id)
                  else:
                      await context.bot.send_photo(GROUP_CHAT_ID, file_id)
              assignment_sheet.append_row([user, module, status, content_type, content, grade, time.strftime('%Y-%m-%d')])
              logger.info(f"Assignment saved for @{user} in Module {module}")
              await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, Module {module} {content_type.lower()} submitted! {grade} {encouragement} 🎉")
          except Exception as e:
              logger.error(f"Submission error: {e}")
              await context.bot.send_message(chat_id=update.effective_chat.id, text="Submission failed. Try again! 😓")
          finally:
              context.user_data.pop('mode', None)
              context.user_data.pop('module', None)
      elif mode == 'small_win':
          try:
              if content_type in ["Video", "Photo"]:
                  file_id = update.message.video.file_id if content_type == "Video" else update.message.photo[-1].file_id
                  sent_message = await context.bot.send_message(GROUP_CHAT_ID, f"Small win from @{user}")
                  message_id = sent_message.message_id
                  content = f"telegram:{GROUP_CHAT_ID}:{message_id}"
                  if content_type == "Video":
                      await context.bot.send_video(GROUP_CHAT_ID, file_id)
                  else:
                      await context.bot.send_photo(GROUP_CHAT_ID, file_id)
              wins_sheet.append_row([user, "Small " + content_type, content, time.strftime('%Y-%m-%d')])
              logger.info(f"Small win saved for @{user}")
              await context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, small win shared! {encouragement} 😄")
          except Exception as e:
              logger.error(f"Small win error: {e}")
              await context.bot.send_message(chat_id=update.effective_chat.id, text="Error sharing win. Try again! 😓")
          finally:
              context.user_data.pop('mode', None)

  # Webhook handler
  @app.route('/', methods=['GET', 'POST'])
  def webhook():
      if request.method == 'POST':
          data = request.get_json(force=True)
          logger.info(f"Received update from Telegram: {data}")
          update = Update.de_json(data, application.bot)
          application.process_update(update)
          return "ok", 200
      return "Bot is alive!", 200

  # Reminder route for cron
  @app.route('/reminder', methods=['GET'])
  def reminder():
      logger.info("Running daily reminder")
      application.bot.send_message(GROUP_CHAT_ID, "Daily reminder: Submit or share a win! 🚀")
      return "Reminder sent", 200

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CommandHandler("menu", menu))
  application.add_handler(CommandHandler("remove", remove))
  application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
  application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.TEXT, handle_submission))
  application.add_handler(CommandHandler("getmedia", get_media))

  scheduler_thread = Thread(target=run_scheduler, args=(application,))
  scheduler_thread.start()

  if __name__ == '__main__':
      app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))
