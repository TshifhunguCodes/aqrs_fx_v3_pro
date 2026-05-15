"""
Risk Manager V3
ATR-based lot sizing, daily drawdown enforcement, max open trades,
trailing stop management, breakeven.
"""
import MetaTrader5 as mt5
from core.config import (
    PAIR_RISK, MAX_OPEN_TRADES, MAX_DAILY_DRAWDOWN,
    DEFAULT_BALANCE, TRAILING_STOP_POINTS
)
from core.logger import logger


def get_balance() -> float:
    try:
        info = mt5.account_info()
        return info.balance if info else DEFAULT_BALANCE
    except Exception:
        return DEFAULT_BALANCE


def lot_size(symbol: str, sl_dist_price: float, balance: float = None) -> float:
    """
    ATR-distance-based position sizing.
    Risk fraction × balance / (SL distance in price × contract value).
    Falls back to flat percentage if contract value unavailable.
    """
    balance = balance or get_balance()
    risk_frac = PAIR_RISK.get(symbol, 0.005)
    risk_amount = balance * risk_frac

    try:
        info = mt5.symbol_info(symbol)
        if info and sl_dist_price > 0:
            contract = info.trade_contract_size
            tick_val = info.trade_tick_value
            tick_sz  = info.trade_tick_size
            point_val = (tick_val / tick_sz) if tick_sz > 0 else 1
            lots = risk_amount / (sl_dist_price * point_val * contract)
            lots = max(info.volume_min, min(lots, info.volume_max))
            return round(lots, 2)
    except Exception:
        pass

    # Fallback
    return round(risk_amount / 100, 2)


def daily_loss_exceeded() -> bool:
    try:
        info = mt5.account_info()
        if not info:
            return False
        balance = info.balance
        equity  = info.equity
        drawdown = (balance - equity) / balance if balance > 0 else 0
        if drawdown >= MAX_DAILY_DRAWDOWN:
            logger.warning(f"Daily drawdown limit reached: {drawdown:.2%}")
            return True
    except Exception:
        pass
    return False


def open_trade_count(magic: int = 777) -> int:
    try:
        positions = mt5.positions_get()
        if positions is None:
            return 0
        return sum(1 for p in positions if p.magic == magic)
    except Exception:
        return 0


def can_open_trade(magic: int = 777) -> tuple[bool, str]:
    if daily_loss_exceeded():
        return False, "DAILY_LOSS_LIMIT"
    if open_trade_count(magic) >= MAX_OPEN_TRADES:
        return False, "MAX_TRADES_REACHED"
    return True, "OK"


def manage_trailing_stops(magic: int = 777):
    """Move trailing stops for index instruments (US30, NAS100)."""
    try:
        positions = mt5.positions_get()
        if not positions:
            return
        for pos in positions:
            if pos.magic != magic:
                continue
            trail_pts = TRAILING_STOP_POINTS.get(pos.symbol, 0)
            if trail_pts <= 0:
                continue
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                continue
            point = mt5.symbol_info(pos.symbol).point

            if pos.type == mt5.ORDER_TYPE_BUY:
                new_sl = tick.bid - trail_pts * point
                if new_sl > pos.sl + point:
                    _modify_sl(pos.ticket, new_sl, pos.symbol)

            elif pos.type == mt5.ORDER_TYPE_SELL:
                new_sl = tick.ask + trail_pts * point
                if new_sl < pos.sl - point or pos.sl == 0:
                    _modify_sl(pos.ticket, new_sl, pos.symbol)

    except Exception as e:
        logger.warning(f"Trailing stop error: {e}")


def manage_breakeven(magic: int = 777, trigger_rr: float = 1.0):
    """Move SL to breakeven when price moves trigger_rr × risk in profit."""
    try:
        positions = mt5.positions_get()
        if not positions:
            return
        for pos in positions:
            if pos.magic != magic:
                continue
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                continue
            if pos.sl == 0:
                continue
            risk_dist = abs(pos.price_open - pos.sl)
            if pos.type == mt5.ORDER_TYPE_BUY:
                target = pos.price_open + risk_dist * trigger_rr
                if tick.bid > target and pos.sl < pos.price_open:
                    _modify_sl(pos.ticket, pos.price_open + mt5.symbol_info(pos.symbol).point, pos.symbol)
            elif pos.type == mt5.ORDER_TYPE_SELL:
                target = pos.price_open - risk_dist * trigger_rr
                if tick.ask < target and pos.sl > pos.price_open:
                    _modify_sl(pos.ticket, pos.price_open - mt5.symbol_info(pos.symbol).point, pos.symbol)

    except Exception as e:
        logger.warning(f"Breakeven error: {e}")


def _modify_sl(ticket: int, new_sl: float, symbol: str = ""):
    request = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol":   symbol,
        "sl":       new_sl,
    }
    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"SL modified | ticket={ticket} | new_sl={new_sl:.5f}")
    else:
        logger.warning(f"SL modify failed | ticket={ticket} | retcode={result.retcode if result else 'None'}")
