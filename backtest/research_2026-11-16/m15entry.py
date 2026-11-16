"""M15 EMA 9/21 cross entries, filtered by H4 trend (EMA50 vs 200) and the H1 9/21 state. 12 months XAU/USD, R after costs."""
import bisect, itertools, datetime as dt
from eng import *
import ema921 as m
b = m.TF['15m']; I = m.IND['15m']; e9, e21, A, T = I['e9'], I['e21'], I['A'], I['T']
h1 = m.TF['1h']; H = m.IND['1h']; T1c = [x['t'] + 3600 for x in h1]
def h1state(t):
    j = bisect.bisect_right(T1c, t) - 1
    return None if j < 30 else ('UP' if H['e9'][j] > H['e21'][j] else 'DN')
def h1atr(t):
    j = bisect.bisect_right(T1c, t) - 1; return H['A'][j]
def run(t0, t1, stop='3xm15', exit_='m15', hours='all'):
    i = max(bisect.bisect_left(T, t0), 60); e = bisect.bisect_left(T, t1); tr = []
    while i < e:
        up = e9[i] > e21[i] and e9[i - 1] <= e21[i - 1]; dn = e9[i] < e21[i] and e9[i - 1] >= e21[i - 1]
        if not (up or dn): i += 1; continue
        tc = b[i]['t'] + 900; lt = ldn(tc); d = 'UP' if up else 'DN'
        if (lt.weekday() == 4 and lt.hour >= 19) or (hours == '07-22' and not 7 <= lt.hour < 22): i += 1; continue
        if m.h4t(tc) != d or h1state(tc) != d: i += 1; continue
        sg = 1 if up else -1; en = b[i]['c']
        R = {'3xm15': 3 * A[i], '2xm15': 2 * A[i], '1xh1': h1atr(tc), '2xh1': 2 * h1atr(tc)}[stop]; sl = en - sg * R; pl = None
        for j in range(i + 1, len(b)):
            y = b[j]
            if (y['l'] <= sl) if up else (y['h'] >= sl): pl = sg * (sl - en); break
            yc = y['t'] + 900
            if exit_ == 'm15' and ((e9[j] < e21[j]) if up else (e9[j] > e21[j])): pl = sg * (y['c'] - en); break
            if exit_ == 'h1' and h1state(yc) != d: pl = sg * (y['c'] - en); break
            if exit_ == '2R' and ((y['h'] >= en + 2 * R) if up else (y['l'] <= en - 2 * R)): pl = 2 * R; break
            yl = ldn(yc)
            if yl.weekday() == 4 and yl.hour >= 21: pl = sg * (y['c'] - en); break
        if pl is None: break
        tr.append((pl - COST) / R); i = j + 1
    return tr
def line(r):
    if not r: return '   0'
    n = len(r); g = sum(v for v in r if v > 0); l = -sum(v for v in r if v <= 0); eq = pk = dd = 0
    for v in r: eq += v; pk = max(pk, eq); dd = max(dd, pk - eq)
    return f'{n:4d} tr {sum(r):+6.1f}R PF {g/l if l else 99:4.2f} win {100*sum(v>0 for v in r)/n:3.0f}% run {dd:4.1f}R'
print('M15 9/21 cross entry, only when H4 trend AND H1 9/21 agree | TRAIN Nov-May | TEST Jun-Nov (unseen) | per week')
for st, ex, hr in itertools.product(('2xm15', '3xm15', '1xh1', '2xh1'), ('m15', 'h1', '2R'), ('all', '07-22')):
    a, t = run(m.S, m.M, st, ex, hr), run(m.M, m.E, st, ex, hr)
    ok = ' <- both PF>1.1' if a and t and (sum(v for v in a if v > 0) / max(1e-9, -sum(v for v in a if v <= 0))) > 1.1 and (sum(v for v in t if v > 0) / max(1e-9, -sum(v for v in t if v <= 0))) > 1.1 else ''
    print(f'stop {st:5s} exit {ex:3s} {hr:5s} | {line(a)} | {line(t)} | {(len(a)+len(t))/55:.1f}{ok}')
