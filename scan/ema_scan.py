#!/usr/bin/env python3
"""PAPER TEST from 16 Nov 2026 (Woody asked for a frequent strategy, EMA 9/21): H1 EMA 9/21 cross.
16 Nov 15:20 (Woody: "H4 should not block trades"): the H4 filter is removed; H4 is logged per trade (with/against) for the review.
  Without H4 the test only held up with entries 07:00-17:00 London: stop 2 ATR train +27.3R PF 2.28, unseen +8.8R PF 1.51, ~1-2 a week;
  at all hours it lost on the unseen half (-0.3R to -9.3R). So: entries 07:00-17:00 weekdays, stop 2 x 1H ATR.
Original version (kept for reference):
Research (backtest/research_2026-11-16/ema921.py, 12 months XAU/USD, R after costs):
  train +17.3R PF 1.71, unseen half +17.9R PF 1.62, ~135 trades a year (2-3 a week), worst losing run ~8R;
  all 15 nearby settings (EMA 5-12 / 20-26, stops 1.5-3 ATR) profitable in both halves. The plain cross with no H4 filter lost.
Rules:
  H4 TREND  EMA50 above EMA200 on completed 4H candles = buys only; below = sells only.
  ENTRY     a 1H candle closes with EMA9 crossing above EMA21 (buy) / below (sell), in the H4 direction. Market order.
  STOP      3 x 1H ATR(14) from entry, fixed.  EXIT  the opposite 9/21 cross on a 1H close, the stop, or Friday 21:00 London.
  BLOCKS    no entries 5 min either side of high-impact USD news, Friday after 19:00, or while the market is closed.
  SIZE      1% risk: ounces = 1% x balance / stop distance (0.01 lot = 1 oz).
Run every 5 minutes by loop.sh; acts on each newly closed 1H candle and checks the stop on 5m candles. Never places orders."""
import csv, datetime as dt, json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from auto_scan import candles, ema, news_block, ldn, L, API, LINE
from brain_link import propose, finish  # 17 Nov: the Neural Brain decides and publishes; this engine only proposes
import requests
G = '/home/user/gold-desk'; ST, LOG = f'{G}/ema_state.json', f'{G}/ema_log.csv'; MSG, RES = f'{G}/scan_msg.txt', f'{G}/scan_result.txt'
BALANCE, RISK, MULT = 182.34, 0.01, 2.0
FIELDS = ['opened', 'side', 'entry', 'stop', 'risk', 'closed', 'exit', 'usd_001', 'R', 'how', 'h4']
def atr_s(b, n=14):
    tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
    o = [None] * len(b); a = sum(tr[:n]) / n; o[n - 1] = a
    for i in range(n, len(b)): a = (a * (n - 1) + tr[i]) / n; o[i] = a
    return o
def mark():
    for _ in range(3):
        try:
            m = requests.post(API, json={'type': 'metaAndAssetCtxs', 'dex': 'xyz'}, timeout=20).json()
            return [float(x['markPx']) for u, x in zip(m[0]['universe'], m[1]) if u['name'] == 'xyz:GOLD'][0]
        except Exception: time.sleep(3)
    raise SystemExit('no mark price; EMA scan skipped')
def rows():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f: csv.writer(f).writerow(FIELDS)
    return list(csv.DictReader(open(LOG, newline='')))
def save(rs):
    with open(LOG, 'w', newline='') as f: w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rs)
def send(text, fb):
    raise PermissionError("17 Nov 2026: strategy engines may not publish; propose to the Neural Brain (brain_link.propose)")

