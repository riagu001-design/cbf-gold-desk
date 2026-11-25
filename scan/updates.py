#!/usr/bin/env python3
"""Daily MARKET UPDATES to Telegram (Woody 18 Nov 2026: no more days of silence). These are information, not trades.
Sent through the brain's one channel (brain/publisher.py), weekdays only, at most once per slot:
  04:00  Asia range set (high / low, information only since 23 Nov)
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
FOOT = 'ℹ️ Market brief only, not a trade. Setups come as separate 👑 TRADE SETUP messages.'


def market():
    now_ms = dt.datetime.now(L).timestamp() * 1000
    done = lambda iv, days: [x for x in candles(iv, days) if x['T'] < now_ms]
    h4, h1, m15 = done('4h', 60), done('1h', 8), done('15m', 3)
    c4 = [x['c'] for x in h4]; down = ema(c4, 50)[-1] < ema(c4, 200)[-1]
    d = {k: dmi(v) for k, v in (('H4', h4), ('H1', h1), ('M15', m15))}
    sel = sum(1 for x in d.values() if x and x['control'] == 'sellers'); n = sum(1 for x in d.values() if x)
    m = 'SELL' if down and sel * 2 > n else 'BUY' if not down and (n - sel) * 2 > n else 'WAIT'
    di = ' · '.join(f"{k} {x['control']} (ADX {x['adx']:.0f})" for k, x in d.items() if x)
    return m, f"4H trend {'down' if down else 'up'} · {di}", m15[-1]['c'], m15, d, down


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


def engine_now():
    """The live trend pullback engine's read from the desk feed, as short lines (clean layout, Woody 25 Nov 2026)."""
    try:
        b = [r for r in json.load(open(f'{G}/crown/desk.json')) if r.get('kind') == 'best'][0]
    except (OSError, ValueError, IndexError):
        return []
    if b.get('entry') is None: return []
    head = {'VALID': '✅ SETUP SENT', 'BLOCKED': '⛔ BLOCKED', 'WATCH': '👀 READY, waiting for the dip'}.get(b.get('status'), b.get('status'))
    out = [f"🎯 Live engine (Trend Pullback): {b['side']} lean · {head}"]
    miss = [ln.split('|', 1)[1].split(' (')[0] for ln in (b.get('note') or '').split('\n') if ln.startswith('no|')]
    sell = b['side'] == 'SELL'
    plain = lambda t: (f"H4 {'lower' if sell else 'higher'} highs and {'lower' if sell else 'higher'} lows (now mixed)" if t.startswith('H4 structure')
                       else f"15m {'sellers' if sell else 'buyers'} to lead the DI" if t.startswith('15m DI') else t)
    if miss: out.append('   Waiting for: ' + '; '.join(plain(t) for t in miss))
    out.append(f"   Dip level {b['entry']:.2f} · Stop {b['stop']:.2f} · Target {b['target']:.2f}")
    return out


def control_line(d):
    sel = sum(1 for x in d.values() if x and x['control'] == 'sellers'); n = sum(1 for x in d.values() if x)
    head = '🔴 Sellers in Control' if sel * 2 > n else '🟢 Buyers in Control' if (n - sel) * 2 > n else '⚪ Mixed Control'
    parts = ' | '.join(f"{k}: {x['control'].capitalize()}" for k, x in d.items() if x)
    return f'🧭 Control: {head} ({parts})'


def news_line(now):
    """Woody's layout (18 Nov): the list of today's high-impact releases, then the no-trade rule, only when there is news."""
    try:
        n = json.load(open(f'{G}/news_today.json'))
    except (OSError, ValueError):
        return '⏰ News calendar not checked today'
    ev = n.get('events', []) if n.get('date') == now.strftime('%Y-%m-%d') else []
    later = [(t, name) for t, name in ev if t > now.strftime('%H:%M')]
    if not later: return '⏰ News: no more high-impact news today'
    times = sorted({t for t, _ in later})
    def pm5(t, k):
        h, m = map(int, t.split(':')); x = h * 60 + m + k; return f'{x // 60:02d}:{x % 60:02d}'
    return '\n'.join(['⏰ News (London): ' + ' · '.join(f'{t} {name}' for t, name in later),
                      '   ⚠️ No new trades ' + ', '.join(f'{pm5(t, -5)}-{pm5(t, 5)}' for t in times)])


