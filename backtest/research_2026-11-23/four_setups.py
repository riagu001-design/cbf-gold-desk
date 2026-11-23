"""Four setups (23 Nov 2026, Woody: "Delete all of them : And use 1. Trend pullback 2. Breakout and retest
3. Failed breakout reversal 4. Range trading").
Data: 12 months of XAUUSD 15m bars (data/xau_15m.json, UTC). H1 and H4 are built from them, completed bars only.
Every swing is a fractal pivot (k bars each side) and is used only once it is confirmed (k bars later): no look-ahead.
Costs 0.40 per oz per trade (spread + slippage guess until we have the broker's figures). Same-bar stop and target:
stop first (worst case). Friday 21:00 London exit. Entries 07:00-20:00 London weekdays.
First half = in-sample, second half = unseen.

Rules (mechanical versions of Woody's text):
 1 PULLBACK  H4 trend = last two confirmed H4 swing highs AND lows both higher (up) or both lower (down).
             The pullback low (since the last M15 minor swing high) touches an H1 swing level (within 0.25 x H1 ATR).
             Entry when an M15 candle closes above that minor swing high. Stop below the pullback low - 0.1 ATR.
             (Sells mirrored.)
 2 RETEST    Levels: previous London day's high/low, today's London session (07:00-12:00) high/low after 12:00.
             An M15 close beyond the level, then within 16 candles a candle trades back to the level and closes
             beyond it in the breakout direction. Stop beyond the retest swing - 0.1 ATR. Each level once a day.
 3 FAILED    Price trades beyond one of those levels (at most 2 closes beyond), closes back inside within 4 candles,
             then within 6 candles closes through the minor swing made during the poke (toward the range interior).
             Stop beyond the failed-breakout extreme + 0.1 ATR. Trades AGAINST the initial move.
 4 RANGE     H1 ADX under 20; the last 48 H1 candles' high and low each touched at least twice (separate touches);
             width 2-8 x H1 ATR. M15 rejection candle at an edge (wick into the outer 10%, closes back inside,
             against the edge). Target the midpoint (whole position). Stop beyond the edge + 0.15 H1 ATR.
             Taken only when the midpoint is at least 1R away after costs.
Exit plans compared on the SAME entries (setups 1-3):
 A  single 2R target
 B  thirds at 0.5R / 1R / 1.5R, stop unchanged
 C  thirds at 0.5R / 1R / 1.5R, stop to breakeven after TP1
One position at a time per test; the combined test takes the first signal and counts overlapping signals once.
Usage: python3 four_setups.py  (prints the tables)"""
import os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from pullback import load, prepare, resample, stats, L
COST = 0.40
SESS = {'all': (7, 20), 'london': (7, 13), 'newyork': (13, 20)}


def pivots(b, k):
    """[(confirm_index, value, index)] for swing highs and lows."""
    hi, lo = [], []
    for i in range(k, len(b) - k):
        w = b[i - k:i + k + 1]
        if b[i]['h'] == max(x['h'] for x in w) and b[i]['h'] > max(x['h'] for x in b[i - k:i]): hi.append((i + k, b[i]['h'], i))
        if b[i]['l'] == min(x['l'] for x in w) and b[i]['l'] < min(x['l'] for x in b[i - k:i]): lo.append((i + k, b[i]['l'], i))
    return hi, lo


