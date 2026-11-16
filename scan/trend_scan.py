#!/usr/bin/env python3
"""PAPER TEST (from 16 Nov 2026, Woody's yes): 1H trend breakout on gold, replacing the 5m dip setups.
Rule (backtest/research_2026-11-16, 12 months XAU/USD: +$1,189 at 0.01 lot, PF 1.30, 12 of 12 nearby settings profitable;
unseen half +$400 PF 1.25; worst losing run ~$540 at 0.01 lot):
  ENTRY  when a 1H candle closes above the highest high (BUY) or below the lowest low (SELL) of the 20 hours before it.
  STOP   3 x 1H ATR(14) from entry, trailed after every closed hour to (close -/+ 3 x ATR), never loosened. No target.
  EXIT   when price touches the trailing stop, or Friday 21:00 London. One position at a time.
  BLOCK  no entries 5 min either side of high-impact USD news; none while the market is closed (Sun 23:00-Fri 20:00, break 22-23).
Run every 5 minutes by loop.sh. Sends Telegram messages marked PAPER TEST. Never places orders."""
import csv, datetime as dt, json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from auto_scan import candles, atr, ema, ldn, news_block, send_telegram, L, API, LINE
import requests
DESK = '/home/user/gold-desk'; ST = f'{DESK}/trend_state.json'; LOG = f'{DESK}/trend_log.csv'
MSG, RES = f'{DESK}/scan_msg.txt', f'{DESK}/scan_result.txt'
N, MULT, ACCOUNT = 20, 3.0, 182.34
FIELDS = ['opened_london', 'side', 'entry', 'first_stop', 'risk_usd_001', 'closed_london', 'exit', 'result_usd_001', 'R', 'how']
def atr_series(b, n=14):
    tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
    o = [None] * len(b); a = sum(tr[:n]) / n; o[n - 1] = a
    for i in range(n, len(b)): a = (a * (n - 1) + tr[i]) / n; o[i] = a
    return o
def mark_price():
    for _ in range(3):
        try:
            m = requests.post(API, json={'type': 'metaAndAssetCtxs', 'dex': 'xyz'}, timeout=20).json()
            return [float(x['markPx']) for u, x in zip(m[0]['universe'], m[1]) if u['name'] == 'xyz:GOLD'][0]
        except Exception: time.sleep(3)
    raise SystemExit('no mark price; trend scan skipped')
def log_rows():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f: csv.writer(f).writerow(FIELDS)
    return list(csv.DictReader(open(LOG, newline='')))
