"""Gold-only SMC strategy core.

This is intentionally isolated from exchange execution and notifications.
The logic mirrors the existing paper bot: 15m BOS/CHoCH, ATR-adjusted
order block, 1H+4H EMA50 alignment, session filter, HIGH confidence gate,
0.05% SL buffer and 1:4 TP.
"""
import numpy as np
import pandas as pd

RR_RATIO = 4.0
STRUCTURE_SIZE = 5
ATR_LEN = 200
SL_BUFFER_PCT = 0.0005
HTF_EMA_LEN = 50
ASIA_START, ASIA_END = 0, 9
LONDON_START, LONDON_END = 7, 16
US_START, US_END = 12, 24


def compute_atr(df, length=ATR_LEN):
    prev = df["Close"].shift(1)
    tr = pd.concat([df["High"]-df["Low"], (df["High"]-prev).abs(),
                    (df["Low"]-prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()


def compute_parsed_hl(df, atr):
    wide = (df["High"] - df["Low"]) >= (2 * atr)
    return (pd.Series(np.where(wide, df["Low"], df["High"]), index=df.index),
            pd.Series(np.where(wide, df["High"], df["Low"]), index=df.index))


def compute_leg_structure(df, size=STRUCTURE_SIZE):
    highest, lowest = df["High"].rolling(size).max(), df["Low"].rolling(size).min()
    hs, ls = df["High"].shift(size), df["Low"].shift(size)
    leg = 0
    sh = {"level": None, "crossed": False, "bar": None}
    sl = {"level": None, "crossed": False, "bar": None}
    bias, events = 0, []
    for i in range(len(df)):
        old = leg
        if i >= size and not np.isnan(highest.iloc[i]) and not np.isnan(lowest.iloc[i]):
            if hs.iloc[i] > highest.iloc[i]: leg = 0
            elif ls.iloc[i] < lowest.iloc[i]: leg = 1
        if leg != old and i > 0:
            if leg == 1: sl = {"level": df["Low"].iloc[i-size], "crossed": False, "bar": i-size}
            else: sh = {"level": df["High"].iloc[i-size], "crossed": False, "bar": i-size}
        c = df["Close"].iloc[i]
        pc = df["Close"].iloc[i-1] if i else np.nan
        if sh["level"] is not None and not sh["crossed"] and not np.isnan(pc) and pc <= sh["level"] < c:
            tag = "CHOCH" if bias == -1 else "BOS"; sh["crossed"] = True; bias = 1
            events.append({"index":i,"time":df.index[i],"type":tag,"bias":"BULLISH","pivot_bar":sh["bar"],"pivot_level":sh["level"]})
        if sl["level"] is not None and not sl["crossed"] and not np.isnan(pc) and pc >= sl["level"] > c:
            tag = "CHOCH" if bias == 1 else "BOS"; sl["crossed"] = True; bias = -1
            events.append({"index":i,"time":df.index[i],"type":tag,"bias":"BEARISH","pivot_bar":sl["bar"],"pivot_level":sl["level"]})
    return events


def find_order_block(ph, pl, pivot_bar, break_bar, bias):
    if pivot_bar is None or break_bar <= pivot_bar: return None
    w = ph.iloc[pivot_bar:break_bar] if bias == "BEARISH" else pl.iloc[pivot_bar:break_bar]
    if w.empty: return None
    idx = w.idxmax() if bias == "BEARISH" else w.idxmin()
    return {"top": ph.loc[idx], "bottom": pl.loc[idx]}


def htf_bias(df, ema_len=HTF_EMA_LEN):
    ema = df["Close"].ewm(span=ema_len, adjust=False).mean()
    out = pd.Series(0, index=df.index)
    out[(df["Close"] > ema) & (df["Close"] > df["Open"])] = 1
    out[(df["Close"] < ema) & (df["Close"] < df["Open"])] = -1
    return out


def session_mask(df):
    idx = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
    h = idx.hour
    return pd.Series(((h >= ASIA_START) & (h < ASIA_END)) |
                     ((h >= LONDON_START) & (h < LONDON_END)) |
                     ((h >= US_START) & (h < US_END)), index=df.index)


def compute_signals(df15, df1h):
    """Return strategy candidates. Caller must use only the last CLOSED 15m bar."""
    df15 = df15.copy(); df1h = df1h.copy()
    df4h = df1h.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
    b1 = htf_bias(df1h.iloc[:-1] if len(df1h)>1 else df1h)
    b4 = htf_bias(df4h.iloc[:-1] if len(df4h)>1 else df4h)
    b1 = b1.reindex(df15.index, method="ffill").fillna(0)
    b4 = b4.reindex(df15.index, method="ffill").fillna(0)
    sess = session_mask(df15)
    ph, pl = compute_parsed_hl(df15, compute_atr(df15))
    out=[]
    for ev in compute_leg_structure(df15):
        i=ev["index"]; entry=float(df15["Close"].iloc[i]); s=bool(sess.iloc[i])
        h=bool((b1.iloc[i]==1 and b4.iloc[i]==1) if ev["bias"]=="BULLISH" else (b1.iloc[i]==-1 and b4.iloc[i]==-1))
        ob=find_order_block(ph,pl,ev["pivot_bar"],i,ev["bias"])
        if ev["bias"]=="BULLISH":
            anchor=float(ob["bottom"] if ob else ev["pivot_level"]); stop=anchor*(1-SL_BUFFER_PCT); direction="BUY"
        else:
            anchor=float(ob["top"] if ob else ev["pivot_level"]); stop=anchor*(1+SL_BUFFER_PCT); direction="SELL"
        risk=(entry-stop) if direction=="BUY" else (stop-entry)
        if risk<=0: continue
        tp=entry+(risk*RR_RATIO if direction=="BUY" else -risk*RR_RATIO)
        out.append({"index":i,"time":df15.index[i],"type":direction,"entry":entry,"sl":stop,"tp":tp,
                    "structure":ev["type"],"session_ok":s,"htf_ok":h,
                    "confidence":"HIGH" if s and h else "LOW"})
    return out


def latest_executable_signal(df15, df1h, freshness_bars=4):
    signals=compute_signals(df15,df1h)
    if len(df15)<2: return None
    last=len(df15)-2
    candidates=[s for s in signals if last-freshness_bars <= s["index"] <= last]
    if not candidates: return None
    s=candidates[-1]
    return s if s["confidence"]=="HIGH" else None
