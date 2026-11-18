#!/usr/bin/env python3
"""Daily MARKET UPDATES to Telegram (Woody 18 Nov 2026: no more days of silence). These are information, not trades.
Sent through the brain's one channel (brain/publisher.py), weekdays only, at most once per slot:
  04:00  Asia range set (high / low for the Asia breakout engine)
  07:45  London open plan     12:45  New York open plan
  any time 04:00-21:00: Market flip (SELL / BUY / WAIT changed and held for two checks, at most one flip message an hour)
Market = SELL when the 4H EMA50/200 trend is down AND sellers lead the DI on most of H4/H1/M15; BUY mirrored; else WAIT
(the same rule as the dashboard's Market box). Run every 5 minutes by loop.sh; prints one line."""
import datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'brain'))
from auto_scan import candles, ema, ldn, L
from bars_json import dmi
import publisher
G = '/home/user/gold-desk'; ST = f'{G}/updates_state.json'
SLOTS = [('asia', 4 * 60, 'ASIA RANGE SET'), ('ldn', 7 * 60 + 45, 'LONDON OPEN PLAN'), ('ny', 12 * 60 + 45, 'NEW YORK OPEN PLAN')]
FOOT = 'ℹ️ Market update only, not a trade. Trade setups come as 🟢 A-grade or 🟡 B-grade signals.'


def market():
    now_ms = dt.datetime.now(L).timestamp() * 1000
    done = lambda iv, days: [x for x in candles(iv, days) if x['T'] < now_ms]
    h4, h1, m15 = done('4h', 60), done('1h', 8), done('15m', 3)
    c4 = [x['c'] for x in h4]; down = ema(c4, 50)[-1] < ema(c4, 200)[-1]
    d = {k: dmi(v) for k, v in (('H4', h4), ('H1', h1), ('M15', m15))}
    sel = sum(1 for x in d.values() if x and x['control'] == 'sellers'); n = sum(1 for x in d.values() if x)
    m = 'SELL' if down and sel * 2 > n else 'BUY' if not down and (n - sel) * 2 > n else 'WAIT'
    di = ' · '.join(f"{k} {x['control']} (ADX {x['adx']:.0f})" for k, x in d.items() if x)
    return m, f"4H trend {'down' if down else 'up'} · {di}", m15[-1]['c'], m15


def asia_range(m15, day):
    start = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(23), L); end = dt.datetime.combine(day, dt.time(4), L)
    r = [x for x in m15 if start <= ldn(x['t']) < end]
    return (max(x['h'] for x in r), min(x['l'] for x in r)) if len(r) >= 12 else (None, None)


def brain_now():
    try:
        st = json.load(open(f'{G}/brain/status.json')); n = st.get('now', {})
        top = sorted(n.get('scores', []), key=lambda r: -r['score'])[:3]
        lab = lambda s: '🟢 A' if s >= 85 else '🟡 B' if s >= 75 else '⚪ no signal'
        return [f"{r['side']} {r['strategy']} {r['score']} ({lab(r['score'])})" for r in top]
    except (OSError, ValueError):
        return []


def news_line(now):
    try:
        n = json.load(open(f'{G}/news_today.json'))
        ev = [f'{t} {name}' for t, name in n.get('events', [])] if n.get('date') == now.strftime('%Y-%m-%d') else []
        later = [e for e in ev if e[:5] > now.strftime('%H:%M')]
        return '📰 News today: ' + ('; '.join(later) + ' London (no entries 5 min either side)' if later else 'no more high-impact US news')
    except (OSError, ValueError):
        return '📰 News: calendar not checked'


def main():
    now = dt.datetime.now(L); mins = now.hour * 60 + now.minute; tag = now.strftime('%H:%M'); today = str(now.date())
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    if st.get('day') != today: st.update(day=today, sent=[])
    say = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London: updates: {why}'))
    if now.weekday() > 4 or not (4 * 60 <= mins < 21 * 60): return say('outside update hours (weekdays 04:00-21:00)')
    m, why, px, m15 = market(); ah, al = asia_range(m15, now.date())
    icon = {'SELL': '🔴 ▼ SELL', 'BUY': '🟢 ▲ BUY', 'WAIT': '🟡 WAIT (trend and DI disagree)'}[m]
    sent = []
    for key, at, title in SLOTS:
        if key in st['sent'] or not (at <= mins < at + 30): continue
        if key == 'asia' and not ah: continue
        lines = [f'👑 CBFX | {title} · {tag} London', f'💲 Gold {px:.2f}', f'📈 Market: {icon}', f'   {why}']
        if ah: lines.append(f'🌏 Asia range: high {ah:.2f} · low {al:.2f} (width {ah - al:.2f})')
        if key == 'asia' and ah:
            lines.append(f"🎯 Asia breakout engine, 04:00-09:00: {'buy a 15m close above ' + format(ah, '.2f') if m == 'BUY' else 'sell a 15m close below ' + format(al, '.2f') if m == 'SELL' else 'needs the 1H bias and 4H trend to agree first'}")
        b = brain_now()
        if b: lines.append('🧠 Best setups if they fire now: ' + ' · '.join(b))
        lines += [news_line(now), FOOT]
        r = publisher.publish('\n'.join(lines), 'update'); st['sent'].append(key); sent.append(f'{key} {r}')
        st['last_market'] = m; st['last_flip_ts'] = now.timestamp()
    # market flip: changed from the last announced value, held for two checks, at most one message an hour
    last = st.get('last_market')
    if last is None: st['last_market'] = m
    elif m != last:
        if st.get('pending') == m and now.timestamp() - st.get('last_flip_ts', 0) >= 3600:
            txt = '\n'.join([f'👑 CBFX | MARKET FLIP · {tag} London', f'📈 Market: {icon}  (was {last})', f'   {why}', f'💲 Gold {px:.2f}', FOOT])
            r = publisher.publish(txt, 'update'); st.update(last_market=m, last_flip_ts=now.timestamp(), pending=None); sent.append(f'flip {last}->{m} {r}')
        else: st['pending'] = m
    else: st['pending'] = None
    return say(('sent ' + '; '.join(sent)) if sent else f'Market {m} ({why})')


if __name__ == '__main__':
    main()