def signals(m15, h1, h4):
    """Every entry signal of the four setups: dict(i, setup, side, entry, stop, target=None)."""
    p4h, p4l = pivots(h4, 2); p1h, p1l = pivots(h1, 3); pmh, pml = pivots(m15, 2)
    out = []; j1 = j4 = -1; a4h = a4l = a1 = amh = aml = 0
    day_lv = {}; used = set(); brk = {}; poke = {}
    for i in range(60, len(m15)):
        x = m15[i]; ct = x['ts'] + dt.timedelta(minutes=15); ld = ct.astimezone(L); A = x['atr']
        while j1 + 1 < len(h1) and h1[j1 + 1]['ts'] + dt.timedelta(hours=1) <= ct: j1 += 1
        while j4 + 1 < len(h4) and h4[j4 + 1]['ts'] + dt.timedelta(hours=4) <= ct: j4 += 1
        while a4h < len(p4h) and p4h[a4h][0] <= j4: a4h += 1
        while a4l < len(p4l) and p4l[a4l][0] <= j4: a4l += 1
        while amh < len(pmh) and pmh[amh][0] <= i: amh += 1
        while aml < len(pml) and pml[aml][0] <= i: aml += 1
        while a1 < len(p1h) and p1h[a1][0] <= j1: a1 += 1
        if j1 < 60 or A is None or h1[j1]['atr'] is None: continue
        A1 = h1[j1]['atr']; ok_time = ld.weekday() < 5 and 7 <= ld.hour < 20
        # ---- levels for 2 and 3: previous London day high/low, London session high/low (after 12:00)
        dkey = ld.date()
        if dkey not in day_lv:
            prev = [b for b in m15[max(0, i - 400):i] if (b['ts'] + dt.timedelta(minutes=15)).astimezone(L).date() < dkey]
            if prev:
                pd = (prev[-1]['ts'] + dt.timedelta(minutes=15)).astimezone(L).date()
                pb = [b for b in prev if (b['ts'] + dt.timedelta(minutes=15)).astimezone(L).date() == pd]
                day_lv[dkey] = {'PDH': max(b['h'] for b in pb), 'PDL': min(b['l'] for b in pb)}
            else: day_lv[dkey] = {}
        lv = dict(day_lv[dkey])
        if ld.hour >= 12:
            ls = [b for b in m15[max(0, i - 80):i + 1] if (b['ts'] + dt.timedelta(minutes=15)).astimezone(L).date() == dkey
                  and 7 <= (b['ts'] + dt.timedelta(minutes=15)).astimezone(L).hour < 12]
            if ls: lv['LDH'] = max(b['h'] for b in ls); lv['LDL'] = min(b['l'] for b in ls)
        p = m15[i - 1]
        # ---- 1 PULLBACK
        if ok_time and a4h >= 2 and a4l >= 2 and amh and aml:
            up = p4h[a4h - 1][1] > p4h[a4h - 2][1] and p4l[a4l - 1][1] > p4l[a4l - 2][1]
            dn = p4h[a4h - 1][1] < p4h[a4h - 2][1] and p4l[a4l - 1][1] < p4l[a4l - 2][1]
            levels = [v for c, v, k in p1h[max(0, a1 - 15):a1]] + [v for c, v, k in p1l if c <= j1][-15:]
            tol = 0.25 * A1
            if up:
                _, P, pi = pmh[amh - 1]
                if x['c'] > P >= p['c']:
                    Lw = min(b['l'] for b in m15[pi:i + 1])
                    if any(abs(Lw - v) <= tol for v in levels):
                        st = Lw - 0.1 * A
                        if 0.5 * A <= x['c'] - st <= 4 * A: out.append(dict(i=i, setup='1 pullback', side='BUY', entry=x['c'], stop=st))
            if dn:
                _, P, pi = pml[aml - 1]
                if x['c'] < P <= p['c']:
                    Hw = max(b['h'] for b in m15[pi:i + 1])
                    if any(abs(Hw - v) <= tol for v in levels):
                        st = Hw + 0.1 * A
                        if 0.5 * A <= st - x['c'] <= 4 * A: out.append(dict(i=i, setup='1 pullback', side='SELL', entry=x['c'], stop=st))
        # ---- 2 RETEST and 3 FAILED, per level
        for name, v in lv.items():
            key = (dkey, name)
            # breakout candle (2)
            if key not in brk and key not in used:
                if x['c'] > v >= p['c']: brk[key] = dict(i=i, sg=1, v=v)
                elif x['c'] < v <= p['c']: brk[key] = dict(i=i, sg=-1, v=v)
            elif key in brk and brk[key]['i'] < i:
                B = brk[key]; sg = B['sg']
                if i - B['i'] > 16 or sg * (x['c'] - v) < -0.5 * A: del brk[key]; used.add(key)
                elif ok_time and (x['l'] <= v + 0.1 * A if sg > 0 else x['h'] >= v - 0.1 * A) and sg * (x['c'] - v) > 0 and sg * (x['c'] - x['o']) > 0:
                    ext = min(b['l'] for b in m15[B['i']:i + 1]) if sg > 0 else max(b['h'] for b in m15[B['i']:i + 1])
                    st = ext - sg * 0.1 * A
                    if 0.5 * A <= sg * (x['c'] - st) <= 4 * A:
                        out.append(dict(i=i, setup='2 retest', side='BUY' if sg > 0 else 'SELL', entry=x['c'], stop=st))
                    del brk[key]; used.add(key)
            # failed breakout (3): poke beyond, back inside, break the minor swing toward the interior
            fk = ('F',) + key
            if fk not in poke and fk not in used:
                if x['h'] > v and p['h'] <= v and p['c'] < v: poke[fk] = dict(i=i, sg=1, ext=x['h'], closes=int(x['c'] > v), back=None)
                elif x['l'] < v and p['l'] >= v and p['c'] > v: poke[fk] = dict(i=i, sg=-1, ext=x['l'], closes=int(x['c'] < v), back=None)
            elif fk in poke and poke[fk]['i'] < i:
                P = poke[fk]; sg = P['sg']
                P['ext'] = max(P['ext'], x['h']) if sg > 0 else min(P['ext'], x['l'])
                if P['back'] is None:
                    if sg * (x['c'] - v) > 0: P['closes'] += 1
                    if P['closes'] > 2 or i - P['i'] > 4: del poke[fk]; used.add(fk); continue
                    if sg * (x['c'] - v) < 0:
                        seg = m15[P['i']:i + 1]
                        P['back'] = i; P['swing'] = min(b['l'] for b in seg) if sg > 0 else max(b['h'] for b in seg)
                else:
                    if i - P['back'] > 6 or sg * (x['c'] - v) > 0: del poke[fk]; used.add(fk); continue
                    if ok_time and sg * (P['swing'] - x['c']) > 0:
                        st = P['ext'] + sg * 0.1 * A
                        if 0.5 * A <= sg * (st - x['c']) <= 4 * A:
                            out.append(dict(i=i, setup='3 failed', side='SELL' if sg > 0 else 'BUY', entry=x['c'], stop=st))
                        del poke[fk]; used.add(fk)
        # ---- 4 RANGE
        H = h1[j1]
        if ok_time and H['adx'] is not None and H['adx'] < 20:
            w = h1[j1 - 47:j1 + 1]; top, bot = max(b['h'] for b in w), min(b['l'] for b in w); W = top - bot
            if 2 * A1 <= W <= 8 * A1:
                def touches(f):
                    n, last = 0, -9
                    for k, b in enumerate(w):
                        if f(b) and k - last >= 3: n += 1; last = k
                        elif f(b): last = k
                    return n
                if touches(lambda b: b['h'] >= top - 0.15 * W) >= 2 and touches(lambda b: b['l'] <= bot + 0.15 * W) >= 2:
                    mid = (top + bot) / 2; rng = x['h'] - x['l'] or 1e-9
                    if x['h'] >= top - 0.1 * W and x['c'] < top - 0.1 * W and x['c'] < x['o'] and (x['h'] - max(x['o'], x['c'])) / rng >= 0.4:
                        st = max(x['h'], top) + 0.15 * A1
                        if (x['c'] - mid - COST) >= (st - x['c']): out.append(dict(i=i, setup='4 range', side='SELL', entry=x['c'], stop=st, target=mid))
                    if x['l'] <= bot + 0.1 * W and x['c'] > bot + 0.1 * W and x['c'] > x['o'] and (min(x['o'], x['c']) - x['l']) / rng >= 0.4:
                        st = min(x['l'], bot) - 0.15 * A1
                        if (mid - x['c'] - COST) >= (x['c'] - st): out.append(dict(i=i, setup='4 range', side='BUY', entry=x['c'], stop=st, target=mid))
    return out


