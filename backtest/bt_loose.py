#!/usr/bin/env python3
"""Looser versions of the live trend-day dip (rules v3.2), same costs, stops, targets and daily limits.
  python3 bt_loose.py data.json
Knobs:
  e5   require the 5m EMA20 on the trend side of the 5m EMA50 (live: yes)
  e15  require the 15m EMA20/50 aligned with the 1H trend (live: yes)
  tol  how close the candle must come to the 5m EMA20, in 5m ATR (live: 0.25)
  trig which candles count: 'live' = strong close / engulfing / pin, 'any' = any candle closing back beyond the EMA20 in the trend direction
  hrs  'live' = 07:00-10:30 + 13:00-16:30, 'long' = 07:00-16:30 straight
  room minimum room to the next level in R (live: 1.0)"""
import bisect
import json
import sys
from datetime import datetime, timezone

from bt_more import L, H, M, ema, atr, ctx, walk, body, bull, bear, stats


def run(d, e5=True, e15=True, tol=0.25, trig='live', hrs='live', room=1.0, cost=0.35):
    m5 = d['5m']; t5 = [b['t'] for b in m5]
    ab = atr(m5); e20b, e50b = ema([b['c'] for b in m5], 20), ema([b['c'] for b in m5], 50)
    at = ctx(d)
    tr = []; busy = 0; dpl = {}; dl = {}
    for i in range(60, len(m5)):
        b = m5[i]; T = b['t'] + 5 * M
        if T < busy or ab[i] is None: continue
        lt = datetime.fromtimestamp(T / 1000, timezone.utc).astimezone(L); day = lt.date(); mins = lt.hour * 60 + lt.minute
        if lt.weekday() >= 5: continue
        if hrs == 'live' and not (420 <= mins <= 630 or 780 <= mins <= 990): continue
        if hrs == 'long' and not (420 <= mins <= 990): continue
        if dl.get(day, 0) >= 2 or dpl.get(day, 0) <= -20: continue
        c = at(T)
        if not c or c['bias'] == 'FLAT': continue
        buy = c['bias'] == 'UP'; sg = 1 if buy else -1
        if e15 and not (c['e20'] > c['e50'] if buy else c['e20'] < c['e50']): continue
        if e5 and not (e20b[i] > e50b[i] if buy else e20b[i] < e50b[i]): continue
        A = ab[i]; E = e20b[i]
        if not ((b['l'] <= E + tol * A) if buy else (b['h'] >= E - tol * A)): continue
        pv = m5[i - 1]; rng = b['h'] - b['l'] or 1e-9; pos = (b['c'] - b['l']) / rng
        bey = b['c'] > E if buy else b['c'] < E
        if trig == 'live':
            strong = bey and (bull(b) and pos >= 2 / 3 if buy else bear(b) and pos <= 1 / 3)
            eng = (bull(b) and bear(pv) and b['c'] >= pv['o'] and b['o'] <= pv['c'] and body(b) > body(pv)) if buy else (bear(b) and bull(pv) and b['c'] <= pv['c'] and b['o'] >= pv['o'] and body(b) > body(pv))
            wk = (min(b['o'], b['c']) - b['l']) if buy else (b['h'] - max(b['o'], b['c']))
            pin = wk >= 2 * max(body(b), 1e-9) and wk >= 0.5 * rng and (pos >= 0.6 if buy else pos <= 0.4)
            ok = strong or (bey and (eng or pin))
        else:
            ok = bey and (bull(b) if buy else bear(b))
        if not ok or abs(b['c'] - E) > 1.5 * A or rng > 2 * A: continue
        ext = min(x['l'] for x in m5[i - 2:i + 1]) if buy else max(x['h'] for x in m5[i - 2:i + 1])
        en = b['c']; stp = ext - sg * 1.5
        if sg * (en - stp) < 0.5 * A: stp = en - sg * 0.5 * A
        R = abs(en - stp)
        if R > 10 or sg * (en - stp) <= 0: continue
        opp = [x for x in c['lv'] if x > en + 0.1] if buy else [x for x in c['lv'] if x < en - 0.1]
        nx = (min(opp) if buy else max(opp)) if opp else None
        rr = abs(nx - en) / R if nx else 9
        if rr < room: continue
        tp = en + sg * R * min(2, max(rr, room))
        res, k = walk(m5, t5, T, buy, en, stp, tp)
        if res is None: break
        pl = round(res - cost, 2); busy = m5[min(k, len(m5) - 1)]['t'] + 5 * M
        tr.append(dict(t=lt.strftime('%m-%d %H:%M'), en=en, side='BUY' if buy else 'SELL', R=round(R, 2), pl=pl))
        dpl[day] = dpl.get(day, 0) + pl; dl[day] = dl.get(day, 0) + (pl < 0)
    return tr


if __name__ == '__main__':
    d = json.load(open(sys.argv[1]))
    days = len({datetime.fromtimestamp(b['t'] / 1000, timezone.utc).astimezone(L).date() for b in d['5m']
                if datetime.fromtimestamp(b['t'] / 1000, timezone.utc).astimezone(L).weekday() < 5})
    print(f'{days} trading days, 13 Oct to 5 Nov')
    V = [('LIVE v3.2', {}),
         ('A no 5m EMA20>50 rule', dict(e5=False)),
         ('B touch within 0.5 ATR', dict(tol=0.5)),
         ('C any trend candle closing back over EMA20', dict(trig='any')),
         ('D trade 07:00-16:30 straight', dict(hrs='long')),
         ('E no 15m EMA rule', dict(e15=False)),
         ('A+B', dict(e5=False, tol=0.5)),
         ('A+D', dict(e5=False, hrs='long')),
         ('B+D', dict(tol=0.5, hrs='long')),
         ('A+B+D', dict(e5=False, tol=0.5, hrs='long')),
         ('A+B+C+D', dict(e5=False, tol=0.5, trig='any', hrs='long'))]
    for name, kw in V:
        t = run(d, **kw)
        print(f'{name:44s} {len(t) / days:4.1f}/day  ' + stats(t))
    if len(sys.argv) > 2:
        for x in run(d, **dict(eval(sys.argv[2]))): print(x)
