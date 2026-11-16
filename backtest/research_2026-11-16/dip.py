"""The live v3.9 trend-day dip (scan/auto_scan.py) on Twelve Data 5m bars, indicators precomputed. Variants: sides, target cap, 4H filter."""
import bisect, sys
from eng import *
b5 = load('xau_5m.json'); T5 = [x['t'] for x in b5]
b15, b1h, b4h, b1d = resample(b5, 900), resample(b5, 3600), resample(b5, 14400), resample(b5, 86400)
e20_5 = ema([x['c'] for x in b5], 20); a5 = atr(b5)
c15 = [x['c'] for x in b15]; e20_15, e50_15 = ema(c15, 20), ema(c15, 50); t15c = [x['t'] + 900 for x in b15]
e50_1h = ema([x['c'] for x in b1h], 50); t1c = [x['t'] + 3600 for x in b1h]
e50_4h = ema([x['c'] for x in b4h], 50); t4c = [x['t'] + 14400 for x in b4h]
tdc = [x['t'] + 86400 for x in b1d]
SH, SL_ = [], []  # (confirm time, price) of 1H swing highs / lows (confirmed when bar i+2 closes)
for i in range(2, len(b1h) - 2):
    w = b1h[i - 2:i + 3]; ct = b1h[i + 2]['t'] + 3600
    if b1h[i]['h'] == max(x['h'] for x in w): SH.append((ct, b1h[i]['h']))
    if b1h[i]['l'] == min(x['l'] for x in w): SL_.append((ct, b1h[i]['l']))
SHt = [x[0] for x in SH]; SLt = [x[0] for x in SL_]
def last(ts, arr, T): j = bisect.bisect_right(ts, T) - 1; return j
def signal(i, sides, cap, use4h):
    bar, pv = b5[i], b5[i - 1]; T = bar['t'] + 300; now = ldn(T)
    mins = now.hour * 60 + now.minute; wd = now.weekday()
    if wd == 5 or (wd == 6 and mins < 1380) or (wd == 4 and mins >= 1200) or 1320 <= mins < 1380 or mins < 360: return None
    j15 = last(t15c, None, T); j1 = last(t1c, None, T); j4 = last(t4c, None, T); jd = last(tdc, None, T)
    if min(j15, j1, j4, jd) < 55 and j4 < 55: pass
    if j15 < 55 or j1 < 55 or j4 < 10 or jd < 0: return None
    hs = [p for t, p in SH[:bisect.bisect_right(SHt, T)][-4:]]; ls = [p for t, p in SL_[:bisect.bisect_right(SLt, T)][-4:]]
    if len(hs) < 2 or len(ls) < 2: return None
    st = 'UP' if hs[-1] > hs[-2] and ls[-1] > ls[-2] else 'DN' if hs[-1] < hs[-2] and ls[-1] < ls[-2] else 'MIX'
    c1 = b1h[j1]['c']; bias1 = 'UP' if c1 > e50_1h[j1] and st != 'DN' else 'DN' if c1 < e50_1h[j1] and st != 'UP' else 'FLAT'
    k = 2 / 51; price = bar['c']; bias4 = 'UP' if price > e50_4h[j4] * (1 - k) + price * k else 'DN'
    e20, e50 = e20_15[j15], e50_15[j15]
    if abs(e20 - e50) < 0.05: return None
    buy = e20 > e50
    if bias1 != ('UP' if buy else 'DN') or ('BUY' if buy else 'SELL') not in sides: return None
    if use4h and bias4 != ('UP' if buy else 'DN'): return None
    A5 = a5[i]; E5 = e20_5[i]
    if A5 is None: return None
    sg = 1 if buy else -1; rng = bar['h'] - bar['l'] or 1e-9; pos = (bar['c'] - bar['l']) / rng
    body, pbody = abs(bar['c'] - bar['o']), abs(pv['c'] - pv['o'])
    lv = [b1d[jd]['h'], b1d[jd]['l']] + hs + ls
    touch = bar['l'] <= E5 + 0.5 * A5 if buy else bar['h'] >= E5 - 0.5 * A5
    strong = (bar['c'] > E5 and bar['c'] > bar['o'] and pos >= 2/3) if buy else (bar['c'] < E5 and bar['c'] < bar['o'] and pos <= 1/3)
    eng_ = (bar['c'] > bar['o'] and pv['c'] < pv['o'] and bar['c'] >= pv['o'] and bar['o'] <= pv['c'] and body > pbody) if buy else \
           (bar['c'] < bar['o'] and pv['c'] > pv['o'] and bar['c'] <= pv['o'] and bar['o'] >= pv['c'] and body > pbody)
    wick = (min(bar['o'], bar['c']) - bar['l']) if buy else (bar['h'] - max(bar['o'], bar['c']))
    pin = wick >= 2 * max(body, 1e-9) and wick >= 0.5 * rng and (pos >= 0.6 if buy else pos <= 0.4)
    beyond = bar['c'] > E5 if buy else bar['c'] < E5
    if not touch or not ((beyond and (eng_ or pin)) or strong): return None
    en = bar['c']
    if abs(en - E5) > 1.5 * A5 or rng > 2 * A5: return None
    ext = min(x['l'] for x in b5[i - 2:i + 1]) if buy else max(x['h'] for x in b5[i - 2:i + 1])
    sl = ext - sg * 1.5
    if sg * (en - sl) < A5: sl = en - sg * A5
    R = abs(en - sl)
    if sg * (en - sl) <= 0 or R > 10: return None
    opp = [x for x in lv if x > en + 0.1] if buy else [x for x in lv if x < en - 0.1]
    nx = (min(opp) if buy else max(opp)) if opp else None
    rr = abs(nx - en) / R if nx else 9
    if rr < 1: return None
    return dict(t=T, buy=buy, en=en, sl=sl, tp=en + sg * R * min(cap, rr), R=R)
def run(t0, t1, sides=('SELL',), cap=2.5, use4h=True):
    i = max(bisect.bisect_left(T5, t0), 60); e = bisect.bisect_left(T5, t1); tr = []; day = {}
    while i < e:
        s = signal(i, sides, cap, use4h)
        if s:
            dk = ldn(s['t']).date(); d = day.setdefault(dk, [0, 0])
            if d[1] < 5 and d[0] > -40:
                pl, j, how = walk(b5, i, s['buy'], s['en'], s['sl'], s['tp'])
                s.update(pl=pl, how=how); tr.append(s)
                if pl is None: break
                d[0] += pl; d[1] += pl < 0; i = j + 1; continue
        i += 1
    return tr
if __name__ == '__main__':
    import datetime as dt
    ts = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=UTC).timestamp())
    A, M, B = ts(2026, 6, 8), ts(2026, 9, 1), ts(2026, 11, 17)
    print('5m data', ldn(b5[0]['t']).date(), '->', ldn(b5[-1]['t']).date(), ' TRAIN 8 Jun-31 Aug | TEST 1 Sep-16 Nov (unseen)')
    for name, kw in [('LIVE: sells only, 2.5R, 4H on', {}), ('sells only, 1.5R', dict(cap=1.5)), ('buys only, 2.5R', dict(sides=('BUY',))),
                     ('both sides, 2.5R', dict(sides=('BUY', 'SELL'))), ('both, 1.5R', dict(sides=('BUY', 'SELL'), cap=1.5)),
                     ('both, 2.5R, 4H off', dict(sides=('BUY', 'SELL'), use4h=False))]:
        print(f'{name:32s} train {stats(run(A, M, **kw))["txt"]}\n{"":32s} TEST  {stats(run(M, B, **kw))["txt"]}')