def brief(title, tag, px, m, down, d, ah, al, m15, now):
    """Clean market brief (Woody 25 Nov 2026): price, bias, control, levels, the live engine, news."""
    icon = {'SELL': '🔴 SELL', 'BUY': '🟢 BUY', 'WAIT': '🟡 WAIT (trend and DI disagree)'}[m]
    day = [x for x in m15 if ldn(x['t']).date() == now.date()]
    lines = [f'👑 CBFX | {title} · {tag} London', f'💲 Gold: {px:.2f}', f"📈 Bias: {icon} · 4H trend {'down' if down else 'up'}", control_line(d), '']
    if ah: lines.append(f'🌏 Asia range: {ah:.2f} – {al:.2f} ({ah - al:.2f})')
    if day: lines.append(f"📏 Today: high {max(x['h'] for x in day):.2f} · low {min(x['l'] for x in day):.2f}")
    e = engine_now()  # 24 Nov 2026: the only live engine is the trend pullback (old engines deleted 23 Nov)
    if e: lines += [''] + e
    return lines + ['', news_line(now), '', FOOT]


def main():
    now = dt.datetime.now(L); mins = now.hour * 60 + now.minute; tag = now.strftime('%H:%M'); today = str(now.date())
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    if st.get('day') != today: st.update(day=today, sent=[])
    say = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London: updates: {why}'))
    if now.weekday() > 4 or not (4 * 60 <= mins < 21 * 60): return say('outside update hours (weekdays 04:00-21:00)')
    m, why, px, m15, d, down = market(); ah, al = asia_range(m15, now.date())
    icon = {'SELL': '🔴 ▼ SELL', 'BUY': '🟢 ▲ BUY', 'WAIT': '🟡 WAIT (trend and DI disagree)'}[m]
    sent = []
    for key, at, title in SLOTS:
        if key in st['sent'] or not (at <= mins < at + 30): continue
        if key == 'asia' and not ah: continue
        lines = brief(title, tag, px, m, down, d, ah, al, m15, now)
        r = publisher.publish('\n'.join(lines), 'update'); st['sent'].append(key); sent.append(f'{key} {r}')
        st['last_market'] = m; st['last_flip_ts'] = now.timestamp()
    # market flip: changed from the last announced value, held for two checks, at most one message an hour
    last = st.get('last_market')
    if last is None: st['last_market'] = m
    elif m != last:
        if st.get('pending') == m and now.timestamp() - st.get('last_flip_ts', 0) >= 3600:
            txt = '\n'.join([f'👑 CBFX | MARKET FLIP · {tag} London', f'📈 Bias: {icon} (was {last}) · 4H trend {"down" if down else "up"}',
                             control_line(d), f'💲 Gold: {px:.2f}', '', FOOT])
            r = publisher.publish(txt, 'update'); st.update(last_market=m, last_flip_ts=now.timestamp(), pending=None); sent.append(f'flip {last}->{m} {r}')
        else: st['pending'] = m
    else: st['pending'] = None
    return say(('sent ' + '; '.join(sent)) if sent else f'Market {m} ({why})')


if __name__ == '__main__':
    if '--preview' in sys.argv:  # print a London brief from live data without sending
        now = dt.datetime.now(L); m, why, px, m15, d, down = market(); ah, al = asia_range(m15, now.date())
        print('\n'.join(brief('LONDON OPEN PLAN', now.strftime('%H:%M'), px, m, down, d, ah, al, m15, now)))
    else:
        main()
