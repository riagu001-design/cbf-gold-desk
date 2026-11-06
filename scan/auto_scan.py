#!/usr/bin/env python3
"""Automatic XAUUSD scan for XAUUSD_RULES.md v3.1 (market orders only, 5m entry trigger).

Run just after each 5m candle closes (scan/loop.sh). Prints one summary line. When a setup fires it writes
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
RES = f'{DESK}/scan_result.txt'  # trade results the checker could not send itself (sent by the session, see SEND.md)
BALANCE_START = 194.74  # balance after the 30 Oct weekly report
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


NEWS = f'{DESK}/news_today.json'
TG_ENV = '/root/.claude/channels/telegram/.env'
TG_CHAT = '1192966973'


def news_block(now):
    """Return (blocked, note). news_today.json = {"date": "YYYY-MM-DD", "events": [["HH:MM", "name"], ...]} in London time."""
    try:
        n = json.load(open(NEWS))
    except (OSError, ValueError):
        return False, 'News calendar not checked'
    if n.get('date') != now.strftime('%Y-%m-%d'):
        return False, 'News calendar not checked'
    for hm, name in n.get('events', []):
        h, m = map(int, hm.split(':'))
        if abs((now.hour * 60 + now.minute) - (h * 60 + m)) <= 15:
            return True, f'{name} at {hm}'
    return False, None


def send_telegram(text):
    """Send directly to the trader's Telegram. Returns 'ok <id>' or 'FAILED <why>'. Never prints the token."""
    try:
        token = [l.split('=', 1)[1].strip() for l in open(TG_ENV) if l.startswith('TELEGRAM_BOT_TOKEN=')][0]
        r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', data={'chat_id': TG_CHAT, 'text': text}, timeout=15).json()
        return f"ok {r['result']['message_id']}" if r.get('ok') else f"FAILED {r.get('description')}"
    except Exception as e:  # blocked host, no token file, timeout
        return f'FAILED {type(e).__name__}'


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


def resolve_open(rows, state, bars):
    """Follow the open auto trade on closed 5m candles; fill its result."""
    ot = state.get('open')
    if not ot:
        return None
    buy, sg = ot['side'] == 'BUY', 1 if ot['side'] == 'BUY' else -1
    res = None
    for x in bars:
        if x['t'] < ot['bar_close_ms']:
            continue
        hit_sl = x['l'] <= ot['stop'] if buy else x['h'] >= ot['stop']
        hit_tp = x['h'] >= ot['target'] if buy else x['l'] <= ot['target']
        xt = ldn(x['T'] + 1)
        if hit_sl:
            res = ('SL', sg * (ot['stop'] - ot['entry']), ot['stop'])
        elif hit_tp:
            res = ('TP', sg * (ot['target'] - ot['entry']), ot['target'])
        elif x['T'] + 1 - ot['bar_close_ms'] >= 8 * 3600e3 or (xt.hour >= 21):
            res = ('TIME', sg * (x['c'] - ot['entry']), x['c'])
        if res:
            break
    if not res:
        return f"open {ot['side']} {ot['entry']} SL {ot['stop']} TP {ot['target']}"
    kind, pl, exit_px = res
    for r in rows:
        if r['given_at_london'] == ot['given'] and not r['result']:
            r['result'] = f'{kind} {pl:+.2f}'
    state['open'] = None
    day = ot['given'][:10]
    d = state.setdefault('days', {}).setdefault(day, {'pl': 0.0, 'losses': 0})
    d['pl'] = round(d['pl'] + pl, 2)
    d['losses'] += 1 if pl < 0 else 0
    send_result(rows, ot, kind, pl, exit_px, xt, d)
    return f"closed {ot['side']} {kind} {pl:+.2f}"


LINE = '━━━━━━━━━━━━━━━━'


