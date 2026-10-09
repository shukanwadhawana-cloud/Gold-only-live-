"""Exchange execution layer for the Bitcoin-only bot.

This module is intentionally gated. It is not invoked by the normal runner.
When enabled, entry is immediately followed by exchange-side SL and TP. If
protective orders cannot be installed, the position is closed immediately.
"""
import json
import os
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from exchange_adapter import make_exchange, btc_market, balance_usdt, size_for_risk, set_one_x_leverage
from config import (ALLOWED_SYMBOLS, MAX_OPEN_POSITIONS, STATE_FILE, RR_RATIO,
                    ESTIMATED_TAKER_FEE_RATE, ESTIMATED_SLIPPAGE_RATE,
                    ESTIMATED_FUNDING_RATE_PER_8H, ESTIMATED_HOLD_HOURS)


def _round_to_tick(price, tick, rounding):
    price = Decimal(str(price))
    tick = Decimal(str(tick))
    if tick <= 0:
        raise ValueError('Exchange did not provide a valid price tick size.')
    return (price / tick).to_integral_value(rounding=rounding) * tick


def _price_tick(market):
    for rule in ((market.get('info') or {}).get('filters') or []):
        if str(rule.get('filterType', '')).upper() == 'PRICE_FILTER' and rule.get('tickSize'):
            return Decimal(str(rule['tickSize']))
    raise RuntimeError('Binance PRICE_FILTER tickSize is missing; cannot safely place protective orders.')


def _protection_prices(market, direction, fill_price, initial_stop):
    tick = _price_tick(market)
    fill_price = Decimal(str(fill_price))
    initial_stop = Decimal(str(initial_stop))
    if direction == 'BUY':
        if initial_stop >= fill_price:
            raise ValueError('Filled BUY entry is not above its stop-loss.')
        stop = _round_to_tick(initial_stop, tick, ROUND_FLOOR)
        initial_r = fill_price - stop
        take_profit = _round_to_tick(fill_price + RR_RATIO * initial_r, tick, ROUND_CEILING)
    else:
        if initial_stop <= fill_price:
            raise ValueError('Filled SELL entry is not below its stop-loss.')
        stop = _round_to_tick(initial_stop, tick, ROUND_CEILING)
        initial_r = stop - fill_price
        take_profit = _round_to_tick(fill_price - RR_RATIO * initial_r, tick, ROUND_FLOOR)
    if initial_r <= 0:
        raise ValueError('Rounded stop-loss leaves no positive risk distance.')
    return stop, take_profit, initial_r


