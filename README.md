# Gold-only-live-

Gold-only execution bot extracted from the proven SMC paper-trading strategy.

## Current safety state
- Telegram: **not used**
- Asset: Gold only
- Strategy gate: HIGH confidence only
- TP: 4R
- Trailing: 0.6R, 1.2R, 1.8R, 2.4R, 3.0R, 3.6R ... indefinitely
- Default execution mode: `DRY_RUN=true`
- Real API keys are never stored in source
- Live execution remains disabled until exchange symbol/rules and demo execution are verified

## Architecture
Signal engine -> risk/position sizing -> exchange adapter -> exchange-side protection -> local audit ledger.

The exchange is the source of truth for real positions. GitHub is the code and audit trail.

## Important
GitHub Actions scheduled jobs are not a safe substitute for a continuously running live trader. The bot therefore starts with dry-run/demo validation. Before real money, the exchange adapter must be verified against the exact Gold instrument and its minimum order/contract rules, and protective SL/TP must be placed at the exchange immediately after entry.
