#!/usr/bin/env python3
"""PAPER TEST from 16 Nov 2026 (Woody): M15 entry, H1 confirmation, H4 bias. Runs next to the H1 EMA 9/21 test to compare.
Rules (the only variant positive in both halves of the 12-month test, backtest/research_2026-11-16/m15entry.py:
 train +67.3R PF 3.73, unseen half +5.6R PF 1.18, ~2 trades a week, worst run ~15R; other M15 variants lost on the unseen half):
  H4 BIAS   EMA50 above EMA200 = buys only; below = sells only (completed 4H candles).
  H1 CONF   1H EMA9 above EMA21 for buys, below for sells (completed 1H candles).
  ENTRY     a 15m candle closes with EMA9 crossing EMA21 in that direction. Market order.
  STOP      2 x 1H ATR(14), fixed.  EXIT  when the H1 confirmation flips (1H EMA9 crosses back), the stop, or Friday 21:00 London.
  BLOCKS    no entries 5 min either side of high-impact USD news, Friday after 19:00, or while the market is closed.
Run every 5 minutes by loop.sh. Never places orders."""
import csv, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from auto_scan import candles, ema, news_block, ldn, L, LINE
from ema_scan import atr_s, mark, send, BALANCE, RISK
G = '/home/user/gold-desk'; ST, LOG = f'{G}/m15_state.json', f'{G}/m15_log.csv'; MSG, RES = f'{G}/scan_msg.txt', f'{G}/scan_result.txt'
FIELDS = ['opened', 'side', 'entry', 'stop', 'risk', 'closed', 'exit', 'usd_001', 'R', 'how']
def rows():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f: csv.writer(f).writerow(FIELDS)
    return list(csv.DictReader(open(LOG, newline='')))
def save(rs):
    with open(LOG, 'w', newline='') as f: w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rs)
def main():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    now = dt.datetime.now(L); tag = now.strftime('%H:%M'); mins = now.hour * 60 + now.minute; wd = now.weekday()
    m15, h1, h4 = candles('15m', 5), candles('1h', 20), candles('4h', 60); px = mark()
    c15 = [x['c'] for x in m15]; f9, f21 = ema(c15, 9), ema(c15, 21)
    c1 = [x['c'] for x in h1]; e9, e21, A = ema(c1, 9), ema(c1, 21), atr_s(h1)
    c4 = [x['c'] for x in h4]; t4 = 'UP' if ema(c4, 50)[-1] > ema(c4, 200)[-1] else 'DN'; h1s = 'UP' if e9[-1] > e21[-1] else 'DN'
    st.update(h4=t4, h1=h1s, m15=dict(ema9=round(f9[-1], 1), ema21=round(f21[-1], 1)))
    out = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London, gold {px}: {why}'))
    pos = st.get('open'); rs = rows()
    if pos:
        buy = pos['side'] == 'BUY'; sg = 1 if buy else -1; hit = None
        for x in [x for x in candles('5m', 2) if x['T'] + 1 > pos['checked_ms']]:
            if (x['l'] <= pos['stop']) if buy else (x['h'] >= pos['stop']): hit = ('STOP', pos['stop'], ldn(x['T'] + 1)); break
            pos['checked_ms'] = x['T'] + 1
        if not hit and h1s != ('UP' if buy else 'DN'): hit = ('H1 FLIPPED', px, now)
        if not hit and wd == 4 and now.hour >= 21: hit = ('FRIDAY 21:00', px, now)
        if hit:
            how, ex, xt = hit; pl = round(sg * (ex - pos['entry']), 2); R = round((pl - 0.4) / pos['risk'], 2)
            for r in rs:
                if r['opened'] == pos['opened'] and not r['closed']:
                    r.update(closed=xt.strftime('%Y-%m-%d %H:%M'), exit=f'{ex:.1f}', usd_001=f'{pl:+.2f}', R=f'{R:+.2f}', how=how)
            save(rs); st['open'] = None; done_ = [float(r['R']) for r in rs if r['R']]
            r = send('\n'.join([f'🧪 PAPER TEST · M15 ENTRY TRADE CLOSED ({how})', LINE, f'{"🟢" if buy else "🔴"} {pos["side"]} from {pos["entry"]:.1f} (opened {pos["opened"][5:]} London)',
                                f'🏁 Exit {ex:.1f} at {xt.strftime("%a %H:%M")} London', f'💰 {R:+.2f}R = {"+" if R >= 0 else "−"}${abs(R) * BALANCE * RISK:.2f} at 1% risk ({"+" if pl >= 0 else "−"}${abs(pl):.2f} per oz)',
                                LINE, f'📒 M15 paper test so far: {len(done_)} trades, {sum(done_):+.1f}R', 'Not a real trade: nothing to do in MT5.']), RES)
            return out(f'M15 paper {pos["side"]} closed ({how}) at {ex:.1f}: {R:+.2f}R; Telegram {r}')
        st['open'] = pos; return out(f'M15 paper {pos["side"]} open from {pos["entry"]:.1f}, stop {pos["stop"]:.1f}')
    closed = wd == 5 or (wd == 6 and mins < 1380) or (wd == 4 and mins >= 19 * 60) or 1320 <= mins < 1380
    if closed or st.get('last_bar') == m15[-1]['t']: return out(f'M15 test: H4 {t4.lower()}, H1 {h1s.lower()}, waiting')
    st['last_bar'] = m15[-1]['t']
    up = f9[-1] > f21[-1] and f9[-2] <= f21[-2]; dn = f9[-1] < f21[-1] and f9[-2] >= f21[-2]
    d = 'UP' if up else 'DN' if dn else None
    if not d or d != t4 or d != h1s: return out(f'M15 test: no 15m cross with H1 and H4 agreeing (H4 {t4.lower()}, H1 {h1s.lower()})')
    blocked, note = news_block(now)
    if blocked: return out(f'M15 test: cross but news block ({note})')
    buy = d == 'UP'; sg = 1 if buy else -1; side = 'BUY' if buy else 'SELL'; stop = round(px - sg * 2 * A[-1], 1); risk = round(abs(px - stop), 2)
    oz = round(BALANCE * RISK / risk, 4); opened = now.strftime('%Y-%m-%d %H:%M')
    r = send('\n'.join([f'🧪 PAPER TEST · GOLD M15 ENTRY {side} {"🟢" if buy else "🔴"}', 'Not a real trade: watch only, nothing to do in MT5.', LINE,
                        f'📍 Entry {px:.1f} (15m EMA9 crossed {"above" if buy else "below"} EMA21; H1 confirms, H4 bias {"up" if buy else "down"})',
                        f'🛑 Stop {stop:.1f} (2 x 1H ATR, −${risk:.0f} per oz) · exit when the H1 EMA9/21 flips',
                        f'⚖️ 1% risk of ${BALANCE:.0f} = {oz} oz. At 0.01 lot (1 oz) the risk would be ${risk:.0f}.', f'🕐 Signal {tag} London'] + ([f'📰 {note}'] if note else [])), MSG)
    rs.append(dict(opened=opened, side=side, entry=f'{px:.1f}', stop=f'{stop:.1f}', risk=f'{risk:.2f}')); save(rs)
    st['open'] = dict(opened=opened, side=side, entry=px, stop=stop, risk=risk, checked_ms=m15[-1]['T'] + 1)
    return out(f'M15 PAPER {side} {px:.1f} stop {stop:.1f}; Telegram {r}')
if __name__ == '__main__':
    main()