def setup_message(side, entry, stop, tp, skip, R, reward, at, exit_by, why, with4h, with1h=True, bias1='UP'):
    """The Telegram setup message: what to do, the three prices, when not to enter, and why."""
    buy = side == 'BUY'
    return '\n'.join([
        f'🚨 GOLD (XAUUSD) · {side} NOW {"🟢" if buy else "🔴"}',
        'Market order at the live price',
        LINE,
        f'📍 Entry: {entry:.1f}',
        f'🛑 Stop loss: {stop:.1f} (−${R:.2f})',
        f'🎯 Take profit: {tp:.1f} (+${reward:.2f})',
        f'⚖️ Risk : reward 1 : {reward / R:.1f} · lot 0.01',
        LINE,
        f'⛔ Do not enter if price is already {"above" if buy else "below"} {skip:.1f}',
        f'⏰ Close it at {exit_by} London if neither is hit',
        '📊 Why: ' + ' · '.join(why),
        ('✅ 1H trend agrees' if with1h else f'⚠️ 1H trend is {"flat" if bias1 == "FLAT" else ("down" if buy else "up")}: direction from the 15m trend only'),
        ('✅ 4H trend agrees' if with4h else f'⚠️ 4H trend is {"down" if buy else "up"}: this trade is against it'),
        LINE,
        'ℹ️ Desk prices (Hyperliquid). If MT5 differs, keep the same distances from your MT5 entry.',
        f'🕐 Signal {at} London',
    ])


def send_result(rows, ot, kind, pl, exit_px, xt, day):
    """Tell the trader on Telegram that the trade closed; if the direct send fails, queue it in RES for the session."""
    head = {'TP': 'TARGET HIT', 'SL': 'STOP HIT', 'TIME': 'TIME EXIT (8 hours or 21:00)'}[kind]
    risk = abs(ot['entry'] - ot['stop']) or 1
    total = 0.0
    for r in rows:
        try:
            total += float(r['result'].split()[-1]) if r['result'] and not r['result'].startswith('SKIPPED') else 0
        except ValueError:
            pass
    icon, sicon = {'TP': '✅', 'SL': '❌', 'TIME': '⏱'}[kind], '🟢' if ot['side'] == 'BUY' else '🔴'
    msg = '\n'.join([
        f'{icon} GOLD TRADE CLOSED · {head}',
        LINE,
        f'{sicon} {ot["side"]} from {ot["entry"]} (sent {ot["given"][11:16]} London)',
        f'🏁 Exit: {exit_px:.1f} at {xt.strftime("%H:%M")} London',
        f'💰 Result: {"+" if pl >= 0 else "−"}${abs(pl):.2f} ({pl / risk:+.1f}R) at 0.01 lot',
        LINE,
        f'📅 Today: {"+" if day["pl"] >= 0 else "−"}${abs(day["pl"]):.2f} · {day["losses"]} loss{"es" if day["losses"] != 1 else ""}',
        f'💼 Account: about ${BALANCE_START + total:.2f}',
    ] + (['⚠️ Close it in MT5 now if it is still open.'] if kind == 'TIME' else []))
    if os.environ.get('SCAN_TEST') == '1':
        print('RESULT MESSAGE (test, not sent):\n' + msg)
        return
    sent = send_telegram(msg)
    if not sent.startswith('ok'):
        with open(RES, 'a') as f:
            f.write(msg + '\n\n')


