"""
AQRS FX Pro — Core Engine V3
Full pipeline: SMC/ICT + Volume Profile + Regime + Lifecycle + ML + RL Gate
"""
import pandas as pd
import threading

from market.mt5_connector import MT5Connector
from market.candles import add_indicators, merge_htf_context
from market.spread import get_spread
from market.behavior import classify_behavior

from strategy.htf_bias import get_bias
from strategy.structure import classify_structure, premium_discount, detect_inducement
from strategy.liquidity import liquidity_sweep, sweep_supports_direction
from strategy.fvg import detect_fvg, detect_fvg_zones, price_in_fvg
from strategy.order_blocks import detect_order_block, detect_ob_zones, price_in_ob
from strategy.manipulation import manipulation_score
from strategy.candle_confirm import get_candle_confirmation
from strategy.session import is_valid_session, current_session
from strategy.scoring import calculate_score
from strategy.indicator_confirm import indicator_tape
from systems.alpha import generate_alpha_setup
from systems.flow import generate_flow_setup
from execution.gate import execution_gate

from regime.volume_profile import build_volume_profile, vp_zone, vp_near_poc
from regime.market_lifecycle import classify_lifecycle
from regime.market_regime import classify_regime

from intelligence.adaptive_filter import adaptive_gate
from intelligence.unsupervised_model import predict_regime

from risk.risk_manager import lot_size, can_open_trade, get_balance
from risk.dynamic_exit import dynamic_sltp
from risk.news_guard import is_trading_allowed

from execution.entries import EntryExecutor
from analytics.trade_journal import log_trade

from core.config import (SYMBOLS, TIMEFRAME, HTF_TIMEFRAME,
                          MIN_SIGNAL_SCORE, MAX_SPREADS,
                          PAIR_MIN_ADX, PAIR_MIN_SCORE,
                          PAIR_REQUIRE_PD_ALIGNMENT,
                          PAIR_REQUIRE_ZONE_OR_SWEEP,
                          TELEGRAM_ENABLED, TELEGRAM_NOTIFY_TRADES,
                          PAIR_PIP_SIZE, PAIR_MIN_STOP_PIPS,
                          FLOW_RISK_MULTIPLIER, MAGIC_NUMBER)

# Optional Telegram notifications
try:
    from notifications import send as tg_send, trade_opened as tg_trade_opened
    from core.config import TELEGRAM_BOT_TOKEN
    _tg_available = bool(TELEGRAM_BOT_TOKEN)
except Exception:
    _tg_available = False
    def tg_send(*args, **kwargs): pass
    def tg_trade_opened(*args, **kwargs): return ""
from core.logger import logger