class LiveExecutor:
    def __init__(self):
        if os.getenv('LIVE_TRADING','false').lower() != 'true' or os.getenv('ALLOW_LIVE_ORDERS','false').lower() != 'true':
            raise RuntimeError('Live execution is locked. Set both LIVE_TRADING=true and ALLOW_LIVE_ORDERS=true only after preflight approval.')
        self.ex = make_exchange()
        self.market = btc_market(self.ex)
        if self.market['id'] not in ALLOWED_SYMBOLS:
            raise RuntimeError(f'Unexpected live symbol: {self.market["id"]}')
        set_one_x_leverage(self.ex, self.market)

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

    def reconcile_readonly(self):
        """Compare local durable state with exchange positions and open protection orders."""
        positions = []
        for p in self._positions():
            contracts = p.get('contracts')
            if contracts is None:
                contracts = (p.get('info') or {}).get('positionAmt', 0)
            if abs(Decimal(str(contracts or 0))) > 0:
                positions.append(p)
        orders = self.ex.fetch_open_orders(self.market['symbol'])
        state = None
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
        if not positions and not orders and state is None:
            return {'status': 'CLEAN_FLAT', 'positions': 0, 'open_orders': 0}
        if not positions and orders:
            return {'status': 'ORPHAN_ORDERS', 'positions': 0, 'open_orders': len(orders)}
        if not positions and state is not None:
            return {'status': 'STALE_LOCAL_STATE', 'positions': 0, 'open_orders': 0}
        if positions and state is None:
            return {'status': 'UNTRACKED_POSITION', 'positions': len(positions), 'open_orders': len(orders)}
        open_ids = {str(o.get('id')) for o in orders if o.get('id') is not None}
        required_ids = {str(state.get('sl_order_id')), str(state.get('tp_order_id'))}
        if not required_ids.issubset(open_ids):
            return {'status': 'PROTECTION_MISSING', 'positions': len(positions), 'open_orders': len(orders)}
        return {'status': 'MANAGED_OPEN_POSITION', 'positions': len(positions), 'open_orders': len(orders)}

    def open_trade(self, signal):
        if signal.get('type') not in ('BUY','SELL'):
            raise ValueError('Only BUY/SELL signals are executable.')
        entry = Decimal(str(signal['entry']))
        sl = Decimal(str(signal['sl']))
        tp = Decimal(str(signal['tp']))
        risk = abs(entry - sl)
        if risk <= 0:
            raise ValueError('Signal Entry and SL must differ.')
        if signal['type'] == 'BUY' and not (sl < entry < tp):
            raise ValueError('BUY signal geometry must satisfy SL < Entry < TP.')
        if signal['type'] == 'SELL' and not (tp < entry < sl):
            raise ValueError('SELL signal geometry must satisfy TP < Entry < SL.')
        signal_rr = abs(tp - entry) / risk
        if abs(signal_rr - RR_RATIO) > Decimal('0.10'):
            raise ValueError(f'Signal TP must preserve {RR_RATIO}R; got {signal_rr}R.')
        reconciliation = self.reconcile_readonly()
        if reconciliation['status'] != 'CLEAN_FLAT':
            raise RuntimeError(f"Exchange/local state is not clean-flat; refusing entry: {reconciliation}")

        balance = balance_usdt(self.ex)
        sizing = size_for_risk(self.ex, signal['type'], signal['entry'], signal['sl'], balance)
        if not sizing['qty_meets_min'] or not sizing['notional_meets_min'] or not sizing.get('risk_limit_pass', False):
            raise RuntimeError(f"Capital/risk/fee limits do not support exchange minimums: {sizing}")

        side = 'buy' if signal['type'] == 'BUY' else 'sell'
        order = self.ex.create_order(self.market['symbol'], 'market', side, float(sizing['qty']))
        filled_raw = order.get('filled')
        if (filled_raw is None or Decimal(str(filled_raw)) <= 0) and order.get('id'):
            try:
                refreshed = self.ex.fetch_order(order['id'], self.market['symbol'])
                filled_raw = refreshed.get('filled')
                order = refreshed
            except Exception:
                pass
        if filled_raw is None or Decimal(str(filled_raw)) <= 0:
            raise RuntimeError('Entry fill quantity is unconfirmed; refusing to guess protection size. Reconcile exchange position immediately.')
        filled = Decimal(str(filled_raw))
        avg_raw = order.get('average') or order.get('price')
        if avg_raw is None:
            raise RuntimeError('Entry fill price is unconfirmed; refusing to calculate protection from signal price.')
        avg = Decimal(str(avg_raw))
        actual_sl, actual_tp, initial_r = _protection_prices(self.market, signal['type'], avg, signal['sl'])
        close_side = 'sell' if signal['type'] == 'BUY' else 'buy'

        sl_order = tp_order = None
        try:
            sl_order = self.ex.create_order(self.market['symbol'], 'STOP_MARKET', close_side, float(filled), None,
                                            {'stopPrice': float(actual_sl), 'reduceOnly': True, 'workingType': 'MARK_PRICE'})
            tp_order = self.ex.create_order(self.market['symbol'], 'TAKE_PROFIT_MARKET', close_side, float(filled), None,
                                            {'stopPrice': float(actual_tp), 'reduceOnly': True, 'workingType': 'MARK_PRICE'})
            if not sl_order or not sl_order.get('id') or not tp_order or not tp_order.get('id'):
                raise RuntimeError('Binance did not return both protective order IDs.')
        except Exception as exc:
            # Never cancel an installed stop before the position is confirmed flat.
            close_error = None
            try:
                self.ex.create_order(
                    self.market['symbol'], 'market', close_side, float(filled), None, {'reduceOnly': True}
                )
            except Exception as close_exc:
                close_error = close_exc

            flat_confirmed = False
            try:
                flat_confirmed = not self._open_position_exists()
            except Exception:
                flat_confirmed = False

            if flat_confirmed:
                for protective in (sl_order, tp_order):
                    if protective and protective.get('id'):
                        try:
                            self.ex.cancel_order(protective['id'], self.market['symbol'])
                        except Exception:
                            pass
            else:
                # Persist the uncertain position so restart reconciliation blocks new entries.
                emergency_state = {
                    'symbol': self.market['id'], 'ccxt_symbol': self.market['symbol'],
                    'direction': signal['type'], 'entry': str(avg), 'sl': str(actual_sl),
                    'tp': str(actual_tp), 'qty': str(filled), 'initial_r': str(initial_r),
                    'locked_level_r': '0',
                    'sl_order_id': sl_order.get('id') if sl_order else None,
                    'tp_order_id': tp_order.get('id') if tp_order else None,
                    'entry_order_id': order.get('id'), 'protection_setup_error': str(exc),
                }
                tmp = STATE_FILE + '.tmp'
                with open(tmp, 'w') as f:
                    json.dump(emergency_state, f, indent=2)
                os.replace(tmp, STATE_FILE)

            detail = f"Protective-order setup failed: {exc}"
            if close_error:
                detail += f" | emergency close failed: {close_error}"
            if not flat_confirmed:
                detail += " | position may remain open; any installed protective orders were retained and state persisted for reconciliation."
            raise RuntimeError(detail) from exc

        state = {
            'symbol': self.market['id'], 'ccxt_symbol': self.market['symbol'], 'direction': signal['type'],
            'entry': str(avg), 'sl': str(actual_sl), 'tp': str(actual_tp), 'qty': str(filled), 'initial_r': str(initial_r),
            'locked_level_r': '0', 'sl_order_id': sl_order.get('id'), 'tp_order_id': tp_order.get('id'),
            'entry_order_id': order.get('id')
        }
        tmp = STATE_FILE + '.tmp'
        with open(tmp,'w') as f: json.dump(state,f,indent=2)
        os.replace(tmp, STATE_FILE)
        return state

    def advance_trailing_stop(self, state, new_stop):
        new_stop = Decimal(str(new_stop))
        old_stop = Decimal(str(state['sl']))
        tick = _price_tick(self.market)
        if state['direction'] == 'BUY':
            if new_stop <= old_stop:
                raise ValueError('A BUY trailing stop may only move upward; refusing to loosen protection.')
            new_stop = _round_to_tick(new_stop, tick, ROUND_FLOOR)
            if new_stop <= old_stop:
                raise ValueError('Tick rounding would loosen a BUY trailing stop.')
        else:
            if new_stop >= old_stop:
                raise ValueError('A SELL trailing stop may only move downward; refusing to loosen protection.')
            new_stop = _round_to_tick(new_stop, tick, ROUND_CEILING)
            if new_stop >= old_stop:
                raise ValueError('Tick rounding would loosen a SELL trailing stop.')
        old_id = state.get('sl_order_id')
        close_side = 'sell' if state['direction'] == 'BUY' else 'buy'
        # Install the replacement stop before cancelling the old one so a
        # transient API failure cannot leave the live position unprotected.
        order = self.ex.create_order(
            self.market['symbol'], 'STOP_MARKET', close_side, float(state['qty']), None,
            {'stopPrice': float(new_stop), 'reduceOnly': True, 'workingType': 'MARK_PRICE'}
        )
        new_id = order.get('id')
        if not new_id:
            raise RuntimeError('Binance returned no order id for replacement trailing stop.')
        if old_id and old_id != new_id:
            try:
                self.ex.cancel_order(old_id, self.market['symbol'])
            except Exception as exc:
                print(f'Warning: replacement SL {new_id} is active but old SL {old_id} could not be cancelled: {exc}')
        state['sl_order_id'] = new_id
        state['sl'] = str(new_stop)
        tmp = STATE_FILE + '.tmp'
        with open(tmp,'w') as f: json.dump(state,f,indent=2)
        os.replace(tmp, STATE_FILE)
        return order