def main():
    os.makedirs(DESK, exist_ok=True)
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    rows = read_log()
    if os.path.exists(MSG):
        print('a setup message is still waiting to be sent; scan skipped')
        return
    m5, m15, h1, h4, d1 = candles('5m', 2), candles('15m', 5), candles('1h', 15), candles('4h', 40), candles('1d', 6)
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
    trade_note = resolve_open(rows, state, m5)
    write_log(rows)

    def done(why):
        json.dump(state, open(STATE, 'w'), indent=1)
        print(f'{tag} London, gold {mark}: no setup ({why})' + (f'; {trade_note}' if trade_note else ''))

    mins = now.hour * 60 + now.minute
    force = os.environ.get('SCAN_TEST') == '1'  # test only: ignore hours and candle age
    if not force and (now.weekday() >= 5 or not (420 <= mins <= 992) or (now.weekday() == 4 and mins >= 19 * 60)):
        return done('outside 07:00-16:30 London')
    if state.get('open'):
        return done('a trade is already open')
    d = state.get('days', {}).get(now.strftime('%Y-%m-%d'), {'pl': 0, 'losses': 0})
    if d['losses'] >= 2 or d['pl'] <= DAY_LOSS:
        return done(f"daily limit hit ({d['losses']} losses, {d['pl']:+.2f})")

    # v3.1 (3 Nov, trader's yes): 1H trend and 15m EMA zone decide direction and place; the 5m candle is the trigger
    bar, pv = m5[-1], m5[-2]
    A5 = atr(m5)
    if not force and state.get('last_bar') == bar['t']:
        return done('candle already checked')
    state['last_bar'] = bar['t']
    if not force and (time.time() * 1000 - bar['T']) > 4 * 60e3:
        return done('signal candle closed over 4 min ago')

    hi, lo = swings(h1)
    e50h, c1 = ema([b['c'] for b in h1], 50)[-1], h1[-1]['c']
    st = 'UP' if hi[-1] > hi[-2] and lo[-1] > lo[-2] else 'DN' if hi[-1] < hi[-2] and lo[-1] < lo[-2] else 'MIX'
    bias1 = 'UP' if c1 > e50h and st != 'DN' else 'DN' if c1 < e50h and st != 'UP' else 'FLAT'  # v3.4: shown, no longer a block
    bias4 = 'UP' if h4[-1]['c'] > ema([b['c'] for b in h4], 50)[-1] else 'DN'
    c15 = [b['c'] for b in m15]
    e20, e50, A = ema(c15, 20)[-1], ema(c15, 50)[-1], atr(m15)
    # v3.4 (6 Nov, trader's call): the 15m EMA20 vs EMA50 alone sets the side; the 1H trend no longer blocks a trade.
    if abs(e20 - e50) < 0.05:
        return done('15m EMAs level, no direction')
    buy = e20 > e50
    bias = 'UP' if buy else 'DN'
    sg = 1 if buy else -1
    rng = bar['h'] - bar['l'] or 1e-9
    pos = (bar['c'] - bar['l']) / rng
    body, pbody = abs(bar['c'] - bar['o']), abs(pv['c'] - pv['o'])
    # v3.2 (4 Nov, trader's yes): trend-day dip. The 1H trend and the 15m EMAs set the side; the closed 5m candle must dip
    # to the 5m EMA20 (+-0.25 x 5m ATR), with the 5m EMA20 on the trend side of its EMA50, and close as the trigger.
    # Backtest 13 Oct-4 Nov (sessions): 19 trades, 63% wins, +$88.75, PF 3.17, both halves positive (backtest/bt_more.py 'dip').
    c5 = [b['c'] for b in m5]
    E5, E5b = ema(c5, 20)[-1], ema(c5, 50)[-1]
    # v3.3 (5 Nov, trader's yes to looser rules): the 5m EMA20/50 rule is dropped, the dip may come within 0.5 x 5m ATR,
    # and the desk trades 07:00-16:30 straight. Backtest 13 Oct-5 Nov: 39 trades (2.2/day), 56% wins, +$123, PF 2.29,
    # halves +40/+83, vs v3.2 22 trades +$66 PF 2.02 (/home/user/gold-desk/bt5/bt_loose.py 'A+B+D').
    pdh, pdl = d1[-1]['h'], d1[-1]['l']  # candles() drops the forming day, so [-1] is yesterday
    lv = [pdh, pdl] + hi[-4:] + lo[-4:]
    touch = bar['l'] <= E5 + 0.5 * A5 if buy else bar['h'] >= E5 - 0.5 * A5
    strong = (bar['c'] > E5 and bar['c'] > bar['o'] and pos >= 2 / 3) if buy else (bar['c'] < E5 and bar['c'] < bar['o'] and pos <= 1 / 3)
    eng = (bar['c'] > bar['o'] and pv['c'] < pv['o'] and bar['c'] >= pv['o'] and bar['o'] <= pv['c'] and body > pbody) if buy else \
          (bar['c'] < bar['o'] and pv['c'] > pv['o'] and bar['c'] <= pv['c'] and bar['o'] >= pv['o'] and body > pbody)
    wick = (min(bar['o'], bar['c']) - bar['l']) if buy else (bar['h'] - max(bar['o'], bar['c']))
    pin = wick >= 2 * max(body, 1e-9) and wick >= 0.5 * rng and (pos >= 0.6 if buy else pos <= 0.4)
    beyond = bar['c'] > E5 if buy else bar['c'] < E5
    if not touch:
        return done(f'15m {bias}, no dip to the 5m EMA20 ({E5:.1f})')
    # Same trades as before; the label names the Homma candle when there is one (trader, 6 Nov).
    trig = ('engulfing' if beyond and eng else 'pin bar' if beyond and pin else 'strong close' if strong else None)
    homma = {'engulfing': f'Homma: {"bullish" if buy else "bearish"} engulfing (tsutsumi)', 'pin bar': 'Homma: hammer (takuri)' if buy else 'Homma: shooting star (nagare boshi)',
             'strong close': f'strong {"bullish" if buy else "bearish"} close (not a Homma pattern)'}.get(trig)
    if not trig:
        return done(f'15m {bias}, dip to the 5m EMA20 but no trigger candle')
    entry = mark
    if abs(entry - E5) > 1.5 * A5:
        return done(f'stretched {abs(entry - E5):.1f} from the 5m EMA20 (max {1.5 * A5:.1f})')
    if rng > 2 * A5:
        return done(f'signal candle too big ({rng:.1f} > {2 * A5:.1f})')
    ext = min(b['l'] for b in m5[-3:]) if buy else max(b['h'] for b in m5[-3:])
    stop = ext - sg * 1.5
    if sg * (entry - stop) < 0.5 * A5:
        stop = entry - sg * 0.5 * A5
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
    cap = 2  # v3.2: the dip backtest used 2R or the next level, with no 4H cap
    tp = entry + sg * R * min(cap, roomR)
    skip = entry + sg * 0.3 * R
    side = 'BUY' if buy else 'SELL'
    entry, stop, tp, skip = (round(v, 1) for v in (entry, stop, tp, skip))
    reward = abs(tp - entry)
    given = now.strftime('%Y-%m-%d %H:%M')
    reason = f'15m {bias.replace("DN", "DOWN")} (1H {bias1.replace("DN", "DOWN").lower()}), 5m dip to the EMA20, {trig} on the {ldn(bar["t"]).strftime("%H:%M")} candle'
    exit_by = min(now + dt.timedelta(hours=8), now.replace(hour=21, minute=0)).strftime('%H:%M')
    why = [f'15m trend {"up" if buy else "down"}', f'5m {"dip" if buy else "pullback"} to the EMA20', f'{homma} on the {ldn(bar["t"]).strftime("%H:%M")} candle']
    msg = setup_message(side, entry, stop, tp, skip, R, reward, now.strftime('%H:%M'), exit_by, why, bias4 == bias, bias1 == bias, bias1)
    blocked, note = news_block(now)
    if blocked:
        return done(f'setup skipped: high-impact news ({note})')
    if note:
        msg = msg.replace(LINE + '\nℹ️', f'📰 {note}\n' + LINE + '\nℹ️', 1)
    sent = send_telegram(msg)
    if not sent.startswith('ok'):
        open(MSG, 'w').write(msg)  # loop.sh exits and wakes the session, which sends it another way
    rows.append(dict(given_at_london=given, side=side, entry=entry, stop=stop, target=tp, reason=reason, result=''))
    write_log(rows)
    state['open'] = dict(given=given, side=side, entry=entry, stop=stop, target=tp, bar_close_ms=bar['T'] + 1)
    json.dump(state, open(STATE, 'w'), indent=1)
    print(f'{tag} London, gold {mark}: SETUP {side} {entry} SL {stop} TP {tp} ({trig}); Telegram {sent}' + (f'; {trade_note}' if trade_note else ''))


if __name__ == '__main__':
    main()
