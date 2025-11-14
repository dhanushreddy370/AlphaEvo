import pandas as pd
import os

class TradeLogger:
    def __init__(self, log_file='trade_log.csv'):
        self.log_file = log_file
        self.trades = []
        self.columns = [
            'entry_time', 'exit_time', 'trade_type', 'entry_price',
            'exit_price', 'stop_loss', 'take_profit', 'position_size',
            'pnl_currency', 'account_balance', 'result', 'setup_type', 'trigger_level'
        ]

    def log_trade(self, entry_time, exit_time, trade_type, entry_price, exit_price, sl, tp, position_size, pnl_currency, account_balance, result, setup_type, trigger_level):
        """Logs a single completed trade."""
        self.trades.append({
            'entry_time': entry_time,
            'exit_time': exit_time,
            'trade_type': trade_type,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'stop_loss': sl,
            'take_profit': tp,
            'position_size': position_size,
            'pnl_currency': pnl_currency,
            'account_balance': account_balance,
            'result': result,
            'setup_type': setup_type,
            'trigger_level': trigger_level
        })

    def save_log(self):
        """Saves all logged trades to a CSV file."""
        if not self.trades:
            print("No trades to log.")
            return

        log_df = pd.DataFrame(self.trades, columns=self.columns)
        log_df.to_csv(self.log_file, index=False)
        print(f"Trade log saved to {self.log_file}")
