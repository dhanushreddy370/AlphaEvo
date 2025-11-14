
"""
This script runs an advanced backtest of a trading strategy based on market structure,
with a filter to only trade during specific session hours.

Strategy V2.2: Market Structure Shift with Session Filter
- This strategy is identical to V2.1 but limits all trading activity to the
  London and New York session hours (08:00 to 22:00 UTC).
"""
import pandas as pd
import numpy as np
from trade_logger import TradeLogger
import os
from data_handler import load_data
from reporting import generate_report
from tqdm import tqdm
import datetime

# --- Account Management Class ---
class Account:
    def __init__(self, initial_balance=10000):
        self.balance = initial_balance
        self.initial_balance = initial_balance

    def get_position_size(self, risk_percent, entry_price, sl_price):
        sl_pips = abs(entry_price - sl_price)
        if sl_pips == 0: return 0
        risk_amount = self.balance * (risk_percent / 100)
        return risk_amount / sl_pips

    def update_balance(self, pnl):
        self.balance += pnl

# --- Strategy Helper Functions ---
def add_indicators(df, fast_ema=50, slow_ema=200):
    df['ema_fast'] = df['close'].ewm(span=fast_ema, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow_ema, adjust=False).mean()
    return df

def find_swing_points(df, lookback=5):
    df['swing_high'] = df['high'].rolling(window=2*lookback+1, center=True).apply(lambda x: x.iloc[lookback] == x.max(), raw=False)
    df['swing_low'] = df['low'].rolling(window=2*lookback+1, center=True).apply(lambda x: x.iloc[lookback] == x.min(), raw=False)
    return df

# --- Main Backtest Function V2.2 ---
def run_backtest(df, logger):
    print("Starting backtest with v2.2 Market Structure + Session Filter strategy...")
    account = Account(initial_balance=10000)
    
    trade_is_open = False
    
    swing_highs = df[df['swing_high'] == 1]
    swing_lows = df[df['swing_low'] == 1]

    # Define trading session hours in UTC
    london_open = datetime.time(8, 0)
    ny_close = datetime.time(22, 0)

    i = 200
    with tqdm(total=len(df) - i, desc="Backtesting") as pbar:
        while i < len(df):
            if trade_is_open:
                i += 1
                pbar.update(1)
                continue

            current_candle = df.iloc[i]
            current_time = current_candle['timestamp'].time()

            # --- SESSION FILTER ---
            if not (london_open <= current_time <= ny_close):
                i += 1
                pbar.update(1)
                continue

            trend = 'Bullish' if current_candle['ema_fast'] > current_candle['ema_slow'] else 'Bearish'
            
            trade_triggered = False
            trade_type, entry_price, stop_loss, take_profit = None, 0, 0, 0
            setup_type, trigger_level = None, None

            if trend == 'Bullish':
                relevant_swing_highs = swing_highs[swing_highs.index < i]
                potential_lower_highs = relevant_swing_highs[relevant_swing_highs['ema_fast'] < relevant_swing_highs['ema_slow']]
                if not potential_lower_highs.empty:
                    last_lower_high = potential_lower_highs.iloc[-1]
                    if current_candle['close'] > last_lower_high['high']:
                        trade_type = 'buy'
                        setup_type = 'MSS - Bullish'
                        trigger_level = f"Break of LH at {last_lower_high['high']:.5f}"
                        entry_price = current_candle['close']
                        recent_lows = swing_lows[swing_lows.index < i]
                        if not recent_lows.empty:
                            stop_loss = recent_lows.iloc[-1]['low']
                            trade_triggered = True

            elif trend == 'Bearish':
                relevant_swing_lows = swing_lows[swing_lows.index < i]
                potential_higher_lows = relevant_swing_lows[relevant_swing_lows['ema_fast'] > relevant_swing_lows['ema_slow']]
                if not potential_higher_lows.empty:
                    last_higher_low = potential_higher_lows.iloc[-1]
                    if current_candle['close'] < last_higher_low['low']:
                        trade_type = 'sell'
                        setup_type = 'MSS - Bearish'
                        trigger_level = f"Break of HL at {last_higher_low['low']:.5f}"
                        entry_price = current_candle['close']
                        recent_highs = swing_highs[swing_highs.index < i]
                        if not recent_highs.empty:
                            stop_loss = recent_highs.iloc[-1]['high']
                            trade_triggered = True

            if trade_triggered:
                sl_distance = abs(entry_price - stop_loss)
                if sl_distance <= 0.0001:
                    i += 1
                    pbar.update(1)
                    continue
                
                take_profit = entry_price + (sl_distance * 2) if trade_type == 'buy' else entry_price - (sl_distance * 2)
                position_size = account.get_position_size(risk_percent=1, entry_price=entry_price, sl_price=stop_loss)

                if position_size > 0:
                    trade_is_open = True
                    exit_price, exit_time, result, pnl_currency = 0, None, None, 0
                    
                    for j in range(i + 1, len(df)):
                        future_candle = df.iloc[j]
                        if trade_type == 'buy':
                            if future_candle['low'] <= stop_loss: result, exit_price = 'loss', stop_loss
                            elif future_candle['high'] >= take_profit: result, exit_price = 'win', take_profit
                        else:
                            if future_candle['high'] >= stop_loss: result, exit_price = 'loss', stop_loss
                            elif future_candle['low'] <= take_profit: result, exit_price = 'win', take_profit

                        if result:
                            exit_time = future_candle['timestamp']
                            pnl_currency = (exit_price - entry_price) * position_size if trade_type == 'buy' else (entry_price - exit_price) * position_size
                            account.update_balance(pnl_currency)
                            logger.log_trade(current_candle['timestamp'], exit_time, trade_type, entry_price, exit_price, stop_loss, take_profit, position_size, pnl_currency, account.balance, result, setup_type, trigger_level)
                            pbar.update(j - i)
                            i = j
                            trade_is_open = False
                            break
                    
                    if not result:
                        pbar.update(len(df) - i)
                        i = len(df)
                else:
                    i += 1
                    pbar.update(1)
            else:
                i += 1
                pbar.update(1)

    print("Backtest finished.")

if __name__ == "__main__":
    BACKTEST_VERSION_NAME = 'v2.2_session_filter'
    DATA_FILE = 'manipCont2/EURUSD2025_10months.csv' 
    OUTPUT_DIR = os.path.join('results', BACKTEST_VERSION_NAME)
    LOG_FILE = os.path.join(OUTPUT_DIR, 'trade_log.csv')
    REPORT_FILE = os.path.join(OUTPUT_DIR, 'performance_report.txt')

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Starting Trading Simulator for {BACKTEST_VERSION_NAME}...")
    
    data = load_data(DATA_FILE)
    if data is not None and not data.empty:
        print("Adding indicators and identifying swing points...")
        data = add_indicators(data)
        data = find_swing_points(data)
        
        logger = TradeLogger(log_file=LOG_FILE)
        run_backtest(data, logger)
        logger.save_log()
        generate_report(LOG_FILE, REPORT_FILE, data)
    else:
        print("Could not run simulation due to data loading issues.")
        
    print(f"Simulation finished. Results are in the '{OUTPUT_DIR}' directory.")
