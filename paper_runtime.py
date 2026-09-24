"""Continuous, restart-safe Gold-only paper runtime for Voroa.

No Binance authentication, Telegram, or real orders are used here.
Only closed candles are used for signals and exits. State/audit files make the
paper session durable across worker restarts.
"""
from __future__ import annotations

import time
from decimal import Decimal

from config import CAPITAL_CAP_USDT, MAX_RISK_USDT, RISK_FRACTION, FRESHNESS_BARS
from market_data import get_gold_bars
from paper_state import audit, load_state, reconcile_trade_stats, save_state
from strategy import latest_executable_signal

POLL_SECONDS = 60
ZERO = Decimal("0")
TIMEFRAME_SECONDS = 15 * 60
STALE_BAR_MULTIPLIER = 3


def gold_market_closed(now) -> bool:
    """Return True during normal CME Gold weekend/daily maintenance windows."""
    weekday = now.weekday()
    utc_minutes = now.hour * 60 + now.minute
    if weekday == 5:  # Saturday
        return True
    if weekday == 6 and utc_minutes < 22 * 60:  # Sunday before reopen
        return True
    if weekday == 4 and utc_minutes >= 21 * 60:  # Friday after close
        return True
    if weekday in (0, 1, 2, 3) and 21 * 60 <= utc_minutes < 22 * 60:
        return True
    return False


def stale_bar(bar_time, now) -> bool:
    """Fail closed when the completed candle is not advancing during open hours."""
    age_seconds = max(0.0, (now - bar_time).total_seconds())
    return age_seconds > TIMEFRAME_SECONDS * STALE_BAR_MULTIPLIER


def money(value: Decimal) -> str:
    return f"{value:.4f}"


def d(value) -> Decimal:
    return Decimal(str(value))


def risk_budget() -> Decimal:
    return min(MAX_RISK_USDT, CAPITAL_CAP_USDT * RISK_FRACTION)


def paper_qty(entry: Decimal, sl: Decimal) -> Decimal:
    risk_distance = abs(entry - sl)
    if risk_distance <= ZERO:
        return ZERO
    # Research-mode quantity only; exchange contract size/minimums are NOT assumed.
    return risk_budget() / risk_distance


def execution_direction(strategy_direction: str) -> str:
    """Gold-only execution is intentionally inverted while strategy signals remain unchanged."""
    return "SELL" if strategy_direction == "BUY" else "BUY" if strategy_direction == "SELL" else strategy_direction


def signal_key(signal: dict) -> str:
    return f"{signal['time']}|{signal['type']}|{signal['entry']}|{signal['sl']}"


def trail_stop(direction: str, entry: Decimal, current_sl: Decimal, initial_r: Decimal, r_now: Decimal) -> Decimal:
    if direction == "BUY":
        new_sl = current_sl
        levels = ((Decimal("0.6"), ZERO), (Decimal("1.2"), Decimal("0.6")),
                  (Decimal("1.8"), Decimal("1.2")), (Decimal("2.4"), Decimal("1.8")),
                  (Decimal("3.0"), Decimal("2.4")), (Decimal("3.6"), Decimal("3.0")))
        for trigger, lock_r in levels:
            if r_now >= trigger:
                new_sl = max(new_sl, entry + initial_r * lock_r)
        return new_sl
    new_sl = current_sl
    levels = ((Decimal("0.6"), ZERO), (Decimal("1.2"), Decimal("0.6")),
              (Decimal("1.8"), Decimal("1.2")), (Decimal("2.4"), Decimal("1.8")),
              (Decimal("3.0"), Decimal("2.4")), (Decimal("3.6"), Decimal("3.0")))
    for trigger, lock_r in levels:
        if r_now >= trigger:
            new_sl = min(new_sl, entry - initial_r * lock_r)
    return new_sl


