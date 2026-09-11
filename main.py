"""Gold-only bot runner.

Default mode is read-only/dry-run. With Binance credentials present it can
run the account/contract preflight, but no real order is placed until the
explicit live gates are enabled in a later step.
"""
import os
from strategy import latest_executable_signal
from market_data import get_gold_bars
from config import CAPITAL_CAP_USDT, MAX_RISK_USDT, RISK_FRACTION, FRESHNESS_BARS


def main():
    print("=== GOLD-ONLY BOT ===")
    print("Symbol: XAUUSDT only")
    print(f"Capital cap: {CAPITAL_CAP_USDT} USDT")
    print(f"Risk budget: min({MAX_RISK_USDT} USDT, active_capital × {RISK_FRACTION})")
    print("Live orders: BLOCKED by default")

    df15 = get_gold_bars("15m")
    df1h = get_gold_bars("1h")
    if len(df15) < 100 or len(df1h) < 50:
        raise RuntimeError("Not enough Gold candles for strategy.")

    sig = latest_executable_signal(df15, df1h, FRESHNESS_BARS)
    if not sig:
        print("GOLD: no fresh HIGH-confidence executable signal.")
        return

    print("\n=== CURRENT GOLD SIGNAL ===")
    print(f"Direction: {sig['type']}")
    print(f"Entry: {sig['entry']:.5f}")
    print(f"SL: {sig['sl']:.5f}")
    print(f"TP: {sig['tp']:.5f}")
    print(f"Structure: {sig['structure']}")
    print(f"Session: {sig['session_ok']} | HTF: {sig['htf_ok']} | RR: 1:4")

    if os.getenv("LIVE_TRADING", "false").lower() == "true":
        raise RuntimeError("LIVE_TRADING is intentionally still blocked in this build. Run preflight first.")
    print("DRY RUN: no exchange order placed.")


if __name__ == "__main__":
    main()
