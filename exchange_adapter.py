"""Binance-first Gold-only exchange adapter.

The adapter discovers the actual XAUUSDT market from exchange metadata rather
than guessing a CCXT symbol. Live order placement is blocked unless both
LIVE_TRADING and ALLOW_LIVE_ORDERS are true.
"""
from decimal import Decimal, ROUND_DOWN
import os
import ccxt
from config import SYMBOL, CAPITAL_CAP_USDT, risk_budget


def make_exchange():
    name = os.getenv("EXCHANGE", "binance").lower()
    if name != "binance":
        raise ValueError("This live build is intentionally Binance-only. Use Binance for XAUUSDT.")
    ex = ccxt.binance({
        "enableRateLimit": True,
        "apiKey": os.getenv("BINANCE_API_KEY", ""),
        "secret": os.getenv("BINANCE_API_SECRET", ""),
        "options": {"defaultType": "swap"},
    })
    if os.getenv("SANDBOX", "false").lower() == "true":
        ex.set_sandbox_mode(True)
    return ex


def gold_market(ex=None):
    ex = ex or make_exchange()
    markets = ex.load_markets()
    # Prefer exact exchange id XAUUSDT and a swap/contract market.
    matches = [m for m in markets.values() if str(m.get("id", "")).upper() == SYMBOL and m.get("contract")]
    if not matches:
        matches = [m for m in markets.values() if "XAU" in str(m.get("id", "")).upper() and m.get("quote") == "USDT" and m.get("contract")]
    if not matches:
        raise RuntimeError("Binance account/API did not expose a contract market for XAUUSDT.")
    return matches[0]


def market_info():
    ex = make_exchange(); m = gold_market(ex)
    return {
        "exchange": "binance",
        "id": m["id"],
        "symbol": m["symbol"],
        "active": m.get("active"),
        "contract": m.get("contract"),
        "swap": m.get("swap"),
        "settle": m.get("settle"),
        "limits": m.get("limits"),
        "precision": m.get("precision"),
        "info": m.get("info", {}),
    }


def balance_usdt(ex=None):
    ex = ex or make_exchange()
    bal = ex.fetch_balance({"type": "swap"})
    total = bal.get("total", {}).get("USDT")
    if total is None:
        total = bal.get("free", {}).get("USDT", 0)
    return Decimal(str(total or 0))


def ticker(ex=None):
    ex = ex or make_exchange(); m = gold_market(ex)
    return ex.fetch_ticker(m["symbol"])


def _floor_amount(ex, symbol, amount):
    # CCXT precision is authoritative when available.
    try:
        return Decimal(str(ex.amount_to_precision(symbol, float(amount))))
    except Exception:
        return Decimal(str(amount))


def size_for_risk(ex, direction, entry, sl, balance):
    m = gold_market(ex); risk_budget_usdt = risk_budget(balance)
    price_risk = abs(Decimal(str(entry)) - Decimal(str(sl)))
    if price_risk <= 0:
        raise ValueError("Entry and SL must differ.")
    raw_qty = risk_budget_usdt / price_risk
    qty = _floor_amount(ex, m["symbol"], raw_qty)
    limits = m.get("limits") or {}; amount_min = ((limits.get("amount") or {}).get("min"))
    cost_min = ((limits.get("cost") or {}).get("min"))
    min_qty = Decimal(str(amount_min)) if amount_min else Decimal("0")
    min_cost = Decimal(str(cost_min)) if cost_min else Decimal("0")
    notional = qty * Decimal(str(entry))
    return {
        "symbol": m["symbol"], "qty": qty, "risk_budget_usdt": risk_budget_usdt,
        "price_risk": price_risk, "notional": notional,
        "min_qty": min_qty, "min_notional": min_cost,
        "qty_meets_min": qty >= min_qty,
        "notional_meets_min": notional >= min_cost,
        "capital_cap_usdt": min(balance, CAPITAL_CAP_USDT),
    }


def account_snapshot():
    ex = make_exchange(); m = gold_market(ex); bal = balance_usdt(ex)
    tick = ex.fetch_ticker(m["symbol"])
    return {"balance_usdt": str(bal), "capital_cap_usdt": str(min(bal, CAPITAL_CAP_USDT)),
            "symbol": m["symbol"], "exchange_id": m["id"], "last": tick.get("last"),
            "limits": m.get("limits"), "precision": m.get("precision"), "market_info": m.get("info", {})}


def open_market(direction, amount, price=None):
    if os.getenv("LIVE_TRADING", "false").lower() != "true" or os.getenv("ALLOW_LIVE_ORDERS", "false").lower() != "true":
        raise RuntimeError("LIVE_TRADING/ALLOW_LIVE_ORDERS are not both true; live order blocked.")
    ex = make_exchange(); m = gold_market(ex)
    side = "buy" if direction == "BUY" else "sell"
    return ex.create_order(m["symbol"], "market", side, float(amount))


def protective_order(order_type, direction, amount, stop_price):
    if os.getenv("LIVE_TRADING", "false").lower() != "true" or os.getenv("ALLOW_LIVE_ORDERS", "false").lower() != "true":
        raise RuntimeError("Live protective order blocked by safety gate.")
    ex = make_exchange(); m = gold_market(ex)
    close_side = "sell" if direction == "BUY" else "buy"
    params = {"stopPrice": float(stop_price), "reduceOnly": True, "workingType": "MARK_PRICE"}
    return ex.create_order(m["symbol"], order_type, close_side, float(amount), None, params)


def close_market(direction, amount):
    return protective_order("MARKET", direction, amount, None) if False else _close_market(direction, amount)


def _close_market(direction, amount):
    if os.getenv("LIVE_TRADING", "false").lower() != "true" or os.getenv("ALLOW_LIVE_ORDERS", "false").lower() != "true":
        raise RuntimeError("Live close blocked by safety gate.")
    ex = make_exchange(); m = gold_market(ex)
    side = "sell" if direction == "BUY" else "buy"
    return ex.create_order(m["symbol"], "market", side, float(amount), None, {"reduceOnly": True})
