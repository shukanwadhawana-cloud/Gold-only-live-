"""Read-only exchange discovery. No API key and no orders."""
import ccxt

for name in ('binance','bingx'):
    try:
        ex=getattr(ccxt,name)({'enableRateLimit':True,'options':{'defaultType':'swap'}})
        markets=ex.load_markets()
        matches=[(s,m.get('type'),m.get('contract'),m.get('active'),m.get('limits')) for s,m in markets.items() if 'XAU' in s.upper() or 'GOLD' in s.upper()]
        print(f'{name}: {matches}')
    except Exception as exc:
        print(f'{name}: UNAVAILABLE -> {exc}')
