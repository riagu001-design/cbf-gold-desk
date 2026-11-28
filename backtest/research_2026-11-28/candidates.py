"""New-strategy search on OANDA XAU_USD 15m, Nov 2023 - Nov 2026 (Woody 28 Nov 2026: "find a new strategy").
Candidates and parameters are fixed BEFORE testing (no tuning). Development: 1 Nov 2023 - 31 Oct 2025 (two years,
Y1 and Y2). Final check: 1 Nov 2025 - 27 Nov 2026, looked at once.
PASS = positive in Y1, Y2 and the final year, and still positive with costs doubled.
Costs: spread/slippage COST $/oz per trade, plus overnight financing FIN of the price per night held (both directions,
conservative), counted at each 22:00 UTC rollover. Market orders at candle closes, stops/targets checked on 15m candles
(stop first when both are touched in one candle).
  D20   daily Donchian breakout: close above the prior 20-day high = buy (below the low = sell); stop 2 x ATR20(daily);
        exit at the daily close beyond the 10-day low (high for sells). Turtle system 1.
  D20L  the same, buys only (gold's long drift).
  DEMA  daily trend: buy when the close is above EMA50 and EMA20 > EMA50 (sell mirrored); stop 3 x ATR20; exit at
        the daily close back through EMA50.
  H4PB  4H pullback in the daily trend: daily EMA20 > EMA50 and close > EMA50 = buys only (sells mirrored); a closed
        4H candle dips to within 0.1 ATR of the 4H EMA20, closes back above it and bullish; stop beyond the last three
        4H candles plus 0.3 ATR (at least 1 ATR); target 2R. One trade at a time.
  H4PB3 the same with a 3R target."""
import os, sys, json, datetime as dt
H = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc
COST, FIN = 0.40, 0.0002


def load():
    d = json.load(open(os.path.join(H, '..', 'data', 'xau_15m_oanda.json')))['bars']
    return [dict(ts=dt.datetime.strptime(t, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC), o=o, h=h, l=l, c=c) for t, o, h, l, c in d]


def resample(b, key):
    out, cur = [], None
    for x in b:
        k = key(x['ts'])
        if cur is None or cur['k'] != k:
            if cur: out.append(cur)
            cur = dict(k=k, ts=x['ts'], o=x['o'], h=x['h'], l=x['l'], c=x['c'], end=x['ts'] + dt.timedelta(minutes=15))
        else:
            cur['h'] = max(cur['h'], x['h']); cur['l'] = min(cur['l'], x['l']); cur['c'] = x['c']; cur['end'] = x['ts'] + dt.timedelta(minutes=15)
    out.append(cur); return out


def ema(v, n):
    k, o = 2 / (n + 1), [v[0]]
    for x in v[1:]: o.append(x * k + o[-1] * (1 - k))
    return o


def atr(b, n):
    tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
    o, a = [], None
    for i, t in enumerate(tr):
        a = (sum(tr[:n]) / n if i == n - 1 else None) if a is None else (a * (n - 1) + t) / n
        o.append(a)
    return o


def daily_signals(D, name):
    """Per completed day i: (entry_side or None, exit_long, exit_short, stop distance)."""
    c = [x['c'] for x in D]; e20, e50 = ema(c, 20), ema(c, 50); A = atr(D, 20); out = []
    for i in range(len(D)):
        if i < 55 or A[i] is None: out.append((None, False, False, None)); continue
        hi20, lo20 = max(x['h'] for x in D[i - 20:i]), min(x['l'] for x in D[i - 20:i])
        lo10, hi10 = min(x['l'] for x in D[i - 10:i]), max(x['h'] for x in D[i - 10:i])
        if name in ('D20', 'D20L'):
            side = 1 if c[i] > hi20 else (-1 if c[i] < lo20 and name == 'D20' else None)
            out.append((side, c[i] < lo10, c[i] > hi10, 2 * A[i]))
        else:  # DEMA
            up = c[i] > e50[i] and e20[i] > e50[i]; dn = c[i] < e50[i] and e20[i] < e50[i]
            out.append((1 if up else -1 if dn else None, c[i] < e50[i], c[i] > e50[i], 3 * A[i]))
    return out


