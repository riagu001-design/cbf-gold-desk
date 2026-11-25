#!/usr/bin/env python3
"""LIVE from 24 Nov 2026 (Woody, 23 Nov: "Yes switch it on"): TREND PULLBACK engine, sent to Telegram as a B-grade
(half size) signal by the Neural Brain, reviewed after 20 trades.
Rules (backtest/research_2026-11-23/pullback.py, the version positive in all four quarters of the 12-month test:
 +27.4R over 321 trades, PF 1.14, unseen half +10.5R; Hyperliquid feed 16-23 Nov +7.6R on 8 trades):
  CONTROL  completed 1H candles: EMA20 above EMA50, +DI above -DI, ADX(14) 20 or more = buyers (sellers mirrored).
           The 15m DI must agree (+DI above -DI for buys).
  ENTRY    a closed 15m candle tags the 15m EMA20 (low within 0.1 ATR of it) and closes back above it, bullish and above
           the 15m EMA50 (sells mirrored). Market order at that close.
  STOP     beyond the last three 15m candles plus 0.3 x 15m ATR, at least 1 x 15m ATR.  TARGET  2R.  Friday 21:00 exit.
  H4       (from 23 Nov 20:00) buys only when the last two confirmed H4 swing highs and lows are both higher, sells
           only when both lower (h4_filter.py).
  LIMITS   entries 07:00-20:00 London weekdays, one trade at a time, at most 3 a day; the brain's news, freshness,
           stop-size, daily-loss and conflict checks apply.
Run every 5 minutes by loop.sh. Never places orders."""
import csv, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from auto_scan import candles, ema, atr, ldn, L
from bars_json import dmi
from ema_scan import mark
from brain_link import propose, finish
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backtest', 'research_2026-11-23'))
from four_setups import pivots
G = '/home/user/gold-desk'; ST, LOG = f'{G}/pb_state.json', f'{G}/pb_log.csv'
FIELDS = ['opened', 'side', 'entry', 'stop', 'target', 'risk', 'closed', 'exit', 'usd_001', 'R', 'how', 'brain']
ADX_MIN, RR, MAX_DAY = 20, 2.0, 3


def rows():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f: csv.writer(f).writerow(FIELDS)
    return list(csv.DictReader(open(LOG, newline='')))


def save(rs):
    with open(LOG, 'w', newline='') as f: w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rs)


