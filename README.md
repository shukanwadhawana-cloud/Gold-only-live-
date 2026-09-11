# Gold-only-live-

Gold-only execution bot extracted from the proven SMC paper-trading strategy.

## Current build
- **Asset:** XAUUSDT only. No BTC/ETH/XRP/LINK/AAVE/SOL/AVAX/BNB execution paths.
- **Preferred exchange:** Binance Futures; the adapter dynamically discovers the actual XAUUSDT contract from exchange metadata.
- **Strategy:** 15m BOS/CHoCH, ATR-adjusted order block, 1H+4H EMA50 alignment, session filter, HIGH-confidence gate.
- **Risk:** original strategy SL, 4R TP, progressive 0.6R trailing indefinitely.
- **Capital cap:** configurable, default 20 USDT.
- **Risk budget:** configurable, default max 2 USDT and 10% of active capital cap.
- **Position count:** one Gold position maximum.
- **Telegram:** not used.
- **Live orders:** blocked by default. Both `LIVE_TRADING=true` and `ALLOW_LIVE_ORDERS=true` are required.

## Preflight first
`preflight.py` is read-only. It discovers the actual Binance Gold contract, account USDT balance, exchange minimums/precision, current strategy signal (if any), calculated position quantity and estimated 1R. It refuses to recommend a trade when the configured capital/risk is below exchange minimums.

The bot does not assume that the entire Binance wallet is available for this strategy. The configured capital cap is the maximum allocation the sizing layer may use.

## Live execution architecture
1. Fetch closed Gold candles.
2. Generate the same HIGH-confidence signal logic used by the paper strategy.
3. Calculate quantity from SL distance and the configured R-risk budget.
4. Refuse the trade if Binance minimum quantity/notional rules are not met.
5. Enter Gold only.
6. Immediately install exchange-side protective SL and 4R TP.
7. If protective orders cannot be installed, attempt an immediate market close rather than leave an unprotected position.
8. Trailing logic advances the SL at 0.6R increments.
9. Exchange state is the source of truth; local state is only an audit/reconciliation aid.

## Safety
Do not enable live trading before running the read-only preflight and verifying the exact contract returned by the account. API keys belong only in GitHub Secrets (`BINANCE_API_KEY`, `BINANCE_API_SECRET`) and must never be committed to the repository.

GitHub Actions is suitable for CI/preflight, but a 15-minute scheduled job is not sufficient for reliable continuous live trailing. Continuous live execution needs a continuously running worker or exchange-native protection for the position.
