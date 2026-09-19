# Gold-only Runtime Ledger Template

Use this file as the GitHub-side record/index for runtime audits. Do **not** overwrite the authoritative runtime JSONL with this template.

| Audit date | Cycle range | Closed | Wins | Losses | Breakevens | Open | Realized P&L | Ledger source | Verified |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2026-09-19 | ~5,000+ (partial evidence) | 2 | 0 | 1 | 0 known | 1 | Not reconstructed | Runtime history supplied in chat | Partial |

## Rules
- Closed trade count comes from unique EXIT events.
- A trade is not counted as a win/loss until an EXIT event exists.
- Duplicate EXIT events must not increase totals.
- P&L comes from authoritative `result_usdt` values where present.
- If the runtime ledger is unavailable, mark the audit **Partial** rather than guessing.
- Keep this file as a human-readable audit index; runtime state remains in the persistent worker's storage.
