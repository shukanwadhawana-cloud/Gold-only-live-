"""Binance-first Bitcoin-only exchange adapter.

The adapter discovers the actual BTCUSDT market from exchange metadata rather
than guessing a CCXT symbol. Live order placement is blocked unless both
LIVE_TRADING and ALLOW_LIVE_ORDERS are true.
"""
from decimal import Decimal
import os
import ccxt
from config import SYMBOL, CAPITAL_CAP_USDT, risk_budget, LEVERAGE, ESTIMATED_TAKER_FEE_RATE, ESTIMATED_SLIPPAGE_RATE


def make_exchange():
    name = os.getenv("EXCHANGE", "binance").lower()
    if name != "binance":
        raise ValueError("This live build is intentionally Binance-only. Use Binance BTCUSDT perpetual.")
    ex = ccxt.binance({
        "enableRateLimit": True,
        "apiKey": os.getenv("BINANCE_API_KEY", ""),
        "secret": os.getenv("BINANCE_API_SECRET", ""),
        "options": {"defaultType": "swap"},
    })
    if os.getenv("SANDBOX", "false").lower() == "true":
        ex.set_sandbox_mode(True)
    return ex


def btc_market(ex=None):
    ex = ex or make_exchange()
    markets = ex.load_markets()
    matches = [m for m in markets.values() if str(m.get("id", "")).upper() == SYMBOL and m.get("contract") and m.get("swap") and str(m.get("settle", "")).upper() == "USDT"]
    if not matches:
        raise RuntimeError("Binance account/API did not expose the BTCUSDT USDⓈ-M perpetual.")
    return matches[0]


def set_one_x_leverage(ex, market):
    if LEVERAGE != 1:
        raise RuntimeError("Live leverage safety gate violated: LEVERAGE must be 1.")
    result = ex.set_leverage(1, market["symbol"])
    accepted = result.get("leverage") if isinstance(result, dict) else None
    if accepted is not None and int(accepted) != 1:
        raise RuntimeError(f"Binance did not confirm 1x leverage: {result}")
    return result


def market_info():
    ex = make_exchange(); m = btc_market(ex)
    return {
        "exchange": "binance",
        "id": m["id"],
        "symbol": m["symbol"],
        "active": m.get("active"),
        "contract": m.get("contract"),
        "swap": m.get("swap"),
        "settle": m.get("settle"),
        "contract_size": m.get("contractSize"),
        "limits": m.get("limits"),
        "precision": m.get("precision"),
        "info": m.get("info", {}),
        "leverage": LEVERAGE,
    }


def balance_usdt(ex=None):
    ex = ex or make_exchange()
    bal = ex.fetch_balance({"type": "swap"})
    total = bal.get("total", {}).get("USDT")
    if total is None:
        total = bal.get("free", {}).get("USDT", 0)
    return Decimal(str(total or 0))


def ticker(ex=None):
    ex = ex or make_exchange(); m = btc_market(ex)
    return ex.fetch_ticker(m["symbol"])


def _floor_amount(ex, symbol, amount):
    try:
        return Decimal(str(ex.amount_to_precision(symbol, float(amount))))
    except Exception:
        return Decimal(str(amount))


def minimum_notional(m):
    """Return the strictest exchange minimum from CCXT limits and Binance filters."""
    limits = m.get("limits") or {}
    cost_min = (limits.get("cost") or {}).get("min")
    minimum = Decimal(str(cost_min)) if cost_min not in (None, "") else Decimal("0")
    info = m.get("info") or {}
    for rule in info.get("filters") or []:
        if str(rule.get("filterType", "")).upper() not in {"MIN_NOTIONAL", "NOTIONAL"}:
            continue
        raw = rule.get("notional")
        if raw is None:
            raw = rule.get("minNotional")
        if raw is None:
            continue
        try:
            minimum = max(minimum, Decimal(str(raw)))
        except Exception:
            continue
    return minimum


