
import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime
import threading
import pytz
import os
import sys

# --- Import Your Utility Modules ---
import config_v2_2 as config
import market_structure_engine_v2_2 as market_structure_engine
import mt5_trade_functions
import telegram_message_bot
import AllFunctions

# --- MT5 Path ---
MT5_PATH = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"

# --- Configuration for Termination ---
TERMINATION_FLAG_FILE = 'stop_flag_v2_2.txt'

# --- Global Variables ---
stop_event = threading.Event()

def run_bot(chat_id_for_alerts):
    """The main function that contains the live trading loop for V2.2."""
    print(f"--- Initializing MSS + Session Filter (V2.2) Live Trading Bot for {config.SYMBOL} ---")
    if not mt5.initialize(path=MT5_PATH):
        print(f"MT5 initialization from path {MT5_PATH} failed. Error: {mt5.last_error()}")
        telegram_message_bot.send_telegram_message(f"🚨 CRITICAL: MT5 initialization failed.", config.TELEGRAM_BOT_TOKEN, chat_id_for_alerts)
        return
        
    if not mt5.login(config.ACCOUNT, password=config.PASSWORD, server=config.SERVER):
        print(f"MT5 login failed. Error: {mt5.last_error()}")
        telegram_message_bot.send_telegram_message(f"🚨 CRITICAL: MT5 login failed.", config.TELEGRAM_BOT_TOKEN, chat_id_for_alerts)
        mt5.shutdown()
        return

    print(f"Successfully logged into account {config.ACCOUNT} on {config.SERVER}")
    telegram_message_bot.send_telegram_message(f"✅ MSS + Session Filter Bot (V2.2) STARTED for {config.SYMBOL}.", config.TELEGRAM_BOT_TOKEN, chat_id_for_alerts)

    last_known_position_ticket = 0

    while not stop_event.is_set():
        try:
            display_time = datetime.now(config.TIMEZONE).strftime('%H:%M:%S')

            current_position = mt5_trade_functions.get_open_position(config.SYMBOL, config.MAGIC_NUMBER)
            if last_known_position_ticket != 0 and current_position is None:
                trade_details = mt5_trade_functions.get_trade_exit_details(last_known_position_ticket)
                if trade_details:
                    msg = (f"🏁 TRADE CLOSED: {config.SYMBOL}\n"
                           f"Ticket: {last_known_position_ticket}\n"
                           f"Exit Price: {trade_details['price']}\n"
                           f"Result: ${trade_details['profit']:.2f}")
                    telegram_message_bot.send_telegram_message(msg, config.TELEGRAM_BOT_TOKEN, chat_id_for_alerts)
                last_known_position_ticket = 0

            if current_position:
                last_known_position_ticket = current_position.ticket
                AllFunctions.print_and_erase(f"[{display_time}] Position {last_known_position_ticket} is open. Monitoring...")
                time.sleep(5)
                continue

            num_bars = config.SLOW_EMA + 100
            rates_df = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_M1, 0, num_bars)
            if rates_df is None or len(rates_df) < num_bars:
                time.sleep(5)
                continue
            rates_df = pd.DataFrame(rates_df)
            rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s').dt.tz_localize('UTC')

            rates_df = market_structure_engine.add_indicators(rates_df, config.FAST_EMA, config.SLOW_EMA)
            rates_df = market_structure_engine.find_swing_points(rates_df, config.SWING_LOOKBACK)
            
            swing_highs = rates_df[rates_df['swing_high'] == 1]
            swing_lows = rates_df[rates_df['swing_low'] == 1]

            current_candle_index = len(rates_df) - 2
            mss_signal = market_structure_engine.get_market_structure_shift(
                rates_df, swing_highs, swing_lows, current_candle_index, 
                config.LONDON_OPEN, config.NY_CLOSE
            )

            if mss_signal:
                trade_type = mss_signal['trade_type']
                entry_price = mss_signal['entry_price']
                stop_loss = mss_signal['stop_loss']
                trigger_level = mss_signal['trigger_level']

                sl_distance = abs(entry_price - stop_loss)
                if sl_distance <= 0.0001:
                    time.sleep(max(1, 60 - datetime.now().second))
                    continue

                take_profit = entry_price + (sl_distance * config.TAKE_PROFIT_RATIO) if trade_type == 'buy' else entry_price - (sl_distance * config.TAKE_PROFIT_RATIO)
                
                account_info = mt5.account_info()
                current_balance = account_info.balance if account_info else 0

                lot_size = mt5_trade_functions.calculate_lot_size(config.SYMBOL, stop_loss, config.RISK_PERCENT, current_balance)

                if lot_size is None or lot_size <= 0:
                    telegram_message_bot.send_telegram_message(f"❌ Lot size calculation failed.", config.TELEGRAM_BOT_TOKEN, chat_id_for_alerts)
                    time.sleep(max(1, 60 - datetime.now().second))
                    continue

                trade_result = mt5_trade_functions.market_order(symbol=config.SYMBOL, volume=lot_size, order_type=trade_type.upper(), stoploss_price=stop_loss, takeprofit_price=take_profit, magic=config.MAGIC_NUMBER, strategy_name="MSS_Bot_V2.2")

                if trade_result and trade_result.retcode == mt5.TRADE_RETCODE_DONE:
                    msg = (f"🚀 LIVE TRADE EXECUTED: {trade_type.upper()} {config.SYMBOL}\n"
                           f"Trigger: {trigger_level}\n"
                           f"Lot Size: {lot_size} (Risk: {config.RISK_PERCENT}%)\n"
                           f"Entry Price: {trade_result.price}\n"
                           f"TP: {take_profit:.5f}\n"
                           f"SL: {stop_loss:.5f}\n"
                           f"Ticket: {trade_result.order}")
                    telegram_message_bot.send_telegram_message(msg, config.TELEGRAM_BOT_TOKEN, chat_id_for_alerts)
                else:
                    error_message = mt5.last_error() or "Unknown error"
                    telegram_message_bot.send_telegram_message(f"❌ Trade execution failed. Error: {error_message}. Result: {trade_result}", config.TELEGRAM_BOT_TOKEN, chat_id_for_alerts)
                
                time.sleep(300)

            else:
                AllFunctions.print_and_erase(f"[{display_time}] Scanning {config.SYMBOL} for MSS setup (in session)...")
                time.sleep(max(1, 60 - datetime.now().second))

        except Exception as e:
            telegram_message_bot.send_telegram_message(f"🚨 CRITICAL ERROR in main loop: {e}", config.TELEGRAM_BOT_TOKEN, chat_id_for_alerts)
            time.sleep(10)

