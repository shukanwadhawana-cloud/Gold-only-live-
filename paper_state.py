"""Durable paper-trading state and audit persistence."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

STATE_FILE = Path(os.getenv("PAPER_STATE_FILE", "gold_paper_state.json"))
AUDIT_FILE = Path(os.getenv("PAPER_AUDIT_FILE", "gold_paper_audit.jsonl"))


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "version": 2,
            "equity_usdt": "20",
            "realized_pnl_usdt": "0",
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "breakevens": 0,
            "open_position": None,
            "last_signal_key": None,
        }
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        state.setdefault("breakevens", 0)
        return state
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot load paper state: {exc}") from exc


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{STATE_FILE.name}.",
        dir=str(STATE_FILE.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, default=_json_default)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, STATE_FILE)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def audit(event: str, **fields) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": now_iso(), "event": event, **fields}
    with AUDIT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(record, default=_json_default, separators=(",", ":")) + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())


def read_audit() -> list[dict]:
    """Read valid JSONL audit records; ignore blank/malformed lines."""
    if not AUDIT_FILE.exists():
        return []
    records = []
    try:
        lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Cannot read paper audit: {exc}") from exc
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def reconcile_trade_stats(state: dict) -> dict:
    """Make closed-trade statistics authoritative from the EXIT audit ledger."""
    exits = []
    seen = set()
    for record in read_audit():
        if record.get("event") != "EXIT":
            continue
        trade_id = record.get("trade_id")
        if not trade_id:
            trade_id = (
                f"{record.get('entry_time','')}|{record.get('type','')}|"
                f"{record.get('entry','')}|{record.get('sl','')}"
            )
        if trade_id in seen:
            continue
        seen.add(trade_id)
        exits.append(record)

    wins = losses = breakevens = 0
    realized = Decimal("0")
    for record in exits:
        result_r = Decimal(str(record.get("result_r", "0")))
        result_usdt = Decimal(str(record.get("result_usdt", "0")))
        realized += result_usdt
        if result_r > 0:
            wins += 1
        elif result_r < 0:
            losses += 1
        else:
            breakevens += 1

    state["trades"] = len(exits)
    state["wins"] = wins
    state["losses"] = losses
    state["breakevens"] = breakevens
    state["realized_pnl_usdt"] = str(realized)

    return state
