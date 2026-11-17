#!/usr/bin/env python3
"""GOLD SWING PULLBACK + MACRO FILTER (Woody's strategies 1 and 4, from 16 Nov 2026). PAPER TEST.
Research (backtest/research_2026-11-16/swing.py, 20 years of daily gold futures, both decades profitable):
  both sides, macro block: 2007-16 +16.4R PF 1.51, 2017-26 +13.0R PF 1.42, ~6 trades a year, worst losing run ~12R.
Rules (daily candles, gold futures GCUSD from FMP):
  TREND   EMA50 above EMA200 -> buys only; below -> sells only.
  MACRO   4-week change of the US 10y real yield (DFII10) and the broad dollar (DTWEXBGS), data a week old:
          both falling = bullish, both rising = bearish. A trade against a clear macro bias is skipped.
  SETUP   the day's low (buy) / high (sell) touches the 21-day EMA, and the day closes back beyond it as a
          bullish (buy) / bearish (sell) candle = the confirmation.
  ENTRY   market order after that daily close (desk messages it; the trader enters at the live price).
  STOP    beyond the 5-day swing low/high, 0.2 x daily ATR further.  TARGET 2R.  Out after 30 trading days.
  SIZE    risk 1% of the account: size = 1% x balance / stop distance (in ounces; 0.01 lot = 1 oz).
Modes:  daily   (run by the session once a day after 22:00 London, after refreshing gold_daily.json): checks the last
                completed day, opens or closes the paper position, messages Telegram.
        status  (run by loop.sh every 5 min): one log line with the live price against the setup levels. Never orders."""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from auto_scan import L, API, LINE
from brain_link import propose, finish  # 17 Nov: the Neural Brain decides and publishes; this engine only proposes
import requests
G = '/home/user/gold-desk'; DAILY, MACRO, ST, LOG = f'{G}/gold_daily.json', f'{G}/macro_weekly.json', f'{G}/swing_state.json', f'{G}/swing_log.csv'
MSG, RES = f'{G}/scan_msg.txt', f'{G}/scan_result.txt'
BALANCE, RISK = 182.34, 0.01
def ema(x, n):
    k = 2 / (n + 1); o = [x[0]]
    for v in x[1:]: o.append(v * k + o[-1] * (1 - k))
    return o
def load():
    b = [dict(d=r[0], o=r[1], h=r[2], l=r[3], c=r[4]) for r in json.load(open(DAILY))['bars']]
    c = [x['c'] for x in b]; tr = [b[0]['h'] - b[0]['l']] + [max(x['h'] - x['l'], abs(x['h'] - p['c']), abs(x['l'] - p['c'])) for p, x in zip(b, b[1:])]
    A = [None] * len(b); a = sum(tr[:14]) / 14
    for i in range(14, len(b)): a = (a * 13 + tr[i]) / 14; A[i] = a
    return b, ema(c, 21), ema(c, 50), ema(c, 200), A
def macro(day):
    S = json.load(open(MACRO)); cut = (dt.date.fromisoformat(day) - dt.timedelta(days=7)).isoformat(); ch = []
    for nm in ('ry', 'usd'):
        s = [x for x in S[nm] if x[0] <= cut]
        if len(s) < 5: return None, None, None
        ch.append(s[-1][1] - s[-5][1])
    ry, usd = ch
    return ('UP' if ry < 0 and usd < 0 else 'DN' if ry > 0 and usd > 0 else 'MIX'), ry, usd
def mark():
    m = requests.post(API, json={'type': 'metaAndAssetCtxs', 'dex': 'xyz'}, timeout=20).json()
    return [float(x['markPx']) for u, x in zip(m[0]['universe'], m[1]) if u['name'] == 'xyz:GOLD'][0]
def send(text, fb):
    raise PermissionError("17 Nov 2026: strategy engines may not publish; propose to the Neural Brain (brain_link.propose)")
def logrow(row):
    new = not os.path.exists(LOG)
    with open(LOG, 'a') as f:
        if new: f.write('opened,side,entry,stop,target,closed,exit,R,how\n')
        f.write(','.join(str(row.get(k, '')) for k in ('opened', 'side', 'entry', 'stop', 'target', 'closed', 'exit', 'R', 'how')) + '\n')
