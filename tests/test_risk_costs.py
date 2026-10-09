from decimal import Decimal

from exchange_adapter import size_for_risk


class FakeExchange:
    def __init__(self, min_notional="50", step="0.001"):
        self.market = {
            "id": "BTCUSDT",
            "symbol": "BTC/USDT:USDT",
            "contract": True,
            "swap": True,
            "settle": "USDT",
            "contractSize": 1,
            "limits": {"amount": {"min": 0.001}, "cost": {"min": float(min_notional)}},
            "precision": {"amount": 3, "price": 1},
            "info": {
                "filters": [
                    {"filterType": "MIN_NOTIONAL", "notional": min_notional},
                    {"filterType": "LOT_SIZE", "minQty": "0.001", "stepSize": step},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                ]
            },
        }

    def load_markets(self):
        return {self.market["symbol"]: self.market}

    def amount_to_precision(self, symbol, amount):
        return f"{amount:.3f}"


def test_btc_sizing_includes_fee_slippage_and_funding_inside_two_dollar_risk():
    sizing = size_for_risk(
        FakeExchange(), "BUY", Decimal("100000"), Decimal("99000"), Decimal("100")
    )
    assert sizing["capital_cap_usdt"] == Decimal("100")
    assert sizing["risk_budget_usdt"] == Decimal("2")
    assert sizing["qty"] == Decimal("0.001")
    assert sizing["notional"] == Decimal("100.000")
    assert sizing["estimated_round_trip_fee_usdt"] > 0
    assert sizing["estimated_round_trip_slippage_usdt"] > 0
    assert sizing["estimated_funding_cost_usdt"] > 0
    assert sizing["estimated_total_risk_usdt"] == (
        sizing["estimated_stop_loss_usdt"]
        + sizing["estimated_round_trip_fee_usdt"]
        + sizing["estimated_round_trip_slippage_usdt"]
        + sizing["estimated_funding_cost_usdt"]
    )
    assert sizing["estimated_total_risk_usdt"] <= sizing["risk_budget_usdt"]
    assert sizing["risk_limit_pass"] is True
    assert sizing["notional_meets_min"] is True


def test_risk_sizing_never_rounds_quantity_up_to_meet_exchange_minimum():
    sizing = size_for_risk(
        FakeExchange(min_notional="200"), "BUY",
        Decimal("100000"), Decimal("99000"), Decimal("100")
    )
    assert sizing["notional"] < Decimal("200")
    assert sizing["notional_meets_min"] is False
    assert sizing["risk_limit_pass"] is True
