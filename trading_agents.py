from crewai import Agent

class TradingAgents:
    def __init__(self, llm):
        self.llm = llm

    def market_data_analyst(self):
        return Agent(
            role="Market Data Analyst",
            goal="To provide clean, structured, and relevant market data for further analysis.",
            backstory=(
                "An expert in market data processing, skilled at extracting essential information "
                "from raw candle data, including OHLCV, and basic indicators like ATR, RSI, and Stochastic K. "
                "Ensures data quality and readiness for advanced technical analysis."
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    def technical_analysis_expert(self):
        return Agent(
            role="Technical Analysis Expert",
            goal=(
                "To identify valid 'Market Structure Shift' (MSS) trade setups (buy or sell) "
                "and propose entry, stop-loss, and take-profit levels based on the V2.2 strategy."
            ),
            backstory=(
                "A seasoned technical analyst with deep knowledge of market structure, EMA crossovers, "
                "swing points, and session-based trading. Specializes in the V2.2 strategy, meticulously "
                "looking for bullish and bearish MSS setups, and calculating precise trade parameters."
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    def strategy_performance_analyst(self):
        return Agent(
            role="Strategy Performance Analyst",
            goal=(
                "To provide a critical assessment of a proposed trade, highlighting potential risks "
                "or reasons to avoid it based on past performance data and strategy limitations."
            ),
            backstory=(
                "A meticulous performance analyst who has thoroughly studied the V2.2 strategy's "
                "backtest results. Knows exactly when the strategy tends to fail or underperform, "
                "and uses this knowledge to prevent costly mistakes. Acts as the ultimate gatekeeper "
                "for trade execution."
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    def risk_management_analyst(self):
        return Agent(
            role="Risk Management Analyst",
            goal=(
                "To calculate appropriate position sizing, confirm stop-loss validity, "
                "and ensure the trade's risk-reward ratio meets criteria."
            ),
            backstory=(
                "A cautious risk manager focused on capital preservation. Ensures that every trade "
                "adheres to strict risk parameters, preventing excessive losses and promoting "
                "sustainable growth. Provides final validation on trade sizing and risk exposure."
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    def trading_strategy_manager(self):
        return Agent(
            role="Trading Strategy Manager",
            goal=(
                "To make the optimal trading decision (BUY, SELL, or HOLD) by integrating market data, "
                "technical analysis, strategy performance insights, and risk management considerations."
            ),
            backstory=(
                "The lead decision-maker, responsible for the overall trading strategy. Combines insights "
                "from all specialists to make high-conviction trading calls, balancing opportunity with risk. "
                "Their final word determines the trade action."
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=True # This agent will delegate tasks to others
        )
