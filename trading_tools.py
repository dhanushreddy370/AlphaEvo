import pandas as pd
import os
import datetime
import numpy as np
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional

# Define file paths
BACKTESTER_STRATEGY_FILE = 'backtester.py'
TRADE_LOG_FILE = 'backtesterResults/trade_log.csv'

class ReadBacktesterStrategyTool(BaseTool):
    name: str = "Read Backtester Strategy"
    description: str = "Reads the content of the backtester.py file to understand the trading strategy. Returns the full content of the file as a string."

    def _run(self, **kwargs) -> str:
        try:
            with open(BACKTESTER_STRATEGY_FILE, 'r') as f:
                content = f.read()
            return content
        except FileNotFoundError:
            return f"Error: {BACKTESTER_STRATEGY_FILE} not found."
        except Exception as e:
            return f"Error reading {BACKTESTER_STRATEGY_FILE}: {e}"

class ReadBacktesterTradeLogTool(BaseTool):
    name: str = "Read Backtester Trade Log"
    description: str = "Reads the trade log from backtesterResults/trade_log.csv into a pandas DataFrame. Returns the DataFrame containing the trade history."

    def _run(self, **kwargs) -> pd.DataFrame:
        if not os.path.exists(TRADE_LOG_FILE):
            return f"Error: {TRADE_LOG_FILE} not found."
        try:
            df = pd.read_csv(TRADE_LOG_FILE)
            # Ensure 'entry_time' and 'exit_time' are datetime objects for easier analysis
            df['entry_time'] = pd.to_datetime(df['entry_time'])
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            return df
        except Exception as e:
            return f"Error reading {TRADE_LOG_FILE}: {e}"

# --- Schemas for Tools ---
class EMACalcSchema(BaseModel):
    historical_data: pd.DataFrame
    fast_ema: int = 50
    slow_ema: int = 200
    class Config:
        arbitrary_types_allowed = True

class SwingPointSchema(BaseModel):
    historical_data: pd.DataFrame
    lookback: int = 5
    class Config:
        arbitrary_types_allowed = True

class MSSSetupSchema(BaseModel):
    historical_data: pd.DataFrame
    current_index: int
    class Config:
        arbitrary_types_allowed = True

class EvaluateHistorySchema(BaseModel):
    proposed_trade_details: dict
    historical_trade_log: pd.DataFrame
    class Config:
        arbitrary_types_allowed = True

# --- Tools ---
class CalculateEMAsTool(BaseTool):
    name: str = "Calculate EMAs"
    description: str = "Calculates Exponential Moving Averages (50 and 200) for the given historical data. Returns the DataFrame with 'ema_fast' and 'ema_slow' columns."
    args_schema: Type[BaseModel] = EMACalcSchema

    def _run(self, historical_data: pd.DataFrame, fast_ema: int = 50, slow_ema: int = 200) -> pd.DataFrame:
        df = historical_data.copy()
        df['ema_fast'] = df['close'].ewm(span=fast_ema, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow_ema, adjust=False).mean()
        return df

class SessionCheckSchema(BaseModel):
    timestamp: str
    class Config:
        arbitrary_types_allowed = True

class CheckSessionHoursTool(BaseTool):
    name: str = "Check Session Hours"
    description: str = "Determines if the given timestamp (string or pandas Timestamp object) falls within the defined trading session hours (08:00 to 22:00 UTC). Returns True if within session, False otherwise."
    args_schema: Type[BaseModel] = SessionCheckSchema

    def _run(self, timestamp: str) -> bool:
        # Convert string timestamp to pandas Timestamp if it's not already
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        london_open = datetime.time(8, 0)
        ny_close = datetime.time(22, 0)
        current_time = timestamp.time()
        return london_open <= current_time <= ny_close

