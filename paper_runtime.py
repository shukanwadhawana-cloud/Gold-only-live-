"""Continuous Gold-only paper runtime for Voroa.

No Binance authentication, no Telegram, and no real orders are used here.
The existing Gold SMC strategy is evaluated continuously against free market data.
"""
from __future__ import annotations

import time
from decimal import Decimal
from pathlib import Path

from config import CAPITAL_CAP_USDT, MAX_RISK_USDT, RISK_FRACTION, FRESHNESS_BARS
from market_data import get_gold_bars
from strategy import latest_executable_signal

POLL_SECONDS = 60


def money(value: Decimal) -> str:
    return f"{value:.4f}"


def d(value) -> Decimal:
    return Decimal(str(value))


def paper_qty(entry: Decimal, sl: Decimal) -> Decimal:
    risk_distance = abs(entry - sl)
    if risk_distance <= 0:
        return Decimal("0")
    risk_budget = min(MAX_RISK_USDT, CAPITAL_CAP_USDT * RISK_FRACTION)
    # Research-mode quantity only. Exchange contract size/minimums are NOT assumed.
    return risk_budget / risk_distance


def run() -> None:
    print("=== GOLD-ONLY PAPER RUNTIME ===", flush=True)
    print("Mode: PAPER / READ-ONLY MARKET DATA", flush=True)
    print("Exchange authentication: NOT USED", flush=True)
    print("Live orders: BLOCKED", flush=True)
    print(f"Capital cap: {CAPITAL_CAP_USDT} USDT", flush=True)
    print(f"Risk budget: min({MAX_RISK_USDT} USDT, active_capital × {RISK_FRACTION})", flush=True)
    print(f"Poll interval: {POLL_SECONDS}s", flush=True)

    open_position = None
    last_signal_key = None
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

            signal = latest_executable_signal(df15, df1h, FRESHNESS_BARS)
            last_bar = df15.iloc[-2]
            current_price = d(last_bar["Close"])
            current_high = d(last_bar["High"])
            current_low = d(last_bar["Low"])
            bar_time = df15.index[-2]

            if open_position:
                direction = open_position["type"]
                entry = open_position["entry"]
                sl = open_position["sl"]
                tp = open_position["tp"]
                initial_r = open_position["initial_r"]

                hit = None
                if direction == "BUY":
                    if current_low <= sl:
                        hit = ("SL", sl)
                    elif current_high >= tp:
                        hit = ("TP", tp)
                    else:
                        r_now = (current_price - entry) / initial_r
                        if r_now >= Decimal("0.6"):
                            new_sl = max(sl, entry)
                            if r_now >= Decimal("1.2"):
                                new_sl = max(new_sl, entry + initial_r * Decimal("0.6"))
                            if r_now >= Decimal("1.8"):
                                new_sl = max(new_sl, entry + initial_r * Decimal("1.2"))
                            if r_now >= Decimal("2.4"):
                                new_sl = max(new_sl, entry + initial_r * Decimal("1.8"))
                            if r_now >= Decimal("3.0"):
                                new_sl = max(new_sl, entry + initial_r * Decimal("2.4"))
                            if r_now >= Decimal("3.6"):
                                new_sl = max(new_sl, entry + initial_r * Decimal("3.0"))
                            if new_sl > sl:
                                open_position["sl"] = new_sl
                                sl = new_sl
                                print(f"PAPER TRAIL: BUY stop -> {money(sl)} at {r_now:.2f}R", flush=True)
                else:
                    if current_high >= sl:
                        hit = ("SL", sl)
                    elif current_low <= tp:
                        hit = ("TP", tp)
                    else:
                        r_now = (entry - current_price) / initial_r
                        if r_now >= Decimal("0.6"):
                            new_sl = min(sl, entry)
                            if r_now >= Decimal("1.2"):
                                new_sl = min(new_sl, entry - initial_r * Decimal("0.6"))
                            if r_now >= Decimal("1.8"):
                                new_sl = min(new_sl, entry - initial_r * Decimal("1.2"))
                            if r_now >= Decimal("2.4"):
                                new_sl = min(new_sl, entry - initial_r * Decimal("1.8"))
                            if r_now >= Decimal("3.0"):
                                new_sl = min(new_sl, entry - initial_r * Decimal("2.4"))
                            if r_now >= Decimal("3.6"):
                                new_sl = min(new_sl, entry - initial_r * Decimal("3.0"))
                            if new_sl < sl:
                                open_position["sl"] = new_sl
                                sl = new_sl
                                print(f"PAPER TRAIL: SELL stop -> {money(sl)} at {r_now:.2f}R", flush=True)

                if hit:
                    reason, exit_price = hit
                    pnl_r = ((exit_price - entry) / initial_r) if direction == "BUY" else ((entry - exit_price) / initial_r)
                    risk_budget = min(MAX_RISK_USDT, CAPITAL_CAP_USDT * RISK_FRACTION)
                    pnl_usdt = pnl_r * risk_budget
                    print(
                        f"PAPER EXIT: {direction} {reason} | entry={money(entry)} exit={money(exit_price)} "
                        f"result={pnl_r:.2f}R / {pnl_usdt:.4f} USDT",
                        flush=True,
                    )
                    open_position = None

            if open_position is None and signal:
                signal_key = f"{signal['time']}|{signal['type']}|{signal['entry']}|{signal['sl']}"
                if signal_key != last_signal_key:
                    entry = d(signal["entry"])
                    sl = d(signal["sl"])
                    tp = d(signal["tp"])
                    initial_r = abs(entry - sl)
                    qty = paper_qty(entry, sl)
                    open_position = {
                        "type": signal["type"],
                        "entry": entry,
                        "sl": sl,
                        "tp": tp,
                        "initial_r": initial_r,
                    }
                    last_signal_key = signal_key
                    print(
                        f"PAPER ENTRY: {signal['type']} | bar={signal['time']} | entry={money(entry)} "
                        f"SL={money(sl)} TP={money(tp)} | theoretical_qty={qty:.8f} units | "
                        f"structure={signal['structure']}",
                        flush=True,
                    )

            status = "OPEN" if open_position else "FLAT"
            print(
                f"CYCLE {cycle}: bar={bar_time} close={money(current_price)} | status={status} | "
                f"fresh_high_signal={'YES' if signal else 'NO'}",
                flush=True,
            )
        except Exception as exc:
            print(f"CYCLE {cycle}: DATA/STRATEGY ERROR: {type(exc).__name__}: {exc}", flush=True)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
