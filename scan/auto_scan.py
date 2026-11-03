#!/usr/bin/env python3
"""Automatic XAUUSD scan for XAUUSD_RULES.md v3 (market orders only).

Run just after each 15m candle closes. Prints one summary line. When a setup fires it writes
/home/user/gold-desk/scan_msg.txt (the Telegram text) and logs the trade in live_log.csv.
It also follows the open logged trade on 15m candles (stop, target, 8h / 21:00 time exit) so it
can enforce one trade at a time and the daily limits (2 losses or -$20).
Data: Hyperliquid xyz:GOLD (desk feed). Never places orders.
"""
import csv
import datetime as dt
import json
import os
import time

import requests
from zoneinfo import ZoneInfo

API = 'https://api.hyperliquid.xyz/info'
L = ZoneInfo('Europe/London')
DESK = '/home/user/gold-desk'
LOG = f'{DESK}/live_log.csv'
STATE = f'{DESK}/scan_state.json'
MSG = f'{DESK}/scan_msg.txt'
FIELDS = ['given_at_london', 'side', 'entry', 'stop', 'target', 'reason', 'result']
MAX_STOP, DAY_LOSS = 10.0, -20.0


def candles(iv, days):
    for attempt in range(3):  # the API sometimes returns null; retry
        try:
            r = requests.post(API, json={'type': 'candleSnapshot', 'req': {'coin': 'xyz:GOLD', 'interval': iv,
                              'startTime': int((time.time() - days * 86400) * 1000)}}, timeout=20).json()
        except (requests.RequestException, ValueError):
            r = None
        if r:
            break
        time.sleep(3)
    if not r:
        raise SystemExit(f'price feed returned no {iv} candles; scan skipped')
    now = time.time() * 1000
    return [dict(t=b['t'], T=b['T'], o=float(b['o']), h=float(b['h']), l=float(b['l']), c=float(b['c'])) for b in r if b['T'] < now]


def ema(x, n):
    k, o = 2 / (n + 1), [x[0]]
    for v in x[1:]:
        o.append(v * k + o[-1] * (1 - k))
    return o


def atr(b, n=14):
    tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
    a = sum(tr[:n]) / n
    for v in tr[n:]:
        a = (a * (n - 1) + v) / n
    return a


def swings(b):
    hi = [b[i]['h'] for i in range(2, len(b) - 2) if b[i]['h'] == max(x['h'] for x in b[i - 2:i + 3])]
    lo = [b[i]['l'] for i in range(2, len(b) - 2) if b[i]['l'] == min(x['l'] for x in b[i - 2:i + 3])]
    return hi, lo


def ldn(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).astimezone(L)


def read_log():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f:
            csv.writer(f).writerow(FIELDS)
    with open(LOG, newline='') as f:
        return list(csv.DictReader(f))


def write_log(rows):
    with open(LOG, 'w', newline='') as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)


def resolve_open(rows, state, m15):
    """Follow the open auto trade on closed 15m candles; fill its result."""
    ot = state.get('open')
    if not ot:
        return None
    buy, sg = ot['side'] == 'BUY', 1 if ot['side'] == 'BUY' else -1
    res = None
    for x in m15:
        if x['t'] < ot['bar_close_ms']:
            continue
        hit_sl = x['l'] <= ot['stop'] if buy else x['h'] >= ot['stop']
        hit_tp = x['h'] >= ot['target'] if buy else x['l'] <= ot['target']
        xt = ldn(x['T'] + 1)
        if hit_sl:
            res = ('SL', sg * (ot['stop'] - ot['entry']))
        elif hit_tp:
            res = ('TP', sg * (ot['target'] - ot['entry']))
        elif x['T'] + 1 - ot['bar_close_ms'] >= 8 * 3600e3 or (xt.hour >= 21):
            res = ('TIME', sg * (x['c'] - ot['entry']))
        if res:
            break
    if not res:
        return f"open {ot['side']} {ot['entry']} SL {ot['stop']} TP {ot['target']}"
    kind, pl = res
    for r in rows:
        if r['given_at_london'] == ot['given'] and not r['result']:
            r['result'] = f'{kind} {pl:+.2f}'
    state['open'] = None
    day = ot['given'][:10]
    d = state.setdefault('days', {}).setdefault(day, {'pl': 0.0, 'losses': 0})
    d['pl'] = round(d['pl'] + pl, 2)
    d['losses'] += 1 if pl < 0 else 0
    return f"closed {ot['side']} {kind} {pl:+.2f}"


