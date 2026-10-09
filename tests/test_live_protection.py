from decimal import Decimal
import json

import pytest

import live_executor
from live_executor import _protection_prices, LiveExecutor


MARKET = {
    "info": {
        "filters": [
            {"filterType": "PRICE_FILTER", "tickSize": "0.1"}
        ]
    }
}


def test_long_protective_prices_round_outward_and_keep_four_r():
    stop, take_profit, initial_r = _protection_prices(
        MARKET, "BUY", Decimal("100.03"), Decimal("99.03")
    )
    assert stop == Decimal("99.0")
    assert take_profit == Decimal("104.2")
    assert initial_r == Decimal("1.03")
    assert stop < Decimal("100.03") < take_profit
    assert take_profit >= Decimal("100.03") + Decimal("4") * initial_r


def test_short_protective_prices_round_outward_and_keep_four_r():
    stop, take_profit, initial_r = _protection_prices(
        MARKET, "SELL", Decimal("100.03"), Decimal("101.03")
    )
    assert stop == Decimal("101.1")
    assert take_profit == Decimal("95.7")
    assert initial_r == Decimal("1.07")
    assert take_profit < Decimal("100.03") < stop
    assert take_profit <= Decimal("100.03") - Decimal("4") * initial_r


class FakeExchange:
    def __init__(self, positions=None, orders=None):
        self.positions = positions or []
        self.orders = orders or []

    def fetch_positions(self, symbols=None):
        return self.positions

    def fetch_open_orders(self, symbol):
        return self.orders


def test_readonly_reconciliation_identifies_clean_flat_state(tmp_path, monkeypatch):
    monkeypatch.setattr(live_executor, "STATE_FILE", str(tmp_path / "live_state.json"))
    executor = LiveExecutor.__new__(LiveExecutor)
    executor.ex = FakeExchange()
    executor.market = {"symbol": "BTC/USDT:USDT"}
    assert executor.reconcile_readonly()["status"] == "CLEAN_FLAT"


def test_readonly_reconciliation_blocks_untracked_position(tmp_path, monkeypatch):
    monkeypatch.setattr(live_executor, "STATE_FILE", str(tmp_path / "live_state.json"))
    executor = LiveExecutor.__new__(LiveExecutor)
    executor.ex = FakeExchange(positions=[{"contracts": "0.001"}])
    executor.market = {"symbol": "BTC/USDT:USDT"}
    assert executor.reconcile_readonly()["status"] == "UNTRACKED_POSITION"


def test_readonly_reconciliation_requires_both_protective_orders(tmp_path, monkeypatch):
    path = tmp_path / "live_state.json"
    path.write_text(json.dumps({"sl_order_id": "sl-1", "tp_order_id": "tp-1"}))
    monkeypatch.setattr(live_executor, "STATE_FILE", str(path))
    executor = LiveExecutor.__new__(LiveExecutor)
    executor.ex = FakeExchange(
        positions=[{"contracts": "0.001"}],
        orders=[{"id": "sl-1"}],
    )
    executor.market = {"symbol": "BTC/USDT:USDT"}
    assert executor.reconcile_readonly()["status"] == "PROTECTION_MISSING"
