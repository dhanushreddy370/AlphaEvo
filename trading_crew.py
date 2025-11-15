import os
import pandas as pd
from crewai import Agent, Task, Crew, Process
from trading_agents import TradingAgents
from trading_tools import ReadBacktesterStrategyTool
from trading_tools import ReadBacktesterTradeLogTool
from trading_tools import CalculateEMAsTool
from trading_tools import IdentifySwingPointsTool
from trading_tools import CheckSessionHoursTool
from trading_tools import IdentifyMSSSetupTool
from trading_tools import CalculateTradeParametersTool
from trading_tools import CalculatePositionSizeTool
from trading_tools import CheckRiskRewardRatioTool
from trading_tools import EvaluateTradeAgainstHistoryTool
from dotenv import load_dotenv
import litellm # Import litellm directly


# Load environment variables from .env file
load_dotenv()

class TradingCrew:
    def __init__(self):
        # Configure the LLM using litellm directly
        self.llm = litellm.completion(
            model=f"gemini/{os.getenv('GEMINI_MODEL_NAME')}", # Explicitly specify provider
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        self.agents = TradingAgents(llm=self.llm) # Pass the llm to the agents class
        self.read_backtester_strategy_tool = ReadBacktesterStrategyTool()
        self.read_backtester_trade_log_tool = ReadBacktesterTradeLogTool()
        self.calculate_emas_tool = CalculateEMAsTool()
        self.identify_swing_points_tool = IdentifySwingPointsTool()
        self.check_session_hours_tool = CheckSessionHoursTool()
        self.identify_mss_setup_tool = IdentifyMSSSetupTool()
        self.calculate_trade_parameters_tool = CalculateTradeParametersTool()
        self.calculate_position_size_tool = CalculatePositionSizeTool()
        self.check_risk_reward_ratio_tool = CheckRiskRewardRatioTool()
        self.evaluate_trade_against_history_tool = EvaluateTradeAgainstHistoryTool()

    def create_crew(self, historical_data: pd.DataFrame, current_candle_data: dict, current_index: int, account_balance: float, historical_trade_log: pd.DataFrame):
        # Agents
        market_data_analyst = self.agents.market_data_analyst()
        technical_analysis_expert = self.agents.technical_analysis_expert()
        strategy_performance_analyst = self.agents.strategy_performance_analyst()
        risk_management_analyst = self.agents.risk_management_analyst()
        trading_strategy_manager = self.agents.trading_strategy_manager()

        # Tasks
        process_market_data_task = Task(
            description=(
                f"Process the current market candle data: {current_candle_data}. "
                "Ensure it's clean and ready for technical analysis. "
                "No specific action needed other than acknowledging the data."
            ),
            expected_output="Confirmation that market data has been processed and is ready.",
            agent=market_data_analyst,
            output_file=f"task_outputs/market_data_processed_{current_candle_data['timestamp'].strftime('%Y%m%d%H%M')}.txt"
        )

        perform_technical_analysis_task = Task(
            description=(
                "Analyze the historical data and the current candle to identify a Market Structure Shift (MSS) trade setup. "
                "Use the 'Calculate EMAs', 'Identify Swing Points', 'Check Session Hours', and 'Identify MSS Setup' tools. "
                "If a setup is found, propose the trade type (buy/sell), entry price, and stop-loss. "
                "If no setup, state 'No trade setup identified'."
            ),
            expected_output="A dictionary containing trade setup details (type, entry, SL) or 'No trade setup identified'.",
            agent=technical_analysis_expert,
            tools=[
                self.calculate_emas_tool,
                self.identify_swing_points_tool,
                self.check_session_hours_tool,
                self.identify_mss_setup_tool
            ],
            context=[process_market_data_task],
            input={
                "historical_data": historical_data,
                "current_index": current_index
            },
            output_file=f"task_outputs/technical_analysis_{current_candle_data['timestamp'].strftime('%Y%m%d%H%M')}.txt"
        )

        calculate_trade_parameters_task = Task(
            description=(
                "Given a proposed trade setup from the Technical Analysis Expert, calculate the take-profit level "
                "using the 'Calculate Trade Parameters' tool, assuming a 1:2 Risk/Reward ratio. "
                "If no trade setup was identified, output 'No trade parameters to calculate'."
            ),
            expected_output="A dictionary with the full trade parameters including take-profit, or 'No trade parameters to calculate'.",
            agent=technical_analysis_expert, # TA Expert can also calculate parameters
            tools=[self.calculate_trade_parameters_tool],
            context=[perform_technical_analysis_task],
            output_file=f"task_outputs/trade_parameters_{current_candle_data['timestamp'].strftime('%Y%m%d%H%M')}.txt"
        )

        evaluate_strategy_history_task = Task(
            description=(
                "Evaluate the proposed trade setup against the historical performance of the V2.2 strategy. "
                "Use the 'Read Backtester Trade Log' and 'Evaluate Trade Against History' tools. "
                "Provide a critical assessment, highlighting any historical patterns that suggest caution or avoidance. "
                "If no trade setup, state 'No trade to evaluate'."
            ),
            expected_output="A string indicating potential issues or 'No significant historical issues found'.",
            agent=strategy_performance_analyst,
            tools=[self.read_backtester_trade_log_tool, self.evaluate_trade_against_history_tool],
            context=[calculate_trade_parameters_task],
            output_file=f"task_outputs/strategy_evaluation_{current_candle_data['timestamp'].strftime('%Y%m%d%H%M')}.txt"
        )

        assess_risk_and_position_size_task = Task(
            description=(
                f"Assess the risk of the proposed trade and calculate the appropriate position size. "
                f"Current account balance is {account_balance}. Assume 1% risk per trade. "
                "Use the 'Calculate Position Size' and 'Check Risk Reward Ratio' tools. "
                "Output the calculated position size and confirmation of RR ratio, or 'No trade to assess'."
            ),
            expected_output="A dictionary with 'position_size', 'rr_meets_criteria' (boolean), or 'No trade to assess'.",
            agent=risk_management_analyst,
            tools=[self.calculate_position_size_tool, self.check_risk_reward_ratio_tool],
            context=[calculate_trade_parameters_task],
            output_file=f"task_outputs/risk_assessment_{current_candle_data['timestamp'].strftime('%Y%m%d%H%M')}.txt"
        )

        final_decision_task = Task(
            description=(
                "Synthesize all the analysis from the Market Data Analyst, Technical Analysis Expert, "
                "Strategy Performance Analyst, and Risk Management Analyst. "
                "Make a final trading decision: 'BUY', 'SELL', or 'HOLD'. "
                "Provide a brief justification for the decision."
            ),
            expected_output="A string indicating the final decision ('BUY', 'SELL', or 'HOLD') and a brief justification.",
            agent=trading_strategy_manager,
            context=[
                process_market_data_task,
                perform_technical_analysis_task,
                calculate_trade_parameters_task,
                evaluate_strategy_history_task,
                assess_risk_and_position_size_task
            ],
            output_file=f"task_outputs/final_decision_{current_candle_data['timestamp'].strftime('%Y%m%d%H%M')}.txt"
        )

        # Crew
        trading_crew = Crew(
            agents=[
                market_data_analyst,
                technical_analysis_expert,
                strategy_performance_analyst,
                risk_management_analyst,
                trading_strategy_manager
            ],
            tasks=[
                process_market_data_task,
                perform_technical_analysis_task,
                calculate_trade_parameters_task,
                evaluate_strategy_history_task,
                assess_risk_and_position_size_task,
                final_decision_task
            ],
            process=Process.sequential, # Tasks will be executed in order
            verbose=True,
            output_log_file=f"crew_logs/crew_run_{current_candle_data['timestamp'].strftime('%Y%m%d%H%M')}.log"
        )

        return trading_crew

if __name__ == "__main__":
    # This block is for testing the crew setup, not for running the full simulation.
    # The actual simulation loop will be in market_simulation.py
    print("This script defines the trading crew. It is not meant to be run directly.")
    print("Please run market_simulation.py to start the backtest simulation.")
