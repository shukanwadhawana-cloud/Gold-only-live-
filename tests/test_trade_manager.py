from decimal import Decimal

from trade_manager import locked_level, floor_for_level, next_trailing_state


def test_06r_buy():
    assert locked_level('BUY', 100, 90, 106) == Decimal('0.6')
    assert floor_for_level('BUY', 100, 90, Decimal('0.6')) == Decimal('106')


def test_12r_sell():
    assert locked_level('SELL', 100, 110, 88) == Decimal('1.2')
    assert floor_for_level('SELL', 100, 110, Decimal('1.2')) == Decimal('88')


def test_monotonic():
    level, floor, changed = next_trailing_state('BUY', 100, 90, Decimal('0.6'), 118)
    assert level == Decimal('1.8') and floor == Decimal('118') and changed