def main():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    now = dt.datetime.now(L); tag = now.strftime('%H:%M'); wd = now.weekday(); px = mark()
    out = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London, gold {px}: PB {why}'))
    rs = rows(); pos = st.get('open')
    if pos:  # manage the open trade on closed 5m candles since entry (stop checked first: worst case)
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
    if not (wd < 5 and 7 <= now.hour < 20): return out('no new entries outside 07:00-20:00 London (weekdays)')
    m15, h1 = candles('15m', 5), candles('1h', 20)
    if st.get('last_bar') == m15[-1]['t']: return out('waiting for the next closed 15m candle')
    st['last_bar'] = m15[-1]['t']
    c1 = [x['c'] for x in h1]; d1 = dmi(h1); e20h, e50h = ema(c1, 20)[-1], ema(c1, 50)[-1]
    if not d1 or d1['adx'] < ADX_MIN: return out(f'1H ADX {d1["adx"] if d1 else "?"} under {ADX_MIN}: no clear control')
    buy = e20h > e50h and d1['pdi'] > d1['mdi']; sell = e20h < e50h and d1['mdi'] > d1['pdi']
    if not (buy or sell): return out(f'1H EMA20/50 and DI disagree (+DI {d1["pdi"]}, -DI {d1["mdi"]})')
    # H4 STRUCTURE FILTER (23 Nov 2026 20:00, Woody: "Yes switch it on"; backtest h4_filter.py: trades 321 -> 140,
    # avg +0.09R -> +0.23R, worst run 13.8R -> 7.6R; unseen half +10.5R on 173 trades -> +8.6R on 73).
    # Buys only when the last two confirmed H4 swing highs AND lows are both higher; sells only when both lower.
    h4 = candles('4h', 40); ph, pl = pivots(h4, 2)
    if len(ph) < 2 or len(pl) < 2: return out('not enough H4 swings yet')
    up = ph[-1][1] > ph[-2][1] and pl[-1][1] > pl[-2][1]; dn = ph[-1][1] < ph[-2][1] and pl[-1][1] < pl[-2][1]
    h4txt = f'H4 highs {ph[-2][1]:.1f} -> {ph[-1][1]:.1f}, lows {pl[-2][1]:.1f} -> {pl[-1][1]:.1f}'
    # 25 Nov 2026 (Woody: "H4 should not be a hard blocker"): H4 agreeing = B-grade half size; mixed or against = C-grade,
    # sent at the 0.01 lot minimum with a warning (test to 25 Nov: agree +33.5R / 135, mixed -5.0R / 127, against +6.5R / 67).
    h4ok = up if buy else dn
    d15 = dmi(m15)
    if not d15 or (buy and d15['pdi'] <= d15['mdi']) or (sell and d15['mdi'] <= d15['pdi']):
        return out(f'1H {"buyers" if buy else "sellers"} (ADX {d1["adx"]}) but the 15m DI disagrees')
    c15 = [x['c'] for x in m15]; e20, e50 = ema(c15, 20)[-1], ema(c15, 50)[-1]; A = atr(m15); x = m15[-1]
    if buy: ok = x['l'] <= e20 + 0.1 * A and x['c'] > e20 and x['c'] > x['o'] and x['c'] > e50
    else: ok = x['h'] >= e20 - 0.1 * A and x['c'] < e20 and x['c'] < x['o'] and x['c'] < e50
    side = 'BUY' if buy else 'SELL'
    if not ok: return out(f'1H {"buyers" if buy else "sellers"} (ADX {d1["adx"]}), waiting for a 15m dip to the EMA20 {e20:.1f} that holds')
    today = now.strftime('%Y-%m-%d')
    if sum(1 for r in rs if r['opened'].startswith(today)) >= MAX_DAY: return out(f'{MAX_DAY} entries already today')
    sg = 1 if buy else -1; e = x['c']
    ext = min(b['l'] for b in m15[-3:]) if buy else max(b['h'] for b in m15[-3:])
    stop = ext - sg * 0.3 * A
    if sg * (e - stop) < A: stop = e - sg * A
    stop = round(stop, 1); risk = round(abs(e - stop), 2); target = round(e + sg * RR * risk, 1)
    h4why = ("higher highs and lows" if buy else "lower highs and lows") if h4ok else f'NOT CONFIRMED ({h4txt})'
    dec, r = propose('PB', side, e, stop, 'the 2R target or the stop', (f'Trend Pullback · 1H {"BULLISH" if buy else "BEARISH"} (ADX {d1["adx"]:.1f}) · H4 '
         f'{h4why} · M15 EMA 20/50 ({e20:.2f}/{e50:.2f}) · '
         f'15m candle {"dipped to" if buy else "rallied to"} the EMA20 and closed back {"above" if buy else "below"} it'), target=target, grade=None if h4ok else 'C')
    opened = now.strftime('%Y-%m-%d %H:%M')
    rs.append(dict(opened=opened, side=side, entry=f'{e:.1f}', stop=f'{stop:.1f}', target=f'{target:.1f}', risk=f'{risk:.2f}', brain=dec.get('verdict'))); save(rs)
    st['open'] = dict(opened=opened, side=side, entry=e, stop=stop, target=target, risk=risk, brain_id=dec.get('id'), checked_ms=x['T'] + 1)
    return out(f'SETUP {side} {e:.1f} stop {stop:.1f} target {target:.1f}; {r}')


if __name__ == '__main__':
    main()
