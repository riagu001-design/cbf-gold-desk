#!/usr/bin/env python3
"""DAILY 20-DAY BREAKOUT (D20), PAPER from 28 Nov 2026 (Woody: "find a new strategy"). Research:
backtest/research_2026-11-28/candidates.py on OANDA XAU_USD, Nov 2023 - Nov 2026, rules fixed before testing, final year
held back: 25 trades, 44% wins, +11.5R, PF 1.88, max drawdown 5.1R, positive in both development years (+0.8R, +5.9R)
and the final year (+4.7R), still positive with costs and financing doubled. The only candidate that passed every check.
Rules (Turtle system 1, both directions), on OANDA daily candles (UTC days):
  ENTRY  a daily close above the highest high of the previous 20 days = BUY at that close (below the lowest low = SELL).
  STOP   2 x ATR(20) of the daily candles from the entry, checked on every 15m candle.
  EXIT   a daily close below the lowest low of the previous 10 days (above the 10-day high for sells), or an opposite
         breakout (which reverses). No profit target: winners run.
  One position at a time. Costs: $0.40/oz plus 0.02% a night financing.
Runs every 5 minutes from loop.sh; acts once per closed daily candle. Never places orders; PAPER = True sends nothing."""
import csv, json, os, sys, time, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from auto_scan import candles, atr, ldn, L
G = '/home/user/gold-desk'; ST, LOG = f'{G}/d20_state.json', f'{G}/d20_log.csv'
FIELDS = ['opened', 'side', 'entry', 'stop', 'risk', 'closed', 'exit', 'usd_001', 'R', 'how', 'nights']
PAPER, COST, FIN = True, 0.40, 0.0002


def rows():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f: csv.writer(f).writerow(FIELDS)
    return list(csv.DictReader(open(LOG, newline='')))


def save(rs):
    with open(LOG, 'w', newline='') as f: w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rs)


def close_trade(st, rs, ex, how, when):
    p = st['open']; sg = 1 if p['side'] == 'BUY' else -1; nights = p.get('nights', 0)
    pl = sg * (ex - p['entry']); R = (pl - COST - FIN * p['entry'] * nights) / p['risk']
    for r in rs:
        if r['opened'] == p['opened'] and not r['closed']:
            r.update(closed=when.strftime('%Y-%m-%d %H:%M'), exit=f'{ex:.1f}', usd_001=f'{pl:+.2f}', R=f'{R:+.2f}', how=how, nights=str(nights))
    save(rs); st['open'] = None
    return f'{"PAPER " if PAPER else ""}{p["side"]} closed ({how}) at {ex:.1f}: {R:+.2f}R after {nights} nights'


def main():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    now = dt.datetime.now(L); tag = now.strftime('%H:%M'); rs = rows(); notes = []
    def out(why): json.dump(st, open(ST, 'w'), indent=1); print(f'{tag} London: D20 {why}')
    p = st.get('open')
    if p:  # stop on every closed 15m candle since the last check; count 22:00 UTC rollovers for financing
        sg = 1 if p['side'] == 'BUY' else -1
        for x in [x for x in candles('15m', 3) if x['T'] + 1 > p['checked_ms']]:
            t0 = dt.datetime.fromtimestamp(x['t'] / 1000, dt.timezone.utc)
            if t0.hour == 22 and t0.minute == 0: p['nights'] = p.get('nights', 0) + 1
            if (x['l'] <= p['stop']) if sg > 0 else (x['h'] >= p['stop']):
                return out(close_trade(st, rs, p['stop'], 'STOP 2 ATR', ldn(x['T'] + 1)))
            p['checked_ms'] = x['T'] + 1
    D = candles('1d', 60)
    if len(D) < 25: return out('not enough daily candles')
    last = D[-1]
    if st.get('last_day') == last['t']:
        return out((f'{p["side"]} open from {p["entry"]:.1f}, stop {p["stop"]:.1f}, ' if p else 'flat, ') + 'waiting for the next daily close')
    st['last_day'] = last['t']
    c = last['c']; hi20 = max(x['h'] for x in D[-21:-1]); lo20 = min(x['l'] for x in D[-21:-1])
    lo10 = min(x['l'] for x in D[-11:-1]); hi10 = max(x['h'] for x in D[-11:-1]); A = atr(D, 20)
    sig = 'BUY' if c > hi20 else 'SELL' if c < lo20 else None; when = ldn(last['T'] + 1)
    p = st.get('open')
    if p:
        if (p['side'] == 'BUY' and c < lo10) or (p['side'] == 'SELL' and c > hi10):
            notes.append(close_trade(st, rs, c, '10-DAY EXIT', when))
        elif sig and sig != p['side']:
            notes.append(close_trade(st, rs, c, 'REVERSED', when))
    if not st.get('open') and sig:
        sg = 1 if sig == 'BUY' else -1; stop = round(c - sg * 2 * A, 1); opened = when.strftime('%Y-%m-%d %H:%M')
        rs.append(dict(opened=opened, side=sig, entry=f'{c:.1f}', stop=f'{stop:.1f}', risk=f'{2 * A:.2f}')); save(rs)
        st['open'] = dict(opened=opened, side=sig, entry=c, stop=stop, risk=2 * A, nights=0, checked_ms=last['T'] + 1)
        notes.append(f'{"PAPER " if PAPER else ""}SETUP {sig} {c:.1f} stop {stop:.1f} (2 ATR {2 * A:.1f}); exit on a daily close beyond the 10-day {"low" if sg > 0 else "high"}'
                     + ('; paper, not sent' if PAPER else ''))
    if not notes:
        p = st.get('open')
        notes.append(f'daily close {c:.1f}: ' + (f'{p["side"]} open from {p["entry"]:.1f}, stop {p["stop"]:.1f}, exit level {lo10 if p["side"] == "BUY" else hi10:.1f}' if p
                     else f'no breakout (20-day high {hi20:.1f}, low {lo20:.1f})'))
    return out('; '.join(notes))


if __name__ == '__main__':
    main()
