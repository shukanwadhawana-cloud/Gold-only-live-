import json

import paper_state


def test_reconcile_trade_stats_counts_unique_closed_trades(tmp_path, monkeypatch):
    audit_file = tmp_path / "audit.jsonl"
    records = [
        {"event": "ENTRY", "trade_id": "t1"},
        {"event": "EXIT", "trade_id": "t1", "result_r": "2", "result_usdt": "0.4"},
        {"event": "EXIT", "trade_id": "t1", "result_r": "2", "result_usdt": "0.4"},
        {"event": "ENTRY", "trade_id": "t2"},
        {"event": "EXIT", "trade_id": "t2", "result_r": "-1", "result_usdt": "-0.2"},
        {"event": "ENTRY", "trade_id": "t3"},
        {"event": "EXIT", "trade_id": "t3", "result_r": "0", "result_usdt": "0"},
    ]
    audit_file.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paper_state, "AUDIT_FILE", audit_file)

    state = {
        "equity_usdt": "20",
        "realized_pnl_usdt": "999",
        "trades": 99,
        "wins": 99,
        "losses": 99,
    }

    result = paper_state.reconcile_trade_stats(state)

    assert result["trades"] == 3
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["breakevens"] == 1
    assert result["realized_pnl_usdt"] == "0.2"


def test_reconcile_legacy_exit_without_trade_id(tmp_path, monkeypatch):
    audit_file = tmp_path / "audit.jsonl"
    audit_file.write_text(
        json.dumps({
            "event": "EXIT",
            "entry_time": "2026-09-18 20:00:00+00:00",
            "type": "BUY",
            "entry": "4400",
            "sl": "4390",
            "result_r": "-1",
            "result_usdt": "-0.2",
        }) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paper_state, "AUDIT_FILE", audit_file)

    result = paper_state.reconcile_trade_stats({
        "equity_usdt": "20",
        "realized_pnl_usdt": "0",
        "trades": 0,
        "wins": 0,
        "losses": 0,
    })

    assert result["trades"] == 1
    assert result["wins"] == 0
    assert result["losses"] == 1
