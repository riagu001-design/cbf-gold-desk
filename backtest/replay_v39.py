"""Replay of the live checker (scan/auto_scan.py, rules v3.9) on every closed 5m candle, using only the candles the
live checker would have seen at that moment. Variants: side filter, target cap, 4H filter."""
import json, sys, bisect, datetime as dt
sys.path.insert(0, '/home/user/cbf-gold-desk/scan')
from auto_scan import ema, atr, swings
from zoneinfo import ZoneInfo
L = ZoneInfo('Europe/London'); D = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'data.json'))
M5 = D['5m']; T5 = [b['T'] for b in M5]
def upto(iv, T, days):
    b = D[iv]; j = bisect.bisect_left([x['T'] for x in b], T)  # bars closed by T (T field = close-1ms)
    return [x for x in b[:j] if x['t'] >= T - days * 86400e3]
def ldn(ms): return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).astimezone(L)

def signal(i, side_ok, cap, use4h=True):
    bar, pv = M5[i], M5[i - 1]; T = bar['T'] + 1; now = ldn(T)
    mins = now.hour * 60 + now.minute; wd = now.weekday()
    if wd == 5 or (wd == 6 and mins < 1380) or (wd == 4 and mins >= 1200) or 1320 <= mins < 1380 or mins < 360: return None
    m5 = [x for x in M5[:i + 1] if x['t'] >= T - 2 * 86400e3]
    m15, h1, h4, d1 = upto('15m', T, 5), upto('1h', T, 15), upto('4h', T, 40), upto('1d', T, 6)
    A5 = atr(m5); hi, lo = swings(h1)
    e50h, c1 = ema([b['c'] for b in h1], 50)[-1], h1[-1]['c']
    st = 'UP' if hi[-1] > hi[-2] and lo[-1] > lo[-2] else 'DN' if hi[-1] < hi[-2] and lo[-1] < lo[-2] else 'MIX'
    bias1 = 'UP' if c1 > e50h and st != 'DN' else 'DN' if c1 < e50h and st != 'UP' else 'FLAT'
    k = 2 / 51; price = bar['c']
    bias4 = 'UP' if price > ema([b['c'] for b in h4], 50)[-1] * (1 - k) + price * k else 'DN'
    c15 = [b['c'] for b in m15]; e20, e50 = ema(c15, 20)[-1], ema(c15, 50)[-1]
    if abs(e20 - e50) < 0.05: return None
    buy = e20 > e50
    if bias1 != ('UP' if buy else 'DN'): return None
    if ('BUY' if buy else 'SELL') not in side_ok: return None
    if use4h and bias4 != ('UP' if buy else 'DN'): return None
    sg = 1 if buy else -1; rng = bar['h'] - bar['l'] or 1e-9; pos = (bar['c'] - bar['l']) / rng
    body, pbody = abs(bar['c'] - bar['o']), abs(pv['c'] - pv['o'])
    E5 = ema([b['c'] for b in m5], 20)[-1]
    lv = [d1[-1]['h'], d1[-1]['l']] + hi[-4:] + lo[-4:]
    touch = bar['l'] <= E5 + 0.5 * A5 if buy else bar['h'] >= E5 - 0.5 * A5
    strong = (bar['c'] > E5 and bar['c'] > bar['o'] and pos >= 2/3) if buy else (bar['c'] < E5 and bar['c'] < bar['o'] and pos <= 1/3)
    eng = (bar['c'] > bar['o'] and pv['c'] < pv['o'] and bar['c'] >= pv['o'] and bar['o'] <= pv['c'] and body > pbody) if buy else \
          (bar['c'] < bar['o'] and pv['c'] > pv['o'] and bar['c'] <= pv['o'] and bar['o'] >= pv['c'] and body > pbody)
    wick = (min(bar['o'], bar['c']) - bar['l']) if buy else (bar['h'] - max(bar['o'], bar['c']))
    pin = wick >= 2 * max(body, 1e-9) and wick >= 0.5 * rng and (pos >= 0.6 if buy else pos <= 0.4)
    beyond = bar['c'] > E5 if buy else bar['c'] < E5
    if not touch or not ((beyond and (eng or pin)) or strong): return None
    entry = bar['c']
    if abs(entry - E5) > 1.5 * A5 or rng > 2 * A5: return None
    ext = min(b['l'] for b in m5[-3:]) if buy else max(b['h'] for b in m5[-3:])
    stop = ext - sg * 1.5
    if sg * (entry - stop) < A5: stop = entry - sg * A5
    R = abs(entry - stop)
    if sg * (entry - stop) <= 0 or R > 10: return None
    opp = [x for x in lv if x > entry + 0.1] if buy else [x for x in lv if x < entry - 0.1]
    nxt = (min(opp) if buy else max(opp)) if opp else None
    roomR = abs(nxt - entry) / R if nxt else 9
    if roomR < 1: return None
    tp = entry + sg * R * min(cap, roomR)
    return dict(t=now, side='BUY' if buy else 'SELL', en=entry, sl=stop, tp=tp, R=R, i=i)