def main():
    os.makedirs(DESK, exist_ok=True)
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    rows = read_log()
    if os.path.exists(MSG):
        os.remove(MSG)
    m15, h1, h4, d1 = candles('15m', 5), candles('1h', 15), candles('4h', 40), candles('1d', 6)
    meta = None
    for attempt in range(3):  # the API sometimes returns null; retry
        try:
            meta = requests.post(API, json={'type': 'metaAndAssetCtxs', 'dex': 'xyz'}, timeout=20).json()
        except (requests.RequestException, ValueError):
            meta = None
        if meta:
            break
        time.sleep(3)
    if not meta:
        raise SystemExit('price feed returned no mark price; scan skipped')
    mark = [float(x['markPx']) for u, x in zip(meta[0]['universe'], meta[1]) if u['name'] == 'xyz:GOLD'][0]
    now = dt.datetime.now(L)
    tag = now.strftime('%H:%M')
    trade_note = resolve_open(rows, state, m15)
    write_log(rows)

    def done(why):
        json.dump(state, open(STATE, 'w'), indent=1)
        print(f'{tag} London, gold {mark}: no setup ({why})' + (f'; {trade_note}' if trade_note else ''))

    mins = now.hour * 60 + now.minute
    force = os.environ.get('SCAN_TEST') == '1'  # test only: ignore hours and candle age
    if not force and (now.weekday() >= 5 or not (420 <= mins <= 632 or 780 <= mins <= 992) or (now.weekday() == 4 and mins >= 19 * 60)):
        return done('outside 07:00-10:30 / 13:00-16:30 London')
    if state.get('open'):
        return done('a trade is already open')
    d = state.get('days', {}).get(now.strftime('%Y-%m-%d'), {'pl': 0, 'losses': 0})
    if d['losses'] >= 2 or d['pl'] <= DAY_LOSS:
        return done(f"daily limit hit ({d['losses']} losses, {d['pl']:+.2f})")

    bar, pv = m15[-1], m15[-2]
    if not force and state.get('last_bar') == bar['t']:
        return done('candle already checked')
    state['last_bar'] = bar['t']
    if not force and (time.time() * 1000 - bar['T']) > 6 * 60e3:
        return done('signal candle closed over 6 min ago')

    hi, lo = swings(h1)
    e50h, c1 = ema([b['c'] for b in h1], 50)[-1], h1[-1]['c']
    st = 'UP' if hi[-1] > hi[-2] and lo[-1] > lo[-2] else 'DN' if hi[-1] < hi[-2] and lo[-1] < lo[-2] else 'MIX'
    bias = 'UP' if c1 > e50h and st != 'DN' else 'DN' if c1 < e50h and st != 'UP' else 'FLAT'
    if bias == 'FLAT':
        return done('1H trend flat')
    bias4 = 'UP' if h4[-1]['c'] > ema([b['c'] for b in h4], 50)[-1] else 'DN'
    c15 = [b['c'] for b in m15]
    e20, e50, A = ema(c15, 20)[-1], ema(c15, 50)[-1], atr(m15)
    buy = bias == 'UP'
    sg = 1 if buy else -1
    if not (e20 > e50 if buy else e20 < e50):
        return done(f'1H {bias} but 15m EMAs not aligned')
    rng = bar['h'] - bar['l'] or 1e-9
    pos = (bar['c'] - bar['l']) / rng
    body, pbody = abs(bar['c'] - bar['o']), abs(pv['c'] - pv['o'])
    zlo, zhi = min(e20, e50) - 0.25 * A, max(e20, e50) + 0.25 * A
    pdh, pdl = d1[-2]['h'], d1[-2]['l']
    base = round(mark / 25) * 25
    lv = [pdh, pdl] + hi[-4:] + lo[-4:] + [base + k * 25 for k in (-2, -1, 0, 1, 2)]
    ztouch = bar['l'] <= zhi if buy else bar['h'] >= zlo
    ltouch = any((abs(bar['l'] - x) <= 0.25 * A and bar['c'] > x) if buy else (abs(bar['h'] - x) <= 0.25 * A and bar['c'] < x) for x in lv)
    strong = (bar['c'] > e20 and bar['c'] > bar['o'] and pos >= 2 / 3) if buy else (bar['c'] < e20 and bar['c'] < bar['o'] and pos <= 1 / 3)
    eng = (bar['c'] > bar['o'] and pv['c'] < pv['o'] and bar['c'] >= pv['o'] and bar['o'] <= pv['c'] and body > pbody) if buy else \
          (bar['c'] < bar['o'] and pv['c'] > pv['o'] and bar['c'] <= pv['c'] and bar['o'] >= pv['o'] and body > pbody)
    wick = (min(bar['o'], bar['c']) - bar['l']) if buy else (bar['h'] - max(bar['o'], bar['c']))
    pin = wick >= 2 * max(body, 1e-9) and wick >= 0.5 * rng and (pos >= 0.6 if buy else pos <= 0.4)
    beyond = bar['c'] > e20 if buy else bar['c'] < e20
    if not (ztouch or ltouch):
        return done(f'1H {bias}, no pullback into the 15m EMA zone {zlo:.1f}-{zhi:.1f}')
    trig = 'strong close' if strong else 'engulfing' if beyond and eng else 'pin bar' if beyond and pin else None
    if not trig:
        return done(f'1H {bias}, pullback but no trigger candle')
    entry = mark
    if abs(entry - e20) > 1.5 * A:
        return done(f'stretched {abs(entry - e20):.1f} from EMA20 (max {1.5 * A:.1f})')
    if rng > 2 * A:
        return done(f'signal candle too big ({rng:.1f} > {2 * A:.1f})')
    ext = min(b['l'] for b in m15[-3:]) if buy else max(b['h'] for b in m15[-3:])
    stop = ext - sg * 1.5
    if sg * (entry - stop) < 0.5 * A:
        stop = entry - sg * 0.5 * A
    R = abs(entry - stop)
    if sg * (entry - stop) <= 0:
        return done('price already through the stop level')
    if R > MAX_STOP:
        return done(f'stop ${R:.2f} over the $10 cap')
    opp = [x for x in lv if x > entry + 0.1] if buy else [x for x in lv if x < entry - 0.1]
    nxt = (min(opp) if buy else max(opp)) if opp else None
    roomR = abs(nxt - entry) / R if nxt else 9
    if roomR < 1:
        return done(f'only {roomR:.2f}R of room to {nxt:.1f}')
    cap = 2 if bias4 == bias else 1.5
    tp = entry + sg * R * min(cap, roomR)
    skip = entry + sg * 0.3 * R
    side = 'BUY' if buy else 'SELL'
    entry, stop, tp, skip = (round(v, 1) for v in (entry, stop, tp, skip))
    reward = abs(tp - entry)
    given = now.strftime('%Y-%m-%d %H:%M')
    reason = f'1H {bias.replace("DN", "DOWN")}, 15m pullback to EMA zone, {trig} on the {ldn(bar["t"]).strftime("%H:%M")} candle'
    msg = (f'GOLD {side} NOW (market order)\n'
           f'Entry: {entry} (market, live price {now.strftime("%H:%M")} London)\n'
           f'Stop loss: {stop} (${R:.2f} risk at 0.01 lot)\n'
           f'Take profit: {tp} (+${reward:.2f}, {reward / R:.1f}R)\n'
           f'Skip if price is already {"above" if buy else "below"} {skip}\n'
           f'Why: {reason}. 4H {"with" if bias4 == bias else "against, target capped at 1.5R"}.\n'
           f'Exit by {min(now + dt.timedelta(hours=8), now.replace(hour=21, minute=0)).strftime("%H:%M")} London if neither is hit. '
           f'Prices are the desk feed; if MT5 differs, keep the same distances from your MT5 entry.')
    open(MSG, 'w').write(msg)
    rows.append(dict(given_at_london=given, side=side, entry=entry, stop=stop, target=tp, reason=reason, result=''))
    write_log(rows)
    state['open'] = dict(given=given, side=side, entry=entry, stop=stop, target=tp, bar_close_ms=bar['T'] + 1)
    json.dump(state, open(STATE, 'w'), indent=1)
    print(f'{tag} London, gold {mark}: SETUP {side} {entry} SL {stop} TP {tp} ({trig})' + (f'; {trade_note}' if trade_note else ''))


if __name__ == '__main__':
    main()
