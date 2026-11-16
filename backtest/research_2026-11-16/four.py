"""Woody's four strategies (16 Nov 2026) on 12 months of XAU/USD 15m (Twelve Data). Results in R (1R = the stop distance),
after a $0.40/oz spread cost, and in $ at 1% risk of a $182 account (1R = $1.82). One trade at a time per strategy.
TRAIN 10 Nov 2025-31 May 2026, TEST 1 Jun-16 Nov 2026 (unseen). Timing rule: entries only 13:00-17:00 UK unless noted.
News: high-impact releases are scheduled at :30/:00; entries happen on 15m/1H closes, so the '60 s after NFP/CPI/FOMC' rule never binds."""
import bisect, json, datetime as dt
from eng import *
b15 = load('xau_15m.json'); h1 = resample(b15, 3600); h4 = resample(b15, 14400); d1 = resample(b15, 86400)
T15 = [x['t'] for x in b15]; T1 = [x['t'] for x in h1]; T4c = [x['t'] + 14400 for x in h4]
A15, A1 = atr(b15), atr(h1)
c1, c4 = [x['c'] for x in h1], [x['c'] for x in h4]
e50_1, e9_1, e21_1 = ema(c1, 50), ema(c1, 9), ema(c1, 21)
e50_4, e200_4 = ema(c4, 50), ema(c4, 200)
ts = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=UTC).timestamp())
S, M, E = ts(2025, 11, 10), ts(2026, 6, 1), ts(2026, 11, 17)
RISK_USD = 1.82
MAC = json.load(open('macro.json'))
def macro_bias(t):
    """Weekly bias from the 4-week change in the 10y real yield (DFII10) and the broad dollar (DTWEXBGS), data to the day before."""
    day = (dt.datetime.fromtimestamp(t, UTC) - dt.timedelta(days=1)).date().isoformat()
    def chg(s):
        ds = [d for d, v in s]; j = bisect.bisect_right(ds, day) - 1
        if j < 20: return None
        return s[j][1] - s[j - 20][1]
    ry, usd = chg(MAC['ry']), chg(MAC['usd'])
    if ry is None or usd is None: return None
    if ry < 0 and usd < 0: return 'UP'
    if ry > 0 and usd > 0: return 'DN'
    return 'MIX'
def window(t, lo=13, hi=17):
    lt = ldn(t); return lt.weekday() < 5 and lo <= lt.hour < hi
def h4_trend(t):
    j = bisect.bisect_right(T4c, t) - 1
    if j < 200: return None
    c, a, b = h4[j]['c'], e50_4[j], e200_4[j]
    return 'UP' if c > a > b else 'DN' if c < a < b else None
def rec(t, R, pnl_per_oz, how=''):
    r = (pnl_per_oz - COST) / R
    return dict(t=t, R=1.0, pl=r, how=how)  # pl in R units (stats() prints them as '$' = R)
def s1_pullback(t0, t1, timing=True, use_macro=False, tgt=2.0):
    """H4 trend (close > EMA50 > EMA200, or the reverse); H1 low/high touches the H1 EMA50 (within 0.25 ATR);
    confirmation: the H1 candle closes back beyond the EMA50 in the trend direction, bullish/bearish body, close beyond the prior candle's high/low.
    Stop: beyond the pullback swing (lowest low / highest high of the last 5 H1 candles) + 0.2 ATR. Target 2R. Max hold 48 h."""
    tr = []; i = max(bisect.bisect_left(T1, t0), 60); e = bisect.bisect_left(T1, t1)
    while i < e:
        x, p = h1[i], h1[i - 1]; T = x['t'] + 3600
        if timing and not window(x['t']): i += 1; continue
        tr4 = h4_trend(T)
        if use_macro:
            mb = macro_bias(T)
            if mb in ('UP', 'DN') and mb != tr4: tr4 = None
        if not tr4: i += 1; continue
        buy = tr4 == 'UP'; A = A1[i]; E50 = e50_1[i]
        touch = x['l'] <= E50 + 0.25 * A if buy else x['h'] >= E50 - 0.25 * A
        conf = (x['c'] > E50 and x['c'] > x['o'] and x['c'] > p['h']) if buy else (x['c'] < E50 and x['c'] < x['o'] and x['c'] < p['l'])
        if touch and conf:
            en = x['c']; sw = min(y['l'] for y in h1[i - 4:i + 1]) if buy else max(y['h'] for y in h1[i - 4:i + 1])
            sl = sw - 0.2 * A if buy else sw + 0.2 * A; R = abs(en - sl)
            if R < 0.3 * A: i += 1; continue
            sg = 1 if buy else -1
            pl, j, how = walk(h1, i, buy, en, sl, en + sg * tgt * R, max_s=48 * 3600)
            if pl is None: break
            tr.append(rec(x['t'], R, pl + COST, how)); i = j + 1; continue
        i += 1
    return tr
