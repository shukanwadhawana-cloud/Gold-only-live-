import pandas as pd
from decimal import Decimal

from paper_runtime import btc_market_closed, stale_bar, trail_stop


def test_saturday_bitcoin_perpetual_is_open():
    now = pd.Timestamp("2026-09-19 17:00:00", tz="UTC")
    assert not btc_market_closed(now)


def test_sunday_bitcoin_perpetual_is_open():
    now = pd.Timestamp("2026-09-20 20:00:00", tz="UTC")
    assert not btc_market_closed(now)


def test_weekday_open_window_is_not_closed():
    now = pd.Timestamp("2026-09-21 17:00:00", tz="UTC")
    assert not btc_market_closed(now)


def test_stale_bar_after_three_intervals():
    bar = pd.Timestamp("2026-09-21 16:00:00", tz="UTC")
    now = pd.Timestamp("2026-09-21 16:46:00", tz="UTC")
    assert stale_bar(bar, now)


def test_fresh_bar_is_not_stale():
    bar = pd.Timestamp("2026-09-21 16:30:00", tz="UTC")
    now = pd.Timestamp("2026-09-21 16:46:00", tz="UTC")
    assert not stale_bar(bar, now)


def test_trailing_stop_continues_beyond_3_6r():
    assert trail_stop("BUY", Decimal("100"), Decimal("130"), Decimal("10"), Decimal("4.8")) == Decimal("142")
    assert trail_stop("SELL", Decimal("100"), Decimal("70"), Decimal("10"), Decimal("4.8")) == Decimal("58")
