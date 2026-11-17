#!/usr/bin/env python3
"""PAPER TEST from 16 Nov 2026 (Woody: "Yes add the 4H test"): H4 EMA 9/21 cross, fixed 2R target. Adds about one setup a week,
at any hour, so quiet London days are covered.
Research (backtest/research_2026-11-16/ema921.py, 12 months XAU/USD, R after $0.40/oz cost, no trend filter, all hours):
  stop 2 x 4H ATR: train 27 trades +8.7R PF 1.62, unseen half 31 trades +10.9R PF 1.76, ~1 trade a week;
  stops 1.5 / 2.5 / 3 ATR also profitable in both halves (unseen PF 1.64 / 1.94 / 1.95).
Rules:
  ENTRY   a completed 4H candle closes with EMA9 crossing above EMA21 (buy) or below (sell). Market order.
  STOP    2 x 4H ATR(14), fixed.  TARGET  2R.  Out at the stop, the target, or Friday 21:00 London.
  BLOCKS  no entries 5 min either side of high-impact USD news, Friday after 19:00, or while the market is closed.
Run every 5 minutes by loop.sh; acts on each newly closed 4H candle and checks stop and target on 5m candles. Never places orders."""
import csv, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from auto_scan import candles, ema, news_block, ldn, L, LINE
from ema_scan import atr_s, mark, BALANCE, RISK
from brain_link import propose, finish  # 17 Nov: the Neural Brain decides and publishes; this engine only proposes
G = '/home/user/gold-desk'; ST, LOG = f'{G}/h4_state.json', f'{G}/h4_log.csv'; MSG, RES = f'{G}/scan_msg.txt', f'{G}/scan_result.txt'
MULT = 2.0
FIELDS = ['opened', 'side', 'entry', 'stop', 'target', 'risk', 'closed', 'exit', 'usd_001', 'R', 'how']
def rows():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f: csv.writer(f).writerow(FIELDS)
    return list(csv.DictReader(open(LOG, newline='')))
def save(rs):
    with open(LOG, 'w', newline='') as f: w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rs)
def main():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    now = dt.datetime.now(L); tag = now.strftime('%H:%M'); mins = now.hour * 60 + now.minute; wd = now.weekday()
    h4 = candles('4h', 30); px = mark()
    c = [x['c'] for x in h4]; e9, e21, A = ema(c, 9), ema(c, 21), atr_s(h4)
    st['h4'] = dict(ema9=round(e9[-1], 1), ema21=round(e21[-1], 1), atr=round(A[-1], 1), bar=ldn(h4[-1]['T'] + 1).strftime('%a %H:%M'))
    out = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London, gold {px}: {why}'))
    pos = st.get('open'); rs = rows(); new_bar = st.get('last_bar') != h4[-1]['t']
    if pos:
        buy = pos['side'] == 'BUY'; sg = 1 if buy else -1; hit = None
        for x in [x for x in candles('5m', 2) if x['T'] + 1 > pos['checked_ms']]:
            if (x['l'] <= pos['stop']) if buy else (x['h'] >= pos['stop']): hit = ('STOP', pos['stop'], ldn(x['T'] + 1)); break
            if (x['h'] >= pos['target']) if buy else (x['l'] <= pos['target']): hit = ('TARGET 2R', pos['target'], ldn(x['T'] + 1)); break
            pos['checked_ms'] = x['T'] + 1
        if not hit and wd == 4 and now.hour >= 21: hit = ('FRIDAY 21:00', px, now)
        st['last_bar'] = h4[-1]['t']
        if hit:
            how, ex, xt = hit; pl = round(sg * (ex - pos['entry']), 2); R = round((pl - 0.4) / pos['risk'], 2)
            for r in rs:
                if r['opened'] == pos['opened'] and not r['closed']:
                    r.update(closed=xt.strftime('%Y-%m-%d %H:%M'), exit=f'{ex:.1f}', usd_001=f'{pl:+.2f}', R=f'{R:+.2f}', how=how)
            save(rs); st['open'] = None; done_ = [float(r['R']) for r in rs if r['R']]
            r = finish(pos, ex, how, xt)
            return out(f'4H paper {pos["side"]} closed ({how}) at {ex:.1f}: {R:+.2f}R; {r}')
        st['open'] = pos
        return out(f'4H paper {pos["side"]} open from {pos["entry"]:.1f}, stop {pos["stop"]:.1f}, target {pos["target"]:.1f} ({sg * (px - pos["entry"]):+.2f} per oz)')
    want = 'down' if e9[-1] > e21[-1] else 'up'
    closed = wd == 5 or (wd == 6 and mins < 1380) or (wd == 4 and mins >= 19 * 60) or 1320 <= mins < 1380
    if closed: st['last_bar'] = h4[-1]['t']; return out(f'4H test: no new entries now (market closed, daily break, or Friday after 19:00)')
    if not new_bar: return out(f'4H test: 4H EMA9 {e9[-1]:.1f} vs EMA21 {e21[-1]:.1f}, waiting for a cross {want}')
    st['last_bar'] = h4[-1]['t']
    up = e9[-1] > e21[-1] and e9[-2] <= e21[-2]; dn = e9[-1] < e21[-1] and e9[-2] >= e21[-2]
    if not (up or dn): return out(f'4H test: no 9/21 cross on the 4H candle that closed {st["h4"]["bar"]} (EMA9 {e9[-1]:.1f} vs EMA21 {e21[-1]:.1f})')
    blocked, note = news_block(now)
    if blocked: return out(f'4H test: cross but news block ({note})')
    buy = up; sg = 1 if buy else -1; side = 'BUY' if buy else 'SELL'; risk = round(MULT * A[-1], 2)
    stop = round(px - sg * risk, 1); target = round(px + sg * 2 * risk, 1); oz = round(BALANCE * RISK / risk, 4); opened = now.strftime('%Y-%m-%d %H:%M')
    dec, r = propose('4H', side, px, stop, 'the 2R target, the stop, or Friday 21:00', note, target=target)
    rs.append(dict(opened=opened, side=side, entry=f'{px:.1f}', stop=f'{stop:.1f}', target=f'{target:.1f}', risk=f'{risk:.2f}')); save(rs)
    st['open'] = dict(opened=opened, side=side, entry=px, stop=stop, target=target, risk=risk, brain_id=dec.get('id'), checked_ms=h4[-1]['T'] + 1)
    return out(f'4H PAPER {side} {px:.1f} stop {stop:.1f} target {target:.1f}; {r}')
if __name__ == '__main__':
    main()