def save_rows(rows):
    with open(LOG, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
def send(text, fallback):
    if os.environ.get('SCAN_TEST') == '1': print('MESSAGE (test, not sent):\n' + text); return 'test'
    r = send_telegram(text)
    if not r.startswith('ok'): open(fallback, 'w').write(text)
    return r
def main():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    now = dt.datetime.now(L); tag = now.strftime('%H:%M'); mins = now.hour * 60 + now.minute; wd = now.weekday()
    h1 = candles('1h', 30); A = atr_series(h1); mark = mark_price()
    out = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London, gold {mark}: {why}'))
    pos = st.get('open'); rows = log_rows()
    if pos:
        buy = pos['side'] == 'BUY'; sg = 1 if buy else -1
        m5 = [x for x in candles('5m', 2) if x['T'] + 1 > pos['checked_ms']]
        hit = None
        for x in m5:  # stop first, on every closed 5m candle since the last check
            if (x['l'] <= pos['stop']) if buy else (x['h'] >= pos['stop']): hit = ('STOP', pos['stop'], ldn(x['T'] + 1)); break
        if not hit and wd == 4 and now.hour >= 21: hit = ('FRIDAY 21:00', mark, now)
        if m5: pos['checked_ms'] = m5[-1]['T'] + 1
        if hit:
            how, px, xt = hit; pl = round(sg * (px - pos['entry']), 2); R = round(pl / pos['risk'], 2)
            for r in rows:
                if r['opened_london'] == pos['opened'] and not r['result_usd_001']:
                    r.update(closed_london=xt.strftime('%Y-%m-%d %H:%M'), exit=f'{px:.1f}', result_usd_001=f'{pl:+.2f}', R=f'{R:+.2f}', how=how)
            save_rows(rows); st['open'] = None
            tot = sum(float(r['result_usd_001']) for r in rows if r['result_usd_001'])
            n = sum(1 for r in rows if r['result_usd_001'])
            msg = '\n'.join([f'🧪 PAPER TEST · TREND TRADE CLOSED ({how})', LINE,
                             f'{"🟢" if buy else "🔴"} {pos["side"]} from {pos["entry"]:.1f} (opened {pos["opened"][5:]} London)',
                             f'🏁 Exit: {px:.1f} at {xt.strftime("%a %H:%M")} London',
                             f'💰 Paper result: {"+" if pl >= 0 else "−"}${abs(pl):.2f} at 0.01 lot ({R:+.1f}R) · {"+" if pl >= 0 else "−"}${abs(pl) / 10:.2f} at 0.1 oz',
                             LINE, f'📒 Paper test so far: {n} trade{"s" if n != 1 else ""}, {"+" if tot >= 0 else "−"}${abs(tot):.2f} at 0.01 lot',
                             'Not a real trade: nothing to do in MT5.'])
            r = send(msg, RES)
            return out(f'paper {pos["side"]} closed ({how}) at {px:.1f}: {pl:+.2f} at 0.01 lot; Telegram {r}')
        # trail after each newly closed hour
        for i, x in enumerate(h1):
            if x['T'] + 1 > pos['trail_ms'] and A[i]:
                ns = x['c'] - sg * MULT * A[i]
                pos['stop'] = round(max(pos['stop'], ns) if buy else min(pos['stop'], ns), 1); pos['trail_ms'] = x['T'] + 1
        st['open'] = pos
        return out(f'paper {pos["side"]} open from {pos["entry"]:.1f}, trailing stop {pos["stop"]:.1f} ({sg * (mark - pos["entry"]):+.2f} at 0.01 lot)')
    closed = wd == 5 or (wd == 6 and mins < 1380) or (wd == 4 and mins >= 1200) or 1320 <= mins < 1380
    if closed: return out('market closed (trend paper test: trading Sun 23:00 to Fri 20:00 London, break 22:00-23:00)')
    bar = h1[-1]
    if st.get('last_hour') == bar['t']: return out(f'trend test: no breakout on the {ldn(bar["t"]).strftime("%H:%M")} hour (20h range {min(x["l"] for x in h1[-21:-1]):.1f}-{max(x["h"] for x in h1[-21:-1]):.1f})')
    st['last_hour'] = bar['t']
    hi, lo = max(x['h'] for x in h1[-N - 1:-1]), min(x['l'] for x in h1[-N - 1:-1]); a = A[-1]
    buy, sell = bar['c'] > hi, bar['c'] < lo
    if not (buy or sell): return out(f'trend test: no breakout (1H close {bar["c"]:.1f} inside the 20h range {lo:.1f}-{hi:.1f})')
    blocked, note = news_block(now)
    if blocked: return out(f'trend test: breakout but news block ({note})')
    sg = 1 if buy else -1; side = 'BUY' if buy else 'SELL'; stop = round(mark - sg * MULT * a, 1); risk = round(abs(mark - stop), 2)
    oz = max(0.003, round(0.02 * ACCOUNT / risk, 3))  # size that risks 2% of the account (Hyperliquid allows 0.0001 oz steps, ~$10 minimum)
    opened = now.strftime('%Y-%m-%d %H:%M')
    msg = '\n'.join([f'🧪 PAPER TEST · GOLD TREND {side} {"🟢" if buy else "🔴"}', 'Not a real trade: watch only, nothing to do in MT5.', LINE,
                     f'📍 Entry: {mark:.1f} (1H closed {"above the 20-hour high" if buy else "below the 20-hour low"} {hi if buy else lo:.1f})',
                     f'🛑 Trailing stop: {stop:.1f} (3 x 1H ATR), moved every hour, never loosened · no fixed target',
                     f'⚖️ Risk: ${risk:.2f} at 0.01 lot · ${risk / 10:.2f} at 0.1 oz · 2% of ${ACCOUNT:.0f} = {oz} oz',
                     '⏰ Out when the stop is hit, or Friday 21:00 London', LINE,
                     'ℹ️ Paper test of the 1H trend breakout (12-month backtest: +$1,189 at 0.01 lot, 35% wins, worst run ~$540).',
                     f'🕐 Signal {tag} London'] + ([f'📰 {note}'] if note else []))
    r = send(msg, MSG)
    rows.append(dict(opened_london=opened, side=side, entry=f'{mark:.1f}', first_stop=f'{stop:.1f}', risk_usd_001=f'{risk:.2f}')); save_rows(rows)
    st['open'] = dict(opened=opened, side=side, entry=mark, stop=stop, risk=risk, checked_ms=bar['T'] + 1, trail_ms=bar['T'] + 1)
    return out(f'PAPER TREND {side} {mark:.1f} trailing stop {stop:.1f} (risk ${risk:.2f} at 0.01 lot); Telegram {r}')
if __name__ == '__main__':
    main()
