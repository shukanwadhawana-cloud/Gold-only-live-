import pandas as pd

from paper_runtime import gold_market_closed, stale_bar


def test_saturday_gold_is_closed():
    now = pd.Timestamp("2026-09-19 17:00:00", tz="UTC")
    assert gold_market_closed(now)


def test_sunday_before_reopen_is_closed():
    now = pd.Timestamp("2026-09-20 20:00:00", tz="UTC")
    assert gold_market_closed(now)


def test_weekday_open_window_is_not_closed():
    now = pd.Timestamp("2026-09-21 17:00:00", tz="UTC")
    assert not gold_market_closed(now)


def test_stale_bar_after_three_intervals():
    bar = pd.Timestamp("2026-09-21 16:00:00", tz="UTC")
    now = pd.Timestamp("2026-09-21 16:46:00", tz="UTC")
    assert stale_bar(bar, now)


def test_fresh_bar_is_not_stale():
    bar = pd.Timestamp("2026-09-21 16:30:00", tz="UTC")
    now = pd.Timestamp("2026-09-21 16:46:00", tz="UTC")
    assert not stale_bar(bar, now)