def run(name, b, cost=COST, fin=FIN):
    D = resample(b, lambda t: t.date()); H4 = resample(b, lambda t: (t.date(), t.hour // 4))
    trades, pos = [], None
    if name in ('D20', 'D20L', 'DEMA'):
        sig = daily_signals(D, name); di = 0; pending = None
    else:
        c4 = [x['c'] for x in H4]; e20_4 = ema(c4, 20); A4 = atr(H4, 14)
        cd = [x['c'] for x in D]; de20, de50 = ema(cd, 20), ema(cd, 50); di = -1; hj = 0; rr = 3.0 if name == 'H4PB3' else 2.0
    last_day = None
    for x in b:
        t_end = x['ts'] + dt.timedelta(minutes=15)
        # overnight financing at each 22:00 UTC rollover while a position is open
        if pos and x['ts'].hour == 22 and x['ts'].minute == 0 and x['ts'].date() != last_day:
            pos['fin'] += fin * x['o']; last_day = x['ts'].date()
        if pos:  # stops and targets on the 15m candle
            sg = pos['sg']; ex = None
            if (x['l'] <= pos['stop']) if sg > 0 else (x['h'] >= pos['stop']): ex = pos['stop']
            elif pos.get('tp') and ((x['h'] >= pos['tp']) if sg > 0 else (x['l'] <= pos['tp'])): ex = pos['tp']
            if ex is not None:
                trades.append(dict(ts=pos['ts'], R=(sg * (ex - pos['e']) - cost - pos['fin']) / pos['risk'])); pos = None
        if name in ('D20', 'D20L', 'DEMA'):
            while di < len(D) and D[di]['end'] <= t_end:  # day di just closed at this candle's end
                s, xl, xs, sd = sig[di]; px = D[di]['c']
                if pos and ((pos['sg'] > 0 and xl) or (pos['sg'] < 0 and xs) or (s is not None and s != pos['sg'])):
                    trades.append(dict(ts=pos['ts'], R=(pos['sg'] * (px - pos['e']) - cost - pos['fin']) / pos['risk'])); pos = None
                if not pos and s is not None and sd:
                    pos = dict(ts=D[di]['end'], sg=s, e=px, stop=px - s * sd, risk=sd, fin=0.0)
                di += 1
        else:
            while di + 1 < len(D) and D[di + 1]['end'] <= t_end: di += 1
            while hj < len(H4) and H4[hj]['end'] <= t_end:
                k = hj; hj += 1
                if pos or di < 55 or k < 30 or A4[k] is None: continue
                up = de20[di] > de50[di] and cd[di] > de50[di]; dn = de20[di] < de50[di] and cd[di] < de50[di]
                y = H4[k]; A = A4[k]; e = y['c']
                if up and y['l'] <= e20_4[k] + 0.1 * A and y['c'] > e20_4[k] and y['c'] > y['o']: sg = 1
                elif dn and y['h'] >= e20_4[k] - 0.1 * A and y['c'] < e20_4[k] and y['c'] < y['o']: sg = -1
                else: continue
                ext = min(z['l'] for z in H4[k - 2:k + 1]) if sg > 0 else max(z['h'] for z in H4[k - 2:k + 1])
                stop = ext - sg * 0.3 * A
                if sg * (e - stop) < A: stop = e - sg * A
                risk = abs(e - stop); pos = dict(ts=y['end'], sg=sg, e=e, stop=stop, risk=risk, tp=e + sg * rr * risk, fin=0.0)
    return trades


def st(t):
    if not t: return dict(n=0, R=0.0, win=0, pf=0, dd=0.0, avg=0.0)
    R = [x['R'] for x in t]; w = [r for r in R if r > 0]; l = [-r for r in R if r <= 0]; eq = pk = dd = 0
    for r in R: eq += r; pk = max(pk, eq); dd = max(dd, pk - eq)
    return dict(n=len(R), R=round(sum(R), 1), win=round(100 * len(w) / len(R)), pf=round(sum(w) / sum(l), 2) if l else 99, dd=round(dd, 1), avg=round(sum(R) / len(R), 2))


if __name__ == '__main__':
    b = load(); Y1, Y2, F = dt.datetime(2024, 11, 1, tzinfo=UTC), dt.datetime(2025, 11, 1, tzinfo=UTC), None
    final = '--final' in sys.argv
    print(f"OANDA XAU_USD {b[0]['ts']:%Y-%m-%d} to {b[-1]['ts']:%Y-%m-%d}; costs ${COST}/oz + {FIN*100:.2f}% a night; " + ('FINAL CHECK INCLUDED' if final else 'development years only'))
    print(f"{'':6} | {'n':>3} {'win%':>4} {'avg':>6} {'total R':>7} {'PF':>5} {'DD':>5} | {'Y1 R':>6} {'Y2 R':>6} | {'x2 cost':>7}" + (f" | {'final R':>7} {'final n':>7}" if final else ''))
    for name in ('D20', 'D20L', 'DEMA', 'H4PB', 'H4PB3'):
        t = run(name, b); dev = [x for x in t if x['ts'] < Y2]; a = st(dev)
        y1 = st([x for x in dev if x['ts'] < Y1])['R']; y2 = st([x for x in dev if x['ts'] >= Y1])['R']
        t2 = [x for x in run(name, b, cost=2 * COST, fin=2 * FIN) if x['ts'] < Y2]
        row = f"{name:6} | {a['n']:3} {a['win']:4} {a['avg']:6} {a['R']:7} {a['pf']:5} {a['dd']:5} | {y1:6} {y2:6} | {st(t2)['R']:7}"
        if final:
            f = st([x for x in t if x['ts'] >= Y2]); row += f" | {f['R']:7} {f['n']:7}"
        print(row)
