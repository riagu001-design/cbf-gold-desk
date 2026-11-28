#!/usr/bin/env python3
"""D1/H4/H1/M15 BREAKOUT AND RETEST (BRR4), sent to Telegram as TESTED from 28 Nov 2026 (Woody: "D1 Global Market bias,
H4 Primary direction, H1 Setup identification, M15 Entry Confirmation"). Research: backtest/research_2026-11-28/four_tf.py,
rules fixed before testing, OANDA XAU_USD Nov 2023 - Nov 2026: the only one of nine strategies to pass (year 1 +4.5R,
year 2 +23.2R, costs doubled +15.3R, held-back final year +4.0R); 3 years 259 trades, 41% wins, +31.7R, PF 1.20,
max drawdown 16.8R, longest losing run 9. Buys made the profit (+33.4R); sells were flat (-1.8R).
Rules:
  D1 BIAS + H4 DIRECTION  daily and 4H EMA20 above EMA50 with the close above EMA50 = buys only (both below = sells only).
  H1 SETUP     an H1 close above the previous 20 H1 highs (below the 20 lows) = breakout level; valid for 12 H1 candles.
  M15 ENTRY    an M15 candle comes back to the level (within 0.1 M15 ATR) and closes back beyond it in the breakout
               direction, bullish for buys (bearish for sells). Market order at that close.
  STOP         beyond the last 3 M15 candles plus 0.3 M15 ATR, at least 1 M15 ATR.  TARGET  2R.  Out Friday 21:00.
  LIMITS       entries 07:00-20:00 London weekdays, one trade at a time, at most 3 a day; the brain's news and loss checks.
Sized at the 0.01 lot minimum (the edge is modest). Runs every 5 minutes from loop.sh. Never places orders."""
import csv, json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from auto_scan import candles, ema, atr, ldn, L
from ema_scan import mark
from brain_link import propose, finish
G = '/home/user/gold-desk'; ST, LOG = f'{G}/brr4_state.json', f'{G}/brr4_log.csv'
FIELDS = ['opened', 'side', 'entry', 'stop', 'target', 'risk', 'closed', 'exit', 'usd_001', 'R', 'how', 'brain']
RR, MAX_DAY = 2.0, 3


def rows():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f: csv.writer(f).writerow(FIELDS)
    return list(csv.DictReader(open(LOG, newline='')))


def save(rs):
    with open(LOG, 'w', newline='') as f: w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rs)


def bias(b):
    c = [x['c'] for x in b]
    if len(c) < 55: return 0
    e20, e50 = ema(c, 20)[-1], ema(c, 50)[-1]
    return 1 if e20 > e50 and c[-1] > e50 else -1 if e20 < e50 and c[-1] < e50 else 0


