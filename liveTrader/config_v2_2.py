
import pytz
from datetime import time

# --- MT5 ACCOUNT CREDENTIALS ---
# Replace with your actual account details
ACCOUNT = 5042219354
PASSWORD = "JjU_4sYn"
SERVER = "MetaQuotes-Demo"

# --- TRADING PARAMETERS ---
SYMBOL = "EURUSD" 
TIMEFRAME = "M1" 
MAGIC_NUMBER = 222222 

# --- RISK MANAGEMENT ---
RISK_PERCENT = 1.0  # 1% risk per trade
TAKE_PROFIT_RATIO = 2.0 # 2:1 Risk-to-Reward Ratio

# --- STRATEGY PARAMETERS (V2.2) ---
FAST_EMA = 50
SLOW_EMA = 200
SWING_LOOKBACK = 5

# --- SESSION FILTER ---
# Times are in UTC
LONDON_OPEN = time(8, 0)
NY_CLOSE = time(22, 0)

# --- TIMEZONE ---
# This is for display purposes. The session filter uses UTC.
TIMEZONE = pytz.timezone('Asia/Kolkata') 

# --- TELEGRAM ALERTS ---
# !!! ENTER YOUR TELEGRAM DETAILS BELOW !!!
TELEGRAM_BOT_TOKEN = "8409424214:AAGGdnPhgiGkr_b1cTdqp1UAk6FORhJ2CfY"
