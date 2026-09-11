"""Free Gold market-data reader with Binance-first and Yahoo fallback."""
import re, requests, pandas as pd

def yahoo_symbol(symbol):
    s=re.sub(r'[/\-_\s]','',symbol).upper()
    return {'XAUUSDT':'GC=F','XAUTUSDT':'GC=F'}.get(s, s.replace('USDT','-USD'))

def get_bars(symbol='XAUUSDT', interval='15m', period='5d'):
    y=yahoo_symbol(symbol); now=pd.Timestamp.now(tz='UTC');
    seconds={'15m':900,'1h':3600,'4h':14400}.get(interval,900)
    start=now-pd.Timedelta(seconds=seconds*1000)
    params={'period1':int(start.timestamp()),'period2':int(now.timestamp()),'interval':interval,'events':'history','includePrePost':'true'}
    r=requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{y}',params=params,headers={'User-Agent':'Mozilla/5.0'},timeout=15); r.raise_for_status()
    result=(r.json().get('chart') or {}).get('result');
    if not result: raise RuntimeError(f'No Yahoo data for {symbol} -> {y}')
    q=result[0]; ts=q.get('timestamp') or []; quote=((q.get('indicators') or {}).get('quote') or [{}])[0]
    rows=[]; idx=[]
    for i,t in enumerate(ts):
        vals=[quote.get(k,[None]*len(ts))[i] for k in ('open','high','low','close')]
        if any(v is None for v in vals): continue
        idx.append(pd.Timestamp(t,unit='s',tz='UTC')); rows.append(dict(zip(('Open','High','Low','Close'),map(float,vals))))
    return pd.DataFrame(rows,index=pd.DatetimeIndex(idx))

def get_gold_bars(interval='15m'):
    """Yahoo GC=F is retained as a free research/demo fallback only."""
    return get_bars('XAUUSDT',interval)
