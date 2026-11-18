"""Robustness of the Asia breakout + H1 bias + H4 trend: neighbouring range ends, stops, targets, exits; per-side; per entry hour."""
import bisect, datetime as dt
import asia as A
from features import ema
h4 = A.resample(A.b, 14400); T4 = [x['T'] for x in h4]; c4 = [x['c'] for x in h4]; E50, E200 = ema(c4, 50), ema(c4, 200)
h4up = lambda ts: (lambda i: E50[i] > E200[i])(bisect.bisect_right(T4, ts) - 1)
def go(re_, sm, tg, ex):
    keep = []
    for ts, r, w in A.run(re_, 'break', sm, tg, ex):
        up = A.e9[A.done(ts)] > A.e21[A.done(ts)]
        if h4up(ts) == up: keep.append((ts, r, up))
    return keep
S = A.stats
for re_ in (3, 4, 5):
    for sm in (0.75, 1.0, 1.5):
        for tg in (1.5, 2, 3):
            for ex in (12, 16):
                k = go(re_, sm, tg, ex)
                print(f'range 23-{re_:02d} stop {sm} tgt {tg} out {ex} | train {S([r for ts,r,u in k if ts < A.SPLIT])} | test {S([r for ts,r,u in k if ts >= A.SPLIT])}')
k = go(4, 1.0, 2, 16)
print('\nchosen 23-04 stop 1.0 tgt 2 out 16 by side: BUY', S([r for ts,r,u in k if u]), '| SELL', S([r for ts,r,u in k if not u]))
for h in range(4, 9): print(f'  entry hour {h:02d}', S([r for ts,r,u in k if A.ldn(ts - 900).hour == h]))
print('  per month', {m: round(sum(r for ts,r,u in k if A.ldn(ts).strftime('%y%m') == m), 1) for m in sorted({A.ldn(ts).strftime('%y%m') for ts,r,u in k})})
