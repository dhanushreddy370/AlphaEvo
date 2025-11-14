import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from tqdm import tqdm

"""
This module generates a comprehensive performance and forensics report from a trade log.

It calculates a full suite of quantitative metrics, including:
- Overall P&L, Win Rate, and Profit Factor
- Advanced Ratios (Sharpe, Sortino, Calmar)
- Drawdown analysis
- Win/Loss streak analysis
- Distribution charts for Risk-to-Reward and Stop-Loss size
- Forensic analysis of losing trades to determine cause.
"""

def generate_report(log_file, report_path, price_data_df):
    """
    Generates a comprehensive performance report.
    """
    print(f"\n--- Generating Comprehensive Performance & Forensics Report ---")

    try:
        df = pd.read_csv(log_file)
    except FileNotFoundError:
        print(f"Error: Log file not found at {log_file}")
        return

    if df.empty:
        print("No trades were executed. Cannot generate a report.")
        return

    # --- Setup Output Paths ---
    output_dir = os.path.dirname(report_path)
    base_filename = os.path.splitext(os.path.basename(report_path))[0]
    equity_chart_path = os.path.join(output_dir, f"{base_filename}_equity_curve.png")
    forensics_chart_path = os.path.join(output_dir, f"{base_filename}_forensics_pie.png")
    sl_dist_chart_path = os.path.join(output_dir, f"{base_filename}_sl_distribution.png")

    # --- 1. Data Preparation & Enrichment ---
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    df['win'] = df['pnl_currency'] > 0
    df['day_of_week'] = df['entry_time'].dt.day_name()
    df['holding_period_mins'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 60
    df['sl_pips'] = abs(df['entry_price'] - df['stop_loss']) / 0.0001
    df = df.sort_values('exit_time').reset_index(drop=True)

    # --- 2. Equity Curve & Daily Returns for Advanced Metrics ---
    initial_capital = 10000 # Hardcoded to match backtester
    df['equity'] = initial_capital + df['pnl_currency'].cumsum()
    daily_equity = df.groupby(df['exit_time'].dt.date)['equity'].last()
    start_date = daily_equity.index.min() - pd.Timedelta(days=1) if not daily_equity.empty else pd.to_datetime('today') - pd.Timedelta(days=1)
    daily_equity = pd.concat([pd.Series([initial_capital], index=[start_date]), daily_equity])
    daily_returns = daily_equity.pct_change().dropna()
    daily_returns = daily_returns[daily_returns != 0]

    # --- 3. Comprehensive Metric Calculations ---
    final_capital = df['equity'].iloc[-1]
    total_net_pnl = final_capital - initial_capital
    total_net_pnl_pct = (total_net_pnl / initial_capital) * 100
    win_rate = df['win'].mean() * 100
    total_trades = len(df)
    gross_profit = df[df['pnl_currency'] > 0]['pnl_currency'].sum()
    gross_loss = abs(df[df['pnl_currency'] < 0]['pnl_currency'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
    avg_win = df[df['win']]['pnl_currency'].mean() if len(df[df['win']]) > 0 else 0
    avg_loss = abs(df[~df['win']]['pnl_currency'].mean()) if len(df[~df['win']]) > 0 else 0
    expectancy = df['pnl_currency'].mean()
    df['running_max'] = df['equity'].cummax()
    df['drawdown'] = df['running_max'] - df['equity']
    max_drawdown = df['drawdown'].max()
    max_drawdown_pct = (max_drawdown / df['running_max'].max()) * 100 if df['running_max'].max() > 0 else 0
    total_duration_years = (df['exit_time'].iloc[-1] - df['entry_time'].iloc[0]).days / 365.25 if total_trades > 1 else 0
    cagr = ((final_capital / initial_capital) ** (1 / total_duration_years) - 1) * 100 if total_duration_years > 0 else 0
    sharpe_ratio = (daily_returns.mean() * 252) / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    downside_returns = daily_returns[daily_returns < 0]
    downside_std = downside_returns.std() * np.sqrt(252) if not downside_returns.empty else 0
    sortino_ratio = (daily_returns.mean() * 252) / downside_std if downside_std > 0 else np.inf
    calmar_ratio = cagr / max_drawdown_pct if max_drawdown_pct > 0 else np.inf
    df['streak_counter'] = df['win'].ne(df['win'].shift()).cumsum()
    streaks = df.groupby('streak_counter')['win'].count()
    win_streaks, loss_streaks = streaks[df.groupby('streak_counter')['win'].first()], streaks[~df.groupby('streak_counter')['win'].first()]
    max_win_streak, max_loss_streak = (win_streaks.max() if not win_streaks.empty else 0), (loss_streaks.max() if not loss_streaks.empty else 0)

    # --- 4. Risk-to-Reward Ratio Analysis ---
    df['rr_ratio'] = abs(df['take_profit'] - df['entry_price']) / abs(df['entry_price'] - df['stop_loss'])
    rr_bins = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0, np.inf]
    rr_labels = ['0-0.5', '0.5-1.0', '1.0-1.5', '1.5-2.0', '2.0-2.5', '2.5-3.0', '3.0-5.0', '>5.0']
    df['rr_range'] = pd.cut(df['rr_ratio'], bins=rr_bins, labels=rr_labels, right=False)
    rr_distribution = df['rr_range'].value_counts().sort_index()

    # --- 5. Stop-Loss Distribution Analysis ---
    sl_bins = [0, 5, 10, 15, 20, np.inf]
    sl_labels = ['0-5 pips', '6-10 pips', '11-15 pips', '16-20 pips', '20+ pips']
    df['sl_range'] = pd.cut(df['sl_pips'], bins=sl_bins, labels=sl_labels, right=True, include_lowest=True)
    sl_distribution = df['sl_range'].value_counts().sort_index()

    # --- 6. Trade Timing Forensics (Analysis of Losing Trades) ---
    timing_results = []
    losing_trades = df[~df['win']]
    price_data_df['timestamp'] = pd.to_datetime(price_data_df['timestamp'])
    price_data_df.set_index('timestamp', inplace=True)
    
    for _, trade in tqdm(losing_trades.iterrows(), total=len(losing_trades), desc="Analyzing Losing Trades"):
        entry_time = trade['entry_time']
        future_candles = price_data_df.loc[entry_time:].head(101).iloc[1:]
        if len(future_candles) < 100: continue
        tp_hit = (future_candles['high'].max() >= trade['take_profit']) if trade['trade_type'] == 'buy' else (future_candles['low'].min() <= trade['take_profit'])
        timing_results.append("Entry Too Early" if tp_hit else "Directional Bias Wrong")
    timing_analysis_counts = pd.Series(timing_results).value_counts()

    # --- 7. Generate Final Report File ---
    with open(report_path, 'w') as f:
        f.write("="*50 + "\n" + "=    Strategy Performance & Forensics Report    =" + "\n" + "="*50 + "\n\n")
        f.write("--- I. Overall Performance Summary ---" + "\n")
        f.write(f"Initial Capital:           ${initial_capital:,.2f}\n")
        f.write(f"Final Capital:             ${final_capital:,.2f}\n")
        f.write(f"Total Net Profit:          ${total_net_pnl:,.2f} ({total_net_pnl_pct:.2f}%)\n")
        f.write(f"CAGR:                      {cagr:.2f}%\n")
        f.write(f"Maximum Drawdown:          ${max_drawdown:,.2f} ({max_drawdown_pct:.2f}%)\n\n")
        f.write("--- II. Backtesting Metrics ---" + "\n")
        f.write(f"Total Trades:              {total_trades}\n")
        f.write(f"Win Rate:                  {win_rate:.2f}%\n")
        f.write(f"Profit Factor:             {profit_factor:.2f}\n")
        f.write(f"Expectancy per Trade:      ${expectancy:,.2f}\n")
        f.write(f"Average Win:               ${avg_win:,.2f}\n")
        f.write(f"Average Loss:              ${avg_loss:,.2f}\n")
        f.write(f"Longest Winning Streak:    {int(max_win_streak)} trades\n")
        f.write(f"Longest Losing Streak:     {int(max_loss_streak)} trades\n\n")
        f.write("--- III. Advanced Performance Ratios ---" + "\n")
        f.write(f"Sharpe Ratio:              {sharpe_ratio:.2f}\n")
        f.write(f"Sortino Ratio:             {sortino_ratio:.2f}\n")
        f.write(f"Calmar Ratio:              {calmar_ratio:.2f}\n\n")
        f.write("--- IV. Risk-to-Reward Ratio Distribution ---" + "\n")
        f.write(rr_distribution.to_string() + "\n\n")
        f.write("--- V. Stop-Loss Distribution ---" + "\n")
        f.write(sl_distribution.to_string() + "\n\n")
        f.write("--- VI. Trade Timing Forensics (Analysis of Losing Trades) ---" + "\n")
        if not timing_analysis_counts.empty:
            f.write(timing_analysis_counts.to_string() + "\n\n--- Percentages ---" + "\n")
            f.write((timing_analysis_counts / timing_analysis_counts.sum() * 100).round(2).to_string())
        else: f.write("No losing trades to analyze.")
        f.write("\n" + "="*50 + "\n")

    print(f"Comprehensive text report saved to '{report_path}'")

    # --- 8. Generate and Save Charts ---
    try:
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(14, 8))
        ax.plot(df['exit_time'], df['equity'], label='Equity Curve', color='dodgerblue', linewidth=2)
        ax.fill_between(df['exit_time'], df['running_max'], df['equity'], facecolor='red', alpha=0.3, label='Drawdown')
        ax.set_title(f'{base_filename} Equity Curve', fontsize=16)
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Account Balance ($)', fontsize=12)
        ax.legend()
        ax.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(equity_chart_path)
        plt.close()
        print(f"Equity curve chart saved to '{equity_chart_path}'")
    except Exception as e: print(f"[ERROR] Could not generate equity curve chart: {e}")

    if not timing_analysis_counts.empty:
        try:
            plt.figure(figsize=(10, 8))
            plt.pie(timing_analysis_counts, labels=timing_analysis_counts.index, autopct='%1.1f%%', startangle=140, colors=['#ff6666', '#66b3ff'])
            plt.title(f'Forensic Analysis of Losing Trades', fontsize=16)
            plt.savefig(forensics_chart_path)
            plt.close()
            print(f"Losing trades forensics chart saved to '{forensics_chart_path}'")
        except Exception as e: print(f"[ERROR] Could not generate forensics pie chart: {e}")
