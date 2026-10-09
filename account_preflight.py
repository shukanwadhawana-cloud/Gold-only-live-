"""Read-only Binance account and BTCUSDT feasibility preflight.

This module NEVER places, modifies, or cancels an order. It checks the
authenticated account, discovers the live BTCUSDT contract rules, and—when a
fresh strategy signal exists—calculates whether small capital caps can meet
the exchange minimums.
"""
from decimal import Decimal, InvalidOperation
import os

from exchange_adapter import make_exchange, btc_market, balance_usdt, minimum_notional
from market_data import get_btc_bars
from strategy import latest_executable_signal
from config import (CAPITAL_CAP_USDT, FRESHNESS_BARS, MAX_RISK_USDT, RISK_FRACTION, LEVERAGE, ESTIMATED_TAKER_FEE_RATE, ESTIMATED_SLIPPAGE_RATE)

CAPS = tuple(sorted({Decimal("5"), Decimal("10"), Decimal("20"), Decimal("50"), CAPITAL_CAP_USDT}))


def d(value, default=Decimal("0")):
    try:
        return Decimal(str(value)) if value is not None else default
    except (InvalidOperation, ValueError, TypeError):
        return default


def floor_to_step(value, step):
    if step <= 0:
        return value
    return (value // step) * step


def market_rules(m):
    limits = m.get("limits") or {}
    precision = m.get("precision") or {}
    amount_min = d((limits.get("amount") or {}).get("min"))
    cost_min = minimum_notional(m)
    amount_precision = precision.get("amount")
    price_precision = precision.get("price")
    contract_size = d(m.get("contractSize"), Decimal("1"))
    return {
        "min_qty": amount_min,
        "min_notional": cost_min,
        "amount_precision": amount_precision,
        "price_precision": price_precision,
        "contract_size": contract_size,
    }


def feasibility(balance, entry, sl, rules):
    price_risk = abs(entry - sl)
    if price_risk <= 0:
        raise ValueError("Signal Entry and SL must differ.")

    results = []
    for cap in CAPS:
        active = min(balance, cap)
        risk = min(MAX_RISK_USDT, active * RISK_FRACTION)
        risk_per_contract = price_risk * rules["contract_size"]
        round_trip_cost_rate = Decimal("2") * (ESTIMATED_TAKER_FEE_RATE + ESTIMATED_SLIPPAGE_RATE)
        estimated_cost_per_contract = entry * rules["contract_size"] * round_trip_cost_rate
        total_risk_per_contract = risk_per_contract + estimated_cost_per_contract
        risk_qty = risk / total_risk_per_contract
        capital_qty = active / (entry * rules["contract_size"])
        raw_qty = min(risk_qty, capital_qty)

        # Let CCXT apply exchange precision/step rules where possible.
        qty = raw_qty
        if rules["amount_precision"] is not None:
            # CCXT precision may be decimal places for Binance.
            try:
                qty = d(str(raw_qty))
            except Exception:
                pass

        notional = qty * entry * rules["contract_size"]
        meets_qty = qty >= rules["min_qty"]
        meets_notional = notional >= rules["min_notional"]
        estimated_stop_loss = qty * risk_per_contract
        estimated_round_trip_fee = notional * Decimal("2") * ESTIMATED_TAKER_FEE_RATE
        estimated_round_trip_slippage = notional * Decimal("2") * ESTIMATED_SLIPPAGE_RATE
        estimated_total_risk = estimated_stop_loss + estimated_round_trip_fee + estimated_round_trip_slippage
        risk_limit_pass = estimated_total_risk <= risk
        results.append({
            "cap": cap,
            "active_capital": active,
            "risk_budget": risk,
            "price_risk": price_risk,
            "raw_qty": raw_qty,
            "notional": notional,
            "min_qty": rules["min_qty"],
            "min_notional": rules["min_notional"],
            "meets_minimums": meets_qty and meets_notional and risk_limit_pass,
            "estimated_stop_loss_usdt": estimated_stop_loss,
            "estimated_round_trip_fee_usdt": estimated_round_trip_fee,
            "estimated_round_trip_slippage_usdt": estimated_round_trip_slippage,
            "estimated_total_risk_usdt": estimated_total_risk,
            "risk_limit_pass": risk_limit_pass,
        })
    return results


def main():
    print("=== BINANCE BITCOIN ACCOUNT PREFLIGHT (READ ONLY) ===")
    print("Order placement: NEVER")
    print("Order modification/cancellation: NEVER")
    print("Credentials: read from environment only; never printed")

    if not os.getenv("BINANCE_API_KEY") or not os.getenv("BINANCE_API_SECRET"):
        raise SystemExit("PREFLIGHT_BLOCKED: BINANCE_API_KEY/BINANCE_API_SECRET are not configured.")

    ex = make_exchange()

    # Authentication/account permission check.
    try:
        balance = balance_usdt(ex)
    except Exception as exc:
        raise SystemExit(f"ACCOUNT_CHECK_FAILED: {type(exc).__name__}: {exc}")

    try:
        market = btc_market(ex)
    except Exception as exc:
        raise SystemExit(f"BTC_MARKET_CHECK_FAILED: {type(exc).__name__}: {exc}")

    rules = market_rules(market)
    symbol = market["symbol"]
    ticker = ex.fetch_ticker(symbol)
    last = d(ticker.get("last"))

    print(f"Account USDT total: {balance}")
    print(f"BTC exchange id: {market.get('id')}")
    print(f"BTC CCXT symbol: {symbol}")
    print(f"Active: {market.get('active')}")
    print(f"Contract: {market.get('contract')} | Swap: {market.get('swap')} | Leverage lock: {LEVERAGE}x")
    print(f"Contract size: {rules['contract_size']}")
    print(f"Minimum quantity: {rules['min_qty']}")
    print(f"Minimum notional: {rules['min_notional']}")
    print(f"Price precision: {rules['price_precision']}")
    print(f"Amount precision: {rules['amount_precision']}")
    print(f"Current BTC price: {last}")

    # Strategy signal check is deliberately read-only and uses the same signal engine.
    df15 = get_btc_bars("15m")
    df1h = get_btc_bars("1h")
    if len(df15) < 100 or len(df1h) < 50:
        print("SIGNAL: unavailable — not enough Bitcoin candles.")
        return

    sig = latest_executable_signal(df15, df1h, FRESHNESS_BARS)
    if not sig:
        print("SIGNAL: no fresh HIGH-confidence executable Bitcoin signal right now.")
        print("Feasibility cannot be calculated without an actual Entry → SL distance.")
        return

    entry = d(sig["entry"])
    sl = d(sig["sl"])
    print(f"Signal: {sig['type']} | Entry={entry} | SL={sl} | TP={sig['tp']}")
    print(f"Entry → SL distance: {abs(entry - sl)}")

    print("\n=== CAPITAL FEASIBILITY ===")
    for row in feasibility(balance, entry, sl, rules):
        print(
            f"CAP ${row['cap']}: active={row['active_capital']} | "
            f"1R budget={row['risk_budget']} | qty={row['raw_qty']} | "
            f"notional={row['notional']} | est. SL={row['estimated_stop_loss_usdt']:.4f} | "
            f"fees={row['estimated_round_trip_fee_usdt']:.4f} | "
            f"slippage={row['estimated_round_trip_slippage_usdt']:.4f} | "
            f"total risk={row['estimated_total_risk_usdt']:.4f}/"
            f"{row['risk_budget']} | minimums={'PASS' if row['meets_minimums'] else 'FAIL'}"
        )

    print("\nPREFLIGHT COMPLETE: READ ONLY. No order was sent.")


if __name__ == "__main__":
    main()
