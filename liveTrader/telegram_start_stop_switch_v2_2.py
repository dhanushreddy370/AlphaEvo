
import subprocess
import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Configuration ---
# !!! ENTER YOUR TELEGRAM BOT TOKEN BELOW !!!
BOT_TOKEN = "8409424214:AAGGdnPhgiGkr_b1cTdqp1UAk6FORhJ2CfY"

# !!! IMPORTANT: Replace with your own Telegram User ID to restrict control !!!
AUTHORIZED_USER_ID = 7207365764 # Replace with your actual user ID

# --- Script Paths ---
WORKING_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
BOT_SCRIPT_PATH = os.path.join(WORKING_DIRECTORY, 'live_trader_v2_2.py')

# --- Termination Flag File ---
TERMINATION_FLAG = os.path.join(WORKING_DIRECTORY, 'stop_flag_v2_2.txt')

# --- Process Management ---
running_process = None

# --- Authorization Check ---
async def is_authorized(update: Update) -> bool:
    """Checks if the user sending the command is authorized."""
    user_id = update.effective_user.id
    if user_id != AUTHORIZED_USER_ID:
        await update.message.reply_html(
            "<b>🚫 Access Denied</b>\nSorry, you are not authorized to use this bot."
        )
        print(f"Unauthorized access attempt by User ID: {user_id}")
        return False
    return True

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the trading bot script."""
    global running_process
    if not await is_authorized(update):
        return

    if running_process and running_process.poll() is None:
        await update.message.reply_text("Bot is already running.")
        return

    if os.path.exists(TERMINATION_FLAG):
        os.remove(TERMINATION_FLAG)

    try:
        running_process = subprocess.Popen(
            ["python", BOT_SCRIPT_PATH, str(AUTHORIZED_USER_ID)],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        await update.message.reply_text("🚀 Starting the MSS v2.2 (Session Filter) Trading Bot...")
        print(f"Started {BOT_SCRIPT_PATH} with user ID {AUTHORIZED_USER_ID}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to start the bot. Error: {e}")
        print(f"Error starting bot: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stops the trading bot script."""
    global running_process
    if not await is_authorized(update):
        return

    if not running_process or running_process.poll() is not None:
        await update.message.reply_text("Bot is not currently running.")
        return

    try:
        with open(TERMINATION_FLAG, 'w') as f:
            f.write('stop')
        
        running_process.terminate()
        running_process = None
        
        await update.message.reply_text("🛑 Bot v2.2 stopped.")
        print(f"Stop signal sent for v2.2 and process terminated.")

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to stop the bot. Error: {e}")
        print(f"Error stopping bot: {e}")

# --- Main Bot Function ---
def main() -> None:
    """Run the Telegram bot."""
    if 'YOUR' in BOT_TOKEN or AUTHORIZED_USER_ID == 0:
        print("!!! ERROR: Please set your BOT_TOKEN and AUTHORIZED_USER_ID in the script.")
        return

    print("Starting Telegram Start/Stop Switch for v2.2...")
    
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))

    application.run_polling()

if __name__ == "__main__":
    if os.path.exists(TERMINATION_FLAG):
        os.remove(TERMINATION_FLAG)
    main()
