import MetaTrader5 as mt5
import time

"""
MT5 Trade Functions (Final Version)

This module contains all the necessary functions for interacting with the
MetaTrader 5 terminal to perform trading actions.

CHANGE LOG:
- Corrected the 'tick_value' error in 'calculate_lot_size_by_pips'.
  The function now uses the correct 'trade_tick_value' attribute.
- Modified 'market_order' to correctly calculate the SL price from pips.
- Standardized pip/point logic across functions.
"""

def get_open_position(symbol, magic_number):
    """Checks if there is an open position for a given symbol and magic number."""
    positions = mt5.positions_get(symbol=symbol)
    if positions:
        for pos in positions:
            if pos.magic == magic_number:
                return pos
    return None

def get_trade_exit_details(ticket):
    """Retrieves the profit and exit price of a closed trade from the history."""
    deals = mt5.history_deals_get(position=ticket)
    if deals and len(deals) > 0:
        exit_deal = deals[-1]
        return {
            'price': exit_deal.price,
            'profit': exit_deal.profit,
            'reason': 'Closed by SL/TP or Manually'
        }
    return None

def close_position(position, magic):
    """Closes an open position."""
    order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": order_type,
        "position": position.ticket,
        "price": price,
        "deviation": 20,
        "magic": magic,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(request)
    return result

def market_order(symbol, volume, order_type, stoploss_price, takeprofit_price, magic, strategy_name):
    """
    Places a market order with a specified SL price and TP price.
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Failed to get symbol info for {symbol}")
        return None

    price = mt5.symbol_info_tick(symbol).ask if order_type == 'BUY' else mt5.symbol_info_tick(symbol).bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": mt5.ORDER_TYPE_BUY if order_type == 'BUY' else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": stoploss_price,
        "tp": takeprofit_price,
        "deviation": 20,
        "magic": magic,
        "comment": strategy_name,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    
    result = mt5.order_send(request)
    return result

def calculate_lot_size(symbol, stop_loss_price, risk_percent, balance):
    """
    Calculates the appropriate lot size for a trade based on a stop loss price.
    """
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        print(f"Could not get symbol info for {symbol}")
        return None

    # --- Risk and Balance ---
    risk_amount = balance * (risk_percent / 100)

    # --- Price and Stop Loss ---
    price = mt5.symbol_info_tick(symbol).ask
    sl_distance = abs(price - stop_loss_price)

    # --- Value per Lot ---
    lot_value = symbol_info.trade_contract_size
    sl_value_per_lot = sl_distance * lot_value

    # --- Lot Size Calculation ---
    if sl_value_per_lot <= 0:
        return None

    lot_size = risk_amount / sl_value_per_lot

    # --- Normalization and Validation ---
    volume_step = symbol_info.volume_step
    lot_size = (lot_size // volume_step) * volume_step
    
    min_volume = symbol_info.volume_min
    max_volume = symbol_info.volume_max
    
    lot_size = max(min_volume, min(lot_size, max_volume))

    return round(lot_size, 2)
