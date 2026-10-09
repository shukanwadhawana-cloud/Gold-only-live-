"""Binance BTCUSDT perpetual market-data reader; no other asset is accepted."""
import pandas as pd
from exchange_adapter import make_exchange, btc_market


def get_bars(symbol="BTCUSDT", interval="15m", period="5d"):
    # Hard-lock symbol selection so an accidental caller cannot re-enable another asset.
    if str(symbol).upper() != "BTCUSDT":
        raise ValueError("Bitcoin-only build accepts BTCUSDT only.")
    ex = make_exchange()
    market = btc_market(ex)
    if str(market.get("id", "")).upper() != "BTCUSDT":
        raise RuntimeError(f"Unexpected market data symbol: {market.get('id')}")
    rows = ex.fetch_ohlcv(market["symbol"], timeframe=interval, limit=1000)
    if not rows:
        raise RuntimeError(f"No Binance candles for BTCUSDT {interval}")
    df = pd.DataFrame(rows, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]


def get_btc_bars(interval="15m"):
    return get_bars("BTCUSDT", interval)