def daily():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    b, e21, e50, e200, A = load(); i = len(b) - 1; x = b[i]; now = dt.datetime.now(L)
    px = mark(); basis = round(x['c'] - px, 1)  # futures minus the desk's spot price, to translate levels
    st['basis'] = basis; st['levels'] = dict(day=x['d'], ema21=round(e21[i], 1), ema50=round(e50[i], 1), ema200=round(e200[i], 1), atr=round(A[i], 1))
    pos = st.get('open')
    if pos:
        sg = 1 if pos['side'] == 'BUY' else -1; how = None
        for y in [y for y in b if y['d'] > pos['last_day']]:
            pos['days'] += 1; pos['last_day'] = y['d']
            if (y['l'] <= pos['stop']) if sg > 0 else (y['h'] >= pos['stop']): how, ex = 'STOP', pos['stop']; break
            if (y['h'] >= pos['target']) if sg > 0 else (y['l'] <= pos['target']): how, ex = 'TARGET', pos['target']; break
            if pos['days'] >= 30: how, ex = '30 DAYS', y['c']; break
        if how:
            R = round((sg * (ex - pos['entry']) - 0.4) / pos['risk'], 2)
            logrow(dict(pos, closed=pos['last_day'], exit=ex, R=R, how=how)); st['open'] = None
            r = finish(pos, ex - basis, how, now)  # brain works in desk (spot) prices
            json.dump(st, open(ST, 'w'), indent=1); print(f'swing daily {x["d"]}: paper {pos["side"]} closed {how} {R:+.2f}R; {r}'); return
        json.dump(st, open(ST, 'w'), indent=1); print(f'swing daily {x["d"]}: paper {pos["side"]} open, day {pos["days"]}'); return
    up, dn = e50[i] > e200[i], e50[i] < e200[i]
    buy = up and x['l'] <= e21[i] and x['c'] > e21[i] and x['c'] > x['o']
    sell = dn and x['h'] >= e21[i] and x['c'] < e21[i] and x['c'] < x['o']
    mb, ry, usd = macro(x['d']); st['macro'] = dict(bias=mb, real_yield_4w=ry, dollar_4w=usd)
    if not (buy or sell):
        json.dump(st, open(ST, 'w'), indent=1)
        print(f'swing daily {x["d"]}: no setup ({"up" if up else "down"}trend, close {x["c"]:.1f}, EMA21 {e21[i]:.1f}, macro {mb})'); return
    side = 'BUY' if buy else 'SELL'; sg = 1 if buy else -1
    if mb in ('UP', 'DN') and mb != ('UP' if buy else 'DN'):
        json.dump(st, open(ST, 'w'), indent=1); print(f'swing daily {x["d"]}: {side} setup skipped, macro bias {mb}'); return
    sw = min(y['l'] for y in b[i - 4:i + 1]) if buy else max(y['h'] for y in b[i - 4:i + 1])
    stop = round(sw - sg * 0.2 * A[i], 1); en = x['c']; R = abs(en - stop); tgt = round(en + sg * 2 * R, 1)
    oz = round(BALANCE * RISK / R, 4)
    st['open'] = dict(opened=x['d'], side=side, entry=en, stop=stop, target=tgt, risk=R, days=0, last_day=x['d'])
    logrow(dict(opened=x['d'], side=side, entry=en, stop=stop, target=tgt))
    dec, r = propose('SWING', side, px, stop - basis, 'the 2R target, the stop, or 30 trading days', f'macro bias {mb}; daily setup, prices converted from futures (basis {basis:+.0f})', target=tgt - basis)
    st['open']['brain_id'] = dec.get('id')
    json.dump(st, open(ST, 'w'), indent=1); print(f'swing daily {x["d"]}: PAPER {side} {en:.1f} stop {stop} target {tgt}; {r}')
def status():
    now = dt.datetime.now(L); tag = now.strftime('%H:%M')
    st = json.load(open(ST)) if os.path.exists(ST) else {}; lv = st.get('levels'); px = mark()
    if st.get('open'):
        p = st['open']; print(f'{tag} London, gold {px}: swing paper {p["side"]} open (futures entry {p["entry"]:.1f}, stop {p["stop"]}, target {p["target"]})'); return
    if not lv: print(f'{tag} London, gold {px}: swing test waiting for the first daily check'); return
    ema21_spot = lv['ema21'] - st.get('basis', 0)
    trend = 'up' if lv['ema50'] > lv['ema200'] else 'down'
    print(f'{tag} London, gold {px}: swing test, daily trend {trend}, waiting for a pullback to the 21-day EMA (~{ema21_spot:.0f} spot); macro {st.get("macro", {}).get("bias")}')
if __name__ == '__main__':
    daily() if len(sys.argv) > 1 and sys.argv[1] == 'daily' else status()
