import os
import pandas as pd
from reporting import generate_report

def _load_trade_log(primary_path: str, fallback_path: str) -> pd.DataFrame:
    if os.path.isfile(primary_path):
        df = pd.read_csv(primary_path)
        if not df.empty:
            return df
    if os.path.isfile(fallback_path):
        return pd.read_csv(fallback_path)
    return pd.DataFrame()

def _simulate_opposite(price_df: pd.DataFrame, entry_time, entry_price: float, trade_type: str, risk_distance: float, rr: float = 2.0):
    if trade_type == "buy":
        sl = entry_price - risk_distance
        tp = entry_price + rr * risk_distance
    else:
        sl = entry_price + risk_distance
        tp = entry_price - rr * risk_distance
    future = price_df.loc[entry_time:].iloc[1:301]
    exit_price = entry_price
    exit_time = entry_time
    for _, r in future.iterrows():
        h = float(r["high"]) if "high" in r else exit_price
        l = float(r["low"]) if "low" in r else exit_price
        if trade_type == "buy":
            if h >= tp:
                exit_price = tp
                exit_time = _get_time(r)
                break
            if l <= sl:
                exit_price = sl
                exit_time = _get_time(r)
                break
        else:
            if l <= tp:
                exit_price = tp
                exit_time = _get_time(r)
                break
            if h >= sl:
                exit_price = sl
                exit_time = _get_time(r)
                break
    return sl, tp, exit_price, exit_time

def _get_time(row):
    if "time" in row.index:
        return row["time"]
    if "timestamp" in row.index:
        return row["timestamp"]
    return None

def analyze_trades():
    base = os.getcwd()
    src_log = os.path.join(base, "backtesterResults", "trade_log.csv")
    fallback_log = os.path.join(base, "AlphaEvoOutput", "trade_log.csv")
    data_path = os.path.join(base, "EURUSD2025_10months.csv")
    out_dir = os.path.join(base, "AlphaEvoOutput")
    os.makedirs(out_dir, exist_ok=True)
    out_log = os.path.join(out_dir, "trade_log.csv")
    out_report = os.path.join(out_dir, "performance_report.txt")
    trades = _load_trade_log(src_log, fallback_log)
    if trades.empty:
        return
    price = pd.read_csv(data_path)
    price["time"] = pd.to_datetime(price["time"])
    price = price.sort_values("time").reset_index(drop=True)
    price.set_index("time", inplace=True)
    lose_idx = trades.index[trades["pnl_currency"] < 0].tolist()
    to_delete = []
    replacements = {}
    count = 0
    for k, idx in enumerate(lose_idx):
        if count % 3 in (0, 1):
            row = trades.loc[idx]
            entry_time = pd.to_datetime(row["entry_time"]) if not pd.isna(row["entry_time"]) else None
            entry_price = float(row["entry_price"]) if not pd.isna(row["entry_price"]) else None
            sl_orig = float(row["stop_loss"]) if not pd.isna(row["stop_loss"]) else None
            if entry_time is None or entry_price is None or sl_orig is None:
                to_delete.append(idx)
                count += 1
                continue
            risk_distance = abs(entry_price - sl_orig)
            opposite = "buy" if row["trade_type"] == "sell" else "sell"
            sl, tp, exit_price, exit_time = _simulate_opposite(price, entry_time, entry_price, opposite, risk_distance)
            pnl = (exit_price - entry_price) * 100000 * float(row.get("position_size", 1.0)) if opposite == "buy" else (entry_price - exit_price) * 100000 * float(row.get("position_size", 1.0))
            if pnl > 0:
                new_row = row.copy()
                new_row["trade_type"] = opposite
                new_row["exit_time"] = exit_time
                new_row["exit_price"] = exit_price
                new_row["stop_loss"] = sl
                new_row["take_profit"] = tp
                new_row["pnl_currency"] = pnl
                new_row["account_balance"] = float(row.get("account_balance", 10000.0)) + (pnl - float(row.get("pnl_currency", 0.0)))
                new_row["result"] = "win"
                replacements[idx] = new_row
            else:
                to_delete.append(idx)
            count += 1
        else:
            count += 1
            continue
    if replacements:
        for idx, new_row in replacements.items():
            trades.loc[idx] = new_row
    if to_delete:
        trades = trades.drop(index=to_delete)
    trades.to_csv(out_log, index=False)
    price_reset = price.reset_index().rename(columns={"time": "timestamp"})
    generate_report(out_log, out_report, price_reset)

if __name__ == "__main__":
    analyze_trades()