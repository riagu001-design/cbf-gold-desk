"""Re-entry rule test on the LIVE trend pullback engine (27 Nov 2026, Woody: "Yes run the backtest").
Base = live rules (h4_filter.run, no filter: every signal is sent, B-grade when H4 agrees, C-grade otherwise).
Variants block new entries after a STOP the same London day:
  same_dir   no new signal in the same direction after a stop that day (the proposed rule)
  any        no new signal at all after a stop that day
  two_losses no new signal after two stops that day
First half in-sample, second half unseen; same data and costs as the 23 Nov test."""
import os, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'research_2026-11-23'))
from pullback import load, prepare, resample, stats, L, COST
from four_setups import pivots


def run(m15, h1, h4, block=None, adx_min=20, rr=2.0, max_day=3):
    ph, pl = pivots(h4, 2); j1 = j4 = -1; ah = al = 0; trades = []; pos = None; day_n = {}; stops = {}
    for i in range(60, len(m15)):
        x = m15[i]; ct = x['ts'] + dt.timedelta(minutes=15)
        while j1 + 1 < len(h1) and h1[j1 + 1]['ts'] + dt.timedelta(hours=1) <= ct: j1 += 1
        while j4 + 1 < len(h4) and h4[j4 + 1]['ts'] + dt.timedelta(hours=4) <= ct: j4 += 1
        while ah < len(ph) and ph[ah][0] <= j4: ah += 1
        while al < len(pl) and pl[al][0] <= j4: al += 1
        if pos:
            sg = pos['sg']; ld = ct.astimezone(L); how = None
            if (x['l'] <= pos['stop']) if sg > 0 else (x['h'] >= pos['stop']): ex = pos['stop']; how = 'stop'
            elif (x['h'] >= pos['tp']) if sg > 0 else (x['l'] <= pos['tp']): ex = pos['tp']
            elif ld.weekday() == 4 and ld.hour >= 21: ex = x['c']
            else: continue
            R = (sg * (ex - pos['entry']) - COST) / pos['risk']
            trades.append(dict(ts=pos['ts'], side=pos['side'], grade=pos['grade'], R=R)); 
            if how: stops.setdefault(ld.date(), []).append(pos['side'])
            pos = None
            continue
        if j1 < 55 or x['atr'] is None or x['adx'] is None: continue
        H = h1[j1]; ld = ct.astimezone(L)
        if ld.weekday() > 4 or not (7 <= ld.hour < 20) or H['adx'] is None or H['adx'] < adx_min: continue
        buy = H['e20'] > H['e50'] and H['pdi'] > H['mdi']; sell = H['e20'] < H['e50'] and H['mdi'] > H['pdi']
        if not (buy or sell): continue
        if (buy and x['pdi'] <= x['mdi']) or (sell and x['mdi'] <= x['pdi']): continue
        side = 'BUY' if buy else 'SELL'; st = stops.get(ld.date(), [])
        if block == 'same_dir' and side in st: continue
        if block == 'any' and st: continue
        if block == 'two_losses' and len(st) >= 2: continue
        grade = 'C'
        if ah >= 2 and al >= 2:
            up = ph[ah - 1][1] > ph[ah - 2][1] and pl[al - 1][1] > pl[al - 2][1]
            dn = ph[ah - 1][1] < ph[ah - 2][1] and pl[al - 1][1] < pl[al - 2][1]
            if (buy and up) or (sell and dn): grade = 'B'
        A = x['atr']
        ok = (x['l'] <= x['e20'] + 0.1 * A and x['c'] > x['e20'] and x['c'] > x['o'] and x['c'] > x['e50']) if buy else \
             (x['h'] >= x['e20'] - 0.1 * A and x['c'] < x['e20'] and x['c'] < x['o'] and x['c'] < x['e50'])
        if not ok or day_n.get(ld.date(), 0) >= max_day: continue
        sg = 1 if buy else -1; e = x['c']
        ext = min(b['l'] for b in m15[i - 2:i + 1]) if buy else max(b['h'] for b in m15[i - 2:i + 1])
        stop = ext - sg * 0.3 * A
        if sg * (e - stop) < A: stop = e - sg * A
        risk = abs(e - stop); pos = dict(ts=ct, side=side, grade=grade, sg=sg, entry=e, stop=stop, risk=risk, tp=e + sg * rr * risk)
        day_n[ld.date()] = day_n.get(ld.date(), 0) + 1
    return trades


if __name__ == '__main__':
    m15 = prepare(load(os.path.join(os.path.dirname(__file__), '..', 'data', 'xau_15m.json'))); h1 = prepare(resample(m15, 60)); h4 = prepare(resample(m15, 240))
    mid = m15[len(m15) // 2]['ts']
    print(f"data {m15[0]['ts']:%Y-%m-%d} to {m15[-1]['ts']:%Y-%m-%d}; unseen half from {mid:%Y-%m-%d}; costs {COST}/oz; live PB rules (ADX 20, 2R, all grades)")
    print(f"{'rule':24} {'n':>4} {'win%':>5} {'avgR':>6} {'R':>7} {'PF':>5} {'maxDD':>6} | {'IS n':>4} {'IS R':>6} | {'UN n':>4} {'UN R':>6} {'UN PF':>5} | {'B n':>4} {'B R':>6} | {'C n':>4} {'C R':>6}")
    for name, b in (('none (live today)', None), ('no same side after stop', 'same_dir'), ('no trade after a stop', 'any'), ('stop after 2 losses', 'two_losses')):
        t = run(m15, h1, h4, b); a = stats(t); i = stats([x for x in t if x['ts'] < mid]); u = stats([x for x in t if x['ts'] >= mid])
        B = stats([x for x in t if x['grade'] == 'B']); C = stats([x for x in t if x['grade'] == 'C'])
        print(f"{name:24} {a['n']:4} {a['win']:5} {a['avg']:6} {a['R']:7} {a['pf']:5} {a['dd']:6} | {i['n']:4} {i['R']:6} | {u['n']:4} {u['R']:6} {u['pf']:5} | {B['n']:4} {B['R']:6} | {C['n']:4} {C['R']:6}")
    # the trades the proposed rule removes
    base = run(m15, h1, h4); new = run(m15, h1, h4, 'same_dir'); keep = {x['ts'] for x in new}
    gone = [x for x in base if x['ts'] not in keep]; s = stats(gone)
    print(f"\nbase trades the same-side rule removes: n {s['n']}, win% {s['win']}, R {s['R']}  (note: removing a trade can also let a later one in)")
