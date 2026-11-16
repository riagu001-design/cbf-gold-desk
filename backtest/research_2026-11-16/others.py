"""Simple gold strategies on 12 months of 15m XAU/USD. TRAIN Nov 2025-May 2026, TEST Jun-Nov 2026 (unseen).
Every variant runs at 0.01 lot, $0.40 cost a trade, one trade at a time."""
import bisect, datetime as dt
from eng import *
b = load('xau_15m.json'); T = [x['t'] for x in b]; A15 = atr(b)
h1 = resample(b, 3600); A1 = atr(h1); c1 = [x['c'] for x in h1]
ts = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=UTC).timestamp())
S, M, E = ts(2025, 11, 10), ts(2026, 6, 1), ts(2026, 11, 17)
def london_breakout(t0, t1, stopmode='opp', tgt=1.5, maxR=15):
    """Asian range 00:00-07:00 London; first 15m close outside it between 07:00 and 10:00 = entry; one trade a day; out by 16:00."""
    tr = []; i = bisect.bisect_left(T, t0); e = bisect.bisect_left(T, t1); busy = 0
    days = {}
    for k in range(i, e):
        lt = ldn(b[k]['t']); days.setdefault(lt.date(), []).append(k)
    for d, ks in sorted(days.items()):
        if d.weekday() >= 5: continue
        asia = [k for k in ks if ldn(b[k]['t']).hour < 7]; sess = [k for k in ks if 7 <= ldn(b[k]['t']).hour < 10]
        if len(asia) < 20 or not sess or b[sess[0]]['t'] < busy: continue
        hi = max(b[k]['h'] for k in asia); lo = min(b[k]['l'] for k in asia)
        for k in sess:
            c = b[k]['c']; buy = c > hi; sell = c < lo
            if not (buy or sell): continue
            sg = 1 if buy else -1
            sl = (lo if buy else hi) if stopmode == 'opp' else (hi + lo) / 2
            R = abs(c - sl)
            if R <= 0.5 or R > maxR: break
            tp = c + sg * tgt * R if tgt else None
            end = int(dt.datetime.combine(d, dt.time(16, 0), L).timestamp())
            pl, j, how = walk(b, k, buy, c, sl, tp, max_s=end - b[k]['t'])
            tr.append(dict(t=b[k]['t'], pl=pl, R=R, how=how)); busy = b[min(j, len(b) - 1)]['t']; break
    return tr
def ny_momentum(t0, t1, kA=0.5, tgt=2.0):
    """US open: 13:30-14:30 London move bigger than kA x 1H ATR -> follow it at 14:30, stop 1 x 1H ATR, out at 20:00 or target."""
    tr = []; i = bisect.bisect_left(T, t0); e = bisect.bisect_left(T, t1)
    for k in range(i, e):
        lt = ldn(b[k]['t'] + 900)
        if lt.weekday() >= 5 or not (lt.hour == 14 and lt.minute == 30): continue
        k0 = k - 4; mv = b[k]['c'] - b[k0]['c']
        j1 = bisect.bisect_right([x['t'] + 3600 for x in h1], b[k]['t'] + 900) - 1 if False else None
        A = A15[k] * 2  # ~1H ATR from 15m ATR
        if A is None or abs(mv) < kA * A: continue
        buy = mv > 0; sg = 1 if buy else -1; en = b[k]['c']; R = A; sl = en - sg * R
        end = int(dt.datetime.combine(lt.date(), dt.time(20, 0), L).timestamp())
        pl, j, how = walk(b, k, buy, en, sl, en + sg * tgt * R if tgt else None, max_s=end - b[k]['t'])
        tr.append(dict(t=b[k]['t'], pl=pl, R=R, how=how))
    return tr
def donchian(t0, t1, n=20, mult=3.0, side='both'):
    """1H Donchian breakout: close beyond the last n-hour high/low -> enter; chandelier stop mult x ATR trailed on each hour; no target."""
    tr = []; T1 = [x['t'] for x in h1]; i = max(bisect.bisect_left(T1, t0), n + 15); e = bisect.bisect_left(T1, t1)
    while i < e:
        x = h1[i]; hi = max(y['h'] for y in h1[i - n:i]); lo = min(y['l'] for y in h1[i - n:i]); A = A1[i]
        buy = x['c'] > hi; sell = x['c'] < lo
        if (buy and side in ('both', 'buy')) or (sell and side in ('both', 'sell')):
            sg = 1 if buy else -1; en = x['c']; sl = en - sg * mult * A; R = mult * A
            def trail(s, j, sg=sg):
                y = h1[j]; ns = (y['c'] - sg * mult * A1[j])
                return max(s, ns) if sg > 0 else min(s, ns)
            pl, j, how = walk(h1, i, buy, en, sl, None, max_s=0, trail=trail)
            tr.append(dict(t=x['t'], pl=pl, R=R, how=how))
            if pl is None: break
            i = j + 1; continue
        i += 1
    return tr
def ema_trend(t0, t1, f=20, s=50, mult=2.0):
    """1H EMA f/s cross: go with the cross, stop mult x ATR, exit on the opposite cross."""
    ef, es = ema(c1, f), ema(c1, s); T1 = [x['t'] for x in h1]; tr = []
    i = max(bisect.bisect_left(T1, t0), s + 5); e = bisect.bisect_left(T1, t1)
    while i < e:
        up = ef[i] > es[i] and ef[i - 1] <= es[i - 1]; dn = ef[i] < es[i] and ef[i - 1] >= es[i - 1]
        if up or dn:
            sg = 1 if up else -1; en = h1[i]['c']; sl = en - sg * mult * A1[i]; R = mult * A1[i]
            for j in range(i + 1, len(h1)):
                y = h1[j]
                if (y['l'] <= sl) if up else (y['h'] >= sl): pl = sg * (sl - en) - COST; break
                if (ef[j] < es[j]) if up else (ef[j] > es[j]): pl = sg * (y['c'] - en) - COST; break
            else: pl = None; j = len(h1)
            tr.append(dict(t=h1[i]['t'], pl=pl, R=R)); i = j + 1; continue
        i += 1
    return tr
if __name__ == '__main__':
    print('15m data', ldn(b[0]['t']).date(), '->', ldn(b[-1]['t']).date(), '| TRAIN 10 Nov 2025-31 May 2026 | TEST 1 Jun-16 Nov 2026 (unseen)')
    G = []
    for so in ('opp', 'mid'):
        for tg in (1.0, 1.5, 2.0, None): G.append((f'London breakout stop={so} tgt={tg}', london_breakout, dict(stopmode=so, tgt=tg)))
    for kA in (0.5, 1.0):
        for tg in (1.5, 2.0, None): G.append((f'NY momentum k={kA} tgt={tg}', ny_momentum, dict(kA=kA, tgt=tg)))
    for n in (20, 40):
        for m in (2.0, 3.0):
            for sd in ('both', 'sell', 'buy'): G.append((f'1H Donchian n={n} x{m} {sd}', donchian, dict(n=n, mult=m, side=sd)))
    for f, s in ((20, 50), (50, 200)):
        for m in (2.0, 3.0): G.append((f'1H EMA {f}/{s} stop x{m}', ema_trend, dict(f=f, s=s, mult=m)))
    rows = []
    for name, fn, kw in G:
        a, t = stats(fn(S, M, **kw)), stats(fn(M, E, **kw)); rows.append((name, a, t))
        print(f'{name:38s} train {a["txt"]}\n{"":38s} TEST  {t["txt"]}')
