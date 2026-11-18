"""Follow-up: (a) plain M15 EMA9/21 cross with H1 bias, entries 02-09 London, (b) Asia breakout 23-04 with the H4 trend filter (4H EMA50 vs EMA200)."""
import bisect, datetime as dt
import asia as A
from features import ema
h4 = A.resample(A.b, 14400); T4 = [x['T'] for x in h4]; c4 = [x['c'] for x in h4]; E50, E200 = ema(c4, 50), ema(c4, 200)
h4up = lambda ts: (lambda i: E50[i] > E200[i])(bisect.bisect_right(T4, ts) - 1)
def stats(rs): return A.stats(rs)
# (a) M15 cross 02-09, stop 2 x 1H ATR, exit when H1 flips or 12:00/16:00
for exit_h in (12, 16):
  for filt in ('none', 'h4'):
    out = []
    last_day = None
    for j in range(60, len(A.b)):
        x = A.b[j]; ts = x['T']; t = A.ldn(ts)
        if t.weekday() > 4 or not (2 <= t.hour < 9): continue
        up = A.m9[j] > A.m21[j] and A.m9[j-1] <= A.m21[j-1]; dn = A.m9[j] < A.m21[j] and A.m9[j-1] >= A.m21[j-1]
        i1 = A.done(ts)
        if not (up or dn) or i1 < 30 or (A.e9[i1] > A.e21[i1]) != up: continue
        if filt == 'h4' and h4up(ts) != up: continue
        buy = up; en = x['c']; sl = en - (1 if buy else -1) * 2 * A.A1[i1]
        end_ts = int(dt.datetime.combine(t.date(), dt.time(exit_h), A.L).timestamp())
        r = A.walk(j, buy, en, sl, None, end_ts)
        if r is not None: out.append((ts, r))
    print(f'M15 cross 02-09 H1 bias, H4 filter {filt:4s}, out {exit_h}:00 | train {stats([r for ts, r in out if ts < A.SPLIT])} | test {stats([r for ts, r in out if ts >= A.SPLIT])}')
# (b) Asia breakout with H4 filter
for re_, sm, tg in ((4, 1.0, 2), (4, 1.0, 1.5), (2, 0.5, 2), (2, 1.0, 1.5)):
    t = A.run(re_, 'break', sm, tg, 16)
    f = [(ts, r) for ts, r, w in t if h4up(ts - 1) == (r is not None and True) or True]
    keep = []
    for ts, r, w in t:
        # side = H1 bias at entry
        i1 = A.done(ts); up = A.e9[i1] > A.e21[i1]
        if h4up(ts) == up: keep.append((ts, r))
    print(f'Asia break 23-{re_:02d} stop {sm} tgt {tg} + H4 trend | train {stats([r for ts, r in keep if ts < A.SPLIT])} | test {stats([r for ts, r in keep if ts >= A.SPLIT])}')