def s2_breakout(t0, t1, rng='asia3', retest=False, timing=False, tgt=2.0, buf=0.5):
    """Range = last 3 Asian hours (04:00-07:00 UK) or the first 15 min of London (08:00-08:15 UK). Entry after a 15m close outside it
    (08:15-17:00 UK; with timing=True only 13:00-17:00). Stop beyond the breakout candle's other side + buf x 15m ATR. Target 2R.
    retest=True: after the breakout close, wait for price to come back to the broken level, then enter on the first 15m close back beyond it."""
    tr = []; days = {}
    for k in range(bisect.bisect_left(T15, t0), bisect.bisect_left(T15, t1)):
        days.setdefault(ldn(b15[k]['t']).date(), []).append(k)
    for d, ks in sorted(days.items()):
        if d.weekday() >= 5: continue
        if rng == 'asia3': rk = [k for k in ks if 4 <= ldn(b15[k]['t']).hour < 7]; start = 8 * 60 + 15
        else: rk = [k for k in ks if ldn(b15[k]['t']).hour == 8 and ldn(b15[k]['t']).minute == 0]; start = 8 * 60 + 15
        if len(rk) < (8 if rng == 'asia3' else 1): continue
        hi = max(b15[k]['h'] for k in rk); lo = min(b15[k]['l'] for k in rk)
        sess = [k for k in ks if start <= ldn(b15[k]['t']).hour * 60 + ldn(b15[k]['t']).minute < 17 * 60]
        state = None
        for k in sess:
            x = b15[k]; A = A15[k]; inwin = (not timing) or window(x['t'])
            if state is None:
                if x['c'] > hi: state = ('UP', k)
                elif x['c'] < lo: state = ('DN', k)
                else: continue
                if not retest:
                    if not inwin: break
                    buy = state[0] == 'UP'; en = x['c']; sl = (x['l'] - buf * A) if buy else (x['h'] + buf * A)
                else: continue
            else:
                buy = state[0] == 'UP'; lvl = hi if buy else lo
                touched = x['l'] <= lvl + 0.1 * A if buy else x['h'] >= lvl - 0.1 * A
                if not (touched and ((x['c'] > lvl) if buy else (x['c'] < lvl))) or not inwin: continue
                en = x['c']; sl = (min(x['l'], lvl) - buf * A) if buy else (max(x['h'], lvl) + buf * A)
            R = abs(en - sl)
            if R <= 0: break
            end = int(dt.datetime.combine(d, dt.time(20, 0), L).timestamp())
            pl, j, how = walk(b15, k, buy, en, sl, en + (1 if buy else -1) * tgt * R, max_s=end - x['t'])
            if pl is not None: tr.append(rec(x['t'], R, pl + COST, how))
            break
    return tr
def s3_donchian(t0, t1, n=20, m=10, timing=True, stopN=2.0):
    """20/10 Donchian on H1: enter on a close beyond the 20-hour high/low; exit on a close beyond the opposite 10-hour low/high;
    protective stop 2 x ATR (sizes the trade = 1R)."""
    tr = []; i = max(bisect.bisect_left(T1, t0), n + 15); e = bisect.bisect_left(T1, t1)
    while i < e:
        x = h1[i]
        if timing and not window(x['t']): i += 1; continue
        hi = max(y['h'] for y in h1[i - n:i]); lo = min(y['l'] for y in h1[i - n:i])
        buy, sell = x['c'] > hi, x['c'] < lo
        if not (buy or sell): i += 1; continue
        sg = 1 if buy else -1; en = x['c']; R = stopN * A1[i]; sl = en - sg * R; pl = None
        for j in range(i + 1, len(h1)):
            y = h1[j]
            if (y['l'] <= sl) if buy else (y['h'] >= sl): pl = sg * (sl - en); break
            ex = min(z['l'] for z in h1[j - m:j]) if buy else max(z['h'] for z in h1[j - m:j])
            if (y['c'] < ex) if buy else (y['c'] > ex): pl = sg * (y['c'] - en); break
            lt = ldn(y['t'] + 3600)
            if lt.weekday() == 4 and lt.hour >= 21: pl = sg * (y['c'] - en); break
        if pl is None: break
        tr.append(rec(x['t'], R, pl)); i = j + 1
    return tr
