"""Woody's 4-timeframe framework (28 Nov 2026): D1 global market bias, H4 primary direction, H1 setup identification,
M15 entry confirmation. Rules fixed BEFORE testing; same data, costs, hours and pass test as ten.py.
FILTER for every strategy: D1 bias AND H4 bias (EMA20 vs EMA50 with the close beyond EMA50, on each timeframe) must both
equal the trade direction. Range trading is left out (it needs no trend, which contradicts a D1 and H4 bias).
Strategies already on H4/H1/M15 keep their ten.py rules: trend pullback, breakout and retest, supply and demand,
momentum, Sakata candlesticks. Four are rebuilt on H1 setup / M15 entry:
  LSW4  liquidity sweep: an H1 candle trades beyond the previous 20 H1 lows (highs) and closes back inside; within the next
        4 M15 candles an M15 close beyond the extreme of the previous 3 M15 candles. Stop beyond the sweep extreme plus
        0.3 M15 ATR (at least 1 M15 ATR).
  SMC4  Smart Money Concepts: the same H1 break of structure and order block as ten.py; entry: an M15 candle taps the
        block and closes beyond the previous M15 high (low) while the block holds. Stop beyond the block plus 0.1 H1 ATR.
  KZ4   kill zone (07:00-10:00 and 12:00-15:00 London): an H1 candle tags the H1 EMA20 (0.1 ATR) with the close beyond the
        H1 EMA50; within the next 4 M15 candles, inside the kill zone, an M15 close beyond the previous M15 high (low).
  EMA4  EMA 9/21: an H1 EMA9/EMA21 cross; within the next 4 M15 candles an M15 close beyond the previous M15 high (low).
Default stop (last 3 M15 candles plus 0.3 ATR, at least 1 ATR) and 2R target unless stated."""
import os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ten
from ten import TF, default_stop, st, COST, FIN, Y1, Y2, L
ORIG = ten.sig  # the unfiltered ten.py rules (ten.sig is patched while run4 runs)


def sig4(name, i, m5, T, mem, last_sh, p1l, ld):
    H4, H1, M15 = T[240], T[60], T[15]; k1, k15 = H1.lc[i], M15.lc[i]; new1, new15 = i in H1.close_at, i in M15.close_at
    if name in ('TPB', 'BRR', 'SND', 'MOM', 'SAK'): return ORIG(name, i, m5, T, mem, last_sh, p1l, ld)
    if name == 'SMC4':  # reuse the H1 structure from ten.py's SMC, then confirm on M15
        if new1: ORIG('SMC', i, m5, T, mem, last_sh, p1l, ld)  # updates mem['smc'] on H1 closes (its M5 entry needs new5, skipped below)
        z = mem.get('smc')
        if not z or not new15 or k15 < 60: return None
        sg, far, near, kb, A1 = z
        if k1 - kb > 24: mem.pop('smc'); return None
        y, p = M15.b[k15], M15.b[k15 - 1]
        if sg > 0 and y['l'] <= near and y['c'] > far and y['c'] > p['h']: mem.pop('smc'); return 1, y['c'], far - 0.1 * A1, None
        if sg < 0 and y['h'] >= near and y['c'] < far and y['c'] < p['l']: mem.pop('smc'); return -1, y['c'], far + 0.1 * A1, None
        return None
    if new1 and k1 > 60:
        y = H1.b[k1]; A1 = H1.atr[k1]
        if name == 'LSW4':
            lo20 = min(z['l'] for z in H1.b[k1 - 20:k1]); hi20 = max(z['h'] for z in H1.b[k1 - 20:k1])
            if y['l'] < lo20 and y['c'] > lo20: mem['s'] = (1, y['l'], k15)
            elif y['h'] > hi20 and y['c'] < hi20: mem['s'] = (-1, y['h'], k15)
        elif name == 'KZ4':
            if y['l'] <= H1.e20[k1] + 0.1 * A1 and y['c'] > H1.e50[k1]: mem['s'] = (1, None, k15)
            elif y['h'] >= H1.e20[k1] - 0.1 * A1 and y['c'] < H1.e50[k1]: mem['s'] = (-1, None, k15)
        elif name == 'EMA4':
            if H1.e9[k1] > H1.e21[k1] and H1.e9[k1 - 1] <= H1.e21[k1 - 1]: mem['s'] = (1, None, k15)
            elif H1.e9[k1] < H1.e21[k1] and H1.e9[k1 - 1] >= H1.e21[k1 - 1]: mem['s'] = (-1, None, k15)
    z = mem.get('s')
    if not z or not new15 or k15 < 60: return None
    sg, ext, k0 = z
    if k15 - k0 > 4: mem.pop('s'); return None
    if k15 == k0: return None
    if name == 'KZ4' and not (7 <= ld.hour < 10 or 12 <= ld.hour < 15): return None
    y = M15.b[k15]; A = M15.atr[k15]
    if name == 'LSW4':
        prev3 = M15.b[k15 - 3:k15]
        if (y['c'] > max(q['h'] for q in prev3)) if sg > 0 else (y['c'] < min(q['l'] for q in prev3)):
            mem.pop('s'); stop = ext - sg * 0.3 * A
            if sg * (y['c'] - stop) < A: stop = y['c'] - sg * A
            return sg, y['c'], stop, None
        return None
    p = M15.b[k15 - 1]
    if (y['c'] > p['h']) if sg > 0 else (y['c'] < p['l']):
        mem.pop('s'); return sg, y['c'], default_stop(sg, y['c'], M15.b[k15 - 2:k15 + 1], A), None
    return None


