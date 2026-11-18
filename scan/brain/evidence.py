#!/usr/bin/env python3
"""CrownBearer Neural Brain: evidence builder.

Replays the desk's intraday strategy engines (H1 EMA 9/21, M15 entry, 4H EMA 9/21) over 12 months of XAU/USD 15m
bars with the SAME rules the live engines use, records every setup with its market-context features (features.py)
and its result in R after costs, and saves the set the brain scores with. The daily swing engine is added from its
20-year test (per side), without intraday features.

Train 10 Nov 2025 - 31 May 2026, test 1 Jun - 16 Nov 2026 (never used to build the score).
Writes /home/user/gold-desk/brain/evidence.json and prints a calibration check on the test half.
Usage: python3 evidence.py [path to xau_15m.json]
"""
import bisect, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from features import features, ema, atr, L, FEATURES

COST = 0.40
SRC = sys.argv[1] if len(sys.argv) > 1 else '/home/user/gold-desk/research/xau_15m.json'
OUT = '/home/user/gold-desk/brain/evidence.json'
SPLIT = int(dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc).timestamp())
# Daily swing pullback, 20-year test (backtest/research_2026-11-16/results_swing.txt): R per trade by side.
SWING = {'BUY': {'n': 115, 'R': (12.4 + 18.3) / 115}, 'SELL': {'n': 54, 'R': (1.2 - 5.8) / 54}}


def load(path):
    out = []
    for k, o, h, l, c in json.load(open(path))['bars']:
        t = int(dt.datetime.fromisoformat(k).replace(tzinfo=dt.timezone.utc).timestamp())
        out.append(dict(t=t, T=t + 900, o=o, h=h, l=l, c=c))
    return out


def resample(b, sec):
    out = []; cur = None
    for x in b:
        k = x['t'] // sec * sec
        if cur is None or cur['t'] != k:
            if cur: out.append(cur)
            cur = dict(t=k, T=k + sec, o=x['o'], h=x['h'], l=x['l'], c=x['c'])
        else: cur['h'] = max(cur['h'], x['h']); cur['l'] = min(cur['l'], x['l']); cur['c'] = x['c']
    if cur: out.append(cur)
    return out


def ldn(ts): return dt.datetime.fromtimestamp(ts, dt.timezone.utc).astimezone(L)
def window_0717(ts): t = ldn(ts); return t.weekday() < 5 and 7 <= t.hour < 17
def open_mkt(ts):
    t = ldn(ts); m = t.hour * 60 + t.minute; wd = t.weekday()
    return not (wd == 5 or (wd == 6 and m < 1380) or (wd == 4 and m >= 19 * 60) or 1320 <= m < 1380)


