"""Exchange execution layer for the Gold-only bot.

This module is intentionally gated. It is not invoked by the normal runner.
When enabled, entry is immediately followed by exchange-side SL and TP. If
protective orders cannot be installed, the position is closed immediately.
"""
import json
import os
from decimal import Decimal
from exchange_adapter import make_exchange, gold_market, balance_usdt, size_for_risk
from config import ALLOWED_SYMBOLS, MAX_OPEN_POSITIONS, STATE_FILE


class LiveExecutor:
    def __init__(self):
        if os.getenv('LIVE_TRADING','false').lower() != 'true' or os.getenv('ALLOW_LIVE_ORDERS','false').lower() != 'true':
            raise RuntimeError('Live execution is locked. Set both LIVE_TRADING=true and ALLOW_LIVE_ORDERS=true only after preflight approval.')
        self.ex = make_exchange()
        self.market = gold_market(self.ex)
        if self.market['id'] not in ALLOWED_SYMBOLS:
            raise RuntimeError(f'Unexpected live symbol: {self.market["id"]}')

    def _positions(self):
        try:
            return self.ex.fetch_positions([self.market['symbol']])
        except Exception:
            return self.ex.fetch_positions()

    def _open_position_exists(self):
        for p in self._positions():
            contracts = p.get('contracts')
            if contracts is None:
                info = p.get('info') or {}
                contracts = info.get('positionAmt', 0)
            try:
                if abs(float(contracts)) > 0:
                    return True
            except Exception:
                pass
        return False

    def open_trade(self, signal):
        if signal.get('type') not in ('BUY','SELL'):
            raise ValueError('Only BUY/SELL signals are executable.')
        if self._open_position_exists():
            raise RuntimeError('An existing Gold position is already open; MAX_OPEN_POSITIONS=1.')

        balance = balance_usdt(self.ex)
        sizing = size_for_risk(self.ex, signal['type'], signal['entry'], signal['sl'], balance)
        if not sizing['qty_meets_min'] or not sizing['notional_meets_min']:
            raise RuntimeError(f"Capital/risk too small for exchange minimums: {sizing}")

        side = 'buy' if signal['type'] == 'BUY' else 'sell'
        order = self.ex.create_order(self.market['symbol'], 'market', side, float(sizing['qty']))
        filled = Decimal(str(order.get('filled') or sizing['qty']))
        avg = Decimal(str(order.get('average') or order.get('price') or signal['entry']))
        close_side = 'sell' if signal['type'] == 'BUY' else 'buy'

        sl_order = tp_order = None
        try:
            sl_order = self.ex.create_order(self.market['symbol'], 'STOP_MARKET', close_side, float(filled), None,
                                            {'stopPrice': float(signal['sl']), 'reduceOnly': True, 'workingType': 'MARK_PRICE'})
            tp_order = self.ex.create_order(self.market['symbol'], 'TAKE_PROFIT_MARKET', close_side, float(filled), None,
                                            {'stopPrice': float(signal['tp']), 'reduceOnly': True, 'workingType': 'MARK_PRICE'})
        except Exception:
            try:
                self.ex.create_order(self.market['symbol'], 'market', close_side, float(filled), None, {'reduceOnly': True})
            finally:
                raise

        state = {
            'symbol': self.market['id'], 'ccxt_symbol': self.market['symbol'], 'direction': signal['type'],
            'entry': str(avg), 'sl': str(signal['sl']), 'tp': str(signal['tp']), 'qty': str(filled),
            'locked_level_r': '0', 'sl_order_id': sl_order.get('id'), 'tp_order_id': tp_order.get('id'),
            'entry_order_id': order.get('id')
        }
        tmp = STATE_FILE + '.tmp'
        with open(tmp,'w') as f: json.dump(state,f,indent=2)
        os.replace(tmp, STATE_FILE)
        return state

    def advance_trailing_stop(self, state, new_stop):
        old_id = state.get('sl_order_id')
        if old_id:
            try: self.ex.cancel_order(old_id, self.market['symbol'])
            except Exception as exc: print(f'Warning: could not cancel old SL {old_id}: {exc}')
        close_side = 'sell' if state['direction'] == 'BUY' else 'buy'
        order = self.ex.create_order(self.market['symbol'], 'STOP_MARKET', close_side, float(state['qty']), None,
                                     {'stopPrice': float(new_stop), 'reduceOnly': True, 'workingType': 'MARK_PRICE'})
        state['sl_order_id'] = order.get('id')
        state['sl'] = str(new_stop)
        tmp = STATE_FILE + '.tmp'
        with open(tmp,'w') as f: json.dump(state,f,indent=2)
        os.replace(tmp, STATE_FILE)
        return order
