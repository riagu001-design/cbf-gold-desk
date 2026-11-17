"""CrownBearer Neural Brain: market-context features.

The same code runs live (Hyperliquid candles) and on history (backtest data), so the evidence the brain scores
with is measured exactly the way live setups are measured. Bars are dicts with o, h, l, c and T = close time in
epoch seconds; every list must hold COMPLETED bars only (nothing from the future).

Features (all categorical, so the evidence tables stay small and honest):
  h4      the proposal's direction against the H4 EMA50/EMA200 trend: with / against
  d1      against the daily EMA20/EMA50 trend: with / against
  adx4    H4 ADX(14): weak (<20) / building (20-30) / strong (30+)
  vol     1H ATR(14) against its median of the last 120 hours: low (<0.8x) / normal / high (>1.3x)
  stretch distance from the 1H EMA21 in 1H ATRs: near (<=1.5) / stretched (>1.5)  (chasing check)
  room    distance to the opposing 24-hour extreme (liquidity) in 1H ATRs: tight (<1) / open
  rsi     1H RSI(14) extreme in the trade direction (buy above 70, sell below 30): extreme / ok
  session London time of entry: asia (23-07) / london (07-13) / newyork (13-17) / late (17-22)
"""
import datetime as dt
from zoneinfo import ZoneInfo

L = ZoneInfo('Europe/London')
FEATURES = ['h4', 'd1', 'adx4', 'vol', 'stretch', 'room', 'rsi', 'session']


def ema(x, n):
    k = 2 / (n + 1); o = [x[0]]
    for v in x[1:]: o.append(v * k + o[-1] * (1 - k))
    return o


def atr(b, n=14):
    tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
    o = [None] * len(b)
    if len(b) < n: return o
    a = sum(tr[:n]) / n; o[n - 1] = a
    for i in range(n, len(b)): a = (a * (n - 1) + tr[i]) / n; o[i] = a
    return o


def adx(b, n=14):
    if len(b) < 2 * n + 2: return None
    pdm, mdm, tr = [], [], []
    for p, x in zip(b, b[1:]):
        up, dn = x['h'] - p['h'], p['l'] - x['l']
        pdm.append(up if up > dn and up > 0 else 0); mdm.append(dn if dn > up and dn > 0 else 0)
        tr.append(max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])))
    sp, sm, st = sum(pdm[:n]), sum(mdm[:n]), sum(tr[:n]); dx = []
    for i in range(n, len(tr)):
        sp, sm, st = sp - sp / n + pdm[i], sm - sm / n + mdm[i], st - st / n + tr[i]
        pdi, mdi = 100 * sp / st if st else 0, 100 * sm / st if st else 0
        dx.append(100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0)
    a = sum(dx[:n]) / n
    for v in dx[n:]: a = (a * (n - 1) + v) / n
    return a


def rsi(c, n=14):
    if len(c) < n + 1: return 50
    g = l = 0
    for p, x in zip(c[:n], c[1:n + 1]): d = x - p; g += max(d, 0); l += max(-d, 0)
    g /= n; l /= n
    for p, x in zip(c[n:], c[n + 1:]): d = x - p; g = (g * (n - 1) + max(d, 0)) / n; l = (l * (n - 1) + max(-d, 0)) / n
    return 100 - 100 / (1 + g / l) if l else 100


def session(ts):
    h = dt.datetime.fromtimestamp(ts, dt.timezone.utc).astimezone(L).hour
    return 'london' if 7 <= h < 13 else 'newyork' if 13 <= h < 17 else 'late' if 17 <= h < 22 else 'asia'


def features(side, price, ts, h1, h4, d1):
    """side 'BUY'/'SELL'; h1/h4/d1 completed bars up to ts. Returns (feature dict, raw numbers dict)."""
    buy = side == 'BUY'; f, raw = {}, {}
    c4 = [x['c'] for x in h4]
    if len(c4) >= 200:
        up4 = ema(c4, 50)[-1] > ema(c4, 200)[-1]; f['h4'] = 'with' if up4 == buy else 'against'
    else: f['h4'] = 'unknown'
    cd = [x['c'] for x in d1]
    if len(cd) >= 50:
        upd = ema(cd, 20)[-1] > ema(cd, 50)[-1]; f['d1'] = 'with' if upd == buy else 'against'
    else: f['d1'] = 'unknown'
    a4 = adx(h4[-120:]); raw['adx4'] = round(a4, 1) if a4 is not None else None
    f['adx4'] = 'unknown' if a4 is None else 'weak' if a4 < 20 else 'building' if a4 < 30 else 'strong'
    A = atr(h1[-150:]); a1 = A[-1]; hist = sorted(v for v in A[-120:] if v); med = hist[len(hist) // 2] if hist else a1
    raw['atr1h'] = round(a1, 2); ratio = a1 / med if med else 1; raw['vol_ratio'] = round(ratio, 2)
    f['vol'] = 'low' if ratio < 0.8 else 'high' if ratio > 1.3 else 'normal'
    c1 = [x['c'] for x in h1]; e21 = ema(c1[-200:], 21)[-1]; s = abs(price - e21) / a1 if a1 else 0
    raw['stretch_atr'] = round(s, 2); f['stretch'] = 'stretched' if s > 1.5 else 'near'
    last = h1[-24:]; ext = max(x['h'] for x in last) - price if buy else price - min(x['l'] for x in last)
    room = ext / a1 if a1 else 9; raw['room_atr'] = round(room, 2); f['room'] = 'tight' if room < 1 else 'open'
    r = rsi(c1[-200:]); raw['rsi1h'] = round(r, 1)
    f['rsi'] = 'extreme' if (buy and r > 70) or (not buy and r < 30) else 'ok'
    f['session'] = session(ts)
    return f, raw