def check_for_stop_signal():
    while not stop_event.is_set():
        if os.path.exists(TERMINATION_FLAG_FILE):
            print(f"Stop signal file found. Initiating shutdown...")
            stop_event.set()
            try:
                os.remove(TERMINATION_FLAG_FILE)
            except OSError as e:
                print(f"Error removing flag file: {e}")
        time.sleep(5)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python live_trader_v2_2.py <authorized_user_id>")
        sys.exit(1)

    try:
        chat_id = int(sys.argv[1])
    except ValueError:
        print("Error: The authorized_user_id must be an integer.")
        sys.exit(1)

    signal_thread = threading.Thread(target=check_for_stop_signal)
    signal_thread.daemon = True
    signal_thread.start()

    run_bot(chat_id)

    print("Shutdown sequence initiated.")
    if mt5.terminal_info():
        open_pos = mt5_trade_functions.get_open_position(config.SYMBOL, config.MAGIC_NUMBER)
        if open_pos:
            mt5_trade_functions.close_position(open_pos, magic=config.MAGIC_NUMBER)
            telegram_message_bot.send_telegram_message(f"⚠️ Bot shutting down. Open position closed.", config.TELEGRAM_BOT_TOKEN, chat_id)
        mt5.shutdown()
    print("Program terminated.")
    telegram_message_bot.send_telegram_message(f"🛑 MSS + Session Filter Bot (V2.2) STOPPED.", config.TELEGRAM_BOT_TOKEN, chat_id)
