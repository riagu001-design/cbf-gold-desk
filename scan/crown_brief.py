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


# 23 Nov 2026 (Woody: "Delete all of them"): every strategy engine is switched off until a new setup passes its test.
ENGINES_OFF = True


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

    # CrownBearer Neural Brain: the only signal authority; Crown speaks from its status
    try:
        bs = {} if ENGINES_OFF else json.load(open(f'{G}/brain/status.json')); n = bs.get('now', {}); act = bs.get('active') or []
        top = sorted(n.get('scores', []), key=lambda r: -r['score'])[:3]
        facts.append('NEURAL BRAIN (the only thing that sends Telegram signals; engines only propose): sends only setups scoring 85+ with all checks passed (market open, news, fresh, stop size, daily loss limit -3R, no duplicate or conflicting signal); 75-84 watchlist; below 75 rejected. '
                     f"Now: H4 bias {n.get('bias')}, regime {n.get('regime')}, session {n.get('session')}. Scores a setup would get now: " + ', '.join(f"{r['side']} {r['strategy']} {r['score']}" for r in top) + '. '
                     f"Unseen-test check of the score: 85+ band {bs['calibration_unseen']['85+']['avgR']:+.2f}R per trade on {bs['calibration_unseen']['85+']['n']} setups, below 75 {bs['calibration_unseen']['<75']['avgR']:+.2f}R. "
                     f"Decisions so far: {bs['counts']['proposals']} proposals, {bs['counts']['sent']} sent, {bs['counts']['watchlist']} watchlist, {bs['counts']['rejected']} rejected.")
        for r in (bs.get('last') or [])[-3:]:
            facts.append(f"Brain decision {r['london']}: {r['side']} {r['strategy']} at {r['entry']}, score {r['score']}, {r['verdict']}" + (f" ({'; '.join(r['reasons'])})" if r.get('reasons') else '') + '.')
        if act:
            a_ = act[0]; facts.append(f"ACTIVE BRAIN SIGNAL {a_['id']}: {a_['side']} {a_['strategy']} entry {a_['entry']}, stop {a_['stop']}, TP1 {a_['tp1']}, TP2 {a_['tp2']}, score {a_['score']}, sent {a_['london']} London.")
            spoken.append(f"The brain has an active {a_['side'].lower()} signal from {say(a_['entry'])}, stop {say(a_['stop'])}, first target {say(a_['tp1'])}.")
        elif n.get('best'):
            b_ = n['best']
            spoken.append(f"The brain's H4 bias is {str(n.get('bias')).lower()}. The best setup right now would be a {b_['side'].lower()} from the {b_['strategy']} engine, scoring {b_['score']}"
                          + (", an A-grade score: it goes to Telegram at full size the moment it fires." if b_['band'] == 'SEND' else ", a B-grade score: it goes to Telegram at half size the moment it fires." if b_['band'] == 'WATCHLIST' else ", below 75, so it would not be sent."))
    except (OSError, ValueError, KeyError):
        pass

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
        try:
            sw_ = {} if ENGINES_OFF else json.load(open(f'{G}/swing_state.json'))
        except (OSError, ValueError):
            sw_ = {}
        lv_ = sw_.get('levels') or {}
        if lv_:
            e21s = lv_['ema21'] - sw_.get('basis', 0); tr_ = 'up' if lv_['ema50'] > lv_['ema200'] else 'down'
            facts.append(f"Swing paper test (daily): trend {tr_} (EMA50 {lv_['ema50']} vs EMA200 {lv_['ema200']}, futures), 21-day EMA about {e21s:.0f} in spot terms, daily ATR {lv_['atr']}; macro bias {sw_.get('macro', {}).get('bias')} (both real yields and the dollar falling = bullish, both rising = bearish).")
            spoken.append(f"The desk is paper-testing the daily swing pullback. The daily trend is {tr_}, so it waits for a {'dip' if tr_ == 'up' else 'rally'} to the 21-day average, now about {say(e21s)}. The macro bias is {({'UP': 'bullish', 'DN': 'bearish'}).get(sw_.get('macro', {}).get('bias'), 'mixed')}.")

    try:
        as_ = {} if ENGINES_OFF else json.load(open(f'{G}/asia_state.json')); rg_ = as_.get('range') or {}
        if rg_: facts.append(f"Asia range breakout paper test (added 18 Nov, Woody): today's Asia range (23:00 to 04:00 London) high {rg_['high']}, low {rg_['low']}"
                             + (' (still forming)' if rg_.get('bars', 0) < 20 else '') + '. Entry 04:00 to 09:00 on a 15 minute close beyond it with the 1H bias and 4H trend; stop 1 x 1H ATR, target 2R, out 16:00. Brain score about 53: paper only.'
                             + (f" Open: {as_['open']['side']} from {as_['open']['entry']:.1f}, stop {as_['open']['stop']:.1f}, target {as_['open']['target']:.1f}." if as_.get('open') else ''))
        if as_.get('open'):
            o_ = as_['open']; lv_ = (mark - o_['entry']) * (1 if o_['side'] == 'BUY' else -1)
            spoken.append(f"The Asia breakout paper {o_['side'].lower()} from {say(o_['entry'])} is open, stop {say(o_['stop'])}, target {say(o_['target'])}, {'up' if lv_ >= 0 else 'down'} {abs(lv_):.0f} dollars per ounce.")
    except (OSError, ValueError, KeyError):
        pass
    try:
        em_ = {} if ENGINES_OFF else json.load(open(f'{G}/ema_state.json'))
    except (OSError, ValueError):
        em_ = {}
    if em_.get('h4'):
        t4_ = em_['h4']['trend']; h1_ = em_.get('h1', {})
        facts.append(f"EMA 9/21 paper test (H1; since 16 Nov 15:20 the H4 trend no longer blocks, Woody's call): H4 {t4_} for information (EMA50 {em_['h4']['ema50']} vs EMA200 {em_['h4']['ema200']}); 1H EMA9 {h1_.get('ema9')} vs EMA21 {h1_.get('ema21')}, 1H ATR {h1_.get('atr')}. A test trade starts on a 1H close where EMA9 crosses EMA21 either way, entries 07:00 to 17:00 London weekdays only (without H4 the cross lost at all hours in the test); stop 2 x 1H ATR; out on the opposite cross.")
        if em_.get('open'):
            p_ = em_['open']; lv2 = (mark - p_['entry']) * (1 if p_['side'] == 'BUY' else -1)
            facts.append(f"EMA paper trade open (not real): {p_['side']} from {p_['entry']:.1f}, stop {p_['stop']:.1f}, opened {p_['opened']}; {lv2:+.2f} dollars per ounce now.")
            spoken.append(f"There is an EMA paper test {p_['side'].lower()} from {say(p_['entry'])}, stop {say(p_['stop'])}, {'up' if lv2 >= 0 else 'down'} {abs(lv2):.0f} dollars per ounce. It is not a real trade.")
        else:
            up_ = (h1_.get('ema9') or 0) > (h1_.get('ema21') or 0)
            spoken.append(f"The EMA nine twenty-one test waits for the one hour EMA nine to cross {'below' if up_ else 'above'} the EMA twenty-one, between 7 am and 5 pm. The four hour trend no longer blocks trades.")

    # 4H EMA 9/21 paper test (16 Nov 17:00, Woody)
    try:
        h4p = {} if ENGINES_OFF else json.load(open(f'{G}/h4_state.json'))
    except (OSError, ValueError):
        h4p = {}
    if h4p.get('h4'):
        q_ = h4p['h4']
        facts.append(f"4H EMA 9/21 paper test (added 16 Nov 17:00, Woody): 4H EMA9 {q_['ema9']} vs EMA21 {q_['ema21']}, 4H ATR {q_['atr']}. A test trade starts on a 4H close where EMA9 crosses EMA21 either way, any hour; stop 2 x 4H ATR, target 2R, out Friday 21:00. 12-month test: about 1 trade a week, unseen half +10.9R PF 1.76.")
        if h4p.get('open'):
            p_ = h4p['open']; lv3 = (mark - p_['entry']) * (1 if p_['side'] == 'BUY' else -1)
            facts.append(f"4H paper trade open (not real): {p_['side']} from {p_['entry']:.1f}, stop {p_['stop']:.1f}, target {p_['target']:.1f}, opened {p_['opened']}; {lv3:+.2f} dollars per ounce now.")
            spoken.append(f"There is a four hour paper test {p_['side'].lower()} from {say(p_['entry'])}, stop {say(p_['stop'])}, target {say(p_['target'])}. It is not a real trade.")
        else:
            spoken.append(f"The four hour test waits for the four hour EMA nine to cross {'below' if q_['ema9'] > q_['ema21'] else 'above'} the EMA twenty-one.")

    # H4 DI: who is in control on the 4 hour chart (same Wilder +DI/-DI/ADX as the dashboard)
    try:
        from bars_json import dmi
        d4 = dmi(h4) if len(h4) > 30 else None
    except Exception:
        d4 = None
    if d4:
        grip = {'strong': 'a strong grip', 'building': 'a grip that is building', 'weak': 'only a weak grip'}[d4['strength']]
        facts.append(f'Who is in control, 4 hour DI (14): {d4["control"]} (+DI {d4["pdi"]}, -DI {d4["mdi"]}, ADX {d4["adx"]}, {d4["strength"]}). ADX under 20 weak, 20 to 25 building, 25 and over strong.')
        spoken.append(f'On the four hour chart the {d4["control"]} are in control, with {grip}: ADX {d4["adx"]:.0f}, minus DI {d4["mdi"]:.0f} against plus DI {d4["pdi"]:.0f}.')

    # scan health and latest reason
    last = ''
    try:
        last = open(f'{G}/scan_loop.log').read().strip().splitlines()[-1]
    except (OSError, IndexError):
        pass
    mins = now.hour * 60 + now.minute
    in_session = not (now.weekday() == 5 or (now.weekday() == 6 and mins < 1380) or (now.weekday() == 4 and mins >= 1200) or 1320 <= mins < 1380)
    running = subprocess.run(['bash', '/home/user/cbf-gold-desk/scan/checker_ok.sh'], capture_output=True, text=True).stdout.strip() == 'RUNNING'
    status = 'running' if running else ('not running (it is restarted within 15 minutes)' if in_session else 'off until the next session')
    facts.append(f'Scanner: 5 minute checker {status}; trading hours around the clock, Sunday 23:00 to Friday 20:00 London (daily break 22:00 to 23:00). Last scan: {last or "none yet today"}.')
    if in_session:
        spoken.append('The scanner is ' + ('watching every five minute candle.' if running else 'restarting; the watchdog brings it back within fifteen minutes.'))
        if last and 'no setup (' in last and 'outside' not in last:
            spoken.append('Latest check: ' + last.split('no setup (', 1)[1].split(');')[0].removesuffix(')') + '.')
    else:
        nxt = ('at 11 pm' if ((1320 <= mins < 1380 and now.weekday() < 4) or now.weekday() == 6) else 'on Sunday at 11 pm')  # Friday's 22:00-23:00 hour is the weekend close, not the daily break
        spoken.append(f'The market is closed, so no new trades; scanning resumes {nxt} London time.')

    # trades
    state = json.load(open(f'{G}/scan_state.json')) if os.path.exists(f'{G}/scan_state.json') else {}
    rows = list(csv.DictReader(open(f'{G}/live_log.csv'))) if os.path.exists(f'{G}/live_log.csv') else []
    ot = state.get('open')
    tp_ = json.load(open(f'{G}/trend_state.json')).get('open') if os.path.exists(f'{G}/trend_state.json') else None
    if tp_:
        lv_ = (mark - tp_['entry']) * (1 if tp_['side'] == 'BUY' else -1)
        facts.append(f"Paper test trade (not real): {tp_['side']} from {tp_['entry']:.1f}, trailing stop {tp_['stop']:.1f}, opened {tp_['opened']} London; paper result {lv_:+.2f} dollars at 0.01 lot.")
        spoken.append(f"There is a paper test {tp_['side'].lower()} from {say(tp_['entry'])} with a trailing stop at {say(tp_['stop'])}, currently {'up' if lv_ >= 0 else 'down'} {abs(lv_):.0f} dollars at 0.01 lot. It is not a real trade.")
    if ot:
        live = (mark - ot['entry']) * (1 if ot['side'] == 'BUY' else -1)
        facts.append(f'Open trade: {ot["side"]} at {ot["entry"]}, stop {ot["stop"]}, target {ot["target"]}, sent {ot["given"]} London; live result {live:+.2f} dollars at 0.01 lot.')
        spoken.append(f'We have an open {ot["side"].lower()} from {say(ot["entry"])}, stop {say(ot["stop"])}, target {say(ot["target"])}, currently {"up" if live >= 0 else "down"} {abs(live):.2f} dollars.')
    else:
        facts.append('Open real-strategy trade: none (the old dip strategy is deleted; paper tests are listed above).')
    today = [r for r in rows if r['given_at_london'].startswith(now.strftime('%Y-%m-%d'))]
    pl = 0.0
    for r in rows:
        try:
            pl += float(r['result'].split()[-1]) if r['result'] and not r['result'].startswith('SKIPPED') else 0
        except ValueError:
            pass
    closed = [r for r in rows if r['result'] and not r['result'].startswith('SKIPPED')]
    # 25 Nov 2026: count the live pullback engine (pb_log.csv), not only the old live log
    pbr = list(csv.DictReader(open(f'{G}/pb_log.csv'))) if os.path.exists(f'{G}/pb_log.csv') else []
    pb_today = [r for r in pbr if r['opened'].startswith(now.strftime('%Y-%m-%d'))]
    pb_closed = [r for r in pbr if r.get('closed')]
    pb_pl = sum(float(r['usd_001']) for r in pb_closed if r.get('usd_001')); pb_R = sum(float(r['R']) for r in pb_closed if r.get('R'))
    pl += pb_pl
    desc = lambda r: f"{r['opened'][11:]} {r['side']} {r['entry']} SL {r['stop']} TP {r['target']} " + (f"closed {r['closed'][11:]} {r['how']} {float(r['R']):+.2f}R, {float(r['usd_001']):+.2f} dollars at 0.01 lot" if r.get('closed') else 'open')
    facts.append(f'Pullback engine setups sent today: {len(pb_today)}' + (': ' + '; '.join(desc(r) for r in pb_today) if pb_today else '') + '.')
    facts.append(f'Pullback engine log: {len(pbr)} setups, {len(pb_closed)} closed, {pb_R:+.2f}R, {pb_pl:+.2f} dollars at 0.01 lot (the sized lots scale this). Account about {BALANCE_START + pl:.2f} dollars at 0.01 lot (194.74 at the 30 Oct weekly report plus live results). Review after 20 trades.')
    import csv as _csv
    pb_txt = ''
    try:
        _p = json.load(open(f'{G}/pb_state.json')).get('open')
        if _p:
            _lv = (mark - _p['entry']) * (1 if _p['side'] == 'BUY' else -1)
            facts.append(f"OPEN LIVE SIGNAL (trend pullback, half size): {_p['side']} from {_p['entry']:.1f}, stop {_p['stop']:.1f}, target {_p['target']:.1f}, opened {_p['opened']} London; {_lv:+.2f} dollars per ounce now.")
            pb_txt = f". The trend pullback {_p['side'].lower()} from {say(_p['entry'])} is open, stop {say(_p['stop'])}, target {say(_p['target'])}"
        _b = json.load(open(f'{G}/br_state.json')).get('open')
        if _b: facts.append(f"Paper breakout-retest trade (not sent): {_b['side']} from {_b['entry']:.1f}, stop {_b['stop']:.1f}, targets {_b['tps']}, {_b['legs_hit']} of 3 hit.")
    except (OSError, ValueError, KeyError):
        pass
    paper_today = 0
    for _f in (() if ENGINES_OFF else ('ema_log.csv', 'm15_log.csv', 'h4_log.csv', 'swing_log.csv', 'asia_log.csv')):
        try:
            paper_today += sum(1 for r in _csv.DictReader(open(f'{G}/{_f}')) if (r.get('opened') or '').startswith(now.strftime('%Y-%m-%d')))
        except (OSError, ValueError):
            pass
    spoken.append(f'{"One engine is live, the trend pullback: half size when the four hour structure agrees, the 0.01 lot minimum when it does not. The London breakout retest is paper-tracked" + (pb_txt or "") if ENGINES_OFF else ("Paper test setups today: " + str(paper_today) if paper_today else "No paper test setups yet today")}, and the account is about {BALANCE_START + pl:.0f} dollars if every signal was taken at 0.01 lot.' + (' Today the pullback engine sent ' + '; '.join(f"a {r['side'].lower()} at {r['opened'][11:]}" + (f" that closed at its {'target' if 'TARGET' in r['how'] else 'stop' if 'STOP' in r['how'] else r['how'].lower()} for {'plus' if float(r['R']) >= 0 else 'minus'} {abs(float(r['R'])):.1f} R" if r.get('closed') else ' that is still open') for r in pb_today) + '.' if pb_today else ''))

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
        facts.append('High-impact US news today: ' + ('; '.join(f'{t} {name}' for t, name in ev) if ev else 'none') + '. Since 16 November: no new entries from 5 minutes before to 5 minutes after each release; setups 6 to 15 minutes either side are sent with a news warning (wide spreads, fast spikes).')
        if upcoming:
            spoken.append(f'Next high-impact news: {upcoming[0][1]} at {upcoming[0][0]}. No new entries from 5 minutes before to 5 minutes after it; a setup within 15 minutes comes with a news warning.')
        else:
            spoken.append('There is no more high-impact US news today.')

    if ENGINES_OFF:
        facts.append('Early warning (from 27 Nov 2026 18:15, Woody: "Can you spot the move early"): when the 1 hour control and the 15 minute DI agree and gold pulls back to within one 15 minute ATR of the 15 minute EMA20, Telegram gets a GET READY message. It is information only, not a trade: the ENTER NOW still needs a closed 15 minute candle that dips to the EMA20 and closes back beyond it. Entering on the touch instead was tested and made no more money (+34.7R against +35.0R, deeper drawdown), so the entry rule is unchanged.')
        facts.append('Desk mode from 23 Nov 2026, 19:00 London (Woody deleted the old engines, then said "Do want is best for the system"): ONE LIVE ENGINE, the Trend Pullback (H1 control): 1H EMA20 above EMA50, +DI above -DI and ADX 20 or more = buyers (sellers mirrored), the 15m DI agrees; THE H4 STRUCTURE SETS THE SIZE (from 25 Nov, Woody: "H4 should not be a hard blocker"): when the last two H4 swing highs and lows agree with the trade it is a B-grade signal at half size; when the H4 is mixed or against it is still sent, as a C-grade signal at the 0.01 lot minimum with a warning (in the test to 25 Nov, H4-agree trades made +33.5R on 135, mixed lost 5.0R on 127, against made +6.5R on 67); a closed 15m candle dips to the 15m EMA20 and closes back beyond it; stop beyond the last three 15m candles plus 0.3 ATR (at least 1 ATR); target 2R; entries 07:00 to 20:00 London, at most 3 a day; test with the H4 filter to 25 Nov 2026: 144 trades, 45 percent wins, +34.6R, profit factor 1.43, worst losing run 7.6R, unseen half +12.3R; expect about one B-grade signal every 2 to 3 trading days, and C-grade ones in between. The brain sends both to Telegram (B-grade at HALF size, C-grade at the 0.01 lot minimum); reviewed after 20 live trades. ONE PAPER TEST (not sent): London breakout and retest (previous day or London session high/low; M15 close beyond, retest and close back in the breakout direction; 07:00 to 13:00; thirds at 0.5R, 1R and 1.5R with the stop to breakeven after the first): 12-month test 38 trades, +0.18R a trade, positive in both halves. Woody\'s other new setups (H4 trend pullback, failed breakout, range) lost in the test and are off.')
    else:
        facts.append('Desk mode from 16 Nov 2026 (Woody): all earlier strategies are deleted (5 minute dip and 1 hour breakout: no edge in the 12-month and 20-year tests). Four PAPER TESTS run (the 4H EMA 9/21 cross with a 2R target was added at 17:00 on 16 Nov, Woody, for about one more setup a week at any hour). (0) M15 entry with H1 confirmation (Woody design, 16 Nov; since 15:20 the H4 trend no longer blocks, entries 07:00 to 17:00 London; without H4 it was break-even in the unseen test): 15m EMA9/21 cross in the direction of the 1H EMA9/21, stop 2 x 1H ATR, exit when the 1H EMA9/21 flips; the weakest of the tests. (1) Frequent: H1 EMA 9/21 cross either way (H4 no longer blocks since 16 Nov 15:20; entries 07:00 to 17:00 London; without H4 that test made +8.8R PF 1.5 on the unseen half, about 1 to 2 trades a week), stop 2 x 1H ATR, exit on the opposite cross or Friday 21:00; at all hours without H4 it lost in the test, which is why entries are limited to 07:00 to 17:00. The earlier H4 version made profit factor about 1.4 to 2.0 in both halves. (2) Slow: the daily swing pullback with the macro filter (Woody strategies 1 and 4): daily EMA50 above EMA200 = buys only, below = sells only; the day touches the 21-day EMA and closes back beyond it as a confirmation candle; stop beyond the 5-day swing plus 0.2 daily ATR; target 2R; out after 30 trading days; a trade against a clear macro bias (real yields and dollar both moving) is skipped. 20-year test: about 6 trades a year, both decades profitable (profit factor about 1.4 to 1.5), worst losing run about 12R. Risk 1 percent per trade. With daily stops of about 190 dollars per ounce, 1 percent of a 182 dollar account is about 0.01 ounce, so it cannot be traded at the broker 0.01 lot (1 ounce): that would risk about 190 dollars. Messages are marked PAPER TEST.')
    facts.append('Dashboard: live price and chart, the desk scan, the open trade and account. Prices are the Hyperliquid desk feed; the broker price has been about 3 to 4 dollars lower, so use the same distances from the broker entry.')
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
