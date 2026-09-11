"""Gold-only live bot configuration.

All capital/risk values are configurable through environment variables.
The bot never assumes that the whole wallet is available for trading.
"""
import os
from decimal import Decimal

SYMBOL = "XAUUSDT"
TIMEFRAME = os.getenv("TIMEFRAME", "15m")
HTF_TIMEFRAME = os.getenv("HTF_TIMEFRAME", "1h")

RR_RATIO = Decimal("4")
TRAIL_STEP_R = Decimal("0.6")
STRUCTURE_SIZE = int(os.getenv("STRUCTURE_SIZE", "5"))
ATR_LEN = int(os.getenv("ATR_LEN", "200"))
SL_BUFFER_PCT = Decimal(os.getenv("SL_BUFFER_PCT", "0.0005"))
HTF_EMA_LEN = int(os.getenv("HTF_EMA_LEN", "50"))
REQUIRE_HTF = True

# Hard capital ceiling. This is NOT leverage and is NOT the order size.
# It limits how much account equity the bot may treat as its trading allocation.
CAPITAL_CAP_USDT = Decimal(os.getenv("CAPITAL_CAP_USDT", "20"))
# Maximum fraction of the active capital cap risked on one trade.
RISK_FRACTION = Decimal(os.getenv("RISK_FRACTION", "0.10"))
MAX_RISK_USDT = Decimal(os.getenv("MAX_RISK_USDT", "2"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "1"))

# Safety defaults: real trading is explicitly OFF until all preflight checks pass.
LIVE_TRADING = os.getenv("LIVE_TRADING", "false").lower() == "true"
ALLOW_LIVE_ORDERS = os.getenv("ALLOW_LIVE_ORDERS", "false").lower() == "true"

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

DATA_LIMIT = int(os.getenv("DATA_LIMIT", "500"))
FRESHNESS_BARS = int(os.getenv("FRESHNESS_BARS", "4"))
STATE_FILE = os.getenv("STATE_FILE", "gold_state.json")
AUDIT_FILE = os.getenv("AUDIT_FILE", "audit.jsonl")

# We intentionally do not accept a symbol from the environment: Gold-only means XAUUSDT only.
ALLOWED_SYMBOLS = {SYMBOL}


def active_capital(balance_usdt: Decimal) -> Decimal:
    return min(balance_usdt, CAPITAL_CAP_USDT)


def risk_budget(balance_usdt: Decimal) -> Decimal:
    cap = active_capital(balance_usdt)
    return min(MAX_RISK_USDT, cap * RISK_FRACTION)
