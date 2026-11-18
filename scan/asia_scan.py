#!/usr/bin/env python3
"""ASIA RANGE BREAKOUT (Woody 18 Nov 2026: "add Asia low / Asia high to the M15 entry, H1 bias, 2am to 9am, high quality
entry before London opens"). Paper engine: proposes to the Neural Brain, which decides and sends.
Research (backtest/research_2026-11-18/, 12 months XAU/USD 15m, R after $0.40/oz cost):
  chosen rule: train 45 trades +27.5R PF 2.34; unseen half 34 trades +10.8R PF 1.58 (about 1.5 a week, buys and sells alike).
  Neighbouring settings (range to 04:00 or 05:00, stop 1-1.5 ATR, target 1.5-3R) were profitable in both halves.
  Without the H4 trend filter, and with the range ending at 02:00 or 03:00, it LOST on the unseen half, so those are not used.
Rules:
  RANGE   Asia high and low = 15m candles from 23:00 (previous evening) to 04:00 London.
  ENTRY   04:00-09:00 London, weekdays: a 15m candle CLOSES above the Asia high (buy) or below the Asia low (sell),
          the previous 15m close was inside, the 1H EMA9/21 points the same way (H1 bias) and the 4H EMA50/200 trend agrees.
          Market order at the close. One trade a day.
  STOP    1 x 1H ATR(14).  TARGET 2R.  Out at the stop, the target, or 16:00 London (Friday: the same).
Run every 5 minutes by loop.sh. Never places orders."""
import csv, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from auto_scan import candles, ema, news_block, ldn, L
from ema_scan import atr_s, mark
from brain_link import propose, finish
G = '/home/user/gold-desk'; ST, LOG = f'{G}/asia_state.json', f'{G}/asia_log.csv'
FIELDS = ['opened', 'side', 'entry', 'stop', 'target', 'risk', 'asia_high', 'asia_low', 'closed', 'exit', 'R', 'how']


def rows():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f: csv.writer(f).writerow(FIELDS)
    return list(csv.DictReader(open(LOG, newline='')))


def save(rs):
    with open(LOG, 'w', newline='') as f: w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rs)


def asia_range(m15, day):
    start = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(23), L); end = dt.datetime.combine(day, dt.time(4), L)
    r = [x for x in m15 if start <= ldn(x['t']) < end]
    return (max(x['h'] for x in r), min(x['l'] for x in r), len(r)) if r else (None, None, 0)


def main():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    now = dt.datetime.now(L); tag = now.strftime('%H:%M'); px = mark(); today = now.date()
    out = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London, gold {px}: {why}'))
    m15 = candles('15m', 3); rs = rows(); pos = st.get('open')
    ah, al, n = asia_range(m15, today)
    if ah: st['range'] = dict(day=str(today), high=round(ah, 1), low=round(al, 1), bars=n)
    if pos:
        buy = pos['side'] == 'BUY'; sg = 1 if buy else -1; hit = None
        for x in [x for x in candles('5m', 2) if x['T'] + 1 > pos['checked_ms']]:
            if (x['l'] <= pos['stop']) if buy else (x['h'] >= pos['stop']): hit = ('STOP', pos['stop'], ldn(x['T'] + 1)); break
            if (x['h'] >= pos['target']) if buy else (x['l'] <= pos['target']): hit = ('TARGET 2R', pos['target'], ldn(x['T'] + 1)); break
            pos['checked_ms'] = x['T'] + 1
        if not hit and now.hour >= 16: hit = ('16:00 EXIT', px, now)
        if hit:
            how, ex, xt = hit; R = round((sg * (ex - pos['entry']) - 0.4) / pos['risk'], 2)
            for r in rs:
                if r['opened'] == pos['opened'] and not r['closed']: r.update(closed=xt.strftime('%Y-%m-%d %H:%M'), exit=f'{ex:.1f}', R=f'{R:+.2f}', how=how)
            save(rs); st['open'] = None; b = finish(pos, ex, how, xt)
            return out(f'ASIA paper {pos["side"]} closed ({how}) at {ex:.1f}: {R:+.2f}R; {b}')
        return out(f'ASIA paper {pos["side"]} open from {pos["entry"]:.1f}, stop {pos["stop"]:.1f}, target {pos["target"]:.1f} ({sg * (px - pos["entry"]):+.2f} per oz)')
    if now.weekday() > 4 or not (4 <= now.hour < 9):
        return out('Asia test: entries 04:00-09:00 London weekdays only' + (f' (today Asia high {ah:.1f}, low {al:.1f})' if ah and now.hour >= 4 else ''))
    if st.get('traded') == str(today): return out('Asia test: already traded today (one a day)')
    if not ah or n < 12: return out(f'Asia test: Asia range incomplete ({n} candles)')
    done = [x for x in m15 if x['T'] < now.timestamp() * 1000]
    last, prev = done[-1], done[-2]
    if st.get('last_bar') == last['t']: return out(f'Asia test: waiting for a 15m close beyond the Asia range {al:.1f}-{ah:.1f}')
    st['last_bar'] = last['t']
    up = last['c'] > ah and prev['c'] <= ah; dn = last['c'] < al and prev['c'] >= al
    if not (up or dn): return out(f'Asia test: 15m close {last["c"]:.1f} inside or already beyond the Asia range {al:.1f}-{ah:.1f}')
    h1 = [x for x in candles('1h', 14) if x['T'] < now.timestamp() * 1000]; c1 = [x['c'] for x in h1]
    h4 = [x for x in candles('4h', 60) if x['T'] < now.timestamp() * 1000]; c4 = [x['c'] for x in h4]
    bias1 = ema(c1, 9)[-1] > ema(c1, 21)[-1]; trend4 = ema(c4, 50)[-1] > ema(c4, 200)[-1]
    side = 'BUY' if up else 'SELL'
    if bias1 != up: return out(f'Asia test: {side} break of the Asia range but the 1H EMA9/21 bias disagrees')
    if trend4 != up: return out(f'Asia test: {side} break of the Asia range but the 4H EMA50/200 trend disagrees')
    blocked, note = news_block(now)
    if blocked: return out(f'Asia test: {side} break but news block ({note})')
    sg = 1 if up else -1; risk = round(atr_s(h1)[-1], 2); en = last['c']
    stop = round(en - sg * risk, 1); target = round(en + sg * 2 * risk, 1); opened = now.strftime('%Y-%m-%d %H:%M')
    dec, r = propose('ASIA', side, en, stop, 'the 2R target, the stop, or 16:00 London',
                     f'Asia range {al:.1f}-{ah:.1f} broken on the 15m close; H1 bias and H4 trend agree', target=target)
    rs.append(dict(opened=opened, side=side, entry=f'{en:.1f}', stop=f'{stop:.1f}', target=f'{target:.1f}', risk=f'{risk:.2f}',
                   asia_high=f'{ah:.1f}', asia_low=f'{al:.1f}')); save(rs)
    st.update(traded=str(today), open=dict(opened=opened, side=side, entry=en, stop=stop, target=target, risk=risk, brain_id=dec.get('id'), checked_ms=last['T'] + 1))
    return out(f'ASIA PAPER {side} {en:.1f} stop {stop:.1f} target {target:.1f} (Asia range {al:.1f}-{ah:.1f}); {r}')


if __name__ == '__main__':
    main()