def simulate(m15, sigs, plan='A', setups=None, sess='all'):
    """One position at a time. Returns trades with R after costs."""
    lo, hi = SESS[sess]; trades = []; busy_until = -1
    for s in sigs:
        if setups and s['setup'] not in setups: continue
        if s['i'] <= busy_until: continue
        ld = (m15[s['i']]['ts'] + dt.timedelta(minutes=15)).astimezone(L)
        if not (lo <= ld.hour < hi): continue
        sg = 1 if s['side'] == 'BUY' else -1; e, st = s['entry'], s['stop']; R1 = abs(e - st)
        if s.get('target') is not None: legs = [(1.0, s['target'])]; be = False
        elif plan == 'A': legs = [(1.0, e + sg * 2 * R1)]; be = False
        else: legs = [(1 / 3, e + sg * 0.5 * R1), (1 / 3, e + sg * 1.0 * R1), (1 / 3, e + sg * 1.5 * R1)]; be = plan == 'C'
        open_legs = list(legs); got = 0.0; stop = st; j = s['i'] + 1
        while j < len(m15) and open_legs:
            b = m15[j]; t = (b['ts'] + dt.timedelta(minutes=15)).astimezone(L)
            if (b['l'] <= stop) if sg > 0 else (b['h'] >= stop):
                got += sum(f for f, _ in open_legs) * sg * (stop - e); open_legs = []; break
            hit_tp1 = False
            for leg in list(open_legs):
                if (b['h'] >= leg[1]) if sg > 0 else (b['l'] <= leg[1]):
                    got += leg[0] * sg * (leg[1] - e); open_legs.remove(leg); hit_tp1 = True
            if open_legs and t.weekday() == 4 and t.hour >= 21:
                got += sum(f for f, _ in open_legs) * sg * (b['c'] - e); open_legs = []; break
            if be and hit_tp1: stop = e if sg > 0 else e  # breakeven from the next candle
            j += 1
        busy_until = j
        trades.append(dict(ts=ld, setup=s['setup'], side=s['side'], R=(got - COST) / R1))
    return trades


