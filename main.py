"""Gold-only runner. No Telegram. Dry-run by default."""
import os, json
from strategy import latest_executable_signal
from market_data import get_gold_bars

STATE='gold_state.json'

def load_state():
    try:
        with open(STATE) as f: return json.load(f)
    except (OSError,ValueError): return {}

def save_state(s):
    tmp=STATE+'.tmp'
    with open(tmp,'w') as f: json.dump(s,f,indent=2)
    os.replace(tmp,STATE)

def main():
    df15=get_gold_bars('15m'); df1h=get_gold_bars('1h')
    if len(df15)<100 or len(df1h)<50: raise RuntimeError('Not enough Gold candles for strategy.')
    sig=latest_executable_signal(df15,df1h)
    state=load_state()
    if not sig:
        print('GOLD: no fresh HIGH-confidence executable signal.')
        return
    key=f"{sig['time'].isoformat()}_{sig['type']}"
    if state.get('last_signal')==key:
        print(f'GOLD: signal already processed: {key}'); return
    print('GOLD SIGNAL')
    print(f"Direction: {sig['type']} | Entry: {sig['entry']:.5f} | SL: {sig['sl']:.5f} | TP: {sig['tp']:.5f}")
    print(f"Structure: {sig['structure']} | Session: {sig['session_ok']} | HTF: {sig['htf_ok']} | RR: 1:{4:g}")
    if os.getenv('LIVE_TRADING','false').lower()!='true':
        print('DRY RUN: no exchange order placed.')
    else:
        raise RuntimeError('LIVE_TRADING is not enabled in this initial build. Exchange/demo execution must be validated first.')
    state['last_signal']=key; save_state(state)

if __name__=='__main__': main()
