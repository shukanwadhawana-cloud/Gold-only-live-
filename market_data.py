"""Binance XAUTUSDT perpetual market-data reader."""
import pandas as pd
from exchange_adapter import make_exchange, gold_market

def get_bars(symbol='XAUTUSDT', interval='15m', period='5d'):
    ex = make_exchange()
    market = gold_market(ex)
    if market["id"] != symbol.upper():
        raise RuntimeError(f"Unexpected market data symbol: {market['id']}")
    rows = ex.fetch_ohlcv(market["symbol"], timeframe=interval, limit=1000)
    if not rows:
        raise RuntimeError(f"No Binance candles for {symbol} {interval}")
    df = pd.DataFrame(rows, columns=["timestamp","Open","High","Low","Close","Volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp")[["Open","High","Low","Close","Volume"]]

def get_gold_bars(interval='15m'):
    return get_bars('XAUTUSDT', interval)