def size_for_risk(ex, direction, entry, sl, balance):
    """Calculate quantity using the exchange's actual contract size and limits."""
    m = btc_market(ex)
    risk_budget_usdt = risk_budget(balance)
    price_risk = abs(Decimal(str(entry)) - Decimal(str(sl)))
    if price_risk <= 0:
        raise ValueError("Entry and SL must differ.")

    contract_size = Decimal(str(m.get("contractSize") or 1))
    risk_per_contract = price_risk * contract_size
    # Reserve round-trip taker fees and slippage within the same $2 risk cap.
    round_trip_cost_rate = Decimal("2") * (ESTIMATED_TAKER_FEE_RATE + ESTIMATED_SLIPPAGE_RATE)
    estimated_cost_per_contract = Decimal(str(entry)) * contract_size * round_trip_cost_rate
    total_risk_per_contract = risk_per_contract + estimated_cost_per_contract
    raw_qty = risk_budget_usdt / total_risk_per_contract
    # At hard-locked 1x, notional cannot exceed the active capital allocation.
    capital_cap = min(Decimal(str(balance)), CAPITAL_CAP_USDT)
    capital_qty = capital_cap / (Decimal(str(entry)) * contract_size)
    raw_qty = min(raw_qty, capital_qty)
    qty = _floor_amount(ex, m["symbol"], raw_qty)

    limits = m.get("limits") or {}
    amount_min = ((limits.get("amount") or {}).get("min"))
    min_qty = Decimal(str(amount_min)) if amount_min else Decimal("0")
    min_cost = minimum_notional(m)
    notional = qty * Decimal(str(entry)) * contract_size
    estimated_stop_loss = qty * risk_per_contract
    estimated_round_trip_fee = notional * Decimal("2") * ESTIMATED_TAKER_FEE_RATE
    estimated_round_trip_slippage = notional * Decimal("2") * ESTIMATED_SLIPPAGE_RATE
    estimated_total_risk = estimated_stop_loss + estimated_round_trip_fee + estimated_round_trip_slippage

    return {
        "symbol": m["symbol"],
        "qty": qty,
        "risk_budget_usdt": risk_budget_usdt,
        "price_risk": price_risk,
        "contract_size": contract_size,
        "risk_per_contract": risk_per_contract,
        "notional": notional,
        "min_qty": min_qty,
        "min_notional": min_cost,
        "qty_meets_min": qty >= min_qty,
        "notional_meets_min": notional >= min_cost,
        "capital_cap_usdt": min(balance, CAPITAL_CAP_USDT),
        "estimated_stop_loss_usdt": estimated_stop_loss,
        "estimated_round_trip_fee_usdt": estimated_round_trip_fee,
        "estimated_round_trip_slippage_usdt": estimated_round_trip_slippage,
        "estimated_total_risk_usdt": estimated_total_risk,
        "risk_limit_pass": estimated_total_risk <= risk_budget_usdt,
    }


def account_snapshot():
    ex = make_exchange(); m = btc_market(ex); bal = balance_usdt(ex)
    tick = ex.fetch_ticker(m["symbol"])
    return {
        "balance_usdt": str(bal),
        "capital_cap_usdt": str(min(bal, CAPITAL_CAP_USDT)),
        "symbol": m["symbol"],
        "exchange_id": m["id"],
        "last": tick.get("last"),
        "contract_size": m.get("contractSize"),
        "limits": m.get("limits"),
        "precision": m.get("precision"),
        "market_info": m.get("info", {}),
    }


def open_market(direction, amount, price=None):
    if os.getenv("LIVE_TRADING", "false").lower() != "true" or os.getenv("ALLOW_LIVE_ORDERS", "false").lower() != "true":
        raise RuntimeError("LIVE_TRADING/ALLOW_LIVE_ORDERS are not both true; live order blocked.")
    ex = make_exchange(); m = btc_market(ex); set_one_x_leverage(ex, m)
    side = "buy" if direction == "BUY" else "sell"
    return ex.create_order(m["symbol"], "market", side, float(amount))


def protective_order(order_type, direction, amount, stop_price):
    if os.getenv("LIVE_TRADING", "false").lower() != "true" or os.getenv("ALLOW_LIVE_ORDERS", "false").lower() != "true":
        raise RuntimeError("Live protective order blocked by safety gate.")
    ex = make_exchange(); m = btc_market(ex)
    close_side = "sell" if direction == "BUY" else "buy"
    params = {"stopPrice": float(stop_price), "reduceOnly": True, "workingType": "MARK_PRICE"}
    return ex.create_order(m["symbol"], order_type, close_side, float(amount), None, params)


def close_market(direction, amount):
    return _close_market(direction, amount)


def _close_market(direction, amount):
    if os.getenv("LIVE_TRADING", "false").lower() != "true" or os.getenv("ALLOW_LIVE_ORDERS", "false").lower() != "true":
        raise RuntimeError("Live close blocked by safety gate.")
    ex = make_exchange(); m = btc_market(ex)
    side = "sell" if direction == "BUY" else "buy"
    return ex.create_order(m["symbol"], "market", side, float(amount), None, {"reduceOnly": True})
