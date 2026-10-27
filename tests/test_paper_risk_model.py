from decimal import Decimal

import paper_runtime


def test_paper_quantity_respects_cap_and_all_in_stop_risk():
    entry = Decimal("100000")
    stop = Decimal("99000")
    balance = Decimal("100")

    qty = paper_runtime.paper_qty(entry, stop, "BUY", balance)

    assert qty > 0
    assert qty * paper_runtime.simulated_fill(entry, "BUY", True) <= Decimal("100")
    assert paper_runtime.estimated_all_in_stop_risk(qty, entry, stop, "BUY") <= paper_runtime.risk_budget(balance)


def test_simulated_entry_starts_negative_from_adverse_fill_and_fee():
    reference = Decimal("100000")
    fill = paper_runtime.simulated_fill(reference, "BUY", True)
    qty = Decimal("0.0009")
    entry_fee = fill * qty * paper_runtime.ESTIMATED_TAKER_FEE_RATE
    immediate_mark_loss = abs(fill - reference) * qty + entry_fee

    assert fill > reference
    assert immediate_mark_loss > 0


def test_stop_exit_net_loss_includes_entry_exit_fees_spread_slippage_and_funding(monkeypatch):
    monkeypatch.setattr(paper_runtime, "audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(paper_runtime, "save_state", lambda state: None)

    reference = Decimal("100000")
    stop = Decimal("99000")
    balance = Decimal("100")
    direction = "BUY"
    qty = paper_runtime.paper_qty(reference, stop, direction, balance)
    entry = paper_runtime.simulated_fill(reference, direction, True)
    entry_fee = entry * qty * paper_runtime.ESTIMATED_TAKER_FEE_RATE
    funding = paper_runtime.funding_reserve(entry * qty)
    budget = paper_runtime.risk_budget(balance)

    state = {
        "open_position": {
            "type": direction,
            "entry": str(entry),
            "sl": str(stop),
            "tp": str(entry + paper_runtime.RR_RATIO * abs(entry - stop)),
            "initial_r": str(abs(entry - stop)),
            "qty_research": str(qty),
            "entry_fee_estimate_usdt": str(entry_fee),
            "funding_reserve_usdt": str(funding),
            "risk_budget_at_entry_usdt": str(budget),
            "trade_id": "risk-test",
            "mae_r": "0",
            "mfe_r": "0",
        },
        "realized_pnl_usdt": "0",
        "equity_usdt": str(balance),
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "breakevens": 0,
    }

    paper_runtime.close_position(state, "SL", stop, "test-time")

    result = Decimal(state["realized_pnl_usdt"])
    assert result < 0
    assert abs(result) <= budget
    assert state["open_position"] is None