def walk(s, cost=0.35):
    sg = 1 if s['side'] == 'BUY' else -1
    for j in range(s['i'] + 1, len(M5)):
        x = M5[j]; xt = ldn(x['T'] + 1)
        if (x['l'] <= s['sl']) if sg > 0 else (x['h'] >= s['sl']): return sg * (s['sl'] - s['en']) - cost, j, 'SL'
        if (x['h'] >= s['tp']) if sg > 0 else (x['l'] <= s['tp']): return sg * (s['tp'] - s['en']) - cost, j, 'TP'
        if x['T'] + 1 - (M5[s['i']]['T'] + 1) >= 8 * 3600e3 or (xt.weekday() == 4 and xt.hour >= 21): return sg * (x['c'] - s['en']) - cost, j, 'TIME'
    return None, len(M5), 'OPEN'

def run(start, end, sides=('SELL',), cap=2.5, use4h=True):
    s0 = bisect.bisect_left(T5, start.timestamp() * 1000); e0 = bisect.bisect_left(T5, end.timestamp() * 1000)
    tr = []; i = max(s0, 60); days = {}
    while i < e0:
        s = signal(i, sides, cap, use4h)
        dk = ldn(M5[i]['T'] + 1).date(); dd = days.setdefault(dk, [0.0, 0])
        if s and dd[1] < 5 and dd[0] > -40:
            pl, j, how = walk(s)
            s.update(pl=pl, how=how); tr.append(s)
            if pl is None: break
            dd[0] += pl; dd[1] += pl < 0; i = j + 1; continue
        i += 1
    return tr

def summ(tr):
    c = [x for x in tr if x['pl'] is not None]
    if not c: return '0 trades'
    w = sum(x['pl'] > 0 for x in c); g = sum(x['pl'] for x in c if x['pl'] > 0); l = -sum(x['pl'] for x in c if x['pl'] <= 0)
    eq = pk = dd = 0
    for x in c: eq += x['pl']; pk = max(pk, eq); dd = max(dd, pk - eq)
    return f'{len(c):3d} trades {w:3d} wins ({100*w/len(c):3.0f}%)  {sum(x["pl"] for x in c):+8.2f}  PF {g/l if l else 99:4.2f}  worst drop {dd:5.2f}'

if __name__ == '__main__':
    now = dt.datetime.now(L)
    W = {'out-of-sample 10 Nov 17:45 - now': (dt.datetime(2026,11,10,17,45,tzinfo=L), now),
         'in-sample 30 Oct - 10 Nov 17:45': (dt.datetime(2026,10,30,0,0,tzinfo=L), dt.datetime(2026,11,10,17,45,tzinfo=L))}
    for wn, (a, b) in W.items():
        print('==', wn)
        for name, kw in [('SELLS only, 2.5R (live now)', dict(sides=('SELL',), cap=2.5)),
                         ('SELLS only, 1.5R', dict(sides=('SELL',), cap=1.5)),
                         ('BUYS only, 2.5R', dict(sides=('BUY',), cap=2.5)),
                         ('BOTH sides, 2.5R', dict(sides=('BUY','SELL'), cap=2.5)),
                         ('BOTH sides, 1.5R', dict(sides=('BUY','SELL'), cap=1.5)),
                         ('BOTH, 2.5R, no 4H filter', dict(sides=('BUY','SELL'), cap=2.5, use4h=False))]:
            print(f'  {name:30s}', summ(run(a, b, **kw)))
    print('== live-now trades, out-of-sample:')
    for x in run(dt.datetime(2026,11,10,17,45,tzinfo=L), now):
        print('  ', x['t'].strftime('%a %d %H:%M'), x['side'], round(x['en'],1), 'SL', round(x['sl'],1), 'TP', round(x['tp'],1), x['how'], None if x['pl'] is None else round(x['pl'],2))
    print('== buys it would have taken, out-of-sample:')
    for x in run(dt.datetime(2026,11,10,17,45,tzinfo=L), now, sides=('BUY',)):
        print('  ', x['t'].strftime('%a %d %H:%M'), x['side'], round(x['en'],1), 'SL', round(x['sl'],1), 'TP', round(x['tp'],1), x['how'], None if x['pl'] is None else round(x['pl'],2))