def close_position(state: dict, reason: str, exit_price: Decimal, bar_time, signal=None) -> None:
    pos = state["open_position"]
    entry = d(pos["entry"])
    initial_r = d(pos["initial_r"])
    direction = pos["type"]
    pnl_r = ((exit_price - entry) / initial_r) if direction == "BUY" else ((entry - exit_price) / initial_r)
    pnl_usdt = pnl_r * risk_budget()
    state["realized_pnl_usdt"] = str(d(state["realized_pnl_usdt"]) + pnl_usdt)
    state["equity_usdt"] = str(d(state["equity_usdt"]) + pnl_usdt)
    state["trades"] = int(state["trades"]) + 1
    if pnl_r > ZERO:
        state["wins"] = int(state["wins"]) + 1
    elif pnl_r < ZERO:
        state["losses"] = int(state["losses"]) + 1

    pos["exit"] = str(exit_price)
    pos["exit_time"] = str(bar_time)
    pos["exit_reason"] = reason
    pos["result_r"] = str(pnl_r)
    pos["result_usdt"] = str(pnl_usdt)
    pos["mae_r"] = str(d(pos.get("mae_r", "0")))
    pos["mfe_r"] = str(d(pos.get("mfe_r", "0")))

    print(f"PAPER EXIT: {direction} {reason} | entry={money(entry)} exit={money(exit_price)} result={pnl_r:.2f}R / {pnl_usdt:.4f} USDT", flush=True)
    audit("EXIT", **pos)
    state["open_position"] = None
    save_state(state)


