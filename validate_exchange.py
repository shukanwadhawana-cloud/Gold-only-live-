"""Read-only Binance Gold discovery. No API key and no orders."""
import ccxt


def main():
    ex = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
    markets = ex.load_markets()
    matches = []
    for m in markets.values():
        if str(m.get('id','')).upper() == 'XAUUSDT' or ('XAU' in str(m.get('id','')).upper() and m.get('quote') == 'USDT'):
            matches.append({k:m.get(k) for k in ('id','symbol','type','contract','swap','active','limits','precision')})
    print('Binance Gold markets:')
    for item in matches:
        print(item)
    if not matches:
        raise SystemExit('XAUUSDT was not exposed by this Binance market-data endpoint.')


if __name__ == '__main__':
    main()
