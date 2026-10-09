# Bitcoin-only-live

Bitcoin-only execution bot adapted from the existing SMC paper-trading strategy.

## Current conversion
- **Asset:** BTCUSDT only. No Gold/XAUT, ETH, XRP, LINK, AAVE, SOL, AVAX, or BNB execution paths.
- **Exchange:** Binance USDⓈ-M BTCUSDT perpetual, discovered from exchange metadata at runtime.
- **Strategy:** 15m BOS/CHoCH, ATR-adjusted order block, 1H+4H EMA50 alignment, session filter, HIGH-confidence gate.
- **Risk geometry retained:** strategy SL, 4R take-profit, progressive 0.6R trailing.
- **Capital cap:** 100 USDT maximum allocation at 1×.
- **Risk budget:** maximum 2 USDT and 10% of active capital cap per trade; quantity sizing reserves estimated round-trip taker fees and slippage inside that budget.
- **Leverage:** hard-locked to 1×.
- **Position count:** one Bitcoin position maximum.
- **Live orders:** disabled by default. Both `LIVE_TRADING=true` and `ALLOW_LIVE_ORDERS=true` are required by the execution layer, and the normal entry point forces paper-only mode.

## Critical capital/minimum-order constraint
Binance's published 2026-04-14 BTCUSDT USDⓈ-M perpetual minimum-notional change set the minimum to 50 USDT; the bot must read current exchange metadata/preflight rather than hard-code that value. At 1×, the 100 USDT cap can support the published 50 USDT minimum in principle, but a trade is still rejected unless stop-loss risk plus estimated round-trip fees and slippage fit within the $2 risk budget. Therefore the safe behavior is **reject the trade and remain flat** until actual exchange filters and an explicitly approved capital configuration make the order feasible. Do not raise the cap or leverage automatically.

## Paper runtime persistence
The Bitcoin runtime writes separate files:
- `bitcoin_paper_state.json` — restart-safe paper state.
- `bitcoin_paper_audit.jsonl` — append-only paper event ledger.

Gold state/audit files are deliberately not reused or migrated, so historical Gold P&L is not mixed into Bitcoin statistics.

## Preflight first
`preflight.py` and `account_preflight.py` are read-only. They discover the actual BTCUSDT contract, account USDT balance, exchange minimums/precision, current signal, quantity and estimated 1R. They must refuse a trade when configured capital/risk is below exchange minimums. Credentials are read only from environment variables and must never be committed.

## Live execution architecture
1. Fetch closed BTCUSDT candles.
2. Generate the strategy signal using the existing strategy logic.
3. Size quantity from stop distance and configured risk budget, bounded by the 100 USDT allocation.
4. Refuse orders if exchange minimum quantity/notional rules are not met.
5. Enter BTCUSDT only.
6. Immediately install exchange-side protective SL and 4R TP.
7. If protective orders cannot be installed, attempt an immediate market close rather than leave an unprotected position.
8. Advance the trailing stop at 0.6R increments.
9. Treat exchange state as authoritative; local state is an audit/reconciliation aid.

## Runtime/deployment
Vercel is not the continuous worker; it exposes a read-only health endpoint. GitHub Actions is CI/preflight only, not an unbounded trading worker. Continuous execution requires a verified persistent worker.

## Safety status
This conversion does **not** enable live orders or submit any orders. The existing paper-only entry point remains fail-closed. Run CI, then execute read-only account preflight from an eligible environment. Live execution remains disabled. Before any activation, use read-only account preflight to verify current exchange filters, the account's actual fee tier, funding/fees, minimum quantity/notional, stop and take-profit acceptance, and runtime reconciliation. Do not bypass risk or minimum-order guards.
