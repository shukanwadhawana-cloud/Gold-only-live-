import importlib
import json


def load_paper_state(monkeypatch, tmp_path):
    state_path = tmp_path / "state" / "bitcoin_paper_state.json"
    audit_path = tmp_path / "state" / "bitcoin_paper_audit.jsonl"
    monkeypatch.setenv("PAPER_STATE_FILE", str(state_path))
    monkeypatch.setenv("PAPER_AUDIT_FILE", str(audit_path))
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)

    import paper_state

    return importlib.reload(paper_state)


def test_railway_volume_is_used_when_explicit_paths_are_not_set(monkeypatch, tmp_path):
    monkeypatch.delenv("PAPER_STATE_FILE", raising=False)
    monkeypatch.delenv("PAPER_AUDIT_FILE", raising=False)
    mount = tmp_path / "railway-volume"
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(mount))

    import paper_state

    module = importlib.reload(paper_state)
    assert module.STATE_FILE == mount / "bitcoin_paper_state.json"
    assert module.AUDIT_FILE == mount / "bitcoin_paper_audit.jsonl"
    assert module.persistence_info()["durable"] is True


def test_audit_records_trade_metadata_and_reconciles_unique_exits(monkeypatch, tmp_path):
    module = load_paper_state(monkeypatch, tmp_path)

    module.audit(
        "EXIT",
        trade_id="trade-1",
        type="SELL",
        entry="4200",
        sl="4210",
        result_r="0.6",
        result_usdt="1.2",
        entry_time="2026-10-01T07:00:00+00:00",
    )
    module.audit(
        "EXIT",
        trade_id="trade-1",
        type="SELL",
        entry="4200",
        sl="4210",
        result_r="0.6",
        result_usdt="1.2",
        entry_time="2026-10-01T07:00:00+00:00",
    )
    module.audit(
        "EXIT",
        trade_id="trade-2",
        type="BUY",
        entry="4210",
        sl="4200",
        result_r="-1",
        result_usdt="-2",
        entry_time="2026-10-01T08:00:00+00:00",
    )

    lines = module.AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert records[0]["event"] == "EXIT"
    assert "runtime_commit_sha" in records[0]
    assert "deployment_id" in records[0]
    assert "replica_id" in records[0]

    state = module.load_state()
    state = module.reconcile_trade_stats(state)
    assert state["trades"] == 2
    assert state["wins"] == 1
    assert state["losses"] == 1
    assert state["breakevens"] == 0
    assert state["realized_pnl_usdt"] == "-0.8"
