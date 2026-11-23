"""H4 structure filter on the LIVE trend pullback engine (23 Nov 2026, Woody: "Yes backtest the H4 filter").
Base = pullback.py ADX 20, 2R (the live pb_scan.py rules). Filters tested on the same data and costs:
  agree     buy only when the last two confirmed H4 swing highs AND lows are both higher (sell: both lower)
  not_against  skip a buy only when H4 makes lower highs AND lower lows (mixed structure is allowed)
  ema       H4 EMA20 above EMA50 for buys (the old use4h filter), for comparison
H4 swings are fractal pivots (2 candles each side), used only once confirmed. First half in-sample, second half unseen."""
import os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from pullback import load, prepare, resample, stats, L, COST
from four_setups import pivots


def run(m15, h1, h4, filt=None, adx_min=20, rr=2.0, max_day=3):
    ph, pl = pivots(h4, 2); j1 = j4 = -1; ah = al = 0; trades = []; pos = None; day_n = {}
    for i in range(60, len(m15)):
        x = m15[i]; ct = x['ts'] + dt.timedelta(minutes=15)
        while j1 + 1 < len(h1) and h1[j1 + 1]['ts'] + dt.timedelta(hours=1) <= ct: j1 += 1
        while j4 + 1 < len(h4) and h4[j4 + 1]['ts'] + dt.timedelta(hours=4) <= ct: j4 += 1
        while ah < len(ph) and ph[ah][0] <= j4: ah += 1
        while al < len(pl) and pl[al][0] <= j4: al += 1
        if pos:
            sg = pos['sg']; ld = ct.astimezone(L)
            if (x['l'] <= pos['stop']) if sg > 0 else (x['h'] >= pos['stop']): ex = pos['stop']
            elif (x['h'] >= pos['tp']) if sg > 0 else (x['l'] <= pos['tp']): ex = pos['tp']
            elif ld.weekday() == 4 and ld.hour >= 21: ex = x['c']
            else: continue
            trades.append(dict(ts=pos['ts'], side=pos['side'], R=(sg * (ex - pos['entry']) - COST) / pos['risk'])); pos = None
            continue
        if j1 < 55 or x['atr'] is None or x['adx'] is None: continue
        H = h1[j1]; ld = ct.astimezone(L)
        if ld.weekday() > 4 or not (7 <= ld.hour < 20) or H['adx'] is None or H['adx'] < adx_min: continue
        buy = H['e20'] > H['e50'] and H['pdi'] > H['mdi']; sell = H['e20'] < H['e50'] and H['mdi'] > H['pdi']
        if not (buy or sell): continue
        if (buy and x['pdi'] <= x['mdi']) or (sell and x['mdi'] <= x['pdi']): continue
        if filt and ah >= 2 and al >= 2:
            up = ph[ah - 1][1] > ph[ah - 2][1] and pl[al - 1][1] > pl[al - 2][1]
            dn = ph[ah - 1][1] < ph[ah - 2][1] and pl[al - 1][1] < pl[al - 2][1]
            if filt == 'agree' and not ((buy and up) or (sell and dn)): continue
            if filt == 'not_against' and ((buy and dn) or (sell and up)): continue
            if filt == 'ema':
                F = h4[j4]
                if (buy and F['e20'] < F['e50']) or (sell and F['e20'] > F['e50']): continue
        elif filt: continue
        A = x['atr']
        ok = (x['l'] <= x['e20'] + 0.1 * A and x['c'] > x['e20'] and x['c'] > x['o'] and x['c'] > x['e50']) if buy else \
             (x['h'] >= x['e20'] - 0.1 * A and x['c'] < x['e20'] and x['c'] < x['o'] and x['c'] < x['e50'])
        if not ok or day_n.get(ld.date(), 0) >= max_day: continue
        sg = 1 if buy else -1; e = x['c']
        ext = min(b['l'] for b in m15[i - 2:i + 1]) if buy else max(b['h'] for b in m15[i - 2:i + 1])
        stop = ext - sg * 0.3 * A
        if sg * (e - stop) < A: stop = e - sg * A
        risk = abs(e - stop); pos = dict(ts=ct, side='BUY' if buy else 'SELL', sg=sg, entry=e, stop=stop, risk=risk, tp=e + sg * rr * risk)
        day_n[ld.date()] = day_n.get(ld.date(), 0) + 1
    return trades


if __name__ == '__main__':
    m15 = prepare(load('/home/user/cbf-gold-desk/backtest/data/xau_15m.json')); h1 = prepare(resample(m15, 60)); h4 = prepare(resample(m15, 240))
    mid = m15[len(m15) // 2]['ts']
    print(f"data {m15[0]['ts']:%Y-%m-%d} to {m15[-1]['ts']:%Y-%m-%d}; unseen half from {mid:%Y-%m-%d}; costs {COST}/oz; live PB rules (ADX 20, 2R)")
    print(f"{'filter':22} {'n':>4} {'win%':>5} {'avgR':>6} {'R':>7} {'PF':>5} {'maxDD':>6} | {'IS n':>4} {'IS R':>6} {'IS PF':>5} | {'UN n':>4} {'UN R':>6} {'UN PF':>5} | buys R  sells R")
    for name, f in (('none (live today)', None), ('H4 structure agrees', 'agree'), ('H4 not against', 'not_against'), ('H4 EMA20/50 agrees', 'ema')):
        t = run(m15, h1, h4, f); a = stats(t); i = stats([x for x in t if x['ts'] < mid]); u = stats([x for x in t if x['ts'] >= mid])
        b = stats([x for x in t if x['side'] == 'BUY']); s = stats([x for x in t if x['side'] == 'SELL'])
        print(f"{name:22} {a['n']:4} {a['win']:5} {a['avg']:6} {a['R']:7} {a['pf']:5} {a['dd']:6} | {i['n']:4} {i['R']:6} {i['pf']:5} | {u['n']:4} {u['R']:6} {u['pf']:5} | {b['R']:6} {s['R']:7}")
