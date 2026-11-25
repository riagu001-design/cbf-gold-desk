#!/usr/bin/env python3
"""Write the live desk state for the dashboard: /home/user/gold-desk/crown/desk.json
Rows (one table, column `kind` tells them apart):
  status  - checker running?, last scan line and time, rules version, trading hours
  best    - what the desk is looking for now: side, WATCH or VALID, dip level, estimated stop/target, why no trade
  level   - key levels (prior-day high/low, 1H swings)
  trade   - every setup in the live log with its result
  account - balance, P/L, wins/losses, today's numbers
  event   - today's high-impact US news (London time) with its blackout start
All prices are the Hyperliquid xyz:GOLD desk feed. Times are ISO UTC."""
import csv
import datetime as dt
import json
import os
import subprocess

import auto_scan as a

G = '/home/user/gold-desk'
OUT = f'{G}/crown/desk.json'
START = 194.74  # balance at the 30 Oct weekly report


def iso(x):
    return x.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def ldn_to_utc(s):  # '2026-11-05 08:20' London -> ISO UTC
    return iso(dt.datetime.strptime(s, '%Y-%m-%d %H:%M').replace(tzinfo=a.L))


def main():
    now = dt.datetime.now(a.L)
    rows = []
    m5, m15, h1, h4, d1 = a.candles('5m', 2), a.candles('15m', 5), a.candles('1h', 15), a.candles('4h', 40), a.candles('1d', 6)
    meta = a.requests.post(a.API, json={'type': 'metaAndAssetCtxs', 'dex': 'xyz'}, timeout=20).json()
    mark = [float(x['markPx']) for u, x in zip(meta[0]['universe'], meta[1]) if u['name'] == 'xyz:GOLD'][0]

    # status
    try:
        last = open(f'{G}/scan_loop.log').read().strip().splitlines()[-1]
    except (OSError, IndexError):
        last = ''
    running = subprocess.run(['bash', '/home/user/cbf-gold-desk/scan/checker_ok.sh'], capture_output=True, text=True).stdout.strip() == 'RUNNING'
    mins = now.hour * 60 + now.minute
    hours = not (now.weekday() == 5 or (now.weekday() == 6 and mins < 1380) or (now.weekday() == 4 and mins >= 1200) or 1320 <= mins < 1380 or mins < 360)
    rows.append(dict(kind='status', id='checker', status='running' if running else 'stopped', note=last, at=iso(now),
                     side=None, entry=mark, stop=None, target=None, result=None,
                     strategy='Live: Trend Pullback (H1 control): B-grade half size when the H4 structure agrees, C-grade 0.01 lot when it does not. Paper: London breakout and retest', last='in hours' if hours else 'outside hours'))

    # trend and the dip level, as the checker sees them
    hi, lo = a.swings(h1)
    e50h, c1 = a.ema([b['c'] for b in h1], 50)[-1], h1[-1]['c']
    st = 'UP' if hi[-1] > hi[-2] and lo[-1] > lo[-2] else 'DN' if hi[-1] < hi[-2] and lo[-1] < lo[-2] else 'MIX'
    bias = 'UP' if c1 > e50h and st != 'DN' else 'DOWN' if c1 < e50h and st != 'UP' else 'FLAT'
    bias4 = 'UP' if a.bias4_now(h4, mark) == 'UP' else 'DOWN'
    c15 = [b['c'] for b in m15]
    e20, e50 = a.ema(c15, 20)[-1], a.ema(c15, 50)[-1]
    E5, A5 = a.ema([b['c'] for b in m5], 20)[-1], a.atr(m5)
    pdh, pdl = d1[-1]['h'], d1[-1]['l']
    lv = [(pdh, 'prior-day high'), (pdl, 'prior-day low')] + [(x, '1H swing high') for x in hi[-4:]] + [(x, '1H swing low') for x in lo[-4:]]
    for p, why in sorted(set(lv)):
        rows.append(dict(kind='level', id=f'L{p:.1f}', side='resistance' if p > mark else 'support', entry=round(p, 1), note=why,
                         status=None, stop=None, target=None, result=None, strategy=None, last=None, at=iso(now)))

    side = 'BUY' if e20 > e50 else 'SELL'  # v3.5: the 15m EMAs set the side and the 1H trend must agree
    state = json.load(open(a.STATE)) if os.path.exists(a.STATE) else {}
    ot = state.get('open')
    best = dict(kind='best', id='best', side=side, status='WATCH', entry=None, stop=None, target=None, result=None, at=iso(now),
                strategy='Trend-day dip (v3.5, 15m + 1H trend)', note='', last='',
                # seeds so the dashboard can carry the EMAs and ATR forward live from newer closed candles
                seed=dict(e5=E5, a5=A5, t5=m5[-1]['t'], c5=m5[-1]['c'], e20_15=e20, e50_15=e50, t15=m15[-1]['t'], bias1=bias, bias4=bias4))
    why = []
    if side:
        sg = 1 if side == 'BUY' else -1
        ext = min(b['l'] for b in m5[-3:]) if side == 'BUY' else max(b['h'] for b in m5[-3:])
        stop = ext - sg * 1.5
        if sg * (E5 - stop) < 1.0 * A5:
            stop = E5 - sg * 1.0 * A5
        R = abs(E5 - stop)
        opp = [p for p, _ in lv if (p > E5 + 0.1 if side == 'BUY' else p < E5 - 0.1)]
        nx = (min(opp) if side == 'BUY' else max(opp)) if opp else None
        rr = abs(nx - E5) / R if nx and R else 9
        best.update(entry=round(E5, 1), stop=round(stop, 1), target=round(E5 + sg * R * min(2, max(rr, 1)), 1))
        if R > 10:
            why.append(f'a stop now would be ${R:.1f} away, over the $10 limit')
    if not hours:
        why.append('market closed or night pause (trading Sun 23:00-Fri 20:00 London; no new trades 22:00-23:00 or 00:00-06:00)')
    if bias != ('UP' if side == 'BUY' else 'DOWN'):
        why.append(f'the 1H trend is {bias.lower()}, so no {side.lower()}s until it agrees')
    if bias4 != ('UP' if side == 'BUY' else 'DOWN'):
        why.append(f'the 4H trend is {bias4.lower()}, so no {side.lower()}s until it agrees')
    if ot:
        why.append(f"a trade is open ({ot['side']} {ot['entry']}), one trade at a time")
    if last and 'SETUP' in last:
        t = now.replace(hour=int(last[:2]), minute=int(last[3:5]), second=0)
        if 0 <= (now - t).total_seconds() <= 600:
            best['status'] = 'VALID'
    reason = last.split('no setup (', 1)[1].rsplit(')', 1)[0] if 'no setup (' in last else ''
    best['note'] = f'15m trend {"up" if side == "BUY" else "down"} (EMA20 {e20:.1f} vs EMA50 {e50:.1f}); 1H trend {bias.lower()} (close {c1:.1f} vs EMA50 {e50h:.1f}), 4H {bias4.lower()}; 15m EMA20 {e20:.1f} / EMA50 {e50:.1f}; 5m EMA20 dip level {E5:.1f}'
    best['last'] = '; '.join(why) or (f'waiting for a 5m candle to dip to {E5:.1f} and close strongly' + (f' (last check: {reason})' if reason else ''))
    # 23 Nov 2026: the live engine is the Trend Pullback (pb_scan.py); the 'best' row now describes ITS read, not v3.5.
    best.pop('seed', None)
    try:
        import sys as _s; _s.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backtest', 'research_2026-11-23'))
        from bars_json import dmi
        from four_setups import pivots
        d1h = dmi(h1); c1h = [b['c'] for b in h1]; e20h, e50h1 = a.ema(c1h, 20)[-1], a.ema(c1h, 50)[-1]
        hb = e20h > e50h1 and d1h['pdi'] > d1h['mdi']; hs = e20h < e50h1 and d1h['mdi'] > d1h['pdi']; ctl = d1h['adx'] >= 20 and (hb or hs)
        ph, pl = pivots(h4, 2); up4 = ph[-1][1] > ph[-2][1] and pl[-1][1] > pl[-2][1]; dn4 = ph[-1][1] < ph[-2][1] and pl[-1][1] < pl[-2][1]
        s4 = 'UP (higher highs and lows)' if up4 else 'DOWN (lower highs and lows)' if dn4 else 'MIXED'
        d15 = dmi(m15); A15 = a.atr(m15); pside = 'BUY' if hb else 'SELL' if hs else None
        if pside is None: pside = 'BUY' if e20 > e50 else 'SELL'
        sg = 1 if pside == 'BUY' else -1
        di15 = (d15['pdi'] > d15['mdi']) if sg > 0 else (d15['mdi'] > d15['pdi'])
        h4ok = up4 if sg > 0 else dn4
        ext = min(b['l'] for b in m15[-3:]) if sg > 0 else max(b['h'] for b in m15[-3:])
        pst = ext - sg * 0.3 * A15
        if sg * (e20 - pst) < A15: pst = e20 - sg * A15
        pR = abs(e20 - pst); pin_h = 7 <= now.hour < 20 and now.weekday() < 5
        chk = [('ok' if ctl else 'no', f"1H control: {'buyers' if hb else 'sellers' if hs else 'none'} (ADX {d1h['adx']}, +DI {d1h['pdi']} / -DI {d1h['mdi']}; needs ADX 20+ with EMA20/50 and DI agreeing)"),
               ('ok' if h4ok else 'wait', f"H4 structure {s4}: highs {ph[-2][1]:.1f} -> {ph[-1][1]:.1f}, lows {pl[-2][1]:.1f} -> {pl[-1][1]:.1f}" + ('' if h4ok else ' (not a block since 25 Nov: a setup is sent as C-grade, 0.01 lot)')),
               ('ok' if di15 else 'no', f"15m DI {'agrees' if di15 else 'disagrees'} (+DI {d15['pdi']} / -DI {d15['mdi']})"),
               ('ok' if (e20 > e50) == (sg > 0) else 'no', f"15m EMA20 {e20:.1f} {'above' if e20 > e50 else 'below'} EMA50 {e50:.1f}"),
               ('ok' if pin_h else 'wait', 'Entry window open (07:00-20:00 London weekdays)' if pin_h else 'Outside the entry window: entries 07:00-20:00 London weekdays'),
               ('wait', f"Trigger: a closed 15m candle {'dips to' if sg > 0 else 'rallies to'} the 15m EMA20 ({e20:.1f}) and closes back {'above' if sg > 0 else 'below'} it, {'bullish' if sg > 0 else 'bearish'}")]
        blocked = [t for st_, t in chk if st_ == 'no']
        try:
            pbl = [l for l in open(f'{G}/scan_loop.log').read().splitlines() if ': PB ' in l][-1]
        except (OSError, IndexError):
            pbl = ''
        best.update(side=pside, status='WATCH' if not blocked else 'BLOCKED', entry=round(e20, 1), stop=round(pst, 1), target=round(e20 + sg * 2 * pR, 1),
                    strategy='Trend Pullback (H1 control) · ' + ('B-grade half size (H4 agrees)' if h4ok else 'C-grade 0.01 lot (H4 not confirmed)'), note='\n'.join(f'{st_}|{t}' for st_, t in chk),
                    last=('Blocked: ' + blocked[0].split(' (')[0] if blocked else f"All filters agree: waiting for the 15m dip to {e20:.1f}") + (f'. Engine log {pbl}' if pbl else ''))
        if pbl and 'SETUP' in pbl:
            tl = now.replace(hour=int(pbl[:2]), minute=int(pbl[3:5]), second=0, microsecond=0)
            if 0 <= (now - tl).total_seconds() <= 900: best['status'] = 'VALID'
    except Exception as ex:  # never break the feed
        best.update(status='WATCH', entry=None, stop=None, target=None, strategy='Trend Pullback (H1 control) · ' + ('B-grade half size (H4 agrees)' if h4ok else 'C-grade 0.01 lot (H4 not confirmed)'), note='', last=f'engine read failed: {type(ex).__name__}')
    try:
        po = json.load(open(f'{G}/pb_state.json')).get('open')
        if po:
            rows.append(dict(kind='trade', id='PB' + po['opened'], side=po['side'], entry=po['entry'], stop=po['stop'], target=po['target'], status='Open',
                             result=None, note='Trend pullback, B-grade half size', strategy='Trend Pullback', last='', at=ldn_to_utc(po['opened'])))
    except (OSError, ValueError, KeyError):
        pass
    rows.append(best)

    # trades and account
    log = list(csv.DictReader(open(a.LOG))) if os.path.exists(a.LOG) else []
    pl = wins = losses = 0
    today = now.strftime('%Y-%m-%d')
    t_pl = t_sent = 0
    for i, r in enumerate(log):
        res = r['result'] or ''
        v = None
        if res and not res.startswith('SKIPPED'):
            try:
                v = float(res.split()[-1])
            except ValueError:
                v = None
        if v is not None:
            pl += v; wins += v > 0; losses += v < 0
        if r['given_at_london'].startswith(today):
            t_sent += 1; t_pl += v or 0
        status = 'Open' if not res else 'Skipped' if res.startswith('SKIPPED') else {'SL': 'Stop hit', 'TP': 'Target hit', 'TIME': 'Time exit'}.get(res.split()[0], res)
        rows.append(dict(kind='trade', id=f'T{i + 1}', side=r['side'], entry=float(r['entry']), stop=float(r['stop']), target=float(r['target']),
                         status=status, result=v, note=r['reason'], strategy='Trend-day dip', last=res, at=ldn_to_utc(r['given_at_london'])))
    closed = wins + losses
    rows.append(dict(kind='account', id='account', entry=round(START + pl, 2), result=round(pl, 2), stop=wins, target=losses,
                     status=f'{t_sent} sent today', note=f'{round(100 * wins / closed) if closed else 0}% wins over {closed} closed', side=None,
                     strategy=f'today {t_pl:+.2f}', last=f'{len(log)} setups since the new rules', at=iso(now)))

    # news
    try:
        n = json.load(open(f'{G}/news_today.json'))
        ev = n['events'] if n.get('date') == today else []
    except (OSError, ValueError, KeyError):
        ev = []
    for t, name in ev:
        at = dt.datetime.strptime(f'{today} {t}', '%Y-%m-%d %H:%M').replace(tzinfo=a.L)
        rows.append(dict(kind='event', id='E' + t.replace(':', ''), strategy=name, note=iso(at), last=iso(at - dt.timedelta(minutes=15)),
                         status='high impact', side=None, entry=None, stop=None, target=None, result=None, at=iso(now)))
    try:  # Crown's latest spoken briefing, for the dashboard's read-aloud button
        brief = json.load(open(f'{G}/crown/crown_vars.json'))
        try:  # Crown's latest briefing recorded in Ian's voice (ElevenLabs), uploaded to the dashboard: url + when
            v = json.load(open(f'{G}/crown/voice.json'))
        except (OSError, ValueError):
            v = {}
        rows.append(dict(kind='brief', id='brief', note=brief.get('desk_brief', ''), at=brief.get('at', iso(now)), side=None, entry=None, stop=None,
                         target=None, result=None, status=v.get('at'), strategy='Ian', last=v.get('url')))
    except (OSError, ValueError):
        pass
    # CrownBearer Neural Brain: learning review, then the decision status (score, verdicts, registry, recommendations)
    try:
        import sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'brain'))
        import learn, core
        learn.review(); bs = core.status()
        # 23 Nov 2026: only the trend pullback engine (PB) is live; show its fixed B-grade score, not the deleted engines'
        nw = bs.get('now') or {}
        nw['scores'] = [dict(strategy='PB', side=sd, score=80, expected_R=0.23, band='WATCHLIST') for sd in ('BUY', 'SELL')]
        nw['best'] = dict(strategy='PB', side='BUY' if nw.get('bias') == 'UP' else 'SELL', score=80, expected_R=0.23, band='WATCHLIST')
        nw['support'] = {}; nw['conflict'] = False
        try:
            pbl = open(f'{G}/scan_loop.log').read().splitlines(); pbl = [l for l in pbl if ': PB ' in l][-1:]
        except OSError:
            pbl = []
        nw['explain'] = ('Live engine: Trend Pullback (H1 control) with the H4 structure filter, B-grade score 80, sent to Telegram at half size. '
                         'Latest check: ' + (pbl[0].split(': PB ', 1)[1] if pbl else 'none yet') + '. Paper only: London breakout and retest.')
        bs['now'] = nw
        rows.append(dict(kind='brain', id='brain', status='operational: trend pullback engine only (23 Nov, Woody)', at=iso(now), side=None,
                         entry=None, stop=None, target=None, result=None, strategy='CrownBearer Neural Brain', note='', last='', brain=bs))
    except Exception as ex:
        rows.append(dict(kind='brain', id='brain', status=f'error {type(ex).__name__}: {ex}', at=iso(now), side=None, entry=None, stop=None,
                         target=None, result=None, strategy='CrownBearer Neural Brain', note='', last='', brain={}))
    # 23 Nov 2026: every row carries every field (the dashboard's file reader keeps only the fields it sees in the first
    # row, so the brain field, present only in the last row, was dropped and the brain panel showed dashes)
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    rows = [{k: r.get(k) for k in keys} for r in rows]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rows, open(OUT, 'w'), indent=0)
    print(f'{len(rows)} rows -> {OUT}; best {best["status"]} {best["side"]} {best["entry"]}; why: {best["last"]}')


if __name__ == '__main__':
    main()
