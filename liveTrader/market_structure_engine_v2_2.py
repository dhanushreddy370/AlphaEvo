
import pandas as pd
from datetime import time

def add_indicators(df, fast_ema=50, slow_ema=200):
    """Adds EMAs for trend identification."""
    df['ema_fast'] = df['close'].ewm(span=fast_ema, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow_ema, adjust=False).mean()
    return df

def find_swing_points(df, lookback=5):
    """
    Identifies swing highs and lows in the dataframe.
    """
    df['swing_high'] = df['high'].rolling(window=2*lookback+1, center=True).apply(lambda x: x.iloc[lookback] == x.max(), raw=False)
    df['swing_low'] = df['low'].rolling(window=2*lookback+1, center=True).apply(lambda x: x.iloc[lookback] == x.min(), raw=False)
    return df

def get_market_structure_shift(df, swing_highs, swing_lows, current_index, london_open, ny_close):
    """
    Identifies a Market Structure Shift (MSS) within trading sessions.
    Returns the trade details if an MSS is confirmed.
    """
    current_candle = df.iloc[current_index]
    
    # --- SESSION FILTER ---
    current_time_utc = current_candle['time'].time()
    if not (london_open <= current_time_utc <= ny_close):
        return None # Outside of trading session

    trend = 'Bullish' if current_candle['ema_fast'] > current_candle['ema_slow'] else 'Bearish'

    if trend == 'Bullish':
        relevant_swing_highs = swing_highs[swing_highs.index < current_index]
        potential_lower_highs = relevant_swing_highs[relevant_swing_highs['ema_fast'] < relevant_swing_highs['ema_slow']]

        if not potential_lower_highs.empty:
            last_lower_high = potential_lower_highs.iloc[-1]
            if current_candle['close'] > last_lower_high['high']:
                recent_lows = swing_lows[swing_lows.index < current_index]
                if not recent_lows.empty:
                    stop_loss = recent_lows.iloc[-1]['low']
                    return {
                        'trade_type': 'buy',
                        'entry_price': current_candle['close'],
                        'stop_loss': stop_loss,
                        'trigger_level': f"Break of LH at {last_lower_high['high']:.5f}"
                    }

    elif trend == 'Bearish':
        relevant_swing_lows = swing_lows[swing_lows.index < current_index]
        potential_higher_lows = relevant_swing_lows[relevant_swing_lows['ema_fast'] > relevant_swing_lows['ema_slow']]

        if not potential_higher_lows.empty:
            last_higher_low = potential_higher_lows.iloc[-1]
            if current_candle['close'] < last_higher_low['low']:
                recent_highs = swing_highs[swing_highs.index < current_index]
                if not recent_highs.empty:
                    stop_loss = recent_highs.iloc[-1]['high']
                    return {
                        'trade_type': 'sell',
                        'entry_price': current_candle['close'],
                        'stop_loss': stop_loss,
                        'trigger_level': f"Break of HL at {last_higher_low['low']:.5f}"
                    }
    return None
