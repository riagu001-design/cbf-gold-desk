"""Ten multi-timeframe strategies (Woody 28 Nov 2026: "Build solid strategies around this information"), each on the
direction / setup / entry timeframes Woody gave. All rules and parameters are fixed here BEFORE testing (no tuning).
Data: OANDA XAU_USD 5m, Nov 2023 - Nov 2026 (broker prices); higher timeframes are built from it, aligned to UTC.

PASS TEST (same as the D20 search): positive in development year 1 (Nov 2023 - Oct 2024) and year 2 (Nov 2024 - Oct 2025),
still positive in development with costs doubled, then positive in the held-back final year (Nov 2025 - Nov 2026),
which is only printed with --final.

COMMON RULES (every strategy): DIRECTION = on the direction timeframe, EMA20 above EMA50 and the close above EMA50 is
bullish (buys only), the mirror is bearish (sells only), anything else = no trade (range trading uses the opposite: no
trend). Entries 07:00-20:00 London on weekdays, one trade at a time per strategy, at most 3 a day, market order at the
close of the entry candle. Stop and target as stated per strategy (default: beyond the last 3 entry candles plus 0.3 ATR,
at least 1 ATR of the entry timeframe; target 2R). Stops and targets are checked on 5m candles, the stop first when both
are touched. Out at Friday 21:00 London. Costs: $0.40/oz per trade plus 0.02% a night when held past 22:00 UTC.

  1 TPB  Trend pullback          H4 / H1 / M15  H1 low tags the H1 EMA20 (within 0.1 ATR) in the last 3 H1 candles while the
                                                H1 close stays beyond the H1 EMA50; entry: an M15 close beyond the previous
                                                M15 high (low for sells).
  2 BRR  Breakout and retest     H4 / H1 / M15  an H1 close beyond the previous 20-candle H1 high = breakout level; within
                                                12 H1 candles price comes back to the level (M15 low within 0.1 M15 ATR of it)
                                                and an M15 candle closes back beyond it in the breakout direction. Stop beyond
                                                the retest low (the 3 M15 candles) plus 0.3 ATR.
  3 LSW  Liquidity sweep         H1 / M15 / M5  an M15 candle trades below the previous 20-candle M15 low and closes back above
                                                it (sell-side liquidity taken); within the next 6 M5 candles an M5 close above
                                                the highest high of the previous 3 M5 candles. Stop beyond the sweep extreme
                                                plus 0.3 M5 ATR.
  4 SMC  Smart Money Concepts    H4 / H1 / M5   H1 break of structure (close above the last confirmed H1 swing high); the
                                                bullish order block is the last bearish H1 candle before that break; within
                                                24 H1 candles price taps the block (M5 low inside it) and an M5 candle closes
                                                above the previous M5 high while above the block low. Stop below the block
                                                low minus 0.1 H1 ATR.
  5 SND  Supply and demand       H4 / H1 / M15  demand zone = a small-bodied H1 base candle (body under 0.5 ATR) followed by an
                                                H1 rally candle with a body over 1.5 ATR; first return within 48 H1 candles,
                                                an M15 candle touches the zone and closes back above its top. Stop below the
                                                zone minus 0.3 M15 ATR.
  6 EMA  EMA 9/21 crossover      H1 / M15 / M15 the M15 EMA9 crosses the EMA21 in the H1 direction (direction here = H1 EMA9
                                                above EMA21 and the close above EMA21); entry at that M15 close.
  7 RNG  Range trading           H1 / M15 / M5  H1 ADX(14) under 20 (no trend). M15 range = the last 32 M15 candles (8 hours),
                                                width 1.5 to 6 M15 ATR. Buy in the bottom 15% of the range when an M5 candle
                                                closes above the previous M5 high (sell in the top 15% mirrored). Stop beyond
                                                the range plus 0.3 M15 ATR; target the middle of the range.
  8 MOM  Momentum trading        H4 / H1 / M15  H1 ADX over 25 and H1 RSI(14) over 55 (under 45 for sells); entry: an M15 close
                                                beyond the previous 8-candle M15 high. Stop 1.5 M15 ATR; target 2R.
  9 SAK  Sakata candlesticks     H4 / H1 / M15  a bullish H1 engulfing or hammer (lower wick at least twice the body, close in
                                                the top third) within 0.5 H1 ATR of the H1 EMA20; within the next 4 M15
                                                candles an M15 close above the pattern high. Stop below the pattern low minus
                                                0.3 M15 ATR (at least 1 M15 ATR).
 10 KZ   London/NY kill zone     H1 / M15 / M5  only 07:00-10:00 and 12:00-15:00 London; an M15 low tags the M15 EMA20 (within
                                                0.1 ATR) with the M15 close beyond the M15 EMA50; entry: an M5 close beyond
                                                the previous M5 high inside the kill zone.
Sells are the mirror image throughout."""
import os, sys, json, datetime as dt
from zoneinfo import ZoneInfo
H = os.path.dirname(os.path.abspath(__file__)); UTC = dt.timezone.utc; L = ZoneInfo('Europe/London')
COST, FIN = 0.40, 0.0002
Y1, Y2 = dt.datetime(2024, 11, 1, tzinfo=UTC), dt.datetime(2025, 11, 1, tzinfo=UTC)


