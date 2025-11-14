import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm

# --- Configuration ---
DATA_FILE_PATH = Path("C:/Users/dhanu/OneDrive/Desktop/Trading_algorithm/RLmodel/EURUSD1m25.csv")
OUTPUT_DIR = Path("./data_prepared")

# Chronological split years
TRAIN_END_YEAR = 2014  # Years 1-15 (2000-2014)
FINETUNE_END_YEAR = 2019 # Years 16-20 (2015-2019)
# Test set is from 2020 onwards

# --- 1. Data Loading and Cleaning (CPU) ---
def load_and_clean_data(file_path):
    """
    Loads the M1 data from CSV, sets a proper datetime index, and performs cleaning.
    """
    print("Loading and cleaning data...")
    # Specify dtypes for efficient loading
    dtype_map = {
        'open': 'float32',
        'high': 'float32',
        'low': 'float32',
        'close': 'float32',
        'tick_volume': 'int64',
        'spread': 'int32',
        'real_volume': 'int64'
    }
    # pandas' read_csv is used here
    df = pd.read_csv(file_path, dtype=dtype_map)

    # Convert 'time' column to datetime objects and set as index
    df['time'] = pd.to_datetime(df['time'])
    df = df.set_index('time')

    # Drop columns not needed for the strategy or features
    df = df.drop(columns=['tick_volume', 'spread', 'real_volume'])

    # Ensure data is sorted by time
    df = df.sort_index()
    
    print(f"Data loaded. Shape: {df.shape}. Time range: {df.index.min()} to {df.index.max()}")
    return df

# --- 2. Data Resampling (CPU) ---
def resample_data(m1_df):
    """
    Resamples M1 data into H1, H4, D1, and W1 timeframes.
    """
    print("Resampling data to higher timeframes...")
    resampling_rules = {
        'H1': '1H',
        'H4': '4H',
        'D1': '1D',
        'W1': '1W'
    }
    
    all_data = {'M1': m1_df}
    
    for tf, rule in resampling_rules.items():
        resampled_df = m1_df.resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        all_data[tf] = resampled_df
        print(f"  - {tf} resampled. Shape: {resampled_df.shape}")
        
    return all_data

import datetime

# --- Strategy Helper Functions ---
def add_indicators(df, fast_ema=50, slow_ema=200):
    df['ema_fast'] = df['close'].ewm(span=fast_ema, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow_ema, adjust=False).mean()
    return df

def find_swing_points(df, lookback=5):
    df['swing_high'] = df['high'].rolling(window=2*lookback+1, center=True).apply(lambda x: x.iloc[lookback] == x.max(), raw=False)
    df['swing_low'] = df['low'].rolling(window=2*lookback+1, center=True).apply(lambda x: x.iloc[lookback] == x.min(), raw=False)
    return df

# --- 3. Feature Engineering - Agent's View (CPU) ---
def add_agent_features(df, atr_period=14, rsi_period=14, sto_period=14):
    """
    Adds new features that the agent will use to find its edge.
    Implemented with pure pandas for CPU execution.
    """
    print("Engineering agent-specific features (ATR, RSI, Stochastic)...")
    
    # ATR Calculation
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.DataFrame({'hl': high_low, 'hc': high_close, 'lc': low_close}).max(axis=1)
    df['atr'] = tr.rolling(window=atr_period).mean()

    # RSI Calculation
    delta = df['close'].diff()
    gain = delta.copy()
    loss = delta.copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0
    loss = loss.abs()
    
    avg_gain = gain.rolling(window=rsi_period).mean()
    avg_loss = loss.rolling(window=rsi_period).mean()
    
    rs = avg_gain / avg_loss
    df['rsi'] = 100.0 - (100.0 / (1.0 + rs))

    # Stochastic Oscillator Calculation
    low_min = df['low'].rolling(window=sto_period).min()
    high_max = df['high'].rolling(window=sto_period).max()
    df['stoch_k'] = 100 * ((df['close'] - low_min) / (high_max - low_min))
    
    return df

