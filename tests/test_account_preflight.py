from decimal import Decimal

from account_preflight import feasibility


def test_small_capital_feasibility_uses_contract_size():
    rules = {
        "min_qty": Decimal("0.001"),
        "min_notional": Decimal("0"),
        "amount_precision": 3,
        "price_precision": 2,
        "contract_size": Decimal("1"),
    }
    rows = feasibility(
        balance=Decimal("20"),
        entry=Decimal("3500"),
        sl=Decimal("3490"),
        rules=rules,
    )
    assert rows[0]["cap"] == Decimal("5")
    assert rows[0]["risk_budget"] == Decimal("0.5")
    assert rows[0]["raw_qty"] == Decimal("0.05")
    assert rows[0]["meets_minimums"] is True


def test_cap_is_limited_by_actual_balance():
    rules = {
        "min_qty": Decimal("0.001"),
        "min_notional": Decimal("0"),
        "amount_precision": 3,
        "price_precision": 2,
        "contract_size": Decimal("1"),
    }
    rows = feasibility(
        balance=Decimal("3"),
        entry=Decimal("3500"),
        sl=Decimal("3490"),
        rules=rules,
    )
    assert rows[0]["active_capital"] == Decimal("3")
    assert rows[0]["risk_budget"] == Decimal("0.3")


def test_contract_size_changes_quantity_and_notional():
    rules = {
        "min_qty": Decimal("0.001"),
        "min_notional": Decimal("0"),
        "amount_precision": 3,
        "price_precision": 2,
        "contract_size": Decimal("10"),
    }
    rows = feasibility(
        balance=Decimal("20"),
        entry=Decimal("3500"),
        sl=Decimal("3490"),
        rules=rules,
    )
    assert rows[0]["raw_qty"] == Decimal("0.005")
    assert rows[0]["notional"] == Decimal("175")
