#!/usr/bin/env python3
"""Build Crown's live briefing (rules v3.1 desk) and write it to /home/user/gold-desk/crown/crown_vars.json:
  desk_brief - what Crown says first: a full spoken update (market, trend, scan, trade, account, what's next)
  desk_state - the detailed facts Crown answers follow-up questions from
The watchdog pushes both into the ElevenLabs agent (the API is not reachable from this machine)."""
import csv
import datetime as dt
import json
import os
import subprocess
import time

import requests
from zoneinfo import ZoneInfo

API = 'https://api.hyperliquid.xyz/info'
L = ZoneInfo('Europe/London')
G = '/home/user/gold-desk'
OUT = f'{G}/crown/crown_vars.json'
BALANCE_START = 194.74  # balance after the 30 Oct weekly report; live trades from the log are added to it


def post(body):
    for _ in range(3):
        try:
            r = requests.post(API, json=body, timeout=20).json()
            if r:
                return r
        except (requests.RequestException, ValueError):
            pass
        time.sleep(3)
    return None


def candles(iv, days, closed=True):
    r = post({'type': 'candleSnapshot', 'req': {'coin': 'xyz:GOLD', 'interval': iv, 'startTime': int((time.time() - days * 86400) * 1000)}}) or []
    now = time.time() * 1000
    return [dict(t=b['t'], T=b['T'], o=float(b['o']), h=float(b['h']), l=float(b['l']), c=float(b['c'])) for b in r if b['T'] < now or not closed]


def ema(x, n):
    k, o = 2 / (n + 1), [x[0]]
    for v in x[1:]:
        o.append(v * k + o[-1] * (1 - k))
    return o


def swings(b):
    hi = [b[i]['h'] for i in range(2, len(b) - 2) if b[i]['h'] == max(x['h'] for x in b[i - 2:i + 3])]
    lo = [b[i]['l'] for i in range(2, len(b) - 2) if b[i]['l'] == min(x['l'] for x in b[i - 2:i + 3])]
    return hi, lo


def say(p):
    """Price for speech: 3934.1 -> '3934'."""
    return f'{p:.0f}'


