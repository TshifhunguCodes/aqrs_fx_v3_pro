def indicator_tape(df, direction: str) -> dict:
    """Summarize MACD, DI/ADX, stochastic, and Bollinger confirmation."""
    if df is None or df.empty:
        return {
            "score": 0,
            "confirmations": [],
            "conflicts": [],
            "strong_conflict": False,
        }

    last = df.iloc[-1]
    direction = direction.upper()

    buy_checks = {
        "macd": last.get("macd_histogram", last.get("macd_hist", 0)) > 0 or last.get("macd_slope", 0) > 0,
        "di": last.get("adx_plus_di", last.get("dmp", 0)) > last.get("adx_minus_di", last.get("dmn", 0)),
        "stoch": last.get("stoch_k", 50) > last.get("stoch_d", 50),
        "bb": last.get("close", 0) > last.get("bb_middle", last.get("bb_mid", last.get("close", 0))),
    }
    sell_checks = {
        "macd": last.get("macd_histogram", last.get("macd_hist", 0)) < 0 or last.get("macd_slope", 0) < 0,
        "di": last.get("adx_minus_di", last.get("dmn", 0)) > last.get("adx_plus_di", last.get("dmp", 0)),
        "stoch": last.get("stoch_k", 50) < last.get("stoch_d", 50),
        "bb": last.get("close", 0) < last.get("bb_middle", last.get("bb_mid", last.get("close", 0))),
    }

    aligned = buy_checks if direction == "BUY" else sell_checks
    opposed = sell_checks if direction == "BUY" else buy_checks
    confirmations = [name for name, ok in aligned.items() if ok]
    conflicts = [name for name, ok in opposed.items() if ok]

    return {
        "score": len(confirmations) * 10,
        "confirmations": confirmations,
        "conflicts": conflicts,
        "strong_conflict": len(conflicts) >= 3,
        "buy_count": sum(buy_checks.values()),
        "sell_count": sum(sell_checks.values()),
    }