class IdentifySwingPointsTool(BaseTool):
    name: str = "Identify Swing Points"
    description: str = "Identifies swing highs and lows in the given historical data based on a lookback period. Returns the DataFrame with 'swing_high' and 'swing_low' boolean columns."
    args_schema: Type[BaseModel] = SwingPointSchema

    def _run(self, historical_data: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
        df = historical_data.copy()
        if 'high' not in df.columns or 'low' not in df.columns:
            return pd.DataFrame({"error": ["DataFrame must contain 'high' and 'low' columns for swing point identification."]})

        df['swing_high'] = df['high'].rolling(window=2*lookback+1, center=True).apply(lambda x: x.iloc[lookback] == x.max(), raw=False)
        df['swing_low'] = df['low'].rolling(window=2*lookback+1, center=True).apply(lambda x: x.iloc[lookback] == x.min(), raw=False)
        return df

class IdentifyMSSSetupTool(BaseTool):
    name: str = "Identify MSS Setup"
    description: str = (
        "Identifies a Market Structure Shift (MSS) trade setup (buy or sell) based on the V2.2 strategy. "
        "Requires historical data (pandas DataFrame) with EMAs and swing points, and the index of the current candle. "
        "Returns a dictionary with setup details or None if no setup."
    )
    args_schema: Type[BaseModel] = MSSSetupSchema

    def _run(self, historical_data: pd.DataFrame, current_index: int) -> Optional[dict]:
        # ... (implementation remains the same)
        current_candle = historical_data.iloc[current_index]
        
        required_cols = ['ema_fast', 'ema_slow', 'swing_high', 'swing_low', 'close', 'high', 'low']
        if not all(col in historical_data.columns for col in required_cols):
            return None

        trend = 'Bullish' if current_candle['ema_fast'] > current_candle['ema_slow'] else 'Bearish'
        
        if trend == 'Bullish':
            relevant_swing_highs = historical_data[historical_data['swing_high'] == True].loc[:current_candle.name]
            if not relevant_swing_highs.empty:
                potential_lower_highs = relevant_swing_highs[relevant_swing_highs['ema_fast'] < relevant_swing_highs['ema_slow']]
                if not potential_lower_highs.empty:
                    last_lower_high = potential_lower_highs.iloc[-1]
                    if current_candle['close'] > last_lower_high['high']:
                        recent_lows = historical_data[historical_data['swing_low'] == True].loc[:current_candle.name]
                        if not recent_lows.empty:
                            stop_loss = recent_lows.iloc[-1]['low']
                            if abs(current_candle['close'] - stop_loss) > 0.0001:
                                return {
                                    'trade_type': 'buy', 'entry_price': current_candle['close'], 'stop_loss': stop_loss,
                                    'setup_type': 'MSS - Bullish', 'trigger_level': f"Break of LH at {last_lower_high['high']:.5f}",
                                    'timestamp': current_candle.name
                                }
        elif trend == 'Bearish':
            relevant_swing_lows = historical_data[historical_data['swing_low'] == True].loc[:current_candle.name]
            if not relevant_swing_lows.empty:
                potential_higher_lows = relevant_swing_lows[relevant_swing_lows['ema_fast'] > relevant_swing_lows['ema_slow']]
                if not potential_higher_lows.empty:
                    last_higher_low = potential_higher_lows.iloc[-1]
                    if current_candle['close'] < last_higher_low['low']:
                        recent_highs = historical_data[historical_data['swing_high'] == True].loc[:current_candle.name]
                        if not recent_highs.empty:
                            stop_loss = recent_highs.iloc[-1]['high']
                            if abs(current_candle['close'] - stop_loss) > 0.0001:
                                return {
                                    'trade_type': 'sell', 'entry_price': current_candle['close'], 'stop_loss': stop_loss,
                                    'setup_type': 'MSS - Bearish', 'trigger_level': f"Break of HL at {last_higher_low['low']:.5f}",
                                    'timestamp': current_candle.name
                                }
        return None

class CalculateTradeParametersTool(BaseTool):
    name: str = "Calculate Trade Parameters"
    description: str = "Calculates the take-profit level based on entry price and stop-loss, assuming a 1:2 Risk/Reward ratio."
    
    def _run(self, setup_details: dict) -> dict:
        # ... (implementation remains the same)
        trade_type = setup_details.get('trade_type')
        entry_price = setup_details.get('entry_price')
        stop_loss = setup_details.get('stop_loss')

        if not all([trade_type, entry_price, stop_loss]):
            return {"error": "Missing required trade details."}

        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0.0001:
            return {"error": "Stop loss distance is too small."}

        take_profit = entry_price + (sl_distance * 2) if trade_type == 'buy' else entry_price - (sl_distance * 2)
        setup_details['take_profit'] = take_profit
        return setup_details

class CalculatePositionSizeTool(BaseTool):
    name: str = "Calculate Position Size"
    description: str = "Calculates the appropriate position size based on account balance, risk percentage, entry price, and stop-loss."

    def _run(self, current_balance: float, risk_percent: float, entry_price: float, sl_price: float) -> float:
        # ... (implementation remains the same)
        sl_pips = abs(entry_price - sl_price)
        if sl_pips == 0: return 0.0
        risk_amount = current_balance * (risk_percent / 100)
        return risk_amount / sl_pips

class CheckRiskRewardRatioTool(BaseTool):
    name: str = "Check Risk Reward Ratio"
    description: str = "Verifies if the proposed trade meets a minimum risk-reward ratio (e.g., 1:2)."

    def _run(self, entry_price: float, sl_price: float, tp_price: float, min_rr: float = 2.0) -> bool:
        # ... (implementation remains the same)
        risk = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
        if risk == 0: return False
        return (reward / risk) >= min_rr

class EvaluateTradeAgainstHistoryTool(BaseTool):
    name: str = "Evaluate Trade Against History"
    description: str = "Compares a proposed trade setup against historical trade outcomes from the trade log to identify similar losing patterns."
    args_schema: Type[BaseModel] = EvaluateHistorySchema

    def _run(self, proposed_trade_details: dict, historical_trade_log: pd.DataFrame) -> str:
        # ... (implementation remains the same)
        proposed_trade_type = proposed_trade_details.get('trade_type')
        proposed_timestamp = proposed_trade_details.get('timestamp')

        if proposed_timestamp and proposed_trade_type:
            relevant_history = historical_trade_log[historical_history['trade_type'] == proposed_trade_type]
            if not relevant_history.empty:
                if not pd.api.types.is_datetime64_any_dtype(relevant_history['entry_time']):
                    relevant_history['entry_time'] = pd.to_datetime(relevant_history['entry_time'])

                proposed_hour = proposed_timestamp.hour
                losing_trades_same_hour = relevant_history[
                    (relevant_history['result'] == 'loss') &
                    (relevant_history['entry_time'].dt.hour == proposed_hour)
                ]

                if not losing_trades_same_hour.empty:
                    num_losing = len(losing_trades_same_hour)
                    total_relevant = len(relevant_history)
                    loss_percentage = (num_losing / total_relevant) * 100 if total_relevant > 0 else 0
                    if loss_percentage > 50:
                        return (f"Warning: {proposed_trade_type.capitalize()} trades around {proposed_hour}:00 UTC "
                                f"have historically resulted in losses {loss_percentage:.2f}% of the time. Consider caution.")
        return "No significant historical issues found."
