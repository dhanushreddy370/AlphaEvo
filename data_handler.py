import pandas as pd
import zipfile
import io

def load_data(file_path):
    """
    Loads historical data from a CSV file or a ZIP archive containing a CSV file.
    Looks for a 'time' column, converts it to datetime, and renames it to 'timestamp'.
    """
    try:
        if file_path.endswith('.zip'):
            with zipfile.ZipFile(file_path, 'r') as z:
                # Find the first CSV file in the zip archive
                csv_file_name = next((f for f in z.namelist() if f.endswith('.csv')), None)
                if csv_file_name is None:
                    print("Error: No CSV file found in the ZIP archive.")
                    return None
                with z.open(csv_file_name) as f:
                    # Use io.TextIOWrapper to decode the file in memory
                    df = pd.read_csv(io.TextIOWrapper(f, 'utf-8'))
                    print(f"Data loaded successfully from {csv_file_name} within {file_path}")
        elif file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            print(f"Data loaded successfully from {file_path}")
        else:
            print(f"Error: Unsupported file format for {file_path}. Please use .csv or .zip.")
            return None
        
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df.rename(columns={'time': 'timestamp'}, inplace=True)
            print("Found and processed 'time' column as timestamp.")
        elif 'timestamp' not in df.columns:
            print("Error: Could not find a 'time' or 'timestamp' column in the data.")
            return None

        return df
    except FileNotFoundError:
        print(f"Error: Data file not found at {file_path}")
        return None
    except Exception as e:
        print(f"An error occurred while loading data: {e}")
        return None

def resample_to_htf(df):
    """Resamples the base data to multiple higher timeframes."""
    if 'timestamp' not in df.columns:
        print("Error: DataFrame must have a 'timestamp' column for resampling.")
        return {}
    
    if not isinstance(df.index, pd.DatetimeIndex):
        df.set_index('timestamp', inplace=True)
    
    timeframes = {'15m': '15min', '1h': 'h', '4h': '4h', '1d': 'D', '1w': 'W'}
    htf_data = {}

    for key, rule in timeframes.items():
        resampled_df = df.resample(rule).agg({
            'open': 'first', 
            'high': 'max', 
            'low': 'min', 
            'close': 'last'
        }).dropna()
        
        if key == '4h':
            high_low = resampled_df['high'] - resampled_df['low']
            high_prev_close = abs(resampled_df['high'] - resampled_df['close'].shift(1))
            low_prev_close = abs(resampled_df['low'] - resampled_df['close'].shift(1))
            true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
            resampled_df['atr'] = true_range.ewm(alpha=1/14, adjust=False).mean()

        htf_data[key] = resampled_df.reset_index()

    df.reset_index(inplace=True)
    
    return htf_data

def add_atr(df, period=14):
    """
    Calculates and adds the Average True Range (ATR) to the DataFrame.
    """
    if not all(col in df.columns for col in ['high', 'low', 'close']):
        print("Error: DataFrame must have 'high', 'low', and 'close' columns for ATR calculation.")
        return df

    df['high_low'] = df['high'] - df['low']
    df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
    
    df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
    
    df['atr'] = df['true_range'].ewm(alpha=1/period, adjust=False).mean()
    
    df.drop(['high_low', 'high_prev_close', 'low_prev_close', 'true_range'], axis=1, inplace=True)
    
    print(f"ATR with period {period} added to the DataFrame.")
    return df

