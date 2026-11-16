"""Strategy 1, swing version, on 20 years of daily gold futures (FMP GCUSD):
trend = daily EMA50 above EMA200 (buys) or below (sells); pullback = the day's low (high) touches the 21-day EMA;
confirmation = that day closes back beyond the EMA21 in the trend direction; entry at the close; stop beyond the 5-day swing - 0.2 ATR;
target 2R; max hold 30 days. Cost $0.40/oz. Results in R. Halves: 2007-2016 vs 2017-2026."""
import json, statistics as st
raw = json.load(open('gcusd_daily_fmp.json'))
b = sorted([dict(d=x['date'], o=x['open'], h=x['high'], l=x['low'], c=x['close']) for x in raw], key=lambda x: x['d'])
print('daily bars', len(b), b[0]['d'], '->', b[-1]['d'])
def ema(x, n):
    k = 2 / (n + 1); o = [x[0]]
    for v in x[1:]: o.append(v * k + o[-1] * (1 - k))
    return o
c = [x['c'] for x in b]; e21, e50, e200 = ema(c, 21), ema(c, 50), ema(c, 200)
tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
A = [None] * len(b); a = sum(tr[:14]) / 14
for i in range(14, len(b)): a = (a * 13 + tr[i]) / 14; A[i] = a
def run(side='both', tgt=2.0):
    out = []; i = 210
    while i < len(b):
        x = b[i]; up = e50[i] > e200[i]; dn = e50[i] < e200[i]
        buy = up and side in ('both', 'buy') and x['l'] <= e21[i] and x['c'] > e21[i] and x['c'] > x['o']
        sell = dn and side in ('both', 'sell') and x['h'] >= e21[i] and x['c'] < e21[i] and x['c'] < x['o']
        if not (buy or sell): i += 1; continue
        sg = 1 if buy else -1; en = x['c']
        sw = min(y['l'] for y in b[i - 4:i + 1]) if buy else max(y['h'] for y in b[i - 4:i + 1])
        sl = sw - sg * 0.2 * A[i]; R = abs(en - sl)
        if R <= 0: i += 1; continue
        tp = en + sg * tgt * R; pl = None
        for j in range(i + 1, min(i + 31, len(b))):
            y = b[j]
            if (y['l'] <= sl) if buy else (y['h'] >= sl): pl = sg * (sl - en); break
            if (y['h'] >= tp) if buy else (y['l'] <= tp): pl = sg * (tp - en); break
        else:
            if j >= len(b) - 1: break
            pl = sg * (b[j]['c'] - en)
        out.append(dict(d=x['d'], r=(pl - 0.4) / R, R=R)); i = j + 1
    return out
def line(t):
    n = len(t); r = [x['r'] for x in t]; w = sum(v > 0 for v in r)
    eq = pk = dd = 0
    for v in r: eq += v; pk = max(pk, eq); dd = max(dd, pk - eq)
    g = sum(v for v in r if v > 0); l = -sum(v for v in r if v <= 0)
    return f'{n:4d} trades {100*w/max(n,1):3.0f}% wins {sum(r):+6.1f}R  PF {g/l if l else 99:4.2f}  worst run {dd:4.1f}R  median stop ${st.median([x["R"] for x in t]) if t else 0:.0f}'
for side in ('both', 'buy', 'sell'):
    t = run(side)
    a = [x for x in t if x['d'] < '2017-01-01']; z = [x for x in t if x['d'] >= '2017-01-01']; y = [x for x in t if x['d'] >= '2025-11-10']
    print(f'swing pullback {side:4s}  2007-2016 {line(a)}\n{"":20s}2017-2026 {line(z)}\n{"":20s}last 12 m {line(y)}')
