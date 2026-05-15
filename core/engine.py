"""
AQRS FX Pro — Core Engine V3
Full pipeline: SMC/ICT + Volume Profile + Regime + Lifecycle + ML + RL Gate
"""
import pandas as pd
import threading

from market.mt5_connector import MT5Connector
from market.candles import add_indicators, merge_htf_context
from market.spread import get_spread

from strategy.htf_bias import get_bias
from strategy.structure import classify_structure, premium_discount, detect_inducement
from strategy.liquidity import liquidity_sweep, sweep_supports_direction
from strategy.fvg import detect_fvg, detect_fvg_zones, price_in_fvg
from strategy.order_blocks import detect_order_block, detect_ob_zones, price_in_ob
from strategy.manipulation import manipulation_score
from strategy.candle_confirm import get_candle_confirmation
from strategy.session import is_valid_session, current_session
from strategy.scoring import calculate_score

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
                          TELEGRAM_ENABLED, TELEGRAM_NOTIFY_TRADES)

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

        # ── HTF bias ──────────────────────────────────────────────────────────
        bias = get_bias(df_h1)   # bias from H1
        if bias == "RANGE":
            logger.info(f"{symbol} H1 in range — skipping")
            return

        direction = "BUY" if bias == "BULLISH" else "SELL"

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
        )
        sl = exits["sl"]
        tp = exits["tp"]

        # ── Position sizing ───────────────────────────────────────────────────
        balance = get_balance()
        volume  = lot_size(symbol, exits["sl_dist"], balance)

        # ── Execute ───────────────────────────────────────────────────────────
        result = self.executor.execute(symbol, direction, volume, sl, tp)

        log_trade({
            "symbol":        symbol,
            "direction":     direction,
            "score":         score,
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
