"""Read-only Binance/XAUUSDT preflight.

This never places an order. It tells us whether the exchange's current
contract rules make the chosen capital/risk settings feasible.
"""
from decimal import Decimal
from exchange_adapter import make_exchange, gold_market, balance_usdt, size_for_risk
from market_data import get_gold_bars
from paper_runtime import gold_market_closed, stale_bar
from strategy import latest_executable_signal
from config import CAPITAL_CAP_USDT, risk_budget


def main():
    ex = make_exchange()
    m = gold_market(ex)
    balance = balance_usdt(ex)
    print("=== GOLD LIVE PREFLIGHT (READ ONLY) ===")
    print("Exchange: Binance")
    print(f"Exchange symbol: {m['id']} / CCXT: {m['symbol']}")
    print(f"Contract: {m.get('contract')} | Swap: {m.get('swap')} | Active: {m.get('active')}")
    print(f"Wallet USDT: {balance}")
    print(f"Capital cap: {min(balance, CAPITAL_CAP_USDT)} USDT (configured ceiling {CAPITAL_CAP_USDT})")
    print(f"Risk budget: {risk_budget(balance)} USDT")
    print(f"Limits: {m.get('limits')}")
    print(f"Precision: {m.get('precision')}")

    df15 = get_gold_bars("15m")
    df1h = get_gold_bars("1h")
    if len(df15) < 2:
        print("RESULT: insufficient closed 15m Gold data. DO NOT trade.")
        return

    last_bar = df15.iloc[-2]
    bar_time = df15.index[-2]
    import pandas as pd
    now = pd.Timestamp.now(tz="UTC")

    if gold_market_closed(now):
        print(f"RESULT: Gold market is in a scheduled closed window. DO NOT trade. Last closed bar: {bar_time}")
        return
    if stale_bar(bar_time, now):
        age_minutes = (now - bar_time).total_seconds() / 60.0
        print(f"RESULT: Gold data is stale ({age_minutes:.1f}m old). DO NOT trade.")
        return

    sig = latest_executable_signal(df15, df1h)
    if not sig:
        print("No fresh HIGH-confidence Gold signal right now; contract/account checks above are still valid.")
        return

    print("\n=== CURRENT STRATEGY SIZING EXAMPLE ===")
    print(f"Signal: {sig['type']} {sig['structure']} @ {sig['entry']}")
    print(f"SL: {sig['sl']} | TP: {sig['tp']}")
    s = size_for_risk(ex, sig['type'], sig['entry'], sig['sl'], balance)
    for k, v in s.items():
        print(f"{k}: {v}")
    if not s['qty_meets_min'] or not s['notional_meets_min']:
        print("RESULT: current configured risk/capital is too small for the exchange minimum. DO NOT trade.")
    else:
        print("RESULT: minimum-order constraints are met for this signal. Live trading is still disabled by default.")


if __name__ == "__main__":
    main()