def run() -> None:
    print("=== GOLD-ONLY PAPER RUNTIME ===", flush=True)
    print("Mode: PAPER / READ-ONLY MARKET DATA", flush=True)
    print("Exchange authentication: NOT USED", flush=True)
    print("Live orders: BLOCKED", flush=True)
    print(f"Capital cap: {CAPITAL_CAP_USDT} USDT", flush=True)
    print(f"Risk budget: min({MAX_RISK_USDT} USDT, active_capital × {RISK_FRACTION})", flush=True)
    print(f"Poll interval: {POLL_SECONDS}s", flush=True)

    state = load_state()
    state = reconcile_trade_stats(state)
    if d(state.get("equity_usdt", "0")) <= ZERO:
        state["equity_usdt"] = str(CAPITAL_CAP_USDT)
    save_state(state)
    audit("RUNTIME_START", equity_usdt=state["equity_usdt"], capital_cap_usdt=str(CAPITAL_CAP_USDT))

    cycle = 0
    while True:
        cycle += 1
        try:
            df15 = get_gold_bars("15m")
            df1h = get_gold_bars("1h")
            if len(df15) < 100 or len(df1h) < 50:
                print(f"CYCLE {cycle}: insufficient Gold candles; retrying.", flush=True)
                time.sleep(POLL_SECONDS)
                continue

            # Signals and simulated fills use the last CLOSED 15m candle only.
            last_bar = df15.iloc[-2]
            current_price = d(last_bar["Close"])
            current_high = d(last_bar["High"])
            current_low = d(last_bar["Low"])
            bar_time = df15.index[-2]
            now = __import__("pandas").Timestamp.now(tz="UTC")

            # Weekend/maintenance candles can legitimately stop advancing.
            # During open hours, stale data is fail-closed: no signals or trades.
            if stale_bar(bar_time, now):
                if gold_market_closed(now):
                    print(
                        f"CYCLE {cycle}: GOLD MARKET CLOSED | last_closed_bar={bar_time} | waiting for reopen.",
                        flush=True,
                    )
                else:
                    age_minutes = (now - bar_time).total_seconds() / 60.0
                    print(
                        f"CYCLE {cycle}: STALE GOLD DATA | last_closed_bar={bar_time} | "
                        f"age={age_minutes:.1f}m | signals/orders skipped.",
                        flush=True,
                    )
                    audit(
                        "STALE_DATA",
                        cycle=cycle,
                        bar_time=str(bar_time),
                        age_minutes=age_minutes,
                    )
                time.sleep(POLL_SECONDS)
                continue

            signal = latest_executable_signal(df15, df1h, FRESHNESS_BARS)

            pos = state.get("open_position")
            if pos:
                direction = pos["type"]
                entry = d(pos["entry"])
                sl = d(pos["sl"])
                tp = d(pos["tp"])
                initial_r = d(pos["initial_r"])

                # MAE/MFE are updated from the closed candle range, never future candles.
                if direction == "BUY":
                    favorable_r = (current_high - entry) / initial_r
                    adverse_r = (current_low - entry) / initial_r
                else:
                    favorable_r = (entry - current_low) / initial_r
                    adverse_r = (entry - current_high) / initial_r
                pos["mfe_r"] = str(max(d(pos.get("mfe_r", "0")), favorable_r))
                pos["mae_r"] = str(min(d(pos.get("mae_r", "0")), adverse_r))

                # Conservative same-candle rule: if SL and TP are both touched,
                # SL is assumed to have happened first.
                if direction == "BUY":
                    sl_hit = current_low <= sl
                    tp_hit = current_high >= tp
                else:
                    sl_hit = current_high >= sl
                    tp_hit = current_low <= tp

                if sl_hit:
                    close_position(state, "SL", sl, bar_time)
                    pos = None
                elif tp_hit:
                    close_position(state, "TP", tp, bar_time)
                    pos = None
                else:
                    r_now = favorable_r
                    new_sl = trail_stop(direction, entry, sl, initial_r, r_now)
                    if new_sl != sl:
                        pos["sl"] = str(new_sl)
                        print(f"PAPER TRAIL: {display_direction(direction)} stop -> {money(new_sl)} at {r_now:.2f}R", flush=True)
                        audit("TRAIL", direction=direction, bar_time=str(bar_time), old_sl=str(sl), new_sl=str(new_sl), r_now=str(r_now))
                        save_state(state)

                    # An opposite confirmed HIGH signal closes the paper position.
                    if signal and execution_direction(signal["type"]) != direction:
                        close_position(state, "OPPOSITE_SIGNAL", current_price, bar_time, signal)
                        pos = None

            if state.get("open_position") is None and signal:
                key = signal_key(signal)
                if key != state.get("last_signal_key"):
                    entry = d(signal["entry"])
                    sl = d(signal["sl"])
                    tp = d(signal["tp"])
                    initial_r = abs(entry - sl)
                    if initial_r <= ZERO:
                        raise RuntimeError("Rejected signal with zero SL distance.")
                    qty = paper_qty(entry, sl)
                    state["open_position"] = {
                        "type": execution_direction(signal["type"]),
                        "entry": str(entry),
                        "sl": str(sl),
                        "tp": str(tp),
                        "initial_r": str(initial_r),
                        "qty_research": str(qty),
                        "signal_time": str(signal["time"]),
                        "entry_time": str(bar_time),
                        "structure": signal["structure"],
                        "mae_r": "0",
                        "mfe_r": "0",
                        "trade_id": key,
                        "strategy_direction": signal["type"],
                    }
                    state["last_signal_key"] = key
                    print(f"PAPER ENTRY: {state['open_position']['type']} | bar={signal['time']} | entry={money(entry)} SL={money(sl)} TP={money(tp)} | theoretical_qty={qty:.8f} units | structure={signal['structure']}", flush=True)
                    audit("ENTRY", **state["open_position"])
                    save_state(state)

            status = "OPEN" if state.get("open_position") else "FLAT"
            print(
                f"CYCLE {cycle}: bar={bar_time} close={money(current_price)} | status={status} | "
                f"equity={money(d(state['equity_usdt']))} | closed={state['trades']} "
                f"wins={state['wins']} losses={state['losses']} breakeven={state.get('breakevens', 0)} "
                f"open={1 if state.get('open_position') else 0} | "
                f"fresh_high_signal={'YES' if signal else 'NO'}",
                flush=True,
            )
            save_state(state)
        except Exception as exc:
            print(f"CYCLE {cycle}: DATA/STRATEGY ERROR: {type(exc).__name__}: {exc}", flush=True)
            audit("ERROR", cycle=cycle, error_type=type(exc).__name__, error=str(exc))

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