def main():
    b15 = load(SRC); h1, h4, d1 = resample(b15, 3600), resample(b15, 14400), resample(b15, 86400)
    T1, T4, TD, T15 = [x['T'] for x in h1], [x['T'] for x in h4], [x['T'] for x in d1], [x['T'] for x in b15]
    c1 = [x['c'] for x in h1]; e9, e21, A1 = ema(c1, 9), ema(c1, 21), atr(h1)
    c4 = [x['c'] for x in h4]; f9, f21, A4 = ema(c4, 9), ema(c4, 21), atr(h4)
    c15 = [x['c'] for x in b15]; m9, m21 = ema(c15, 9), ema(c15, 21)
    done = lambda T, ts: bisect.bisect_right(T, ts)  # number of bars completed by ts

    def ctx(side, price, ts):
        return features(side, price, ts, h1[max(0, done(T1, ts) - 300):done(T1, ts)], h4[max(0, done(T4, ts) - 260):done(T4, ts)], d1[:done(TD, ts)])

    def h1_up(ts):
        j = done(T1, ts) - 1; return e9[j] > e21[j]

    def walk(i15, buy, en, sl, exit_fn, tp=None):
        """Walk 15m bars after index i15; exit_fn(ts) -> True when the strategy's own exit fires at a bar close."""
        sg = 1 if buy else -1; R = abs(en - sl); mfe = mae = 0.0; tp1 = tp2 = False
        for j in range(i15 + 1, len(b15)):
            x = b15[j]; hi, lo = (x['h'], x['l'])
            fav = (hi - en) if buy else (en - lo); adv = (en - lo) if buy else (hi - en)
            if (lo <= sl) if buy else (hi >= sl):
                mae = max(mae, R); return dict(R=round((sg * (sl - en) - COST) / R, 3), how='STOP', mfe=round(mfe / R, 2), mae=1.0, tp1=tp1, tp2=tp2, bars=j - i15)
            mfe = max(mfe, fav); mae = max(mae, adv); tp1 |= mfe >= R; tp2 |= mfe >= 2 * R
            if tp is not None and ((hi >= tp) if buy else (lo <= tp)):
                return dict(R=round((sg * (tp - en) - COST) / R, 3), how='TARGET', mfe=round(mfe / R, 2), mae=round(mae / R, 2), tp1=True, tp2=True, bars=j - i15)
            t = ldn(x['T'])
            if exit_fn(x['T']) or (t.weekday() == 4 and t.hour >= 21):
                return dict(R=round((sg * (x['c'] - en) - COST) / R, 3), how='EXIT', mfe=round(mfe / R, 2), mae=round(mae / R, 2), tp1=tp1, tp2=tp2, bars=j - i15)
        return None

    trades = []
    # H1 EMA 9/21: 1H close cross, either way, entries 07:00-17:00 London, stop 2 x 1H ATR, exit on the opposite cross.
    for i in range(30, len(h1)):
        up = e9[i] > e21[i] and e9[i - 1] <= e21[i - 1]; dn = e9[i] < e21[i] and e9[i - 1] >= e21[i - 1]
        ts = h1[i]['T']
        if not (up or dn) or not window_0717(ts) or not open_mkt(ts): continue
        buy = up; en = h1[i]['c']; sl = en - (1 if buy else -1) * 2 * A1[i]; i15 = done(T15, ts) - 1
        r = walk(i15, buy, en, sl, lambda t, b=buy: t % 3600 == 0 and (h1_up(t) != b))
        if r: f, raw = ctx('BUY' if buy else 'SELL', en, ts); trades.append(dict(strategy='H1', ts=ts, side='BUY' if buy else 'SELL', f=f, raw=raw, **r))
    # M15 entry: 15m cross in the 1H EMA9/21 direction, 07:00-17:00, stop 2 x 1H ATR, exit when the 1H state flips.
    for j in range(60, len(b15)):
        up = m9[j] > m21[j] and m9[j - 1] <= m21[j - 1]; dn = m9[j] < m21[j] and m9[j - 1] >= m21[j - 1]
        ts = b15[j]['T']
        if not (up or dn) or not window_0717(ts) or not open_mkt(ts) or done(T1, ts) < 30 or h1_up(ts) != up: continue
        buy = up; en = b15[j]['c']; sl = en - (1 if buy else -1) * 2 * A1[done(T1, ts) - 1]
        r = walk(j, buy, en, sl, lambda t, b=buy: t % 3600 == 0 and (h1_up(t) != b))
        if r: f, raw = ctx('BUY' if buy else 'SELL', en, ts); trades.append(dict(strategy='M15', ts=ts, side='BUY' if buy else 'SELL', f=f, raw=raw, **r))
    # 4H EMA 9/21: 4H close cross, any hour, stop 2 x 4H ATR, target 2R.
    for i in range(30, len(h4)):
        up = f9[i] > f21[i] and f9[i - 1] <= f21[i - 1]; dn = f9[i] < f21[i] and f9[i - 1] >= f21[i - 1]
        ts = h4[i]['T']
        if not (up or dn) or not open_mkt(ts): continue
        buy = up; en = h4[i]['c']; risk = 2 * A4[i]; sl = en - (1 if buy else -1) * risk; tp = en + (1 if buy else -1) * 2 * risk
        r = walk(done(T15, ts) - 1, buy, en, sl, lambda t: False, tp)
        if r: f, raw = ctx('BUY' if buy else 'SELL', en, ts); trades.append(dict(strategy='4H', ts=ts, side='BUY' if buy else 'SELL', f=f, raw=raw, **r))
    # ASIA range breakout (18 Nov 2026): range 23:00-04:00 London, 15m close beyond it 04:00-09:00 weekdays with the 1H EMA9/21
    # bias and the 4H EMA50/200 trend, stop 1 x 1H ATR, target 2R, out 16:00. One a day.
    g50, g200 = ema(c4, 50), ema(c4, 200)
    days = {}
    for j, x in enumerate(b15): days.setdefault(ldn(x['t']).date(), []).append(j)
    for d, idx in sorted(days.items()):
        if d.weekday() > 4: continue
        rng = [j for j in days.get(d - dt.timedelta(days=1), []) if ldn(b15[j]['t']).hour >= 23] + [j for j in idx if ldn(b15[j]['t']).hour < 4]
        if len(rng) < 12: continue
        ah, al = max(b15[j]['h'] for j in rng), min(b15[j]['l'] for j in rng)
        end_ts = int(dt.datetime.combine(d, dt.time(16), L).timestamp())
        for j in [j for j in idx if 4 <= ldn(b15[j]['t']).hour < 9]:
            x = b15[j]; ts = x['T']
            if done(T1, ts) < 30 or done(T4, ts) < 200: continue
            up = x['c'] > ah and b15[j - 1]['c'] <= ah; dn = x['c'] < al and b15[j - 1]['c'] >= al
            if not (up or dn) or h1_up(ts) != up or (g50[done(T4, ts) - 1] > g200[done(T4, ts) - 1]) != up: continue
            buy = up; en = x['c']; risk = A1[done(T1, ts) - 1]; sl = en - (1 if buy else -1) * risk; tp = en + (1 if buy else -1) * 2 * risk
            r = walk(j, buy, en, sl, lambda t, e=end_ts: t >= e, tp)
            if r: f, raw = ctx('BUY' if buy else 'SELL', en, ts); trades.append(dict(strategy='ASIA', ts=ts, side='BUY' if buy else 'SELL', f=f, raw=raw, **r))
            break
    trades.sort(key=lambda x: x['ts'])
    for t in trades: t['half'] = 'train' if t['ts'] < SPLIT else 'test'
    json.dump(dict(built=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), source=os.path.basename(SRC), split='2026-06-01',
                   swing=SWING, trades=trades), open(OUT, 'w'))
    for s in ('H1', 'M15', '4H', 'ASIA'):
        for h in ('train', 'test'):
            r = [t['R'] for t in trades if t['strategy'] == s and t['half'] == h]
            print(f'{s:4s} {h:5s} {len(r):4d} trades  {sum(r):+7.1f}R  avg {sum(r)/max(len(r),1):+.3f}R')
    print('saved', OUT, len(trades), 'setups')


if __name__ == '__main__':
    main()