def s3_ema(t0, t1, timing=True, stopN=2.0):
    """9/21 EMA cross on H1: enter on the cross, exit on the opposite cross; protective stop 2 x ATR (1R)."""
    tr = []; i = max(bisect.bisect_left(T1, t0), 30); e = bisect.bisect_left(T1, t1)
    while i < e:
        up = e9_1[i] > e21_1[i] and e9_1[i - 1] <= e21_1[i - 1]; dn = e9_1[i] < e21_1[i] and e9_1[i - 1] >= e21_1[i - 1]
        if not (up or dn) or (timing and not window(h1[i]['t'])): i += 1; continue
        sg = 1 if up else -1; en = h1[i]['c']; R = stopN * A1[i]; sl = en - sg * R; pl = None
        for j in range(i + 1, len(h1)):
            y = h1[j]
            if (y['l'] <= sl) if up else (y['h'] >= sl): pl = sg * (sl - en); break
            if (e9_1[j] < e21_1[j]) if up else (e9_1[j] > e21_1[j]): pl = sg * (y['c'] - en); break
            lt = ldn(y['t'] + 3600)
            if lt.weekday() == 4 and lt.hour >= 21: pl = sg * (y['c'] - en); break
        if pl is None: break
        tr.append(rec(h1[i]['t'], R, pl)); i = j + 1
    return tr
def show(name, fn, **kw):
    a, t = fn(S, M, **kw), fn(M, E, **kw)
    def line(tr):
        if not tr: return '   0 trades'
        n = len(tr); w = sum(x['pl'] > 0 for x in tr); R = sum(x['pl'] for x in tr)
        eq = pk = dd = 0
        for x in tr: eq += x['pl']; pk = max(pk, eq); dd = max(dd, pk - eq)
        g = sum(x['pl'] for x in tr if x['pl'] > 0); l = -sum(x['pl'] for x in tr if x['pl'] <= 0)
        return f'{n:4d} trades {100*w/n:3.0f}% wins {R:+6.1f}R (${R*RISK_USD:+6.1f} at 1%)  PF {g/l if l else 99:4.2f}  worst run {dd:4.1f}R'
    print(f'{name:52s} train {line(a)}\n{"":52s} TEST  {line(t)}')
    return a, t
if __name__ == '__main__':
    print('XAU/USD 15m', ldn(b15[0]['t']).date(), '->', ldn(b15[-1]['t']).date(), '| R after $0.40/oz cost | $ = 1% risk of $182 per trade')
    print('-- 1. Trend pullback (H4 trend, H1 pullback to EMA50, confirmation candle, stop beyond swing, 2R)')
    show('1  13-17 UK only', s1_pullback)
    show('1  any hour', s1_pullback, timing=False)
    show('1+4 macro filter, 13-17 UK', s1_pullback, use_macro=True)
    show('1+4 macro filter, any hour', s1_pullback, timing=False, use_macro=True)
    print('-- 2. Breakout (15m close outside the range, stop beyond the breakout candle + 0.5 ATR, 2R)')
    for r in ('asia3', 'lon15'):
        show(f'2  {r} plain breakout', s2_breakout, rng=r)
        show(f'2  {r} retest', s2_breakout, rng=r, retest=True)
        show(f'2  {r} retest, 13-17 UK only', s2_breakout, rng=r, retest=True, timing=True)
    print('-- 3. Trend following')
    show('3  Donchian 20/10, 13-17 UK entries', s3_donchian)
    show('3  Donchian 20/10, any hour', s3_donchian, timing=False)
    show('3  EMA 9/21 cross, 13-17 UK entries', s3_ema)
    show('3  EMA 9/21 cross, any hour', s3_ema, timing=False)
