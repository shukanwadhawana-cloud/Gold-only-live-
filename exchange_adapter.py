"""Exchange adapter. Default is read-only/dry-run.

Supports Binance Futures and BingX swap through CCXT. Real order placement
is deliberately blocked unless LIVE_TRADING=true AND the symbol has been
validated by the exchange. API secrets are read only from environment vars.
"""
import os
import ccxt

EXCHANGE_NAME=os.getenv('EXCHANGE','binance').lower()
SYMBOL=os.getenv('EXCHANGE_SYMBOL','').strip()
LIVE_TRADING=os.getenv('LIVE_TRADING','false').lower()=='true'


def make_exchange():
    key=os.getenv('EXCHANGE_API_KEY',''); secret=os.getenv('EXCHANGE_API_SECRET','')
    klass=getattr(ccxt,EXCHANGE_NAME,None)
    if klass is None: raise ValueError(f'Unsupported exchange: {EXCHANGE_NAME}')
    cfg={'enableRateLimit':True,'apiKey':key,'secret':secret,'options':{'defaultType':'swap'}}
    ex=klass(cfg)
    # Never silently enable live mode. Sandbox/testnet is explicit and exchange-dependent.
    if os.getenv('SANDBOX','false').lower()=='true':
        try: ex.set_sandbox_mode(True)
        except Exception as exc: print(f'Sandbox mode unavailable for {EXCHANGE_NAME}: {exc}')
    return ex


def validate():
    ex=make_exchange(); markets=ex.load_markets()
    if not SYMBOL: raise ValueError('EXCHANGE_SYMBOL is required; do not guess the Gold contract.')
    if SYMBOL not in markets:
        matches=[s for s in markets if 'XAU' in s.upper() or 'GOLD' in s.upper()]
        raise ValueError(f'{SYMBOL} not found on {EXCHANGE_NAME}. Possible Gold symbols returned: {matches[:20]}')
    m=markets[SYMBOL]
    return {'exchange':EXCHANGE_NAME,'symbol':SYMBOL,'active':m.get('active'),'type':m.get('type'),'contract':m.get('contract'),'limits':m.get('limits'),'precision':m.get('precision')}


def ticker():
    ex=make_exchange(); return ex.fetch_ticker(SYMBOL)


def open_market(direction, amount):
    if not LIVE_TRADING: raise RuntimeError('LIVE_TRADING=false: order blocked (dry-run).')
    ex=make_exchange(); side='buy' if direction=='BUY' else 'sell'
    return ex.create_order(SYMBOL,'market',side,amount)


def close_market(direction, amount):
    if not LIVE_TRADING: raise RuntimeError('LIVE_TRADING=false: close blocked (dry-run).')
    ex=make_exchange(); side='sell' if direction=='BUY' else 'buy'
    return ex.create_order(SYMBOL,'market',side,amount,params={'reduceOnly':True})
