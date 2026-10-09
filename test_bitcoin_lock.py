import os
import importlib


def test_bot_is_hard_locked_to_bitcoin_and_preserves_risk(monkeypatch):
    monkeypatch.delenv("LEVERAGE", raising=False)
    monkeypatch.delenv("CAPITAL_CAP_USDT", raising=False)
    monkeypatch.delenv("MAX_RISK_USDT", raising=False)
    monkeypatch.delenv("RISK_FRACTION", raising=False)
    import config
    config = importlib.reload(config)
    assert config.SYMBOL == "BTCUSDT"
    assert config.ALLOWED_SYMBOLS == {"BTCUSDT"}
    assert config.LEVERAGE == 1
    assert str(config.CAPITAL_CAP_USDT) == "100"
    assert str(config.MAX_RISK_USDT) == "2"
    assert str(config.RISK_FRACTION) == "0.10"
    assert str(config.ESTIMATED_TAKER_FEE_RATE) == "0.0005"
    assert str(config.ESTIMATED_SLIPPAGE_RATE) == "0.0002"
    assert str(config.ESTIMATED_FUNDING_RATE_PER_8H) == "0.0001"
    assert str(config.ESTIMATED_HOLD_HOURS) == "8"


def test_market_data_rejects_non_bitcoin_without_exchange_access():
    import market_data
    try:
        market_data.get_bars("NOT_ALLOWED_SYMBOL")
    except ValueError as exc:
        assert "BTCUSDT only" in str(exc)
    else:
        raise AssertionError("Non-Bitcoin symbol should be rejected")


def test_main_forces_live_orders_off(monkeypatch):
    monkeypatch.setenv("LIVE_TRADING", "true")
    monkeypatch.setenv("ALLOW_LIVE_ORDERS", "true")
    monkeypatch.setenv("VOROA_PAPER_ONLY", "false")
    import main
    importlib.reload(main)
    assert os.environ["LIVE_TRADING"] == "false"
    assert os.environ["ALLOW_LIVE_ORDERS"] == "false"
    assert os.environ["VOROA_PAPER_ONLY"] == "true"


def test_exchange_filter_minimum_notional_overrides_lower_ccxt_cost_limit():
    from decimal import Decimal
    from exchange_adapter import minimum_notional

    market = {
        "limits": {"cost": {"min": 5}},
        "info": {
            "filters": [
                {"filterType": "MIN_NOTIONAL", "notional": "50"},
                {"filterType": "LOT_SIZE", "minQty": "0.001"},
            ]
        },
    }
    assert minimum_notional(market) == Decimal("50")