def main():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    now = dt.datetime.now(L); tag = now.strftime('%H:%M'); wd = now.weekday(); px = mark()
    out = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London, gold {px}: BRR4 {why}'))
    rs = rows(); pos = st.get('open')
    if pos:  # manage on closed 5m candles, stop first
        buy = pos['side'] == 'BUY'; sg = 1 if buy else -1; hit = None
        for x in [x for x in candles('5m', 2) if x['T'] + 1 > pos['checked_ms']]:
            if (x['l'] <= pos['stop']) if buy else (x['h'] >= pos['stop']): hit = ('STOP', pos['stop'], ldn(x['T'] + 1)); break
            if (x['h'] >= pos['target']) if buy else (x['l'] <= pos['target']): hit = ('TARGET 2R', pos['target'], ldn(x['T'] + 1)); break
            pos['checked_ms'] = x['T'] + 1
        if not hit and wd == 4 and now.hour >= 21: hit = ('FRIDAY 21:00', px, now)
        if hit:
            how, ex, xt = hit; pl = round(sg * (ex - pos['entry']), 2); R = round((pl - 0.4) / pos['risk'], 2)
            for r in rs:
                if r['opened'] == pos['opened'] and not r['closed']:
                    r.update(closed=xt.strftime('%Y-%m-%d %H:%M'), exit=f'{ex:.1f}', usd_001=f'{pl:+.2f}', R=f'{R:+.2f}', how=how)
            save(rs); st['open'] = None
            return out(f'{pos["side"]} closed ({how}) at {ex:.1f}: {R:+.2f}R; {finish(pos, ex, how, xt)}')
        st['open'] = pos
        return out(f'{pos["side"]} open from {pos["entry"]:.1f}, stop {pos["stop"]:.1f}, target {pos["target"]:.1f} ({sg * (px - pos["entry"]):+.2f} per oz)')
    h1 = candles('1h', 20)
    # H1 setup: track the latest breakout level (checked on every new closed H1 candle, at any hour)
    if st.get('h1_last') != h1[-1]['t'] and len(h1) > 21:
        st['h1_last'] = h1[-1]['t']; y = h1[-1]
        d = bias(candles('1d', 120)); d4 = bias(candles('4h', 40)); dirn = d if d == d4 else 0; st['dir'] = dirn
        hi20 = max(x['h'] for x in h1[-21:-1]); lo20 = min(x['l'] for x in h1[-21:-1])
        if dirn > 0 and y['c'] > hi20: st['setup'] = dict(side='BUY', level=hi20, h1_t=y['t'], left=12)
        elif dirn < 0 and y['c'] < lo20: st['setup'] = dict(side='SELL', level=lo20, h1_t=y['t'], left=12)
        elif st.get('setup'):
            st['setup']['left'] -= 1
            if st['setup']['left'] <= 0: st['setup'] = None
    s = st.get('setup'); dirn = st.get('dir', 0)
    if not (wd < 5 and 7 <= now.hour < 20):
        return out('no new entries outside 07:00-20:00 London (weekdays)' + (f'; watching the {s["side"]} retest of {s["level"]:.1f}' if s else ''))
    if not s:
        return out({1: 'D1 and H4 bullish', -1: 'D1 and H4 bearish', 0: 'D1 and H4 do not agree'}[dirn] + ', waiting for an H1 breakout')
    m15 = candles('15m', 5)
    if st.get('m15_last') == m15[-1]['t']: return out(f'watching the {s["side"]} retest of {s["level"]:.1f}, waiting for the next closed 15m candle')
    st['m15_last'] = m15[-1]['t']
    if m15[-1]['t'] <= s['h1_t'] + 3600 * 1000 - 1: return out(f'{s["side"]} breakout at {s["level"]:.1f} just formed')
    x = m15[-1]; A = atr(m15); buy = s['side'] == 'BUY'; sg = 1 if buy else -1; lvl = s['level']
    touched = (x['l'] <= lvl + 0.1 * A) if buy else (x['h'] >= lvl - 0.1 * A)
    held = (x['c'] > lvl and x['c'] > x['o']) if buy else (x['c'] < lvl and x['c'] < x['o'])
    if not (touched and held): return out(f'waiting for a 15m retest of the {s["side"]} breakout level {lvl:.1f} that holds')
    if not (bias(candles('1d', 120)) == sg and bias(candles('4h', 40)) == sg):  # the test checks D1 and H4 again at the entry
        st['setup'] = None; return out(f'{s["side"]} retest held at {lvl:.1f} but D1 and H4 no longer agree: setup dropped')
    today = now.strftime('%Y-%m-%d')
    if sum(1 for r in rs if r['opened'].startswith(today)) >= MAX_DAY: return out(f'{MAX_DAY} entries already today')
    e = x['c']; ext = min(b['l'] for b in m15[-3:]) if buy else max(b['h'] for b in m15[-3:])
    stop = ext - sg * 0.3 * A
    if sg * (e - stop) < A: stop = e - sg * A
    stop = round(stop, 1); risk = round(abs(e - stop), 2); target = round(e + sg * RR * risk, 1)
    dec, r = propose('BRR4', s['side'], e, stop, 'the 2R target or the stop', target=target, grade='T',
                     note=(f'Breakout and retest · D1 and H4 {"bullish" if buy else "bearish"} · H1 closed {"above" if buy else "below"} the 20-candle '
                           f'{"high" if buy else "low"} {lvl:.1f} · a 15m candle retested it and closed back {"above" if buy else "below"}. '
                           f'Passed the 3-year broker test (+31.7R, PF 1.20); about 1 or 2 a week.'))
    opened = now.strftime('%Y-%m-%d %H:%M'); st['setup'] = None
    rs.append(dict(opened=opened, side=s['side'], entry=f'{e:.1f}', stop=f'{stop:.1f}', target=f'{target:.1f}', risk=f'{risk:.2f}', brain=dec.get('verdict'))); save(rs)
    st['open'] = dict(opened=opened, side=s['side'], entry=e, stop=stop, target=target, risk=risk, brain_id=dec.get('id'), checked_ms=x['T'] + 1)
    return out(f'SETUP {s["side"]} {e:.1f} stop {stop:.1f} target {target:.1f}; {r}')


if __name__ == '__main__':
    main()
