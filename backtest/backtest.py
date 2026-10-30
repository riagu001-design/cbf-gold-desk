#!/usr/bin/env python3
"""Backtest of XAUUSD_RULES.md (30 Oct 2026) on Hyperliquid xyz:GOLD 15m candles.

  python3 backtest.py data.json [variant]

Market entry at the signal bar's close plus a fixed cost; stops and targets checked bar by bar on 15m candles,
stop first when one bar touches both. No news filter (no calendar history). 0.01 lot = $1 per $1 move.
Variants: be2r  = TP1 1R moves SL to entry, TP2 2R or next level (0.01 lot cannot close half)
          plain = no stop move, TP 2R or next level
          be15  = SL to entry at 1R, TP 1.5R
"""
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LDN = ZoneInfo('Europe/London')
COST = 0.35          # spread + slippage per trade, $ at 0.01 lot
MAX_STOP = 10.0
DAY_LOSS = -20.0


def ema(xs, n):
    k, out = 2 / (n + 1), [xs[0]]
    for x in xs[1:]:
        out.append(x * k + out[-1] * (1 - k))
    return out


def atr(bars, n=14):
    tr = [bars[0]['h'] - bars[0]['l']] + [max(b['h'] - b['l'], abs(b['h'] - p['c']), abs(b['l'] - p['c'])) for p, b in zip(bars, bars[1:])]
    out, a = [None] * len(bars), sum(tr[:n]) / n
    out[n - 1] = a
    for i in range(n, len(tr)):
        a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    return out


def group(bars, ms):
    out = []
    for b in bars:
        k = b['t'] // ms * ms
        if out and out[-1]['t'] == k:
            o = out[-1]
            o['h'], o['l'], o['c'], o['n'] = max(o['h'], b['h']), min(o['l'], b['l']), b['c'], o['n'] + 1
        else:
            out.append(dict(t=k, o=b['o'], h=b['h'], l=b['l'], c=b['c'], n=1))
    return out