def load():
    d = json.load(open(os.path.join(H, '..', 'data', 'xau_5m_oanda.json')))['bars']
    return [dict(ts=dt.datetime.strptime(t, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC), o=o, h=h, l=l, c=c) for t, o, h, l, c in d]


def ema(v, n):
    k, o = 2 / (n + 1), [v[0]]
    for x in v[1:]: o.append(x * k + o[-1] * (1 - k))
    return o


def atr(b, n=14):
    o, a = [], None
    for i, x in enumerate(b):
        t = x['h'] - x['l'] if i == 0 else max(x['h'] - x['l'], abs(x['h'] - b[i - 1]['c']), abs(x['l'] - b[i - 1]['c']))
        if a is None:
            o.append(None)
            if i == n - 1: a = sum(max(y['h'] - y['l'], 0) for y in b[:n]) / n; o[-1] = a
        else:
            a = (a * (n - 1) + t) / n; o.append(a)
    return o


def adx_rsi(b, n=14):
    adx = [None] * len(b); rsi = [None] * len(b); tr = pdm = mdm = None; acc = []; dx = []; ax = None; ag = al = None
    for i in range(1, len(b)):
        up, dn = b[i]['h'] - b[i - 1]['h'], b[i - 1]['l'] - b[i]['l']
        p = up if up > dn and up > 0 else 0.0; m = dn if dn > up and dn > 0 else 0.0
        t = max(b[i]['h'] - b[i]['l'], abs(b[i]['h'] - b[i - 1]['c']), abs(b[i]['l'] - b[i - 1]['c']))
        ch = b[i]['c'] - b[i - 1]['c']; g, l_ = max(ch, 0), max(-ch, 0)
        if ag is None:
            acc.append((t, p, m, g, l_))
            if len(acc) == n:
                tr, pdm, mdm = sum(a[0] for a in acc), sum(a[1] for a in acc), sum(a[2] for a in acc)
                ag, al = sum(a[3] for a in acc) / n, sum(a[4] for a in acc) / n
            else: continue
        else:
            tr, pdm, mdm = tr - tr / n + t, pdm - pdm / n + p, mdm - mdm / n + m
            ag, al = (ag * (n - 1) + g) / n, (al * (n - 1) + l_) / n
        pdi, mdi = (100 * pdm / tr, 100 * mdm / tr) if tr else (0, 0)
        dx.append(100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0)
        if ax is None and len(dx) == n: ax = sum(dx) / n
        elif ax is not None: ax = (ax * (n - 1) + dx[-1]) / n
        adx[i] = ax; rsi[i] = 100 - 100 / (1 + ag / al) if al else 100
    return adx, rsi