def run4(name, m5, T, D1, cost=COST, fin=FIN):
    orig = ten.sig
    def filt(nm, i, m5_, T_, mem, last_sh, p1l, ld):
        s = sig4(name, i, m5_, T_, mem, last_sh, p1l, ld) if nm == name else orig(nm, i, m5_, T_, mem, last_sh, p1l, ld)
        if s and nm == name:
            kd = D1.lc[i]; k4 = T_[240].lc[i]
            if not (D1.bias(kd) == s[0] and T_[240].bias(k4) == s[0]): return None
        return s
    ten.sig = filt
    try: return ten.run(name, m5, T, cost, fin)
    finally: ten.sig = orig


if __name__ == '__main__':
    final = '--final' in sys.argv
    m5 = ten.load(); T = ten.build(m5)
    D1 = TF(m5, 1440); lc, k = [], -1
    for i in range(len(m5)):
        if i in D1.close_at: k = D1.close_at[i]
        lc.append(k)
    D1.lc = lc
    print(f"D1 bias + H4 direction + H1 setup + M15 entry; OANDA XAU_USD {m5[0]['ts']:%Y-%m-%d} to {m5[-1]['ts']:%Y-%m-%d}; " + ('FINAL YEAR INCLUDED' if final else 'development years only'))
    print(f"{'strategy':24} | {'n':>4} {'win%':>4} {'avg':>6} {'dev R':>6} {'PF':>5} {'DD':>5} | {'Y1 R':>6} {'Y2 R':>6} | {'x2 cost':>7}" + (f" | {'final R':>7} {'n':>4} {'PASS':>5}" if final else ''))
    for code, label in (('TPB', 'Trend pullback'), ('BRR', 'Breakout & retest'), ('LSW4', 'Liquidity sweep'), ('SMC4', 'Smart Money Concepts'),
                        ('SND', 'Supply & demand'), ('EMA4', 'EMA 9/21 crossover'), ('MOM', 'Momentum trading'), ('SAK', 'Sakata candlesticks'), ('KZ4', 'London/NY kill zone')):
        t = run4(code, m5, T, D1); dev = [x for x in t if x['ts'] < Y2]; a = st(dev)
        y1 = st([x for x in dev if x['ts'] < Y1])['R']; y2 = st([x for x in dev if x['ts'] >= Y1])['R']
        x2 = st([x for x in run4(code, m5, T, D1, 2 * COST, 2 * FIN) if x['ts'] < Y2])['R']
        row = f"{label:24} | {a['n']:4} {a['win']:4} {a['avg']:6} {a['R']:6} {a['pf']:5} {a['dd']:5} | {y1:6} {y2:6} | {x2:7}"
        if final:
            f = st([x for x in t if x['ts'] >= Y2]); ok = y1 > 0 and y2 > 0 and x2 > 0 and f['R'] > 0
            row += f" | {f['R']:7} {f['n']:4} {'YES' if ok else 'no':>5}"
        print(row, flush=True)