class AQRSFX:

    def __init__(self):
        self.mt5      = MT5Connector()
        self.executor = EntryExecutor()

    # ─────────────────────────────────────────────────────────────────────────
    def process_pair(self, symbol: str):

        logger.info(f"━━ {symbol} | session={current_session()}")

        # ── Global gates ─────────────────────────────────────────────────────
        allowed, block_reason = is_trading_allowed()
        if not allowed:
            logger.info(f"{symbol} blocked — {block_reason}")
            return

        if not is_valid_session(strict=False):
            logger.info(f"{symbol} skipped — off-hours")
            return

        ok, reason = can_open_trade()
        if not ok:
            logger.info(f"{symbol} risk gate: {reason}")
            return

        # ── Spread check ──────────────────────────────────────────────────────
        spread = get_spread(symbol)
        if spread > MAX_SPREADS.get(symbol, 50):
            logger.warning(f"{symbol} spread {spread} too high")
            return

        # ── Data: M5 + H1 ────────────────────────────────────────────────────
        df_m5 = self.mt5.get_rates(symbol, TIMEFRAME,     500)
        df_h1 = self.mt5.get_rates(symbol, HTF_TIMEFRAME, 200)

        df_m5 = add_indicators(df_m5)
        df_h1 = add_indicators(df_h1)

        # Merge H1 context into M5
        try:
            df = merge_htf_context(df_m5, df_h1)
        except Exception:
            df = df_m5   # fallback if merge fails

        current_price = df.iloc[-1]['close']
        atr           = df.iloc[-1]['atr']
        pip_size      = PAIR_PIP_SIZE.get(symbol, 0.01 if "JPY" in symbol else 0.0001)
        min_stop_distance = PAIR_MIN_STOP_PIPS.get(symbol, 8) * pip_size
        behavior = classify_behavior(df, pip_size)

        # ── HTF bias ──────────────────────────────────────────────────────────
        bias = get_bias(df_h1)   # bias from H1
        direction = "BUY" if bias == "BULLISH" else "SELL" if bias == "BEARISH" else ("BUY" if df.iloc[-1].get("ema8", 0) > df.iloc[-1].get("ema21", 0) else "SELL")

        # Require trend strength
        min_adx = PAIR_MIN_ADX.get(symbol, 20)
        adx = df['adx'].iloc[-1]
        if adx < min_adx:
            logger.info(f"{symbol} ADX too low ({adx:.1f} < {min_adx}) - skipping")
            return

        # ── Candle confirmation (hard gate — fail fast) ───────────────────────
        candle_confirm = get_candle_confirmation(df, direction)
        if not candle_confirm["confirmed"]:
            logger.info(f"{symbol} no candle confirmation")
            return
        indicators = indicator_tape(df, direction)
        if indicators["strong_conflict"]:
            logger.info(f"{symbol} indicator tape conflicts with {direction}: {indicators['conflicts']}")
            return

        # ── Market structure ──────────────────────────────────────────────────
        structure = classify_structure(df)
        pd_zone   = premium_discount(structure["last_sh"], structure["last_sl"], current_price)
        if structure["trend"] != "RANGE" and structure["trend"] != bias:
            logger.info(f"{symbol} M5 structure={structure['trend']} conflicts with H1 bias={bias}")
            return

        # ── Regime + Lifecycle ────────────────────────────────────────────────
        regime    = classify_regime(df, df_h1)
        lifecycle = classify_lifecycle(df, direction)

        if not lifecycle["allow_new_entry"]:
            logger.info(f"{symbol} lifecycle={lifecycle['phase']} — no new entry")
            return

        # ── Volume Profile ────────────────────────────────────────────────────
        vp        = build_volume_profile(df.tail(100))
        vp_z      = vp_zone(current_price, vp)
        near_poc  = vp_near_poc(current_price, vp, atr)

        # ── SMC zones ─────────────────────────────────────────────────────────
        fvg_signal = detect_fvg(df)
        fvg_zones  = detect_fvg_zones(df)
        in_fvg     = price_in_fvg(current_price, fvg_zones,
                                   "BULLISH" if direction == "BUY" else "BEARISH")

        ob_signal  = detect_order_block(df)
        ob_zones   = detect_ob_zones(df)
        in_ob      = price_in_ob(current_price, ob_zones,
                                  "BULLISH" if direction == "BUY" else "BEARISH")

        # ── MTF alignment ─────────────────────────────────────────────────────
        h1_last    = df_h1.iloc[-1]
        m5_last    = df.iloc[-1]
        mtf_aligned = (
            (m5_last.get('ema8', 0) > m5_last.get('ema21', 0) and
             h1_last.get('ema8', 0) > h1_last.get('ema21', 0))
            if direction == "BUY" else
            (m5_last.get('ema8', 0) < m5_last.get('ema21', 0) and
             h1_last.get('ema8', 0) < h1_last.get('ema21', 0))
        )

        # ── MACD alignment ────────────────────────────────────────────────────
        macd_hist     = df.iloc[-1].get('macd_hist', 0)
        macd_aligned  = (macd_hist > 0 if direction == "BUY" else macd_hist < 0)
        liquidity      = liquidity_sweep(df)
        if liquidity and not sweep_supports_direction(liquidity, direction):
            logger.info(f"{symbol} liquidity={liquidity} opposes {direction}")
            return

        # ── Score ─────────────────────────────────────────────────────────────
        inducement = detect_inducement(df, direction)
        pd_aligned = (
            (direction == "BUY" and pd_zone == "DISCOUNT") or
            (direction == "SELL" and pd_zone == "PREMIUM")
        )
        if PAIR_REQUIRE_PD_ALIGNMENT.get(symbol, False) and not pd_aligned:
            logger.info(f"{symbol} pd={pd_zone} not aligned for {direction}")
            return

        has_smc_entry_zone = in_fvg or in_ob or bool(liquidity) or inducement
        if PAIR_REQUIRE_ZONE_OR_SWEEP.get(symbol, False) and not has_smc_entry_zone:
            logger.info(f"{symbol} skipped - no OB/FVG/sweep/inducement confirmation")
            return

        score_data = {
            "bias":               bias,
            "structure_trend":    structure["trend"],
            "bos":                structure["bos"],
            "choch":              structure["choch"],
            "liquidity":          liquidity,
            "fvg":                fvg_signal,
            "ob":                 ob_signal,
            "price_in_fvg":       in_fvg,
            "price_in_ob":        in_ob,
            "manipulation":       manipulation_score(df, symbol),
            "candle_confirm":     candle_confirm,
            "premium_discount":   pd_zone,
            "inducement":         inducement,
            "valid_session":      is_valid_session(strict=True),
            "direction":          direction,
            "lifecycle_modifier": lifecycle["score_modifier"],
            "regime_modifier":    regime["score_modifier"],
            "ml_regime":          predict_regime(df),
            "vp_zone":            vp_z,
            "near_poc":           near_poc,
            "mtf_aligned":        mtf_aligned,
            "adx":                df.iloc[-1].get('adx', 0),
            "macd_aligned":       macd_aligned,
            "indicator_score":    indicators["score"],
        }

        score = calculate_score(score_data)

        logger.info(
            f"{symbol} | dir={direction} | score={score} | "
            f"regime={regime['regime']} | lifecycle={lifecycle['phase']} | "
            f"vp={vp_z} | pd={pd_zone} | mtf={mtf_aligned}"
        )

        min_score = max(MIN_SIGNAL_SCORE, PAIR_MIN_SCORE.get(symbol, MIN_SIGNAL_SCORE))
        if score < min_score:
            logger.info(f"{symbol} score {score} < {min_score} - skip")
            return

        decision_context = {
            "symbol": symbol,
            "direction": direction,
            "bias": bias,
            "structure": structure,
            "liquidity": liquidity,
            "price_in_fvg": in_fvg,
            "price_in_ob": in_ob,
            "inducement": inducement,
            "pd_zone": pd_zone,
            "regime": regime,
            "lifecycle": lifecycle,
            "mtf_aligned": mtf_aligned,
            "indicators": indicators,
            "candle_confirm": candle_confirm,
            "behavior_label": behavior["label"],
            "behavior_confidence": behavior["confidence"],
        }
        alpha_setup = generate_alpha_setup(score, decision_context)
        flow_setup = generate_flow_setup(score, decision_context)
        resolved = self._resolve_signals(alpha_setup, flow_setup)
        gate = execution_gate(decision_context, resolved)
        if not gate["approved"]:
            logger.info(f"{symbol} execution gate blocked: {gate['reason']}")
            return

        direction = resolved["direction"]

        # ── Adaptive ML gate ──────────────────────────────────────────────────
        ml_gate = adaptive_gate(
            df, direction, pd_zone,
            lifecycle["phase"], candle_confirm["score"]
        )

        if not ml_gate["approved"]:
            logger.info(f"{symbol} ML gate REJECTED — {ml_gate['reason']}")
            return

        # ── Dynamic exits ─────────────────────────────────────────────────────
        exits = dynamic_sltp(
            entry     = current_price,
            atr       = atr,
            direction = direction,
            regime    = regime["regime"],
            phase     = lifecycle["phase"],
            bb_pct    = df.iloc[-1].get('bb_pct', 0.5),
            rr_override = resolved.get("rr_ratio"),
            sl_mult_override = resolved.get("atr_sl_multiplier"),
            min_stop_distance = min_stop_distance,
        )
        sl = exits["sl"]
        tp = exits["tp"]

        # ── Position sizing ───────────────────────────────────────────────────
        balance = get_balance()
        risk_multiplier = FLOW_RISK_MULTIPLIER if resolved["signal_owner"] == "FLOW" else 1.0
        volume  = lot_size(symbol, exits["sl_dist"], balance, risk_multiplier=risk_multiplier)

        # ── Execute ───────────────────────────────────────────────────────────
        comment = self._order_comment(resolved)
        result = self.executor.execute(symbol, direction, volume, sl, tp, comment=comment, magic=MAGIC_NUMBER)

        log_trade({
            "symbol":        symbol,
            "direction":     direction,
            "score":         score,
            "signal_owner":  resolved["signal_owner"],
            "quality":       resolved["quality"],
            "behavior":      behavior["label"],
            "indicator_tape": indicators,
            "entry":         current_price,
            "sl":            sl,
            "tp":            tp,
            "sl_dist":       exits["sl_dist"],
            "rr":            exits["rr"],
            "structure":     structure["trend"],
            "pd_zone":       pd_zone,
            "session":       current_session(),
            "regime":        regime["regime"],
            "lifecycle":     lifecycle["phase"],
            "vp_zone":       vp_z,
            "ml_regime":     ml_gate["ml_regime"],
            "rl_approved":   ml_gate["approved"],
            "confirmations": candle_confirm["details"],
            "exit_logic":    exits["logic"],
        })

        logger.info(f"{symbol} ✅ order sent | vol={volume} | rr={exits['rr']} | {result}")

        # Send Telegram notification on successful trade
        if _tg_available and TELEGRAM_NOTIFY_TRADES and result and result.retcode == 10009:
            tg_msg = tg_trade_opened(
                symbol=symbol, direction=direction, volume=volume,
                entry=current_price, sl=sl, tp=tp,
                score=score, rr=exits["rr"],
                reason=exits["logic"]
            )
            tg_send(tg_msg)

    # ─────────────────────────────────────────────────────────────────────────
    def _resolve_signals(self, alpha_setup: dict, flow_setup: dict) -> dict:
        """Reduce ALPHA/FLOW into one execution signal."""
        if alpha_setup.get("alpha_signal") == "ALPHA_TRADE":
            score = alpha_setup["alpha_score"]
            direction = alpha_setup.get("alpha_direction")
            owner = "ALPHA"
            trade_type = "ALPHA"
            atr_sl_multiplier = None
            rr_ratio = None
        elif flow_setup.get("flow_signal") == "FLOW_TRADE":
            score = flow_setup["flow_score"]
            direction = flow_setup.get("flow_direction")
            owner = "FLOW"
            trade_type = flow_setup.get("flow_trade_type", "FLOW")
            atr_sl_multiplier = flow_setup.get("flow_atr_sl_multiplier")
            rr_ratio = flow_setup.get("flow_rr_ratio")
        else:
            return {
                "signal": "NO_TRADE",
                "signal_owner": "NONE",
                "resolved_direction": None,
                "confirm_score": 0,
                "quality": "NONE",
                "confirmed_signal": False,
                "direction": "NO_TRADE",
                "market_regime": "UNKNOWN",
                "market_state": "UNKNOWN",
            }

        if direction not in ("LONG", "SHORT"):
            return {"signal": "NO_TRADE", "signal_owner": owner, "direction": "NO_TRADE", "quality": "NONE"}

        quality = "ELITE" if score >= 85 else "HIGH" if score >= 70 else "MEDIUM" if score >= 55 else "NONE"
        return {
            "signal": f"{owner}_TRADE",
            "signal_owner": owner,
            "resolved_direction": direction,
            "confirm_score": score,
            "quality": quality,
            "confirmed_signal": quality != "NONE",
            "direction": "BUY" if direction == "LONG" else "SELL",
            "market_regime": trade_type,
            "market_state": owner,
            "atr_sl_multiplier": atr_sl_multiplier,
            "rr_ratio": rr_ratio,
        }

    def _order_comment(self, resolved: dict) -> str:
        if resolved["signal_owner"] == "ALPHA":
            return f"AQ_ALPHA_{resolved['quality']}"

        setup_code = {
            "MOMENTUM_CONTINUATION": "MOM",
            "MICRO_RETRACEMENT_REENTRY": "REENT",
            "EXHAUSTION_FADE": "EXH",
            "EARLY_REVERSAL_ENTRY": "REV",
        }.get(resolved.get("market_regime"), "FLOW")
        return f"AQ_FLOW_EXP_{setup_code}_{resolved['quality']}"

    def _send_tg_error(self, symbol, context, error):
        """Send Telegram error notification if enabled."""
        if _tg_available and TELEGRAM_ENABLED:
            from notifications import error_alert
            tg_send(error_alert(f"Error processing {symbol}", f"{context}: {error}"))

    # ─────────────────────────────────────────────────────────────────────────
    def run(self):
        self.mt5.connect()
        threads = []
        for symbol in SYMBOLS:
            t = threading.Thread(target=self._process_symbol_safe, args=(symbol,))
            t.start()
            threads.append(t)
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
    
    def _process_symbol_safe(self, symbol):
        try:
            self.process_pair(symbol)
        except Exception as e:
            logger.error(f"{symbol} error: {e}", exc_info=True)
            self._send_tg_error(symbol, "process_pair", e)