def main():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    now = dt.datetime.now(L); tag = now.strftime('%H:%M'); mins = now.hour * 60 + now.minute; wd = now.weekday()
    h1, h4 = candles('1h', 20), candles('4h', 60); px = mark()
    c1 = [x['c'] for x in h1]; e9, e21, A = ema(c1, 9), ema(c1, 21), atr_s(h1)
    c4 = [x['c'] for x in h4]; e50, e200 = ema(c4, 50)[-1], ema(c4, 200)[-1]; trend4 = 'UP' if e50 > e200 else 'DN'
    st['h4'] = dict(trend=trend4, ema50=round(e50, 1), ema200=round(e200, 1)); st['h1'] = dict(ema9=round(e9[-1], 1), ema21=round(e21[-1], 1), atr=round(A[-1], 1))
    out = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London, gold {px}: {why}'))
    pos = st.get('open'); rs = rows(); new_hour = st.get('last_hour') != h1[-1]['t']
    if pos:
        buy = pos['side'] == 'BUY'; sg = 1 if buy else -1; hit = None
        for x in [x for x in candles('5m', 2) if x['T'] + 1 > pos['checked_ms']]:
            if (x['l'] <= pos['stop']) if buy else (x['h'] >= pos['stop']): hit = ('STOP', pos['stop'], ldn(x['T'] + 1)); break
            pos['checked_ms'] = x['T'] + 1
        if not hit and new_hour and ((e9[-1] < e21[-1]) if buy else (e9[-1] > e21[-1])): hit = ('OPPOSITE CROSS', px, now)
        if not hit and wd == 4 and now.hour >= 21: hit = ('FRIDAY 21:00', px, now)
        st['last_hour'] = h1[-1]['t']
        if hit:
            how, ex, xt = hit; pl = round(sg * (ex - pos['entry']), 2); R = round((pl - 0.4) / pos['risk'], 2)
            for r in rs:
                if r['opened'] == pos['opened'] and not r['closed']:
                    r.update(closed=xt.strftime('%Y-%m-%d %H:%M'), exit=f'{ex:.1f}', usd_001=f'{pl:+.2f}', R=f'{R:+.2f}', how=how)
            save(rs); st['open'] = None
            done_ = [float(r['R']) for r in rs if r['R']]
            msg = '\n'.join([f'🧪 PAPER TEST · EMA 9/21 TRADE CLOSED ({how})', LINE, f'{"🟢" if buy else "🔴"} {pos["side"]} from {pos["entry"]:.1f} (opened {pos["opened"][5:]} London)',
                             f'🏁 Exit {ex:.1f} at {xt.strftime("%a %H:%M")} London', f'💰 {R:+.2f}R = {"+" if R >= 0 else "−"}${abs(R) * BALANCE * RISK:.2f} at 1% risk ({"+" if pl >= 0 else "−"}${abs(pl):.2f} per oz)',
                             LINE, f'📒 EMA paper test so far: {len(done_)} trades, {sum(done_):+.1f}R', 'Not a real trade: nothing to do in MT5.'])
            r = finish(pos, ex, how, xt); return out(f'EMA paper {pos["side"]} closed ({how}) at {ex:.1f}: {R:+.2f}R; {r}')
        st['open'] = pos
        return out(f'EMA paper {pos["side"]} open from {pos["entry"]:.1f}, stop {pos["stop"]:.1f} ({sg * (px - pos["entry"]):+.2f} per oz)')
    closed = wd == 5 or (wd == 6 and mins < 1380) or (wd == 4 and mins >= 19 * 60) or 1320 <= mins < 1380
    if closed: return out('EMA test: no new entries now (market closed, daily break, or Friday after 19:00)')
    if not (wd < 5 and 7 <= now.hour < 17): return out('EMA test: no new entries outside 07:00-17:00 London (weekdays)')
    if not new_hour: return out(f'EMA test: 1H EMA9 {e9[-1]:.1f} vs EMA21 {e21[-1]:.1f}, waiting for a cross {"down" if e9[-1] > e21[-1] else "up"} (H4 {trend4.lower()}, info only)')
    st['last_hour'] = h1[-1]['t']
    up = e9[-1] > e21[-1] and e9[-2] <= e21[-2]; dn = e9[-1] < e21[-1] and e9[-2] >= e21[-2]
    if not (up or dn):
        return out(f'EMA test: no 9/21 cross on the {ldn(h1[-1]["t"]).strftime("%H:%M")} hour (EMA9 {e9[-1]:.1f} vs EMA21 {e21[-1]:.1f}; H4 {trend4.lower()}, info only)')
    blocked, note = news_block(now)
    if blocked: return out(f'EMA test: cross but news block ({note})')
    buy = up; sg = 1 if buy else -1; side = 'BUY' if buy else 'SELL'; stop = round(px - sg * MULT * A[-1], 1); risk = round(abs(px - stop), 2)
    oz = round(BALANCE * RISK / risk, 4); opened = now.strftime('%Y-%m-%d %H:%M'); h4w = 'with' if (trend4 == 'UP') == buy else 'against'
    msg = '\n'.join([f'🧪 PAPER TEST · GOLD EMA 9/21 {side} {"🟢" if buy else "🔴"}', 'Not a real trade: watch only, nothing to do in MT5.', LINE,
                     f'📍 Entry {px:.1f} (1H EMA9 crossed {"above" if buy else "below"} EMA21; H4 trend {trend4.lower()}: {h4w} it)',
                     f'🛑 Stop {stop:.1f} (2 x 1H ATR, −${risk:.0f} per oz) · exit on the opposite cross, no fixed target',
                     f'⚖️ 1% risk of ${BALANCE:.0f} = {oz} oz. At 0.01 lot (1 oz) the risk would be ${risk:.0f}.',
                     '⏰ Out on the opposite 9/21 cross, the stop, or Friday 21:00 London', f'🕐 Signal {tag} London'] + ([f'📰 {note}'] if note else []))
    dec, r = propose('H1', side, px, stop, 'the opposite 1H EMA 9/21 cross (or Friday 21:00)', note)
    rs.append(dict(opened=opened, side=side, entry=f'{px:.1f}', stop=f'{stop:.1f}', risk=f'{risk:.2f}', h4=h4w)); save(rs)
    st['open'] = dict(opened=opened, side=side, entry=px, stop=stop, risk=risk, checked_ms=h1[-1]['T'] + 1, brain_id=dec.get('id'))
    return out(f'EMA PAPER {side} {px:.1f} stop {stop:.1f} (risk ${risk:.2f}/oz); {r}')
if __name__ == '__main__':
    main()