def run(data, variant='be2r', verbose=False):
    m15, h1 = data['15m'], data['1h']
    H = 3600e3
    h4 = [b for b in group(h1, 4 * H) if b['n'] == 4]
    c15 = [b['c'] for b in m15]
    e20, e50, a15 = ema(c15, 20), ema(c15, 50), atr(m15)
    h1c = [b['c'] for b in h1]
    e50h = ema(h1c, 50)
    e50_4 = ema([b['c'] for b in h4], 50)
    h1_t = [b['t'] for b in h1]

    # 1H fractal swings (2 bars each side), known 2 bars after the swing bar closes
    sw_hi, sw_lo = [], []
    for i in range(2, len(h1) - 2):
        w = h1[i - 2:i + 3]
        known = h1[i + 2]['t'] + H
        if h1[i]['h'] == max(b['h'] for b in w):
            sw_hi.append((known, h1[i]['h']))
        if h1[i]['l'] == min(b['l'] for b in w):
            sw_lo.append((known, h1[i]['l']))

    days = {}
    for b in m15:
        d = b['t'] // 86400000
        dd = days.setdefault(d, dict(h=b['h'], l=b['l'], ah=None, al=None))
        dd['h'], dd['l'] = max(dd['h'], b['h']), min(dd['l'], b['l'])

    trades, open_until = [], -1
    day_pl, day_losses, losing_days, last_day = {}, {}, 0, None
    for i in range(60, len(m15) - 1):
        b = m15[i]
        close_t = b['t'] + 15 * 60e3
        if i <= open_until:
            continue
        lt = datetime.fromtimestamp(close_t / 1000, timezone.utc).astimezone(LDN)
        lday = lt.date()
        if last_day != lday:
            if last_day is not None:
                pl = day_pl.get(last_day, 0)
                losing_days = losing_days + 1 if pl < 0 else (0 if pl > 0 else losing_days)
            last_day = lday
        if day_losses.get(lday, 0) >= 2 or day_pl.get(lday, 0) <= DAY_LOSS:
            continue
        mins = lt.hour * 60 + lt.minute
        if lt.weekday() >= 5 or mins >= 21 * 60 or (lt.weekday() == 4 and mins >= 19 * 60) or mins < 60:
            continue
        prime = 420 <= mins < 630 or 780 <= mins < 990
        A = a15[i]
        if A is None:
            continue

        # 1H bias from closed 1H bars
        j = max(k for k in range(len(h1)) if h1_t[k] + H <= close_t) if h1_t[0] + H <= close_t else None
        if j is None or j < 60:
            continue
        hs = [p for t, p in sw_hi if t <= close_t][-2:]
        ls = [p for t, p in sw_lo if t <= close_t][-2:]
        struct = 'MIX'
        if len(hs) == 2 and len(ls) == 2:
            if hs[1] > hs[0] and ls[1] > ls[0]:
                struct = 'UP'
            elif hs[1] < hs[0] and ls[1] < ls[0]:
                struct = 'DN'
        bias = 'UP' if h1c[j] > e50h[j] and struct != 'DN' else 'DN' if h1c[j] < e50h[j] and struct != 'UP' else 'FLAT'
        k4 = max((k for k in range(len(h4)) if h4[k]['t'] + 4 * H <= close_t), default=None)
        bias4 = None if k4 is None or k4 < 50 else ('UP' if h4[k4]['c'] > e50_4[k4] else 'DN')

        # key levels known at this bar
        d = b['t'] // 86400000
        pd = days.get(d - 1) or days.get(d - 3)
        if not pd:
            continue
        asian = [x for x in m15[max(0, i - 96):i + 1] if x['t'] // 86400000 == d and datetime.fromtimestamp(x['t'] / 1000, timezone.utc).hour < 6]
        lv = [pd['h'], pd['l']] + hs + ls + [p for t, p in sw_hi if t <= close_t][-4:] + [p for t, p in sw_lo if t <= close_t][-4:]
        if asian and datetime.fromtimestamp(b['t'] / 1000, timezone.utc).hour >= 6:
            lv += [max(x['h'] for x in asian), min(x['l'] for x in asian)]
        base = round(b['c'] / 25) * 25
        lv += [base + k * 25 for k in (-2, -1, 0, 1, 2)]

        rng = b['h'] - b['l'] or 1e-9
        pos = (b['c'] - b['l']) / rng
        signals = []
        for side in ('BUY', 'SELL'):
            buy = side == 'BUY'
            if bias != 'FLAT' and bias != ('UP' if buy else 'DN'):
                continue
            # A pullback
            if bias != 'FLAT' and (e20[i] > e50[i] if buy else e20[i] < e50[i]):
                zlo, zhi = min(e20[i], e50[i]) - 0.25 * A, max(e20[i], e50[i]) + 0.25 * A
                touch = (b['l'] <= zhi) if buy else (b['h'] >= zlo)
                lvl_touch = any((abs(b['l'] - L) <= 0.25 * A and b['c'] > L) if buy else (abs(b['h'] - L) <= 0.25 * A and b['c'] < L) for L in lv)
                ok = (b['c'] > e20[i] and b['c'] > b['o'] and pos >= 2 / 3) if buy else (b['c'] < e20[i] and b['c'] < b['o'] and pos <= 1 / 3)
                if (touch or lvl_touch) and ok:
                    signals.append(('A', side))
            # B break and retest
            if bias != 'FLAT':
                for L in lv:
                    brk = None
                    for k in range(i - 12, i):
                        if (m15[k - 1]['c'] <= L < m15[k]['c']) if buy else (m15[k - 1]['c'] >= L > m15[k]['c']):
                            brk = k
                    if brk is None or brk >= i - 1:
                        continue
                    held = all((m15[k]['c'] > L) if buy else (m15[k]['c'] < L) for k in range(brk, i + 1))
                    retest = (b['l'] <= L + 0.25 * A) if buy else (b['h'] >= L - 0.25 * A)
                    ok = (b['c'] > L and pos >= 2 / 3) if buy else (b['c'] < L and pos <= 1 / 3)
                    if held and retest and ok:
                        signals.append(('B', side))
                        break
            # C sweep at the opens
            if (420 <= mins < 540 or 780 <= mins < 900):
                sweep_lv = [pd['h'], pd['l']] + ([max(x['h'] for x in asian), min(x['l'] for x in asian)] if asian else [])
                for L in sweep_lv:
                    if buy and b['l'] < L < b['c'] and (min(b['o'], b['c']) - b['l']) >= 0.5 * rng:
                        signals.append(('C', side))
                        break
                    if not buy and b['h'] > L > b['c'] and (b['h'] - max(b['o'], b['c'])) >= 0.5 * rng:
                        signals.append(('C', side))
                        break
        if not signals:
            continue
        setup, side = signals[0]
        if not prime and setup != 'A':
            continue
        if losing_days >= 3 and setup == 'C':
            continue
        buy = side == 'BUY'
        sg = 1 if buy else -1
        # no chasing
        if abs(b['c'] - e20[i]) > 1.5 * A or (rng > 2 * A and (b['c'] > b['o']) == buy):
            continue
        entry = b['c']
        swing = min(x['l'] for x in m15[i - 2:i + 1]) if buy else max(x['h'] for x in m15[i - 2:i + 1])
        stop = swing - sg * 1.5
        if sg * (entry - stop) < 0.5 * A:
            stop = entry - sg * 0.5 * A
        R = abs(entry - stop)
        if R > MAX_STOP:
            continue
        opp = [L for L in lv if (L > entry + 0.1) if buy] if buy else [L for L in lv if L < entry - 0.1]
        nxt = (min(opp) if buy else max(opp)) if opp else None
        if nxt is not None and abs(nxt - entry) < 1.0 * R:
            continue
        cap = 2 * R if variant != 'be15' else 1.5 * R
        if bias4 and bias4 != ('UP' if buy else 'DN'):
            cap = min(cap, 1.5 * R)
        tp = entry + sg * (min(cap, abs(nxt - entry)) if nxt is not None else cap)
        # walk forward
        sl, moved, res, k = stop, False, None, i + 1
        while k < len(m15):
            x = m15[k]
            xt = datetime.fromtimestamp((x['t'] + 15 * 60e3) / 1000, timezone.utc).astimezone(LDN)
            hit_sl = (x['l'] <= sl) if buy else (x['h'] >= sl)
            hit_tp = (x['h'] >= tp) if buy else (x['l'] <= tp)
            if hit_sl:
                res = sg * (sl - entry)
                break
            if hit_tp:
                res = sg * (tp - entry)
                break
            if variant != 'plain' and not moved and ((x['h'] >= entry + R) if buy else (x['l'] <= entry - R)):
                sl, moved = entry, True
            if k - i >= 32 or xt.hour * 60 + xt.minute >= 21 * 60:
                res = sg * (x['c'] - entry)
                break
            k += 1
        if res is None:
            break
        pl = round(res - COST, 2)
        trades.append(dict(t=lt.strftime('%m-%d %H:%M'), setup=setup, side=side, entry=round(entry, 2), R=round(R, 2), pl=pl, r=round(res / R, 2)))
        day_pl[lday] = day_pl.get(lday, 0) + pl
        if pl < 0:
            day_losses[lday] = day_losses.get(lday, 0) + 1
        open_until = k
    return trades


def stats(tr):
    if not tr:
        return 'no trades'
    w = [t for t in tr if t['pl'] > 0]
    gp, gl = sum(t['pl'] for t in w), -sum(t['pl'] for t in tr if t['pl'] < 0)
    eq, peak, dd = 0, 0, 0
    for t in tr:
        eq += t['pl']
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return f"{len(tr)} trades, {100 * len(w) / len(tr):.0f}% wins, ${sum(t['pl'] for t in tr):+.2f}, PF {gp / gl if gl else 99:.2f}, worst drop ${dd:.2f}"


if __name__ == '__main__':
    data = json.load(open(sys.argv[1]))
    for v in (sys.argv[2:] or ['be2r', 'plain', 'be15']):
        tr = run(data, v)
        print(f'{v:6s}', stats(tr))
        half = len(tr) // 2
        print('   1st half', stats(tr[:half]), '| 2nd half', stats(tr[half:]))
        for s in 'ABC':
            print('   setup', s, stats([t for t in tr if t['setup'] == s]))
