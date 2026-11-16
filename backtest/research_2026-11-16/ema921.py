"""EMA 9/21 cross on gold, many variants, 12 months of XAU/USD 15m (Twelve Data). R after $0.40/oz cost.
TRAIN 10 Nov 2025-31 May 2026, TEST 1 Jun-16 Nov 2026 (unseen)."""
import bisect, datetime as dt, itertools
from eng import *
b15 = load('xau_15m.json'); TF = {'15m': b15, '1h': resample(b15, 3600), '4h': resample(b15, 14400)}
h4 = TF['4h']; c4 = [x['c'] for x in h4]; e50_4, e200_4 = ema(c4, 50), ema(c4, 200); T4c = [x['t'] + 14400 for x in h4]
ts = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=UTC).timestamp())
S, M, E = ts(2025, 11, 10), ts(2026, 6, 1), ts(2026, 11, 17)
def adx(b, n=14):
    pdm, mdm, tr = [0], [0], [b[0]['h'] - b[0]['l']]
    for p, x in zip(b, b[1:]):
        up, dn = x['h'] - p['h'], p['l'] - x['l']
        pdm.append(up if up > dn and up > 0 else 0); mdm.append(dn if dn > up and dn > 0 else 0)
        tr.append(max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])))
    o = [None] * len(b); a = sp = sm = 0; dx = []; ad = None
    for i in range(1, len(b)):
        if i <= n: a += tr[i]; sp += pdm[i]; sm += mdm[i]; continue
        a = a - a / n + tr[i]; sp = sp - sp / n + pdm[i]; sm = sm - sm / n + mdm[i]
        pdi, mdi = 100 * sp / a, 100 * sm / a; d = 100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0
        if ad is None: dx.append(d); ad = sum(dx) / n if len(dx) == n else None
        else: ad = (ad * (n - 1) + d) / n
        o[i] = ad
    return o
IND = {}
for k, b in TF.items():
    c = [x['c'] for x in b]; IND[k] = dict(e9=ema(c, 9), e21=ema(c, 21), A=atr(b), adx=adx(b), T=[x['t'] for x in b])
def h4t(t):
    j = bisect.bisect_right(T4c, t) - 1
    if j < 200: return None
    return 'UP' if e50_4[j] > e200_4[j] else 'DN'
def run(t0, t1, tf='1h', filt='none', exit_='cross', hours='all', stopN=2.0):
    b = TF[tf]; I = IND[tf]; e9, e21, A, AD, T = I['e9'], I['e21'], I['A'], I['adx'], I['T']; dur = b[1]['t'] - b[0]['t']
    i = max(bisect.bisect_left(T, t0), 60); e = bisect.bisect_left(T, t1); tr = []
    while i < e:
        up = e9[i] > e21[i] and e9[i - 1] <= e21[i - 1]; dn = e9[i] < e21[i] and e9[i - 1] >= e21[i - 1]
        if not (up or dn): i += 1; continue
        lt = ldn(b[i]['t'] + dur)
        if hours == '07-17' and not (lt.weekday() < 5 and 7 <= lt.hour < 17): i += 1; continue
        if lt.weekday() == 4 and lt.hour >= 19: i += 1; continue
        if filt in ('h4', 'h4+adx') and h4t(b[i]['t'] + dur) != ('UP' if up else 'DN'): i += 1; continue
        if filt in ('adx', 'h4+adx') and (AD[i] is None or AD[i] < 20): i += 1; continue
        sg = 1 if up else -1; en = b[i]['c']; R = stopN * A[i]; sl = en - sg * R; tp = en + sg * 2 * R if exit_ == '2R' else None; pl = None
        for j in range(i + 1, len(b)):
            y = b[j]
            if (y['l'] <= sl) if up else (y['h'] >= sl): pl = sg * (sl - en); break
            if tp is not None and ((y['h'] >= tp) if up else (y['l'] <= tp)): pl = sg * (tp - en); break
            if exit_ == 'cross' and ((e9[j] < e21[j]) if up else (e9[j] > e21[j])): pl = sg * (y['c'] - en); break
            if exit_ == 'trail':
                ns = y['c'] - sg * stopN * A[j]; sl = max(sl, ns) if up else min(sl, ns)
            yl = ldn(y['t'] + dur)
            if yl.weekday() == 4 and yl.hour >= 21: pl = sg * (y['c'] - en); break
        if pl is None: break
        tr.append((pl - COST) / R); i = j + 1
    return tr
def st(r):
    if not r: return (0, 0, 0, 0)
    g = sum(v for v in r if v > 0); l = -sum(v for v in r if v <= 0)
    return (len(r), sum(r), g / l if l else 99, 100 * sum(v > 0 for v in r) / len(r))
rows = []
for tf, filt, ex, hr in itertools.product(('15m', '1h', '4h'), ('none', 'h4', 'adx', 'h4+adx'), ('cross', '2R', 'trail'), ('all', '07-17')):
    a, t = st(run(S, M, tf, filt, ex, hr)), st(run(M, E, tf, filt, ex, hr))
    rows.append((tf, filt, ex, hr, a, t))
days = (M - S) / 86400 * 5 / 7
print(f'{"tf":4s} {"filter":7s} {"exit":6s} {"hours":6s} | {"TRAIN n  R    PF  win":24s} | {"TEST n  R    PF  win":24s} | trades/day')
for tf, f, ex, hr, a, t in sorted(rows, key=lambda r: -min(r[4][2], r[5][2])):
    ok = '  <- both halves PF>1.1' if a[2] > 1.1 and t[2] > 1.1 else ''
    print(f'{tf:4s} {f:7s} {ex:6s} {hr:6s} | {a[0]:4d} {a[1]:+6.1f} {a[2]:4.2f} {a[3]:3.0f}% | {t[0]:4d} {t[1]:+6.1f} {t[2]:4.2f} {t[3]:3.0f}% | {(a[0]+t[0])/(days*2.0):.1f}{ok}')
