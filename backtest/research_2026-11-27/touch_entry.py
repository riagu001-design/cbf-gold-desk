"""Early entry test on the LIVE trend pullback engine (27 Nov 2026, Woody: "Can you spot the move early and send the
setup earlier", then "Yes do both").
  close (live)  a closed 15m candle dips to the EMA20 and closes back beyond it; market order at that close
  touch         market order the moment price touches the EMA20 zone (EMA20 + 0.1 ATR for buys), using only what was
                known at the previous 15m close (1H control, 15m DI, EMA20/50, ATR, previous close beyond EMA50).
                Fill at the zone, or at the candle open if it gaps through. Stop beyond the two previous candles and
                the entry, plus 0.3 ATR (at least 1 ATR). If that same candle also reaches the stop it counts as a
                loss (worst case); the target is only checked from the next candle.
Same data, costs, hours (07:00-20:00 London), 3 a day, one at a time, 2R; first half in-sample, second half unseen."""
import os, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'research_2026-11-23'))
from pullback import load, prepare, resample, stats, L, COST
from four_setups import pivots
from reentry import run as run_close


def run_touch(m15, h1, h4, adx_min=20, rr=2.0, max_day=3):
    ph, pl = pivots(h4, 2); j1 = j4 = -1; ah = al = 0; trades = []; pos = None; day_n = {}
    for i in range(61, len(m15)):
        x = m15[i]; p = m15[i - 1]; t0 = x['ts']; ct = t0 + dt.timedelta(minutes=15)
        while j1 + 1 < len(h1) and h1[j1 + 1]['ts'] + dt.timedelta(hours=1) <= t0: j1 += 1
        while j4 + 1 < len(h4) and h4[j4 + 1]['ts'] + dt.timedelta(hours=4) <= t0: j4 += 1
        while ah < len(ph) and ph[ah][0] <= j4: ah += 1
        while al < len(pl) and pl[al][0] <= j4: al += 1
        if pos:
            sg = pos['sg']; ld = ct.astimezone(L)
            if (x['l'] <= pos['stop']) if sg > 0 else (x['h'] >= pos['stop']): ex = pos['stop']
            elif (x['h'] >= pos['tp']) if sg > 0 else (x['l'] <= pos['tp']): ex = pos['tp']
            elif ld.weekday() == 4 and ld.hour >= 21: ex = x['c']
            else: continue
            trades.append(dict(ts=pos['ts'], side=pos['side'], grade=pos['grade'], R=(sg * (ex - pos['entry']) - COST) / pos['risk'])); pos = None
            continue
        if j1 < 55 or p['atr'] is None or p['adx'] is None: continue
        H = h1[j1]; ld = t0.astimezone(L)
        if ld.weekday() > 4 or not (7 <= ld.hour < 20) or H['adx'] is None or H['adx'] < adx_min: continue
        buy = H['e20'] > H['e50'] and H['pdi'] > H['mdi']; sell = H['e20'] < H['e50'] and H['mdi'] > H['pdi']
        if not (buy or sell): continue
        if (buy and p['pdi'] <= p['mdi']) or (sell and p['mdi'] <= p['pdi']): continue
        A = p['atr']; sg = 1 if buy else -1
        if (buy and p['c'] <= max(p['e20'], p['e50'])) or (sell and p['c'] >= min(p['e20'], p['e50'])): continue  # must be away from the EMA20, beyond the EMA50
        zone = p['e20'] + sg * 0.1 * A
        if not ((x['l'] <= zone) if buy else (x['h'] >= zone)): continue
        if day_n.get(ld.date(), 0) >= max_day: continue
        e = min(x['o'], zone) if buy else max(x['o'], zone)
        ext = min(m15[i - 2]['l'], p['l'], e) if buy else max(m15[i - 2]['h'], p['h'], e)
        stop = ext - sg * 0.3 * A
        if sg * (e - stop) < A: stop = e - sg * A
        risk = abs(e - stop); grade = 'C'
        if ah >= 2 and al >= 2:
            up = ph[ah - 1][1] > ph[ah - 2][1] and pl[al - 1][1] > pl[al - 2][1]
            dn = ph[ah - 1][1] < ph[ah - 2][1] and pl[al - 1][1] < pl[al - 2][1]
            if (buy and up) or (sell and dn): grade = 'B'
        day_n[ld.date()] = day_n.get(ld.date(), 0) + 1
        side = 'BUY' if buy else 'SELL'
        if (x['l'] <= stop) if buy else (x['h'] >= stop):  # same candle runs through the stop: worst case loss
            trades.append(dict(ts=t0, side=side, grade=grade, R=(-risk - COST) / risk)); continue
        pos = dict(ts=t0, side=side, grade=grade, sg=sg, entry=e, stop=stop, risk=risk, tp=e + sg * rr * risk)
    return trades


if __name__ == '__main__':
    m15 = prepare(load(os.path.join(os.path.dirname(__file__), '..', 'data', 'xau_15m.json'))); h1 = prepare(resample(m15, 60)); h4 = prepare(resample(m15, 240))
    mid = m15[len(m15) // 2]['ts']
    print(f"data {m15[0]['ts']:%Y-%m-%d} to {m15[-1]['ts']:%Y-%m-%d}; unseen half from {mid:%Y-%m-%d}; costs {COST}/oz; 2R, all grades")
    print(f"{'entry':14} {'n':>4} {'win%':>5} {'avgR':>6} {'R':>7} {'PF':>5} {'maxDD':>6} | {'IS n':>4} {'IS R':>6} | {'UN n':>4} {'UN R':>6} {'UN PF':>5} | {'B n':>4} {'B R':>6} | {'C n':>4} {'C R':>6}")
    for name, t in (('close (live)', run_close(m15, h1, h4)), ('touch', run_touch(m15, h1, h4))):
        a = stats(t); i = stats([x for x in t if x['ts'] < mid]); u = stats([x for x in t if x['ts'] >= mid])
        B = stats([x for x in t if x['grade'] == 'B']); C = stats([x for x in t if x['grade'] == 'C'])
        print(f"{name:14} {a['n']:4} {a['win']:5} {a['avg']:6} {a['R']:7} {a['pf']:5} {a['dd']:6} | {i['n']:4} {i['R']:6} | {u['n']:4} {u['R']:6} {u['pf']:5} | {B['n']:4} {B['R']:6} | {C['n']:4} {C['R']:6}")