def main():
    now = dt.datetime.now(L)
    tag = now.strftime('%H:%M')
    day = now.strftime('%A %d %B')
    meta = post({'type': 'metaAndAssetCtxs', 'dex': 'xyz'})
    ctx = [x for u, x in zip(meta[0]['universe'], meta[1]) if u['name'] == 'xyz:GOLD'][0] if meta else {}
    mark = float(ctx.get('markPx', 0) or 0)
    prev = float(ctx.get('prevDayPx', 0) or 0)
    m5 = candles('5m', 2)
    m15, h1, h4, d1 = candles('15m', 5), candles('1h', 15), candles('4h', 40), candles('1d', 6, closed=False)

    facts, spoken = [], []
    if mark and prev:
        chg = mark - prev
        facts.append(f'Live gold price {mark:.1f} at {tag} London ({chg:+.1f} dollars, {100 * chg / prev:+.2f}% over 24 hours).')
        spoken.append(f'Gold is at {say(mark)}, {"up" if chg >= 0 else "down"} {abs(chg):.0f} dollars on the day.')
    if d1:
        t = d1[-1]
        facts.append(f'Today so far: high {t["h"]:.1f}, low {t["l"]:.1f}. Yesterday: high {d1[-2]["h"]:.1f}, low {d1[-2]["l"]:.1f}.')
        spoken.append(f'Today\'s range is {say(t["l"])} to {say(t["h"])}.')

    bias = 'FLAT'
    if len(h1) > 60 and len(h4) > 50 and len(m15) > 60:
        hi, lo = swings(h1)
        e50h = ema([b['c'] for b in h1], 50)[-1]
        c1 = h1[-1]['c']
        st = 'UP' if hi[-1] > hi[-2] and lo[-1] > lo[-2] else 'DN' if hi[-1] < hi[-2] and lo[-1] < lo[-2] else 'MIX'
        bias = 'UP' if c1 > e50h and st != 'DN' else 'DOWN' if c1 < e50h and st != 'UP' else 'FLAT'
        from auto_scan import bias4_now
        b4 = 'UP' if bias4_now(h4, mark) == 'UP' else 'DOWN'
        c15 = [b['c'] for b in m15]
        e20, e50 = ema(c15, 20)[-1], ema(c15, 50)[-1]
        e5 = ema([b['c'] for b in m5], 20)[-1] if len(m5) > 20 else c1
        facts.append(f'Trend: 1 hour {bias} (close {c1:.1f} vs 1 hour EMA50 {e50h:.1f}); 4 hour {b4}. 15 minute EMA20 {e20:.1f}, EMA50 {e50:.1f}; 5 minute EMA20 (the dip level) {e5:.1f}.')
        up15 = e20 > e50  # v3.5: the 15m EMAs set the side; the 1H trend must agree
        side = 'buys' if up15 else 'sells'
        gap = abs(mark - e5)
        where = 'right at the price' if gap < 1.5 else f'{gap:.0f} dollars {"below" if mark >= e5 else "above"} the price'
        agree = 'agrees' if (bias == 'UP') == up15 and bias != 'FLAT' else ('is flat' if bias == 'FLAT' else 'disagrees')
        if agree == 'agrees':
            if up15:
                spoken.append(f'The 15 minute and one hour trends are both up, but v3.9 takes sells only, so the desk stands aside until gold turns down. The 5 minute EMA20 is about {say(e5)}, {where}, and the four hour is {b4.lower()}.')
            else:
                spoken.append(f'The 15 minute and one hour trends are both down, so the desk looks for sells, on a pullback up to the 5 minute EMA20, now about {say(e5)}, {where}. The four hour is {b4.lower()}.')
        else:
            spoken.append(f'The 15 minute trend is {"up" if up15 else "down"} but the one hour trend {agree}, so the desk stands aside until they agree. The 5 minute EMA20 is about {say(e5)}, {where}, and the four hour is {b4.lower()}.')

    # H4 DI: who is in control on the 4 hour chart (same Wilder +DI/-DI/ADX as the dashboard)
    try:
        from bars_json import dmi
        d4 = dmi(h4) if len(h4) > 30 else None
    except Exception:
        d4 = None
    if d4:
        grip = {'strong': 'a strong grip', 'building': 'a grip that is building', 'weak': 'only a weak grip'}[d4['strength']]
        facts.append(f'Who is in control, 4 hour DI (14): {d4["control"]} (+DI {d4["pdi"]}, -DI {d4["mdi"]}, ADX {d4["adx"]}, {d4["strength"]}). ADX under 20 weak, 20 to 25 building, 25 and over strong.')
        fit = 'which suits the sells-only rules' if d4['control'] == 'sellers' else 'so sells are against the bigger picture'
        spoken.append(f'On the four hour chart the {d4["control"]} are in control, with {grip}: ADX {d4["adx"]:.0f}, minus DI {d4["mdi"]:.0f} against plus DI {d4["pdi"]:.0f}, {fit}.')

    # scan health and latest reason
    last = ''
    try:
        last = open(f'{G}/scan_loop.log').read().strip().splitlines()[-1]
    except (OSError, IndexError):
        pass
    mins = now.hour * 60 + now.minute
    in_session = not (now.weekday() == 5 or (now.weekday() == 6 and mins < 1380) or (now.weekday() == 4 and mins >= 1200) or 1320 <= mins < 1380 or mins < 360)
    running = subprocess.run(['bash', '/home/user/cbf-gold-desk/scan/checker_ok.sh'], capture_output=True, text=True).stdout.strip() == 'RUNNING'
    status = 'running' if running else ('not running (it is restarted within 15 minutes)' if in_session else 'off until the next session')
    facts.append(f'Scanner: 5 minute checker {status}; trading hours around the clock, Sunday 23:00 to Friday 20:00 London (daily break 22:00 to 23:00). Last scan: {last or "none yet today"}.')
    if in_session:
        spoken.append('The scanner is ' + ('watching every five minute candle.' if running else 'restarting; the watchdog brings it back within fifteen minutes.'))
        if last and 'no setup (' in last and 'outside' not in last:
            spoken.append('Latest check: ' + last.split('no setup (', 1)[1].split(');')[0].removesuffix(')') + '.')
    else:
        nxt = 'at 6 am' if mins < 360 and now.weekday() < 5 else ('at 11 pm' if (1320 <= mins < 1380 or now.weekday() == 6) else 'on Sunday at 11 pm')
        spoken.append(f'The market is closed, so no new trades; scanning resumes {nxt} London time.')

    # trades
    state = json.load(open(f'{G}/scan_state.json')) if os.path.exists(f'{G}/scan_state.json') else {}
    rows = list(csv.DictReader(open(f'{G}/live_log.csv'))) if os.path.exists(f'{G}/live_log.csv') else []
    ot = state.get('open')
    if ot:
        live = (mark - ot['entry']) * (1 if ot['side'] == 'BUY' else -1)
        facts.append(f'Open trade: {ot["side"]} at {ot["entry"]}, stop {ot["stop"]}, target {ot["target"]}, sent {ot["given"]} London; live result {live:+.2f} dollars at 0.01 lot.')
        spoken.append(f'We have an open {ot["side"].lower()} from {say(ot["entry"])}, stop {say(ot["stop"])}, target {say(ot["target"])}, currently {"up" if live >= 0 else "down"} {abs(live):.2f} dollars.')
    else:
        facts.append('Open trade: none.')
        spoken.append('No trade is open.')
    today = [r for r in rows if r['given_at_london'].startswith(now.strftime('%Y-%m-%d'))]
    pl = 0.0
    for r in rows:
        try:
            pl += float(r['result'].split()[-1]) if r['result'] and not r['result'].startswith('SKIPPED') else 0
        except ValueError:
            pass
    closed = [r for r in rows if r['result'] and not r['result'].startswith('SKIPPED')]
    facts.append(f'Setups sent today: {len(today)}' + (': ' + '; '.join(f'{r["given_at_london"][11:]} {r["side"]} {r["entry"]} SL {r["stop"]} TP {r["target"]} {r["result"] or "open"}' for r in today) if today else '') + '.')
    facts.append(f'Live log since the new rules: {len(rows)} setups, {len(closed)} closed, {pl:+.2f} dollars. Account about {BALANCE_START + pl:.2f} dollars (194.74 at the 30 Oct weekly report plus live results). Review after 20 trades.')
    spoken.append(f'{"Today the desk has sent " + str(len(today)) + " setup" + ("s" if len(today) != 1 else "") if today else "No setups have been sent today"}, and the account is about {BALANCE_START + pl:.0f} dollars.')

    # news
    try:
        n = json.load(open(f'{G}/news_today.json'))
        ev = n.get('events', []) if n.get('date') == now.strftime('%Y-%m-%d') else None
    except (OSError, ValueError):
        ev = None
    if ev is None:
        facts.append('News: today\'s calendar not loaded yet (the first watchdog of the day loads it).')
    else:
        upcoming = [e for e in ev if int(e[0][:2]) * 60 + int(e[0][3:]) >= mins - 15]
        facts.append('High-impact US news today: ' + ('; '.join(f'{t} {name}' for t, name in ev) if ev else 'none') + '. Since 6 November there is no news block: setups in the 15 minutes either side are still sent, with a news warning (wide spreads, fast spikes).')
        if upcoming:
            spoken.append(f'Next high-impact news: {upcoming[0][1]} at {upcoming[0][0]}. There is no news block now, so a setup near it comes with a news warning.')
        else:
            spoken.append('There is no more high-impact US news today.')

    facts.append('Rules v3.9 (from 10 Nov, 17:45 London): SELLS ONLY, buys are off; the 4 hour trend uses the 4 hour candle still forming; market orders only; trade Sunday 23:00 to Friday 20:00 London, with no new trades 22:00 to 23:00 and 00:00 to 06:00 (night pause); sell only when the 15 minute EMA20 is below the EMA50 and the 1 hour and 4 hour trends are both down; enter when a 5 minute candle dips to within half a 5 minute ATR of the 5 minute EMA20 and closes as a strong close, engulfing or pin bar; no chasing beyond 1.5 x 5 minute ATR from it; stop beyond the last 3 five minute candles plus 1.50 dollars and at least one 5 minute ATR away, at most 10 dollars at 0.01 lot; at least 1R of room; target 2.5R (from 13 Nov, 11:00 London; was 1.5R) or the next level if nearer; exit after 8 hours (or Friday 21:00); one trade at a time; stop for the day after 5 losses or minus 40 dollars; no news block, setups near news carry a warning. Setups go straight to Telegram as ENTER NOW.')
    facts.append('Dashboard: live price and chart, the desk scan, the open trade and account. Prices are the Hyperliquid desk feed; MT5 has been about 3 to 4 dollars lower, so use the same distances from the MT5 entry.')
    spoken.append('Ask me for any detail: levels, the rules, the account or the scanner.')

    brief = f'Crown here, Woody. Desk update at {now.strftime("%-I:%M %p").lower()} London time, {day}. ' + ' '.join(spoken)
    state_txt = f'Desk snapshot taken {day} {tag} London time (say this time; prices move after it).\n' + '\n'.join(facts)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tpl = open('/home/user/cbf-gold-desk/scan/crown_prompt.txt').read()
    json.dump({'desk_brief': brief, 'desk_state': state_txt, 'prompt': tpl.replace('__DESK_STATE__', state_txt), 'at': now.isoformat()}, open(OUT, 'w'), indent=1)
    print(brief)
    print('---')
    print(state_txt)


if __name__ == '__main__':
    main()