class TF:
    """Candles of one timeframe built from 5m, with indicators, and the 5m index at which each candle closes."""
    def __init__(self, m5, minutes):
        self.b, cur, self.close_at = [], None, {}
        for i, x in enumerate(m5):
            t = x['ts']; k = (t.year, t.month, t.day, (t.hour * 60 + t.minute) // minutes)
            if cur is None or cur['k'] != k:
                if cur: self.b.append(cur); self.close_at[cur['i_last']] = len(self.b) - 1
                cur = dict(k=k, ts=t, o=x['o'], h=x['h'], l=x['l'], c=x['c'], i_last=i)
            else:
                cur['h'] = max(cur['h'], x['h']); cur['l'] = min(cur['l'], x['l']); cur['c'] = x['c']; cur['i_last'] = i
        self.b.append(cur); self.close_at[cur['i_last']] = len(self.b) - 1
        c = [x['c'] for x in self.b]
        self.e9, self.e20, self.e21, self.e50 = ema(c, 9), ema(c, 20), ema(c, 21), ema(c, 50)
        self.atr = atr(self.b); self.adx, self.rsi = adx_rsi(self.b)

    def bias(self, k, fast='e20', slow='e50'):
        if k < 60: return 0
        f, s, c = getattr(self, fast)[k], getattr(self, slow)[k], self.b[k]['c']
        return 1 if f > s and c > s else -1 if f < s and c < s else 0


def swing_highs(b, k=2):
    """Confirmed swing highs/lows: list of (confirm_index, value, index)."""
    hi, lo = [], []
    for i in range(k, len(b) - k):
        w = b[i - k:i + k + 1]
        if b[i]['h'] == max(x['h'] for x in w): hi.append((i + k, b[i]['h'], i))
        if b[i]['l'] == min(x['l'] for x in w): lo.append((i + k, b[i]['l'], i))
    return hi, lo


def default_stop(sg, e, bars, A):
    ext = min(x['l'] for x in bars) if sg > 0 else max(x['h'] for x in bars)
    stop = ext - sg * 0.3 * A
    if sg * (e - stop) < A: stop = e - sg * A
    return stop


class Strat:
    def __init__(self, name, tfs): self.name, self.T = name, tfs; self.mem = {}

    def signal(self, i, m5):  # called every 5m candle; returns (side, entry, stop, target) or None
        raise NotImplementedError


def last_closed(tf, i):  # index of the last tf candle closed at or before 5m index i
    return tf.lc[i]


def build(m5):
    T = {m: TF(m5, m) for m in (5, 15, 60, 240)}
    for t in T.values():  # last closed candle per 5m index
        lc, k = [], -1
        for i in range(len(m5)):
            if i in t.close_at: k = t.close_at[i]
            lc.append(k)
        t.lc = lc
    return T


def run(name, m5, T, cost=COST, fin=FIN):
    H4, H1, M15, M5 = T[240], T[60], T[15], T[5]
    trades, pos, day_n, mem = [], None, {}, {}
    p4h, p4l = swing_highs(H1.b, 2)  # H1 swings for SMC structure
    sh_ptr = 0; last_sh = None
    for i, x in enumerate(m5):
        t_end = x['ts'] + dt.timedelta(minutes=5); ld = t_end.astimezone(L)
        if pos:
            if x['ts'].hour == 22 and x['ts'].minute == 0: pos['fin'] += fin * x['o']
            sg = pos['sg']; ex = None
            if (x['l'] <= pos['stop']) if sg > 0 else (x['h'] >= pos['stop']): ex = pos['stop']
            elif (x['h'] >= pos['tp']) if sg > 0 else (x['l'] <= pos['tp']): ex = pos['tp']
            elif ld.weekday() == 4 and ld.hour >= 21: ex = x['c']
            if ex is not None:
                trades.append(dict(ts=pos['ts'], side=pos['sg'], R=(sg * (ex - pos['e']) - cost - pos['fin']) / pos['risk'])); pos = None
            continue
        while sh_ptr < len(p4h) and p4h[sh_ptr][0] <= H1.lc[i]: last_sh = p4h[sh_ptr]; sh_ptr += 1
        if ld.weekday() > 4 or not (7 <= ld.hour < 20) or day_n.get(ld.date(), 0) >= 3: continue
        s = sig(name, i, m5, T, mem, last_sh, p4l, ld)
        if not s: continue
        sg, e, stop, tp = s; risk = abs(e - stop)
        if risk <= 0: continue
        pos = dict(ts=x['ts'], sg=sg, e=e, stop=stop, risk=risk, tp=tp if tp else e + sg * 2 * risk, fin=0.0)
        day_n[ld.date()] = day_n.get(ld.date(), 0) + 1
    return trades


def sig(name, i, m5, T, mem, last_sh, p1l, ld):
    H4, H1, M15, M5 = T[240], T[60], T[15], T[5]
    k4, k1, k15, k5 = H4.lc[i], H1.lc[i], M15.lc[i], M5.lc[i]
    new15, new5, new1 = i in M15.close_at, i in M5.close_at, i in H1.close_at
    if name == 'TPB':
        if not new15 or k15 < 60 or k1 < 60: return None
        d = H4.bias(k4)
        if not d: return None
        A1 = H1.atr[k1]
        tagged = any((H1.b[j]['l'] <= H1.e20[j] + 0.1 * A1) if d > 0 else (H1.b[j]['h'] >= H1.e20[j] - 0.1 * A1) for j in range(k1 - 2, k1 + 1))
        hold = (H1.b[k1]['c'] > H1.e50[k1]) if d > 0 else (H1.b[k1]['c'] < H1.e50[k1])
        y, p = M15.b[k15], M15.b[k15 - 1]
        trig = (y['c'] > p['h']) if d > 0 else (y['c'] < p['l'])
        if tagged and hold and trig: return d, y['c'], default_stop(d, y['c'], M15.b[k15 - 2:k15 + 1], M15.atr[k15]), None
    elif name == 'BRR':
        if new1 and k1 > 60:
            d = H4.bias(k4); y = H1.b[k1]
            hi20 = max(z['h'] for z in H1.b[k1 - 20:k1]); lo20 = min(z['l'] for z in H1.b[k1 - 20:k1])
            if d > 0 and y['c'] > hi20: mem['brr'] = (1, hi20, k1)
            elif d < 0 and y['c'] < lo20: mem['brr'] = (-1, lo20, k1)
        b = mem.get('brr')
        if not b or not new15 or k15 < 60: return None
        sg, lvl, kb = b
        if k1 - kb > 12: mem.pop('brr'); return None
        y = M15.b[k15]; A = M15.atr[k15]
        touched = (y['l'] <= lvl + 0.1 * A) if sg > 0 else (y['h'] >= lvl - 0.1 * A)
        if touched and ((y['c'] > lvl and y['c'] > y['o']) if sg > 0 else (y['c'] < lvl and y['c'] < y['o'])):
            mem.pop('brr'); return sg, y['c'], default_stop(sg, y['c'], M15.b[k15 - 2:k15 + 1], A), None
    elif name == 'LSW':
        if new15 and k15 > 60:
            d = H1.bias(k1); y = M15.b[k15]
            lo20 = min(z['l'] for z in M15.b[k15 - 20:k15]); hi20 = max(z['h'] for z in M15.b[k15 - 20:k15])
            if d > 0 and y['l'] < lo20 and y['c'] > lo20: mem['lsw'] = (1, y['l'], i)
            elif d < 0 and y['h'] > hi20 and y['c'] < hi20: mem['lsw'] = (-1, y['h'], i)
        s = mem.get('lsw')
        if not s or not new5 or k5 < 60: return None
        sg, ext, i0 = s
        if i - i0 > 6: mem.pop('lsw'); return None
        if i == i0: return None
        y = M5.b[k5]; prev3 = M5.b[k5 - 3:k5]
        if (y['c'] > max(z['h'] for z in prev3)) if sg > 0 else (y['c'] < min(z['l'] for z in prev3)):
            mem.pop('lsw'); A = M5.atr[k5]; stop = ext - sg * 0.3 * A
            if sg * (y['c'] - stop) < A: stop = y['c'] - sg * A
            return sg, y['c'], stop, None
    elif name == 'SMC':
        if new1 and k1 > 60:
            d = H4.bias(k4); y = H1.b[k1]
            if d > 0 and last_sh and y['c'] > last_sh[1] and mem.get('smc_bos') != last_sh[2]:
                for j in range(k1, max(k1 - 12, 0), -1):
                    if H1.b[j]['c'] < H1.b[j]['o']: mem['smc'] = (1, H1.b[j]['l'], H1.b[j]['h'], k1, H1.atr[k1]); break
                mem['smc_bos'] = last_sh[2]
            elif d < 0:
                lows = [z for z in p1l if z[0] <= k1]
                if lows and y['c'] < lows[-1][1] and mem.get('smc_bos') != lows[-1][2]:
                    for j in range(k1, max(k1 - 12, 0), -1):
                        if H1.b[j]['c'] > H1.b[j]['o']: mem['smc'] = (-1, H1.b[j]['h'], H1.b[j]['l'], k1, H1.atr[k1]); break
                    mem['smc_bos'] = lows[-1][2]
        z = mem.get('smc')
        if not z or not new5 or k5 < 60: return None
        sg, far, near, kb, A1 = z
        if k1 - kb > 24: mem.pop('smc'); return None
        y, p = M5.b[k5], M5.b[k5 - 1]
        if sg > 0 and y['l'] <= near and y['c'] > far and y['c'] > p['h']:
            mem.pop('smc'); return 1, y['c'], far - 0.1 * A1, None
        if sg < 0 and y['h'] >= near and y['c'] < far and y['c'] < p['l']:
            mem.pop('smc'); return -1, y['c'], far + 0.1 * A1, None
    elif name == 'SND':
        if new1 and k1 > 60:
            d = H4.bias(k4); base, rally = H1.b[k1 - 1], H1.b[k1]; A1 = H1.atr[k1]
            if abs(base['c'] - base['o']) < 0.5 * A1:
                if d > 0 and rally['c'] - rally['o'] > 1.5 * A1: mem['snd'] = (1, base['l'], base['h'], k1)
                elif d < 0 and rally['o'] - rally['c'] > 1.5 * A1: mem['snd'] = (-1, base['h'], base['l'], k1)
        z = mem.get('snd')
        if not z or not new15 or k15 < 60: return None
        sg, far, near, kz = z
        if k1 - kz > 48 or k1 == kz:
            if k1 - kz > 48: mem.pop('snd')
            return None
        y = M15.b[k15]; A = M15.atr[k15]
        if (y['l'] <= near and y['c'] > near) if sg > 0 else (y['h'] >= near and y['c'] < near):
            mem.pop('snd'); stop = far - sg * 0.3 * A
            if sg * (y['c'] - stop) < A: stop = y['c'] - sg * A
            return sg, y['c'], stop, None
        if (y['c'] < far) if sg > 0 else (y['c'] > far): mem.pop('snd')  # zone broken
    elif name == 'EMA':
        if not new15 or k15 < 60 or k1 < 60: return None
        d = H1.bias(k1, 'e9', 'e21')
        up = M15.e9[k15] > M15.e21[k15] and M15.e9[k15 - 1] <= M15.e21[k15 - 1]
        dn = M15.e9[k15] < M15.e21[k15] and M15.e9[k15 - 1] >= M15.e21[k15 - 1]
        y = M15.b[k15]
        if (d > 0 and up) or (d < 0 and dn): return d, y['c'], default_stop(d, y['c'], M15.b[k15 - 2:k15 + 1], M15.atr[k15]), None
    elif name == 'RNG':
        if not new5 or k5 < 60 or k15 < 60 or k1 < 60 or H1.adx[k1] is None or H1.adx[k1] >= 20: return None
        R = M15.b[k15 - 31:k15 + 1]; hi, lo = max(z['h'] for z in R), min(z['l'] for z in R); A = M15.atr[k15]; w = hi - lo
        if not (1.5 * A <= w <= 6 * A): return None
        y, p = M5.b[k5], M5.b[k5 - 1]; mid = (hi + lo) / 2
        if y['c'] <= lo + 0.15 * w and y['c'] > p['h']: return 1, y['c'], lo - 0.3 * A, mid
        if y['c'] >= hi - 0.15 * w and y['c'] < p['l']: return -1, y['c'], hi + 0.3 * A, mid
    elif name == 'MOM':
        if not new15 or k15 < 60 or k1 < 60 or H1.adx[k1] is None: return None
        d = H4.bias(k4); y = M15.b[k15]; A = M15.atr[k15]
        if H1.adx[k1] <= 25: return None
        if d > 0 and H1.rsi[k1] > 55 and y['c'] > max(z['h'] for z in M15.b[k15 - 8:k15]): return 1, y['c'], y['c'] - 1.5 * A, None
        if d < 0 and H1.rsi[k1] < 45 and y['c'] < min(z['l'] for z in M15.b[k15 - 8:k15]): return -1, y['c'], y['c'] + 1.5 * A, None
    elif name == 'SAK':
        if new1 and k1 > 60:
            d = H4.bias(k4); y, p = H1.b[k1], H1.b[k1 - 1]; A1 = H1.atr[k1]; body = abs(y['c'] - y['o']); rng = y['h'] - y['l'] or 1e-9
            near = abs((y['l'] if d > 0 else y['h']) - H1.e20[k1]) <= 0.5 * A1
            if d > 0 and near and ((y['c'] > y['o'] and p['c'] < p['o'] and y['c'] >= p['o'] and y['o'] <= p['c']) or
                                   (min(y['o'], y['c']) - y['l'] >= 2 * body and y['c'] >= y['l'] + 2 / 3 * rng)):
                mem['sak'] = (1, y['h'], y['l'], k15)
            elif d < 0 and near and ((y['c'] < y['o'] and p['c'] > p['o'] and y['c'] <= p['o'] and y['o'] >= p['c']) or
                                     (y['h'] - max(y['o'], y['c']) >= 2 * body and y['c'] <= y['h'] - 2 / 3 * rng)):
                mem['sak'] = (-1, y['l'], y['h'], k15)
        z = mem.get('sak')
        if not z or not new15: return None
        sg, trig, far, kz = z
        if k15 - kz > 4: mem.pop('sak'); return None
        if k15 == kz: return None
        y = M15.b[k15]; A = M15.atr[k15]
        if (y['c'] > trig) if sg > 0 else (y['c'] < trig):
            mem.pop('sak'); stop = far - sg * 0.3 * A
            if sg * (y['c'] - stop) < A: stop = y['c'] - sg * A
            return sg, y['c'], stop, None
    elif name == 'KZ':
        if not (7 <= ld.hour < 10 or 12 <= ld.hour < 15): return None
        if new15 and k15 > 60:
            d = H1.bias(k1); y = M15.b[k15]; A = M15.atr[k15]
            if d > 0 and y['l'] <= M15.e20[k15] + 0.1 * A and y['c'] > M15.e50[k15]: mem['kz'] = (1, i)
            elif d < 0 and y['h'] >= M15.e20[k15] - 0.1 * A and y['c'] < M15.e50[k15]: mem['kz'] = (-1, i)
        z = mem.get('kz')
        if not z or not new5 or k5 < 60: return None
        sg, i0 = z
        if i - i0 > 6: mem.pop('kz'); return None
        if i == i0: return None
        y, p = M5.b[k5], M5.b[k5 - 1]
        if (y['c'] > p['h']) if sg > 0 else (y['c'] < p['l']):
            mem.pop('kz'); return sg, y['c'], default_stop(sg, y['c'], M5.b[k5 - 2:k5 + 1], M5.atr[k5]), None
    return None


def st(t):
    if not t: return dict(n=0, R=0.0, win=0, pf=0, dd=0.0, avg=0.0)
    R = [x['R'] for x in t]; w = [r for r in R if r > 0]; l = [-r for r in R if r <= 0]; eq = pk = dd = 0
    for r in R: eq += r; pk = max(pk, eq); dd = max(dd, pk - eq)
    return dict(n=len(R), R=round(sum(R), 1), win=round(100 * len(w) / len(R)), pf=round(sum(w) / sum(l), 2) if l else 99, dd=round(dd, 1), avg=round(sum(R) / len(R), 2))


NAMES = [('TPB', 'Trend pullback'), ('BRR', 'Breakout & retest'), ('LSW', 'Liquidity sweep'), ('SMC', 'Smart Money Concepts'),
         ('SND', 'Supply & demand'), ('EMA', 'EMA 9/21 crossover'), ('RNG', 'Range trading'), ('MOM', 'Momentum trading'),
         ('SAK', 'Sakata candlesticks'), ('KZ', 'London/NY kill zone')]

if __name__ == '__main__':
    final = '--final' in sys.argv; only = [a for a in sys.argv[1:] if not a.startswith('--')]
    m5 = load(); T = build(m5)
    print(f"OANDA XAU_USD 5m {m5[0]['ts']:%Y-%m-%d} to {m5[-1]['ts']:%Y-%m-%d}, {len(m5)} candles; costs ${COST}/oz + {FIN*100:.2f}%/night; " + ('FINAL YEAR INCLUDED' if final else 'development years only'))
    print(f"{'strategy':22} | {'n':>4} {'win%':>4} {'avg':>6} {'dev R':>6} {'PF':>5} {'DD':>5} | {'Y1 R':>6} {'Y2 R':>6} | {'x2 cost':>7}" + (f" | {'final R':>7} {'n':>4} {'PASS':>5}" if final else ''))
    for code, label in NAMES:
        if only and code not in only: continue
        t = run(code, m5, T); dev = [x for x in t if x['ts'] < Y2]; a = st(dev)
        y1 = st([x for x in dev if x['ts'] < Y1])['R']; y2 = st([x for x in dev if x['ts'] >= Y1])['R']
        x2 = st([x for x in run(code, m5, T, cost=2 * COST, fin=2 * FIN) if x['ts'] < Y2])['R']
        row = f"{label:22} | {a['n']:4} {a['win']:4} {a['avg']:6} {a['R']:6} {a['pf']:5} {a['dd']:5} | {y1:6} {y2:6} | {x2:7}"
        if final:
            f = st([x for x in t if x['ts'] >= Y2]); ok = y1 > 0 and y2 > 0 and x2 > 0 and f['R'] > 0
            row += f" | {f['R']:7} {f['n']:4} {'YES' if ok else 'no':>5}"
        print(row, flush=True)
