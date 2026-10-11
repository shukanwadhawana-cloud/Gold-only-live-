from unittest.mock import Mock, patch

import pytest

import market_data


def bingx_market():
    return {
        "id": "BTC-USDT",
        "symbol": "BTC/USDT:USDT",
        "contract": True,
        "swap": True,
        "settle": "USDT",
        "active": True,
    }


def test_btc_market_selects_only_active_usdt_perpetual():
    exchange = Mock()
    exchange.load_markets.return_value = {
        "BTC/USDT": {"id": "BTC-USDT", "symbol": "BTC/USDT", "contract": False, "swap": False},
        "BTC/USDT:USDT": bingx_market(),
        "ETH/USDT:USDT": {
            "id": "ETH-USDT", "symbol": "ETH/USDT:USDT",
            "contract": True, "swap": True, "settle": "USDT", "active": True,
        },
    }

    assert market_data.btc_market(exchange) == bingx_market()


def test_btc_market_fails_closed_if_contract_missing():
    exchange = Mock()
    exchange.load_markets.return_value = {}

    with pytest.raises(RuntimeError, match="BingX public market data"):
        market_data.btc_market(exchange)


def test_get_bars_uses_public_bingx_and_returns_utc_ohlcv():
    exchange = Mock()
    exchange.load_markets.return_value = {"BTC/USDT:USDT": bingx_market()}
    exchange.fetch_ohlcv.return_value = [
        [1791710100000, 62000, 62100, 61900, 62050, 12.5],
    ]

    with patch.object(market_data, "make_market_data_exchange", return_value=exchange) as factory:
        frame = market_data.get_bars("BTCUSDT", "15m")

    factory.assert_called_once_with()
    exchange.fetch_ohlcv.assert_called_once_with("BTC/USDT:USDT", timeframe="15m", limit=1000)
    assert list(frame.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert str(frame.index.tz) == "UTC"
    assert frame.iloc[0]["Close"] == 62050


def test_get_bars_rejects_non_bitcoin_before_network_call():
    with patch.object(market_data, "make_market_data_exchange") as factory:
        with pytest.raises(ValueError, match="Bitcoin-only"):
            market_data.get_bars("NOTBTC")
        factory.assert_not_called()


def test_get_bars_fails_closed_on_empty_candles():
    exchange = Mock()
    exchange.load_markets.return_value = {"BTC/USDT:USDT": bingx_market()}
    exchange.fetch_ohlcv.return_value = []

    with patch.object(market_data, "make_market_data_exchange", return_value=exchange):
        with pytest.raises(RuntimeError, match="No BingX candles"):
            market_data.get_bars()