# --- 4. Expert Policy Generation ---
def generate_expert_actions(all_data):
    """
    Generates the expert's action based on the v2.2 Market Structure Shift strategy.
    """
    print("Generating expert actions...")
    
    df = all_data['M1'].copy()
    
    # 1. Add indicators needed for the strategy
    df = add_indicators(df)
    df = find_swing_points(df)
    
    # Initialize expert_action column with 0 (Hold)
    expert_actions = pd.Series(np.zeros(len(df), dtype=np.int8), index=df.index)
    
    swing_highs = df[df['swing_high'] == 1]
    swing_lows = df[df['swing_low'] == 1]

    # Define trading session hours in UTC
    london_open = datetime.time(8, 0)
    ny_close = datetime.time(22, 0)

    # Iterate through each candle to determine the expert action
    for i in tqdm(range(200, len(df)), desc="Generating Expert Actions"):
        current_candle = df.iloc[i]
        current_time = current_candle.name.time()

        # --- SESSION FILTER ---
        if not (london_open <= current_time <= ny_close):
            continue

        trend = 'Bullish' if current_candle['ema_fast'] > current_candle['ema_slow'] else 'Bearish'
        
        trade_triggered = False
        trade_type = 0 # 0 = Hold, 1 = Buy, 2 = Sell

        if trend == 'Bullish':
            relevant_swing_highs = swing_highs[swing_highs.index < current_candle.name]
            potential_lower_highs = relevant_swing_highs[relevant_swing_highs['ema_fast'] < relevant_swing_highs['ema_slow']]
            if not potential_lower_highs.empty:
                last_lower_high = potential_lower_highs.iloc[-1]
                if current_candle['close'] > last_lower_high['high']:
                    trade_type = 1 # Buy
                    
        elif trend == 'Bearish':
            relevant_swing_lows = swing_lows[swing_lows.index < current_candle.name]
            potential_higher_lows = relevant_swing_lows[relevant_swing_lows['ema_fast'] > relevant_swing_lows['ema_slow']]
            if not potential_higher_lows.empty:
                last_higher_low = potential_higher_lows.iloc[-1]
                if current_candle['close'] < last_higher_low['low']:
                    trade_type = 2 # Sell

        expert_actions.iloc[i] = trade_type
        
    return expert_actions

# --- Main Execution ---
if __name__ == "__main__":
    # Create output directory if it doesn't exist
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 1. Load data
    m1_data = load_and_clean_data(DATA_FILE_PATH)
    
    # 2. Resample for expert's multi-timeframe view
    all_tf_data = resample_data(m1_data)
    
    # 3. Add features for the agent's view
    m1_data_featured = add_agent_features(all_tf_data['M1'])
    
    # 4. Generate the expert's actions (currently a placeholder)
    expert_actions = generate_expert_actions(all_tf_data)
    m1_data_featured['expert_action'] = expert_actions
    
    # 5. Clean up NaNs produced by rolling windows
    m1_data_featured = m1_data_featured.dropna()
    print(f"Final featured data shape after dropping NaNs: {m1_data_featured.shape}")

    # 6. Chronological Data Splitting
    print("Splitting data into chronological sets...")
    
    train_mask = m1_data_featured.index.year <= TRAIN_END_YEAR
    finetune_mask = (m1_data_featured.index.year > TRAIN_END_YEAR) & (m1_data_featured.index.year <= FINETUNE_END_YEAR)
    test_mask = m1_data_featured.index.year > FINETUNE_END_YEAR

    train_set = m1_data_featured[train_mask]
    finetune_set = m1_data_featured[finetune_mask]
    test_set = m1_data_featured[test_mask]

    print(f"  - Training Set (<= {TRAIN_END_YEAR}): {train_set.shape[0]} bars")
    print(f"  - Fine-tuning Set ({TRAIN_END_YEAR+1}-{FINETUNE_END_YEAR}): {finetune_set.shape[0]} bars")
    print(f"  - Test Set (> {FINETUNE_END_YEAR}): {test_set.shape[0]} bars")

    # 7. Save datasets to Parquet format for efficiency
    print("Saving datasets to Parquet format...")
    train_set.to_parquet(OUTPUT_DIR / "train_set.parquet")
    finetune_set.to_parquet(OUTPUT_DIR / "finetune_set.parquet")
    test_set.to_parquet(OUTPUT_DIR / "test_set.parquet")
    
    print(f"Phase 1 data preparation complete. Files saved in '{OUTPUT_DIR}' directory.")
