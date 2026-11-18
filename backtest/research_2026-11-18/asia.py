#!/usr/bin/env python3
"""Woody 18 Nov 2026: "add Asia low / Asia high to the M15 entry, H1 bias, from 2am to 9am, high quality entry before London".
Tests Asia-range entry variants on 12 months of XAU/USD 15m (backtest/data/xau_15m.json), R after $0.40/oz cost,
train to 31 May 2026, unseen test from 1 Jun. One trade per day per variant. H1 bias = 1H EMA9 vs EMA21 (as the M15 engine).
Asia range = 23:00 (prev day) to RANGE_END London. Entries RANGE_END..09:00 London, weekdays."""
import bisect, datetime as dt, json, os, sys, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scan/brain'))
from features import ema, atr, L
from evidence import load, resample
COST = 0.40
SPLIT = int(dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc).timestamp())
b = load(os.path.join(os.path.dirname(__file__), '../data/xau_15m.json'))
h1 = resample(b, 3600); T1 = [x['T'] for x in h1]; c1 = [x['c'] for x in h1]; e9, e21, A1 = ema(c1, 9), ema(c1, 21), atr(h1)
c15 = [x['c'] for x in b]; m9, m21 = ema(c15, 9), ema(c15, 21)
ldn = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).astimezone(L)
done = lambda ts: bisect.bisect_right(T1, ts) - 1

def walk(j, buy, en, sl, tp, end_ts):
    sg = 1 if buy else -1; R = abs(en - sl)
    for k in range(j + 1, len(b)):
        x = b[k]
        if (x['l'] <= sl) if buy else (x['h'] >= sl): return (sg * (sl - en) - COST) / R
        if tp and ((x['h'] >= tp) if buy else (x['l'] <= tp)): return (sg * (tp - en) - COST) / R
        if x['T'] >= end_ts: return (sg * (x['c'] - en) - COST) / R
    return None

days = {}
for j, x in enumerate(b): days.setdefault(ldn(x['t']).date(), []).append(j)

def run(range_end, entry, stopm, tgt, exit_h, bias=True):
    out = []
    for d, idx in sorted(days.items()):
        if d.weekday() > 4: continue
        prev = [j for j in days.get(d - dt.timedelta(days=1), []) if ldn(b[j]['t']).hour >= 23]
        rng = prev + [j for j in idx if ldn(b[j]['t']).hour < range_end]
        if len(rng) < 6: continue
        ah, al = max(b[j]['h'] for j in rng), min(b[j]['l'] for j in rng)
        win = [j for j in idx if range_end <= ldn(b[j]['t']).hour < 9]
        end_ts = int(dt.datetime.combine(d, dt.time(exit_h), L).timestamp())
        for j in win:
            x = b[j]; ts = x['T']; i1 = done(ts)
            if i1 < 30: continue
            up = e9[i1] > e21[i1]; a = A1[i1]
            sides = ([up] if bias else [True, False])
            sig = None
            for buy in sides:
                if entry == 'sweep':      # wick through the Asia extreme against the bias, close back inside
                    if buy and x['l'] < al and x['c'] > al: sig = (buy, x['l'] - 0.1 * a)
                    if not buy and x['h'] > ah and x['c'] < ah: sig = (buy, x['h'] + 0.1 * a)
                elif entry == 'break':    # close beyond the Asia extreme in the bias direction
                    if buy and x['c'] > ah and b[j - 1]['c'] <= ah: sig = (buy, x['c'] - stopm * a)
                    if not buy and x['c'] < al and b[j - 1]['c'] >= al: sig = (buy, x['c'] + stopm * a)
                elif entry == 'cross_discount':  # M15 EMA9/21 cross in bias, buy only in lower half of the Asia range (sell upper)
                    mid = (ah + al) / 2
                    if buy and m9[j] > m21[j] and m9[j-1] <= m21[j-1] and x['c'] < mid: sig = (buy, min(al, x['c']) - stopm * a)
                    if not buy and m9[j] < m21[j] and m9[j-1] >= m21[j-1] and x['c'] > mid: sig = (buy, max(ah, x['c']) + stopm * a)
                if sig: break
            if not sig: continue
            buy, sl = sig; en = x['c']; R = abs(en - sl)
            if R < 0.3 * a or R > 4 * a: break
            tp = en + (1 if buy else -1) * tgt * R if tgt != 'range' else (ah if buy else al)
            if tgt == 'range' and ((tp - en) if buy else (en - tp)) < R: break
            r = walk(j, buy, en, sl, tp, end_ts)
            if r is not None: out.append((ts, r, buy == up))
            break
    return out

def stats(rs):
    if not rs: return '   0'
    w = [r for r in rs if r > 0]; l = [r for r in rs if r <= 0]
    pf = sum(w) / -sum(l) if l and sum(l) else 9
    return f'{len(rs):4d} {sum(rs):+6.1f}R avg {sum(rs)/len(rs):+.2f} PF {pf:.2f} win {100*len(w)//len(rs)}%'

rows = []
for range_end, entry, stopm, tgt, exit_h in itertools.product((2, 4), ('sweep', 'break', 'cross_discount'), (0.5, 1.0), (1.5, 2, 'range'), (12, 16)):
    if entry == 'sweep' and stopm == 1.0: continue
    t = run(range_end, entry, stopm, tgt, exit_h)
    tr = [r for ts, r, _ in t if ts < SPLIT]; te = [r for ts, r, _ in t if ts >= SPLIT]
    rows.append((sum(tr), f'range 23-{range_end:02d} {entry:14s} stop {stopm} tgt {tgt!s:5s} out {exit_h}:00 | train {stats(tr)} | test {stats(te)}'))
for _, s in sorted(rows, reverse=True): print(s)
print('\nNO H1 BIAS (both sides), sweep, range 23-02, tgt 2, out 12:')
t = run(2, 'sweep', 0.5, 2, 12, bias=False)
print('with-bias  ', stats([r for _, r, w in t if w])); print('against    ', stats([r for _, r, w in t if not w]))
