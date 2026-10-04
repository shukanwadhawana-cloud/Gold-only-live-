"""Continuous, restart-safe Gold-only paper runtime for Voroa.

No Binance authentication, Telegram, or real orders are used here.
Only closed candles are used for signals and exits. State/audit files make the
paper session durable across worker restarts.
"""
from __future__ import annotations

import os
import time
from decimal import Decimal

from config import CAPITAL_CAP_USDT, MAX_RISK_USDT, RISK_FRACTION, FRESHNESS_BARS
from market_data import get_gold_bars
from paper_state import audit, load_state, persistence_info, reconcile_trade_stats, save_state
from strategy import latest_executable_signal

POLL_SECONDS = 60
ZERO = Decimal("0")
TIMEFRAME_SECONDS = 15 * 60
STALE_BAR_MULTIPLIER = 3


def gold_market_closed(now) -> bool:\n    return False
