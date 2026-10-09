"""Pure execution-plan builder; it never sends an order."""
from decimal import Decimal
from trade_manager import floor_for_level
from exchange_adapter import size_for_risk


def build_plan(ex, signal, balance_usdt):
    sizing = size_for_risk(ex, signal['type'], signal['entry'], signal['sl'], balance_usdt)
    qty = sizing['qty']
    entry = Decimal(str(signal['entry']))
    sl = Decimal(str(signal['sl']))
    tp = Decimal(str(signal['tp']))
    risk_per_unit = abs(entry - sl)
    estimated_1r = qty * risk_per_unit * Decimal(str(sizing['contract_size']))
    floors = {}
    for level in (Decimal('0.6'), Decimal('1.2'), Decimal('1.8'), Decimal('2.4'), Decimal('3.0'), Decimal('3.6')):
        floors[str(level)] = floor_for_level(signal['type'], entry, sl, level)
    return {
        'symbol': sizing['symbol'], 'direction': signal['type'], 'entry': entry,
        'sl': sl, 'tp': tp, 'qty': qty, 'notional': sizing['notional'],
        'risk_budget_usdt': sizing['risk_budget_usdt'],
        'estimated_1r_usdt': estimated_1r,
        'estimated_stop_loss_usdt': sizing['estimated_stop_loss_usdt'],
        'estimated_round_trip_fee_usdt': sizing['estimated_round_trip_fee_usdt'],
        'estimated_round_trip_slippage_usdt': sizing['estimated_round_trip_slippage_usdt'],
        'estimated_total_risk_usdt': sizing['estimated_total_risk_usdt'],
        'risk_limit_pass': sizing['risk_limit_pass'],
        'min_qty': sizing['min_qty'], 'min_notional': sizing['min_notional'],
        'valid_minimums': sizing['qty_meets_min'] and sizing['notional_meets_min'],
        'capital_cap_usdt': sizing['capital_cap_usdt'],
        'trailing_floors': floors,
    }
