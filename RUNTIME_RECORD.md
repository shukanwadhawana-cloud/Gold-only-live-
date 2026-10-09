# Bitcoin-only Runtime Record

## Conversion status
- Repository: `shukanwadhawana-cloud/Gold-only-live-`
- Target instrument: BTCUSDT perpetual only.
- Capital cap updated: 100 USDT maximum allocation at 1×.
- Maximum risk budget: 2 USDT and 10% of active cap; estimated round-trip taker fees, slippage, and funding reserve are included in sizing.
- Leverage preserved: 1×.
- Live orders: disabled by default; normal entry point forces paper-only mode.
- No live order has been submitted by this conversion.

## Historical data separation
The former Gold runtime state and audit files are not reused. Bitcoin paper state is written to `bitcoin_paper_state.json` and `bitcoin_paper_audit.jsonl`. Historical Gold results must not be presented as Bitcoin results.

## Live feasibility blocker
Binance's published 2026-04-14 BTCUSDT USDⓈ-M perpetual minimum-notional change set the minimum to 50 USDT. The bot must use current exchange metadata at runtime. The 100 USDT allocation can satisfy that minimum in principle, but a trade must still be rejected if stop-loss risk plus estimated fees, slippage, and funding reserve exceeds the 2 USDT risk budget.

## Required verification
1. CI and unit tests pass.
2. Read-only account preflight confirms the actual BTCUSDT perpetual, current minimum notional, precision and account permissions.
3. Verify sizing remains at or below the 100 USDT cap and the 2 USDT all-in risk budget.
4. Verify protective SL/TP placement, emergency-close behavior, restart recovery and reconciliation on testnet/paper; compare fee and funding assumptions against the account's actual tier/rates.
5. Keep live orders disabled until all checks pass and the capital/minimum-order conflict is explicitly resolved.
