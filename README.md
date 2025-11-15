# AlphaEvo — Agentic MSS Trading System

AlphaEvo is a modular, agentic trading research project focused on detecting and executing Market Structure Shift (MSS) setups with strict risk management. It combines deterministic technical tools with a CrewAI-driven decision flow, supports quick backtest simulation, and integrates a live trading loop for MetaTrader 5 (MT5).

## Problem Statement
- Intraday FX trading requires fast, consistent detection of high-quality setups and disciplined risk management.
- Traditional single-step strategies often suffer from directional bias errors and premature entries, leading to avoidable losses.
- We need a robust, explainable pipeline that:
  - Cleans and structures raw OHLCV market data.
  - Identifies MSS setups using EMA trend and swing points with session constraints.
  - Evaluates proposed trades against historical outcomes to avoid known failure modes.
  - Sizes positions and enforces risk/reward thresholds before execution.

## Solution Overview
AlphaEvo implements the V2.2 MSS strategy and orchestrates analysis through a small team of agents (CrewAI) using deterministic tools:
- Strategy core:
  - EMAs (50/200) for trend direction.
  - Swing highs/lows for structure.
  - Session filter (08:00–22:00 UTC) to avoid low-liquidity hours.
  - MSS detection: break of relevant swing in the direction of trend with valid stop distance.
- Agentic workflow (CrewAI):
  - Market Data Analyst: assures clean, indicator-ready data.
  - Technical Analysis Expert: identifies MSS setups and computes entry/SL/TP (1:2 RR).
  - Strategy Performance Analyst: checks historical trade log to flag patterns that previously underperformed.
  - Risk Management Analyst: verifies RR, sizes positions, and guards capital.
  - Trading Strategy Manager: integrates all signals to choose BUY/SELL/HOLD.
- Backtest:
  - `simulate_live_markets.py` produces a trade log and generates `AlphaEvoOutput/performance_report.txt`.
- Live trading:
  - `liveTrader/` contains the MT5 live execution loop (`live_trader_v2_2.py`) using the same MSS logic and risk rules.

## Repository Structure (key files)
- `trading_agents.py` — CrewAI agent roles and goals.
- `trading_tools.py` — Deterministic tools: EMAs, swing points, session window, MSS setup detection, position sizing, RR checks, history evaluation.
- `trading_crew.py` — Orchestrates agents and tasks; wires tools and agents; expects `GOOGLE_API_KEY` and `GEMINI_MODEL_NAME` via environment.
- `simulate_live_markets.py` — Quick backtest runner that logs trades to `AlphaEvoOutput/trade_log.csv` and generates `AlphaEvoOutput/performance_report.txt`.
- `liveTrader/` — MT5 live trading loop, config, and messaging.
- `AlphaEvoOutput/` — Latest generated trade log and performance report.
- `backtesterResults/` — Baseline backtest report (from prior/alternate runs).

## Setup
- Python: 3.10+
- Suggested packages: `pandas`, `numpy`, `tqdm`, `python-dotenv`, `crewai`, `litellm`, (optional) `MetaTrader5` for live trading.
- Environment variables (for agentic flow):
  - `GOOGLE_API_KEY` — API key for the configured model provider.
  - `GEMINI_MODEL_NAME` — Model name suffix used by `litellm` (e.g., `gemini-1.5-pro`), referenced as `gemini/<name>`.
- Data: Place one of `EURUSD1month.csv` or `EURUSD2025_10months.csv` in the project root. CSV must contain at least `time, open, high, low, close`.

## Usage
- Backtest + Report:
  1. `python simulate_live_markets.py`
  2. Outputs: `AlphaEvoOutput/trade_log.csv` and `AlphaEvoOutput/performance_report.txt`
- Live trading (MT5):
  - Configure credentials and parameters in `liveTrader/config_v2_2.py`.
  - Run `python liveTrader/live_trader_v2_2.py` on a machine with MT5 and broker access.

## Results Comparison
Comparing baseline backtest (`backtesterResults`) vs refined output (`AlphaEvoOutput`):

Paths:
- Baseline: `c:/Users/disha/Desktop/hackathon/AlphaEvo_remote/backtesterResults/`
- Refined: `c:/Users/disha/Desktop/hackathon/AlphaEvo_remote/AlphaEvoOutput/`

### Summary Metrics
| Metric | Baseline (backtesterResults) | Refined (AlphaEvoOutput) |
|---|---:|---:|
| Final Capital | $11,620,363.57 | $17,378,305.83 |
| Total Net Profit | $11,610,363.57 (116,103.64%) | $17,368,305.83 (173,683.06%) |
| Maximum Drawdown | $398,406.69 (3.39%) | $155,717.43 (0.90%) |
| Total Trades | 1,426 | 1,097 |
| Win Rate | 65.43% | 85.05% |
| Profit Factor | 2.35 | 7.04 |
| Expectancy / Trade | $8,141.91 | $15,832.55 |
| Average Win | $21,695.60 | $21,695.60 |
| Average Loss | $17,508.38 | $17,522.49 |
| Sharpe | 13.71 | 17.33 |
| Sortino | 168.57 | 359.19 |
| Calmar | 10,262,003,036,041.65 | 176,929,927,523,105.50 |

### Risk/Reward Distribution (counts)
- Baseline: `1.5–2.0 → 147`, `2.0–2.5 → 1279`
- Refined:  `1.5–2.0 → 116`, `2.0–2.5 → 981`

### Stop-Loss Distribution (counts)
- Baseline: `0–5 pips → 628`, `6–10 → 396`, `11–15 → 182`, `16–20 → 102`, `20+ → 118`
- Refined:  `0–5 pips → 531`, `6–10 → 312`, `11–15 → 120`, `16–20 → 67`, `20+ → 67`

### Forensics
- Baseline losing-trade causes: `Directional Bias Wrong → 376`, `Entry Too Early → 116` (76.42% / 23.58%).
- Refined report: `No losing trades to analyze.`

### Interpretation
- The refined pipeline shows materially higher win rate, profit factor, and expectancy with lower drawdown and fewer total trades — pointing to improved selectivity and better alignment of direction and timing.
- Extremely high CAGR/Calmar in the reports reflect the test harness assumptions and compounding; treat them as indicative rather than realistic. Always validate with conservative risk settings and robust datasets.

## Artifacts
- Baseline equity curve: `backtesterResults/performance_report_equity_curve.png`
- Refined equity curve: `AlphaEvoOutput/performance_report_equity_curve.png`
- Trade log (refined): `AlphaEvoOutput/trade_log.csv`

## Notes & Caveats
- Some components (e.g., `backtester.py`) are referenced by tools and may need to be present for full functionality in your setup.
- Live trading requires MT5 connectivity and proper broker configuration; use at your own risk.
- CrewAI and LLM usage in `trading_crew.py` relies on environment variables; ensure they are set before running agentic workflows.
