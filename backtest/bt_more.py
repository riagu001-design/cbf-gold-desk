#!/usr/bin/env python3
"""Extra setups vs the live rules (v3.1), same costs/sessions/limits.
  python3 bt_more.py data.json
A) trend-day dip: 1H trend + 15m EMAs aligned, 5m candle dips to the 5m EMA20 (+-0.25 x 5m ATR) and closes as a trigger.
B) Homma / Sakata five methods, each tested alone, with and without the 1H trend filter:
   sanzan  three mountains (triple top / bottom, break of the neckline)
   sansen  three rivers (morning / evening star)
   sanku   three gaps (three windows in a row -> fade the move)
   sanpei  three white soldiers / three black crows
   sanpo   rising / falling three methods
Entry at the signal close; stop beyond the pattern +-1.5 (min 0.5 ATR), skip if over $10; target 2R
(capped by 1R+ room to the next level as live); exit after 8h or 21:00 London; one trade at a time per test."""
import bisect
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

L = ZoneInfo('Europe/London'); H = 3600e3; M = 60e3


def ema(x, n):
    k, o = 2 / (n + 1), [x[0]]
    for v in x[1:]: o.append(v * k + o[-1] * (1 - k))
    return o


def atr(b, n=14):
    tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
    o, a = [None] * len(b), sum(tr[:n]) / n; o[n - 1] = a
    for i in range(n, len(tr)): a = (a * (n - 1) + tr[i]) / n; o[i] = a
    return o


