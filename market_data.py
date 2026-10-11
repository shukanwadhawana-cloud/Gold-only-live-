"""Public BingX BTC/USDT perpetual market-data reader for Voroa paper trading.

This module is deliberately separate from exchange_adapter.py, which remains
the Binance-only account/preflight adapter. The continuous Voroa runtime is
paper-only and needs public candles, not Binance account access.
"""
import ccxt
import pandas as pd


def make_market_data_exchange():
    """Create an unauthenticated CCXT BingX swap client for public candles."""
    return ccxt.bingx({
        "enableRateLimit": True,
        "options": {"defaultType": "swap"},
    })


def btc_market(ex=None):
    ex = ex or make_market_data_exchange()
    markets = ex.load_markets()
    matches = [
        market for market in markets.values()
        if market.get("symbol") == "BTC/USDT:USDT"
        and market.get("contract")
        and market.get("swap")
        and str(market.get("settle", "")).upper() == "USDT"
        and market.get("active") is not False
    ]
    if not matches:
        raise RuntimeError("BingX public market data did not expose the active BTC/USDT USDT-settled perpetual.")
    return matches[0]


def get_bars(symbol="BTCUSDT", interval="15m", period="5d"):
    # Hard-lock symbol selection so an accidental caller cannot enable another asset.
    if str(symbol).upper() != "BTCUSDT":
        raise ValueError("Bitcoin-only build accepts BTCUSDT only.")
    ex = make_market_data_exchange()
    market = btc_market(ex)
    rows = ex.fetch_ohlcv(market["symbol"], timeframe=interval, limit=1000)
    if not rows:
        raise RuntimeError(f"No BingX candles for BTCUSDT {interval}")
    df = pd.DataFrame(rows, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]


def get_btc_bars(interval="15m"):
    return get_bars("BTCUSDT", interval)
