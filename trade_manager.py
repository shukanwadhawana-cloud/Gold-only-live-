"""Exact paper-tested 0.6R progressive trailing rules, reused by live layer."""
from decimal import Decimal, ROUND_FLOOR

TRAIL_STEP_R = Decimal("0.6")
EXIT_SL = "SL"
EXIT_TRAILING_STOP = "TRAILING_STOP"
EXIT_TAKE_PROFIT = "TAKE_PROFIT"


def is_executable(confidence):
    return confidence == "HIGH"


def favorable_r(direction, entry, sl, price):
    risk = Decimal(str(abs(entry - sl)))
    if risk == 0:
        raise ValueError("entry and sl must differ")
    e = Decimal(str(entry)); p = Decimal(str(price))
    return ((p - e) / risk) if direction == "BUY" else ((e - p) / risk)


def locked_level(direction, entry, sl, price):
    r = favorable_r(direction, entry, sl, price)
    if r <= 0:
        return Decimal("0")
    return (r / TRAIL_STEP_R).to_integral_value(rounding=ROUND_FLOOR) * TRAIL_STEP_R


def floor_for_level(direction, entry, sl, level_r):
    risk = Decimal(str(abs(entry - sl)))
    level = Decimal(str(level_r))
    e = Decimal(str(entry))
    return e + level * risk if direction == "BUY" else e - level * risk


def next_trailing_state(direction, entry, sl, current_level_r, price):
    current = Decimal(str(current_level_r))
    new_level = locked_level(direction, entry, sl, price)
    if new_level <= current:
        return current, floor_for_level(direction, entry, sl, current), False
    return new_level, floor_for_level(direction, entry, sl, new_level), True
