"""Shared engine: load Twelve Data XAU/USD bars (UTC), resample, indicators, trade walker. Costs: $0.40 a round trip at 0.01 lot."""
import json, bisect, datetime as dt
from zoneinfo import ZoneInfo
L = ZoneInfo('Europe/London'); UTC = dt.timezone.utc; COST = 0.40
def load(path):
    d = json.load(open(path)); out = []
    for k, o, h, l, c in d['bars']:
        t = dt.datetime.fromisoformat(k).replace(tzinfo=UTC)
        out.append(dict(t=int(t.timestamp()), o=o, h=h, l=l, c=c))
    return out
def resample(b, sec):
    out = []; cur = None
    for x in b:
        k = x['t'] // sec * sec
        if cur is None or cur['t'] != k:
            if cur: out.append(cur)
            cur = dict(t=k, o=x['o'], h=x['h'], l=x['l'], c=x['c'])
        else:
            cur['h'] = max(cur['h'], x['h']); cur['l'] = min(cur['l'], x['l']); cur['c'] = x['c']
    if cur: out.append(cur)
    return out
def ema(x, n):
    k = 2 / (n + 1); o = [x[0]]
    for v in x[1:]: o.append(v * k + o[-1] * (1 - k))
    return o
def atr(b, n=14):
    tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
    o = [None] * len(b); a = sum(tr[:n]) / n; o[n - 1] = a
    for i in range(n, len(b)): a = (a * (n - 1) + tr[i]) / n; o[i] = a
    return o
def ldn(ts): return dt.datetime.fromtimestamp(ts, UTC).astimezone(L)
def walk(b, i0, buy, en, sl, tp, max_s=8 * 3600, trail=None):
    """From bar i0+1 on: stop first, then target, then time exit; Friday 21:00 London exit. Returns (pl, j, how)."""
    sg = 1 if buy else -1; t0 = b[i0]['t']
    for j in range(i0 + 1, len(b)):
        x = b[j]
        if (x['l'] <= sl) if buy else (x['h'] >= sl): return sg * (sl - en) - COST, j, 'SL'
        if tp is not None and ((x['h'] >= tp) if buy else (x['l'] <= tp)): return sg * (tp - en) - COST, j, 'TP'
        lt = ldn(x['t'] + 300)
        if (max_s and x['t'] - t0 >= max_s) or (lt.weekday() == 4 and lt.hour >= 21): return sg * (x['c'] - en) - COST, j, 'TIME'
        if trail: sl = trail(sl, j)
    return None, len(b), 'OPEN'
def stats(tr):
    c = [x for x in tr if x['pl'] is not None]
    if not c: return dict(n=0, txt='  0 trades')
    w = sum(x['pl'] > 0 for x in c); g = sum(x['pl'] for x in c if x['pl'] > 0); l = -sum(x['pl'] for x in c if x['pl'] <= 0)
    eq = pk = dd = 0
    for x in c: eq += x['pl']; pk = max(pk, eq); dd = max(dd, pk - eq)
    R = [x['pl'] / x['R'] for x in c if x.get('R')]
    pl = sum(x['pl'] for x in c)
    return dict(n=len(c), pl=pl, pf=g / l if l else 99, dd=dd, wr=w / len(c), avgR=sum(R) / len(R) if R else 0,
                txt=f'{len(c):4d} trades {100*w/len(c):3.0f}% wins  {pl:+8.1f} $  PF {g/l if l else 99:4.2f}  avg {sum(R)/len(R) if R else 0:+.2f}R  worst drop {dd:5.1f}')
