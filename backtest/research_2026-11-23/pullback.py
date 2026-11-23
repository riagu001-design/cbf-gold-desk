"""Trend pullback engine (23 Nov 2026, Woody: "Yes run the backtest").
Idea: when buyers (or sellers) hold H1 control with real strength, buy (sell) the first 15m dip that holds the 15m EMA20.
Data: 12 months of XAUUSD 15m bars (data/xau_15m.json, UTC); H1 and H4 are built from them, using only completed bars.
First half = in-sample, second half = unseen. Costs 0.40 per oz per trade. One trade at a time. Entries 07:00-20:00 London.
Usage: python3 pullback.py [data.json] (a {'bars': [[time,o,h,l,c],...]} file, default the 12-month file); prints a table."""
import json, sys, datetime as dt
from zoneinfo import ZoneInfo
L = ZoneInfo('Europe/London'); UTC = dt.timezone.utc
COST = 0.40

def load(path):
    d = json.load(open(path)); out = []
    for t, o, h, l, c in d['bars']:
        ts = dt.datetime.strptime(t, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
        out.append(dict(ts=ts, o=o, h=h, l=l, c=c))
    return out

def ema_s(x, n):
    k, o = 2 / (n + 1), [x[0]]
    for v in x[1:]: o.append(v * k + o[-1] * (1 - k))
    return o

def atr_s(b, n=14):
    tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
    out, a = [], None
    for i, v in enumerate(tr):
        a = (sum(tr[:n]) / n if i == n - 1 else None) if a is None else (a * (n - 1) + v) / n
        out.append(a)
    return out

def dmi_s(b, n=14):
    """Wilder +DI, -DI, ADX series (None until warmed up)."""
    P, M, A = [None] * len(b), [None] * len(b), [None] * len(b)
    tr = pdm = mdm = None; trs, ps, ms = [], [], []; dx = []; adx = None
    for i in range(1, len(b)):
        up, dn = b[i]['h'] - b[i - 1]['h'], b[i - 1]['l'] - b[i]['l']
        p = up if up > dn and up > 0 else 0.0; m = dn if dn > up and dn > 0 else 0.0
        t = max(b[i]['h'] - b[i]['l'], abs(b[i]['h'] - b[i - 1]['c']), abs(b[i]['l'] - b[i - 1]['c']))
        if tr is None:
            trs.append(t); ps.append(p); ms.append(m)
            if len(trs) == n: tr, pdm, mdm = sum(trs), sum(ps), sum(ms)
            else: continue
        else:
            tr, pdm, mdm = tr - tr / n + t, pdm - pdm / n + p, mdm - mdm / n + m
        pdi, mdi = 100 * pdm / tr if tr else 0, 100 * mdm / tr if tr else 0
        dx.append(100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0)
        if adx is None and len(dx) == n: adx = sum(dx) / n
        elif adx is not None: adx = (adx * (n - 1) + dx[-1]) / n
        P[i], M[i], A[i] = pdi, mdi, adx
    return P, M, A

def resample(b, minutes):
    out, cur = [], None
    for x in b:
        key = x['ts'].replace(minute=(x['ts'].minute // minutes) * minutes if minutes < 60 else 0, second=0)
        if minutes == 240: key = key.replace(hour=(key.hour // 4) * 4)
        if cur is None or cur['ts'] != key:
            if cur: out.append(cur)
            cur = dict(ts=key, o=x['o'], h=x['h'], l=x['l'], c=x['c'])
        else:
            cur['h'] = max(cur['h'], x['h']); cur['l'] = min(cur['l'], x['l']); cur['c'] = x['c']
    if cur: out.append(cur)
    return out

def prepare(b):
    c = [x['c'] for x in b]; e20, e50 = ema_s(c, 20), ema_s(c, 50); a = atr_s(b); p, m, adx = dmi_s(b)
    for i, x in enumerate(b): x.update(e20=e20[i], e50=e50[i], atr=a[i], pdi=p[i], mdi=m[i], adx=adx[i])
    return b

def run(m15, h1, h4, adx_min=25, rr=2.0, use4h=False, m15_di=True, sides=('BUY', 'SELL'), max_day=3, trail=False):
    # map each 15m bar to the last COMPLETED H1 / H4 bar (bar start + length <= 15m bar close)
    j1 = j4 = -1; trades = []; pos = None; day_n = {}
    for i in range(60, len(m15)):
        x = m15[i]; close_ts = x['ts'] + dt.timedelta(minutes=15)
        while j1 + 1 < len(h1) and h1[j1 + 1]['ts'] + dt.timedelta(hours=1) <= close_ts: j1 += 1
        while j4 + 1 < len(h4) and h4[j4 + 1]['ts'] + dt.timedelta(hours=4) <= close_ts: j4 += 1
        if pos:  # manage the open trade on this bar (stop first: worst case)
            sg = pos['sg']
            hit_stop = x['l'] <= pos['stop'] if sg > 0 else x['h'] >= pos['stop']
            hit_tp = x['h'] >= pos['tp'] if sg > 0 else x['l'] <= pos['tp']
            ldn = close_ts.astimezone(L)
            if hit_stop: ex = pos['stop']
            elif hit_tp and not trail: ex = pos['tp']
            elif ldn.weekday() == 4 and ldn.hour >= 21: ex = x['c']
            else:
                if trail and hit_tp: pos['stop'] = max(pos['stop'], pos['entry']) if sg > 0 else min(pos['stop'], pos['entry'])
                if trail and x['e20'] is not None and ((sg > 0 and x['c'] < x['e20'] - 0.5 * x['atr']) or (sg < 0 and x['c'] > x['e20'] + 0.5 * x['atr'])) and abs(x['c'] - pos['entry']) > pos['risk']:
                    ex = x['c']
                else:
                    continue
            r = (sg * (ex - pos['entry']) - COST) / pos['risk']
            trades.append(dict(ts=pos['ts'], side=pos['side'], R=r, entry=pos['entry'], exit=ex)); pos = None
            continue
        if j1 < 55 or x['atr'] is None or x['adx'] is None: continue
        H = h1[j1]; ldn = close_ts.astimezone(L)
        if ldn.weekday() > 4 or not (7 <= ldn.hour < 20): continue
        if H['adx'] is None or H['adx'] < adx_min: continue
        buy = H['e20'] > H['e50'] and H['pdi'] > H['mdi']; sell = H['e20'] < H['e50'] and H['mdi'] > H['pdi']
        if not (buy or sell): continue
        side = 'BUY' if buy else 'SELL'
        if side not in sides: continue
        if m15_di and ((buy and x['pdi'] <= x['mdi']) or (sell and x['mdi'] <= x['pdi'])): continue
        if use4h:
            F = h4[j4]
            if F['e20'] is None or (buy and F['e20'] < F['e50']) or (sell and F['e20'] > F['e50']): continue
        A = x['atr']
        # the dip: this bar tags the 15m EMA20 and closes back on the trend side of it, in the trend direction, above/below EMA50
        if buy:
            ok = x['l'] <= x['e20'] + 0.1 * A and x['c'] > x['e20'] and x['c'] > x['o'] and x['c'] > x['e50']
        else:
            ok = x['h'] >= x['e20'] - 0.1 * A and x['c'] < x['e20'] and x['c'] < x['o'] and x['c'] < x['e50']
        if not ok: continue
        dkey = ldn.date()
        if day_n.get(dkey, 0) >= max_day: continue
        sg = 1 if buy else -1; e = x['c']
        ext = min(b['l'] for b in m15[i - 2:i + 1]) if buy else max(b['h'] for b in m15[i - 2:i + 1])
        stop = ext - sg * 0.3 * A
        if sg * (e - stop) < 1.0 * A: stop = e - sg * 1.0 * A
        risk = abs(e - stop)
        pos = dict(ts=close_ts, side=side, sg=sg, entry=e, stop=stop, risk=risk, tp=e + sg * rr * risk)
        day_n[dkey] = day_n.get(dkey, 0) + 1
    return trades

def stats(t):
    if not t: return dict(n=0, win=0, R=0, pf=0, dd=0, avg=0)
    R = [x['R'] for x in t]; w = [r for r in R if r > 0]; l = [-r for r in R if r <= 0]
    eq = pk = dd = 0
    for r in R: eq += r; pk = max(pk, eq); dd = max(dd, pk - eq)
    return dict(n=len(R), win=round(100 * len(w) / len(R)), R=round(sum(R), 1), pf=round(sum(w) / sum(l), 2) if l else 99, dd=round(dd, 1), avg=round(sum(R) / len(R), 2))

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else '/home/user/cbf-gold-desk/backtest/data/xau_15m.json'
    m15 = prepare(load(path)); h1 = prepare(resample(m15, 60)); h4 = prepare(resample(m15, 240))
    mid = m15[len(m15) // 2]['ts']; days = (m15[-1]['ts'] - m15[0]['ts']).days * 5 / 7
    print(f"data {m15[0]['ts']:%Y-%m-%d} to {m15[-1]['ts']:%Y-%m-%d}, {len(m15)} 15m bars; unseen half from {mid:%Y-%m-%d}; ~{days:.0f} trading days")
    print(f"{'variant':44} {'trades':>6} {'/day':>5} {'win%':>5} {'R':>7} {'PF':>5} {'maxDD':>6} | {'in-sample R':>11} {'PF':>5} | {'UNSEEN R':>8} {'PF':>5} {'win%':>5}")
    variants = [
        ('ADX25, 2R, both sides', {}),
        ('ADX20, 2R', dict(adx_min=20)),
        ('ADX30, 2R', dict(adx_min=30)),
        ('ADX25, 1.5R', dict(rr=1.5)),
        ('ADX25, 3R', dict(rr=3.0)),
        ('ADX25, 2R, + 4H agrees', dict(use4h=True)),
        ('ADX25, 2R, no M15 DI check', dict(m15_di=False)),
        ('ADX25, trail (BE at 2R, exit on EMA20 loss)', dict(trail=True)),
        ('ADX25, 2R, BUYS only', dict(sides=('BUY',))),
        ('ADX25, 2R, SELLS only', dict(sides=('SELL',))),
        ('ADX25, 2R, max 1 a day', dict(max_day=1)),
    ]
    for name, kw in variants:
        t = run(m15, h1, h4, **kw); a = stats(t); i = stats([x for x in t if x['ts'] < mid]); u = stats([x for x in t if x['ts'] >= mid])
        print(f"{name:44} {a['n']:6} {a['n'] / days:5.2f} {a['win']:5} {a['R']:7} {a['pf']:5} {a['dd']:6} | {i['R']:11} {i['pf']:5} | {u['R']:8} {u['pf']:5} {u['win']:5}")