def row(name, t, mid):
    a = stats(t); i = stats([x for x in t if x['ts'] < mid]); u = stats([x for x in t if x['ts'] >= mid])
    return f"{name:34} {a['n']:5} {a['win']:5} {a['avg']:6} {a['R']:7} {a['pf']:5} {a['dd']:6} | {i['avg']:6} {i['R']:7} | {u['avg']:6} {u['R']:7} {u['pf']:5}"


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else '/home/user/cbf-gold-desk/backtest/data/xau_15m.json'
    m15 = prepare(load(path)); h1 = prepare(resample(m15, 60)); h4 = prepare(resample(m15, 240))
    mid = m15[len(m15) // 2]['ts'].astimezone(L)
    sigs = signals(m15, h1, h4)
    print(f"data {m15[0]['ts']:%Y-%m-%d} to {m15[-1]['ts']:%Y-%m-%d}; unseen half from {mid:%Y-%m-%d}; costs {COST}/oz")
    print('signals:', {k: sum(1 for s in sigs if s['setup'] == k) for k in sorted({s['setup'] for s in sigs})})
    hdr = f"{'test':34} {'n':>5} {'win%':>5} {'avgR':>6} {'R':>7} {'PF':>5} {'maxDD':>6} | {'IS avg':>6} {'IS R':>7} | {'UN avg':>6} {'UN R':>7} {'UN PF':>5}"
    for sess in ('all', 'london', 'newyork'):
        print(f"\n=== session: {sess} ==="); print(hdr)
        for su in ('1 pullback', '2 retest', '3 failed', '4 range'):
            plans = ('A', 'B', 'C') if su != '4 range' else ('A',)
            for pl in plans:
                nm = f"{su} {'midpoint' if su == '4 range' else {'A': '2R', 'B': 'thirds', 'C': 'thirds+BE'}[pl]}"
                print(row(nm, simulate(m15, sigs, pl, {su}, sess), mid))
        for pl in ('A', 'B', 'C'):
            print(row(f"1+2 combined {pl}", simulate(m15, sigs, pl, {'1 pullback', '2 retest'}, sess), mid))
