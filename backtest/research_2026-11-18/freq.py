"""How many setups a day, and at what quality? (Woody 18 Nov: 'at least 5 setups a day')"""
import bisect, datetime as dt, json, sys, os
sys.path.insert(0, '../../scan/brain')
import score as S
import asia as A
from features import ema, atr
m, ev = S.load_model()
days_test = len({A.ldn(t['ts']).date() for t in ev['trades'] if t['half'] == 'test'}) or 1
trading_days_test = sum(1 for d in sorted({A.ldn(x['t']).date() for x in A.b if x['T'] >= A.SPLIT}) if d.weekday() < 5)
print('test-half trading days', trading_days_test)
bands = {}
for t in ev['trades']:
    if t['half'] != 'test': continue
    sc = S.score(m, S.expected(m, t['strategy'], t['f'])[0])
    k = 'A 85+' if sc >= 85 else 'B 75-84' if sc >= 75 else 'C 60-74' if sc >= 60 else 'D <60'
    bands.setdefault(k, []).append(t['R'])
cum = []
for k in sorted(bands):
    v = bands[k]; cum += v
    print(f'{k:8s} {len(v):4d} setups {len(v)/trading_days_test:4.2f}/day avg {sum(v)/len(v):+.2f}R | cumulative down to here {len(cum)/trading_days_test:4.2f}/day avg {sum(cum)/len(cum):+.2f}R total {sum(cum):+.1f}R')
# Higher-frequency candidates on 15m / 5m-like bars: 15m EMA9/21 cross with BOTH H1 bias and H4 trend, all hours (not 22-23)
b = A.b; h4 = A.resample(b, 14400); T4 = [x['T'] for x in h4]; c4 = [x['c'] for x in h4]; E50, E200 = ema(c4, 50), ema(c4, 200)
h4up = lambda ts: (lambda i: E50[i] > E200[i])(bisect.bisect_right(T4, ts) - 1)
for name, hours, tgt in (('M15 cross + H1 + H4, all hours, 2R', range(0, 24), 2), ('M15 cross + H1 + H4, 07-20, 2R', range(7, 20), 2), ('M15 cross + H1 + H4, all hours, 1R', range(0, 24), 1)):
    out = []
    for j in range(300, len(b)):
        x = b[j]; ts = x['T']; t = A.ldn(ts)
        if t.weekday() > 4 or t.hour not in hours or t.hour == 22: continue
        up = A.m9[j] > A.m21[j] and A.m9[j-1] <= A.m21[j-1]; dn = A.m9[j] < A.m21[j] and A.m9[j-1] >= A.m21[j-1]
        i1 = A.done(ts)
        if not (up or dn) or (A.e9[i1] > A.e21[i1]) != up or h4up(ts) != up: continue
        en = x['c']; risk = A.A1[i1]; sl = en - (1 if up else -1) * risk; tp = en + (1 if up else -1) * tgt * risk
        r = A.walk(j, up, en, sl, tp, ts + 8 * 3600)
        if r is not None: out.append((ts, r))
    tr = [r for ts, r in out if ts < A.SPLIT]; te = [r for ts, r in out if ts >= A.SPLIT]
    print(f'{name:38s} test {len(te)/trading_days_test:4.2f}/day | train {A.stats(tr)} | test {A.stats(te)}')
