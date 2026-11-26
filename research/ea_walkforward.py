"""Replicates QuantForgEA on exported XAUUSD bars and runs rolling walk-forward.
Usage: python3 -I ea_walkforward.py /tmp/bt
Simplifications: fixed spread (default 0.30), SL checked before TP inside a bar, 1 oz per 1.00 lot-unit (0.01 lot)."""
import sys, itertools, numpy as np, pandas as pd
D = sys.argv[1] if len(sys.argv) > 1 else "/tmp/bt"
m15 = pd.read_csv(f"{D}/M15.csv", parse_dates=["time"]).reset_index(drop=True)
h1 = pd.read_csv(f"{D}/H1.csv", parse_dates=["time"]).reset_index(drop=True)
SPREAD = 0.30
t = m15.time.values; O, H, L, C = (m15[c].values for c in ("open", "high", "low", "close"))
n = len(m15)
# H1 EMAs on closed bars; value usable from open-time+1h
e50 = h1.close.ewm(span=50, adjust=False).mean().values
e200 = h1.close.ewm(span=200, adjust=False).mean().values
h1_avail = (h1.time + pd.Timedelta(hours=1)).values
idx = np.searchsorted(h1_avail, t, side="right") - 1          # last closed H1 bar at M15 bar open
ok_idx = idx >= 200
trend = np.where(ok_idx, np.sign(e50[np.clip(idx, 0, None)] - e200[np.clip(idx, 0, None)]), 0)
tr = np.maximum(H - L, np.maximum(np.abs(H - np.roll(C, 1)), np.abs(L - np.roll(C, 1))))
atr = pd.Series(tr).rolling(14).mean().values
hour = pd.DatetimeIndex(t).hour.values; dow = pd.DatetimeIndex(t).dayofweek.values

def signals(look, hs, he, use_trend=True):
    hh = pd.Series(H).shift(2).rolling(look).max().values   # bars 2..look+1 back from new bar
    ll = pd.Series(L).shift(2).rolling(look).min().values
    c1 = np.roll(C, 1)
    up = c1 > hh; dn = c1 < ll
    if use_trend: up &= trend > 0; dn &= trend < 0
    sess = (hour >= hs) & (hour < he) & (dow < 5)
    s = np.where(up, 1, np.where(dn, -1, 0)) * sess
    return s

def simulate(look=20, am=1.2, rr=1.6, hs=7, he=17, use_trend=True, lo=0, hi=None, sp=SPREAD, min_rr=1.5):
    hi = hi or n
    s = signals(look, hs, he, use_trend); tr_ = []
    i = max(lo, 250); end = hi - 1
    while i < end:
        d = s[i]
        if d == 0 or np.isnan(atr[i-1]) or atr[i-1] <= 0: i += 1; continue
        risk = atr[i-1] * am
        if (risk*rr - sp) / (risk + sp) < min_rr: i += 1; continue
        if d == 1: entry = O[i] + sp; sl = entry - risk; tp = entry + risk*rr
        else:      entry = O[i];      sl = entry + risk; tp = entry - risk*rr
        j = i; res = None
        while j < hi:
            if d == 1: hs_, ht_ = L[j] <= sl, H[j] >= tp
            else:      hs_, ht_ = H[j] + sp >= sl, L[j] + sp <= tp
            if hs_: res = -risk; break
            if ht_: res = risk*rr; break
            j += 1
        if res is None: break
        tr_.append((i, res)); i = j + 1
    return tr_

def stats(tr_):
    if not tr_: return dict(n=0, pf=0, win=0, exp=0, net=0, dd=0)
    r = np.array([x[1] for x in tr_]); w = r[r > 0].sum(); l = -r[r < 0].sum()
    eq = np.cumsum(r); dd = (np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max()
    return dict(n=len(r), pf=w/l if l else 9.99, win=(r > 0).mean(), exp=r.mean(), net=r.sum(), dd=dd)

if __name__ == "__main__":
    yr = np.searchsorted(t, np.datetime64("2025-11-27"))
    for name, (a, b) in {"last-year (tester-like)": (yr, n), "full 2y": (0, n)}.items():
        print(name, stats(simulate(lo=a, hi=b)))
    # walk-forward
    grid = list(itertools.product([10, 20, 40], [1.0, 1.5, 2.0], [1.0, 1.6, 2.5], [(7,17),(12,17),(7,12),(0,24)], [True, False]))
    ts = pd.Series(pd.DatetimeIndex(t)); months = pd.period_range(ts.min(), ts.max(), freq="M")
    TRAIN, TEST = 9, 3; oos_all = []; rows = []
    for k in range(0, len(months) - TRAIN - TEST + 1, TEST):
        a = np.searchsorted(t, months[k].start_time.to_datetime64()); b = np.searchsorted(t, months[k+TRAIN].start_time.to_datetime64())
        c = np.searchsorted(t, months[k+TRAIN+TEST-1].end_time.to_datetime64())
        best = None
        for g in grid:
            st = stats(simulate(g[0], g[1], g[2], g[3][0], g[3][1], g[4], a, b))
            if st["n"] >= 60 and (best is None or st["pf"] > best[0]["pf"]): best = (st, g)
        if best is None: continue
        g = best[1]; tr_ = simulate(g[0], g[1], g[2], g[3][0], g[3][1], g[4], b, c)
        so = stats(tr_); oos_all += tr_
        rows.append((str(months[k+TRAIN]), g, round(best[0]["pf"], 2), so["n"], round(so["pf"], 2), round(so["net"], 1)))
    for r in rows: print(r)
    print("OOS combined", stats(oos_all))
    # also: fixed baseline EA params per OOS span, and best single-fit full-sample (in-sample, for reference only)
    allst = sorted(((stats(simulate(*g[:3], g[3][0], g[3][1], g[4])), g) for g in grid), key=lambda x: -x[0]["pf"])[:5]
    print("TOP IN-SAMPLE (not evidence):"); [print(round(s['pf'],2), s['n'], g) for s, g in allst]