def ctx(d):
    h1 = d['1h']; m15 = d['15m']
    e50h = ema([b['c'] for b in h1], 50); t1 = [b['t'] + H for b in h1]
    sh, sl = [], []
    for i in range(2, len(h1) - 2):
        w = h1[i - 2:i + 3]; k = h1[i + 2]['t'] + H
        if h1[i]['h'] == max(x['h'] for x in w): sh.append((k, h1[i]['h']))
        if h1[i]['l'] == min(x['l'] for x in w): sl.append((k, h1[i]['l']))
    e20, e50, a15 = ema([b['c'] for b in m15], 20), ema([b['c'] for b in m15], 50), atr(m15)
    t15 = [b['t'] + 15 * M for b in m15]
    days = {}
    for b in m15:
        dd = days.setdefault(b['t'] // 86400000, [b['h'], b['l']]); dd[0] = max(dd[0], b['h']); dd[1] = min(dd[1], b['l'])

    def at(T):
        j1 = bisect.bisect_right(t1, T) - 1; j = bisect.bisect_right(t15, T) - 1
        if j1 < 60 or j < 60: return None
        hs = [p for k, p in sh if k <= T][-4:]; ls = [p for k, p in sl if k <= T][-4:]
        if len(hs) < 2 or len(ls) < 2: return None
        st = 'UP' if hs[-1] > hs[-2] and ls[-1] > ls[-2] else 'DN' if hs[-1] < hs[-2] and ls[-1] < ls[-2] else 'MIX'
        c1 = h1[j1]['c']
        bias = 'UP' if c1 > e50h[j1] and st != 'DN' else 'DN' if c1 < e50h[j1] and st != 'UP' else 'FLAT'
        pd = days.get(T // 86400000 - 1) or days.get(T // 86400000 - 3)
        lv = (list(pd) if pd else []) + hs + ls
        return dict(bias=bias, e20=e20[j], e50=e50[j], a15=a15[j], lv=lv)
    return at


def walk(m5, t5, T, buy, en, stp, tp):
    sg = 1 if buy else -1; k = bisect.bisect_left(t5, T)
    while k < len(m5):
        x = m5[k]; xt = datetime.fromtimestamp((x['t'] + 5 * M) / 1000, timezone.utc).astimezone(L)
        if (x['l'] <= stp) if buy else (x['h'] >= stp): return sg * (stp - en), k
        if (x['h'] >= tp) if buy else (x['l'] <= tp): return sg * (tp - en), k
        if x['t'] + 5 * M - T >= 8 * H or xt.hour >= 21: return sg * (x['c'] - en), k
        k += 1
    return None, k


def body(b): return abs(b['c'] - b['o'])
def bull(b): return b['c'] > b['o']
def bear(b): return b['c'] < b['o']


def homma(name, bars, i, A):
    """Return 'BUY'/'SELL'/None and the pattern extreme for the stop."""
    b = bars[i]
    if name == 'sansen' and i >= 2:
        x, y, z = bars[i - 2], bars[i - 1], b
        if bear(x) and body(x) >= 0.6 * A and body(y) <= 0.35 * body(x) and max(y['o'], y['c']) <= x['c'] + 0.1 * A and bull(z) and z['c'] >= (x['o'] + x['c']) / 2:
            return 'BUY', min(x['l'], y['l'], z['l'])
        if bull(x) and body(x) >= 0.6 * A and body(y) <= 0.35 * body(x) and min(y['o'], y['c']) >= x['c'] - 0.1 * A and bear(z) and z['c'] <= (x['o'] + x['c']) / 2:
            return 'SELL', max(x['h'], y['h'], z['h'])
    if name == 'sanpei' and i >= 3:
        s = bars[i - 2:i + 1]
        rng = lambda q: (q['h'] - q['l']) or 1e-9
        if all(bull(q) and body(q) >= 0.4 * A and (q['c'] - q['l']) / rng(q) >= 0.7 for q in s) and s[1]['c'] > s[0]['c'] and s[2]['c'] > s[1]['c'] \
                and s[0]['o'] <= s[1]['o'] <= s[0]['c'] and s[1]['o'] <= s[2]['o'] <= s[1]['c']:
            return 'BUY', s[0]['l']
        if all(bear(q) and body(q) >= 0.4 * A and (q['h'] - q['c']) / rng(q) >= 0.7 for q in s) and s[1]['c'] < s[0]['c'] and s[2]['c'] < s[1]['c'] \
                and s[0]['c'] <= s[1]['o'] <= s[0]['o'] and s[1]['c'] <= s[2]['o'] <= s[1]['o']:
            return 'SELL', s[0]['h']
    if name == 'sanpo' and i >= 5:
        for n in (2, 3, 4):
            if i - n - 1 < 0: continue
            f = bars[i - n - 1]; mid = bars[i - n:i]
            if bull(f) and body(f) >= 0.7 * A and all(q['h'] <= f['h'] and q['l'] >= f['l'] and body(q) <= 0.5 * body(f) for q in mid) and bull(b) and b['c'] > f['c']:
                return 'BUY', min(q['l'] for q in mid + [b])
            if bear(f) and body(f) >= 0.7 * A and all(q['h'] <= f['h'] and q['l'] >= f['l'] and body(q) <= 0.5 * body(f) for q in mid) and bear(b) and b['c'] < f['c']:
                return 'SELL', max(q['h'] for q in mid + [b])
    if name == 'sanku' and i >= 3:
        s = bars[i - 3:i + 1]
        if all(s[k]['l'] > s[k - 1]['h'] for k in (1, 2, 3)):  # three rising windows -> sell
            return 'SELL', b['h']
        if all(s[k]['h'] < s[k - 1]['l'] for k in (1, 2, 3)):
            return 'BUY', b['l']
    if name == 'sanzan' and i >= 40:
        w = bars[i - 40:i]
        pk = [k for k in range(2, len(w) - 2) if w[k]['h'] == max(q['h'] for q in w[k - 2:k + 3])]
        tr = [k for k in range(2, len(w) - 2) if w[k]['l'] == min(q['l'] for q in w[k - 2:k + 3])]
        if len(pk) >= 3:
            p = pk[-3:]; hs = [w[k]['h'] for k in p]
            if max(hs) - min(hs) <= 0.6 * A:
                neck = min(q['l'] for q in w[p[0]:p[2] + 1])
                if b['c'] < neck <= bars[i - 1]['c']: return 'SELL', max(hs)
        if len(tr) >= 3:
            p = tr[-3:]; ls = [w[k]['l'] for k in p]
            if max(ls) - min(ls) <= 0.6 * A:
                neck = max(q['h'] for q in w[p[0]:p[2] + 1])
                if b['c'] > neck >= bars[i - 1]['c']: return 'BUY', min(ls)
    return None, None


def run(d, setup, tf=5, trend=True, cost=0.35):
    m5 = d['5m']; t5 = [b['t'] for b in m5]
    bars = m5 if tf == 5 else d['15m']; ab = atr(bars); dur = tf * M
    e20b, e50b = ema([b['c'] for b in bars], 20), ema([b['c'] for b in bars], 50)
    at = ctx(d); first = m5[0]['t']
    tr = []; busy = 0; dpl = {}; dl = {}
    for i in range(60, len(bars)):
        b = bars[i]; T = b['t'] + dur
        if b['t'] < first or T < busy or ab[i] is None: continue
        lt = datetime.fromtimestamp(T / 1000, timezone.utc).astimezone(L); day = lt.date(); mins = lt.hour * 60 + lt.minute
        if lt.weekday() >= 5 or not (420 <= mins <= 630 or 780 <= mins <= 990): continue
        if dl.get(day, 0) >= 2 or dpl.get(day, 0) <= -20: continue
        c = at(T)
        if not c: continue
        A = ab[i]
        if setup in ('both', 'live'):
            if c['bias'] == 'FLAT': continue
            buy = c['bias'] == 'UP'
            if not (c['e20'] > c['e50'] if buy else c['e20'] < c['e50']): continue
            pv = bars[i - 1]; rng = b['h'] - b['l'] or 1e-9; pos = (b['c'] - b['l']) / rng
            def trig(E):
                strong = (b['c'] > E and bull(b) and pos >= 2 / 3) if buy else (b['c'] < E and bear(b) and pos <= 1 / 3)
                eng = (bull(b) and bear(pv) and b['c'] >= pv['o'] and b['o'] <= pv['c'] and body(b) > body(pv)) if buy else (bear(b) and bull(pv) and b['c'] <= pv['c'] and b['o'] >= pv['o'] and body(b) > body(pv))
                wk = (min(b['o'], b['c']) - b['l']) if buy else (b['h'] - max(b['o'], b['c']))
                pin = wk >= 2 * max(body(b), 1e-9) and wk >= 0.5 * rng and (pos >= 0.6 if buy else pos <= 0.4)
                bey = b['c'] > E if buy else b['c'] < E
                return strong or (bey and (eng or pin))
            A15 = c['a15']; zlo, zhi = min(c['e20'], c['e50']) - 0.25 * A15, max(c['e20'], c['e50']) + 0.25 * A15
            live_ok = ((b['l'] <= zhi) if buy else (b['h'] >= zlo)) and trig(c['e20']) and abs(b['c'] - c['e20']) <= 1.5 * A15 and rng <= 2 * A
            E = e20b[i]
            dip_ok = setup == 'both' and (e20b[i] > e50b[i] if buy else e20b[i] < e50b[i]) and ((b['l'] <= E + 0.25 * A) if buy else (b['h'] >= E - 0.25 * A)) \
                and trig(E) and abs(b['c'] - E) <= 1.5 * A and rng <= 2 * A
            if not (live_ok or dip_ok): continue
            ext = min(x['l'] for x in bars[i - 2:i + 1]) if buy else max(x['h'] for x in bars[i - 2:i + 1])
        elif setup == 'dip':
            if c['bias'] == 'FLAT': continue
            buy = c['bias'] == 'UP'
            if not (c['e20'] > c['e50'] if buy else c['e20'] < c['e50']): continue
            if not (e20b[i] > e50b[i] if buy else e20b[i] < e50b[i]): continue
            E = e20b[i]
            touch = b['l'] <= E + 0.25 * A if buy else b['h'] >= E - 0.25 * A
            if not touch: continue
            pv = bars[i - 1]; rng = b['h'] - b['l'] or 1e-9; pos = (b['c'] - b['l']) / rng
            strong = (b['c'] > E and bull(b) and pos >= 2 / 3) if buy else (b['c'] < E and bear(b) and pos <= 1 / 3)
            eng = (bull(b) and bear(pv) and b['c'] >= pv['o'] and b['o'] <= pv['c'] and body(b) > body(pv)) if buy else (bear(b) and bull(pv) and b['c'] <= pv['c'] and b['o'] >= pv['o'] and body(b) > body(pv))
            wk = (min(b['o'], b['c']) - b['l']) if buy else (b['h'] - max(b['o'], b['c']))
            pin = wk >= 2 * max(body(b), 1e-9) and wk >= 0.5 * rng and (pos >= 0.6 if buy else pos <= 0.4)
            bey = b['c'] > E if buy else b['c'] < E
            if not (strong or (bey and (eng or pin))): continue
            if abs(b['c'] - E) > 1.5 * A or rng > 2 * A: continue
            ext = min(x['l'] for x in bars[i - 2:i + 1]) if buy else max(x['h'] for x in bars[i - 2:i + 1])
        else:
            side, ext = homma(setup, bars, i, A)
            if not side: continue
            buy = side == 'BUY'
            if trend and c['bias'] != ('UP' if buy else 'DN'): continue
        sg = 1 if buy else -1; en = b['c']
        stp = ext - sg * 1.5
        if sg * (en - stp) < 0.5 * A: stp = en - sg * 0.5 * A
        R = abs(en - stp)
        if R > 10 or sg * (en - stp) <= 0: continue
        opp = [x for x in c['lv'] if x > en + 0.1] if buy else [x for x in c['lv'] if x < en - 0.1]
        nx = (min(opp) if buy else max(opp)) if opp else None
        rr = abs(nx - en) / R if nx else 9
        if rr < 1: continue
        tp = en + sg * R * min(2, rr)
        res, k = walk(m5, t5, T, buy, en, stp, tp)
        if res is None: break
        pl = round(res - cost, 2); busy = m5[min(k, len(m5) - 1)]['t'] + 5 * M
        tr.append(dict(t=lt.strftime('%m-%d %H:%M'), en=en, side='BUY' if buy else 'SELL', R=round(R, 2), pl=pl))
        dpl[day] = dpl.get(day, 0) + pl; dl[day] = dl.get(day, 0) + (pl < 0)
    return tr


def stats(t):
    if not t: return '  0 trades'
    w = [x for x in t if x['pl'] > 0]; gp = sum(x['pl'] for x in w); gl = -sum(x['pl'] for x in t if x['pl'] < 0)
    eq = pk = dd = 0
    for x in t: eq += x['pl']; pk = max(pk, eq); dd = max(dd, pk - eq)
    h = len(t) // 2
    return (f"{len(t):3d} trades, {100 * len(w) / len(t):3.0f}% wins, ${sum(x['pl'] for x in t):+7.2f}, PF {gp / gl if gl else 99:4.2f}, "
            f"worst drop ${dd:5.2f}, halves {sum(x['pl'] for x in t[:h]):+.0f}/{sum(x['pl'] for x in t[h:]):+.0f}")


if __name__ == '__main__':
    d = json.load(open(sys.argv[1]))
    print('A) trend-day dip to the 5m EMA20 (1H + 15m trend agree)')
    print(f"   {'5m dip':28s}", stats(run(d, 'dip', 5)))
    print('B) Homma / Sakata five methods')
    for s, label in (('sanzan', 'San-zan three mountains'), ('sansen', 'San-sen three rivers (stars)'), ('sanku', 'San-ku three gaps'),
                     ('sanpei', 'San-pei soldiers / crows'), ('sanpo', 'San-po three methods')):
        for tf in (5, 15):
            for trend in (True, False):
                print(f"   {label:28s} {tf:2d}m {'with 1H trend' if trend else 'any direction':14s}", stats(run(d, s, tf, trend)))
