#!/usr/bin/env python3
"""PAPER TEST from 23 Nov 2026 (Woody: "Do want is best for the system"): London BREAKOUT AND RETEST.
Not proposed to the brain. From 28 Nov 2026 (Woody: "Signals should always go to telegram") its setups and results are
sent to Telegram labelled PAPER TEST; until then they were logged only.
Rules = setup 2 of backtest/research_2026-11-23/four_setups.py (the same signals() code runs on the live feed):
  LEVELS  previous London day high/low; today's London session (07:00-12:00) high/low after 12:00.
  ENTRY   an M15 close beyond a level, then within 16 candles a candle trades back to it and closes beyond it in the
          breakout direction. Entries 07:00-13:00 London weekdays only (the only session that was positive).
  STOP    beyond the retest swing - 0.1 x 15m ATR (0.5 to 4 ATR).
  EXITS   thirds at 0.5R / 1R / 1.5R, stop to breakeven after TP1; Friday 21:00 exit. Costs 0.40/oz in R.
12-month test (London): 38 trades, +0.18R a trade, first half +2.8R, unseen half +3.9R, worst run 2.1R.
Run every 5 minutes by loop.sh. Never places orders."""
import csv, datetime as dt, json, os, sys
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D); sys.path.insert(0, os.path.join(D, '..', 'backtest', 'research_2026-11-23'))
from auto_scan import candles, ldn, L
from ema_scan import mark
from pullback import prepare, resample
from four_setups import signals
G = '/home/user/gold-desk'; ST, LOG = f'{G}/br_state.json', f'{G}/br_log.csv'
FIELDS = ['opened', 'side', 'entry', 'stop', 'tp1', 'tp2', 'tp3', 'risk', 'closed', 'exit_note', 'usd_001', 'R']
COST = 0.40


def rows():
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='') as f: csv.writer(f).writerow(FIELDS)
    return list(csv.DictReader(open(LOG, newline='')))


def save(rs):
    with open(LOG, 'w', newline='') as f: w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rs)


def tell(text):
    """28 Nov 2026 (Woody: "Signals should always go to telegram"): paper-test setups and results go to Telegram, labelled."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brain')); import publisher
        return publisher.publish(text, 'update')
    except Exception as ex:
        return f'FAILED {type(ex).__name__}'


def main():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    now = dt.datetime.now(L); tag = now.strftime('%H:%M'); px = mark()
    out = lambda why: (json.dump(st, open(ST, 'w'), indent=1), print(f'{tag} London, gold {px}: BR paper {why}'))
    pos = st.get('open')
    if pos:  # thirds at 0.5/1/1.5R, stop to breakeven after TP1 (from the next candle), stop checked first
        sg = 1 if pos['side'] == 'BUY' else -1; done = None
        for x in [x for x in candles('5m', 2) if x['T'] + 1 > pos['checked_ms']]:
            if (x['l'] <= pos['stop']) if sg > 0 else (x['h'] >= pos['stop']):
                pos['got'] += pos['left'] * sg * (pos['stop'] - pos['entry']); pos['left'] = 0
                done = ('STOP' if not pos['legs_hit'] else 'BREAKEVEN STOP', ldn(x['T'] + 1)); break
            hit = False
            for k, t in enumerate(pos['tps']):
                if k >= pos['legs_hit'] and ((x['h'] >= t) if sg > 0 else (x['l'] <= t)):
                    pos['got'] += (1 / 3) * sg * (t - pos['entry']); pos['left'] -= 1 / 3; pos['legs_hit'] = k + 1; hit = True
            pos['checked_ms'] = x['T'] + 1
            if pos['legs_hit'] == 3: done = ('ALL THREE TARGETS', ldn(x['T'] + 1)); break
            if hit: pos['stop'] = pos['entry']
        if not done and now.weekday() == 4 and now.hour >= 21:
            pos['got'] += pos['left'] * sg * (px - pos['entry']); pos['left'] = 0; done = ('FRIDAY 21:00', now)
        if done:
            how, xt = done; pl = round(pos['got'], 2); R = round((pl - COST) / pos['risk'], 2); rs = rows()
            for r in rs:
                if r['opened'] == pos['opened'] and not r['closed']:
                    r.update(closed=xt.strftime('%Y-%m-%d %H:%M'), exit_note=how, usd_001=f'{pl:+.2f}', R=f'{R:+.2f}')
            save(rs); st['open'] = None
            tg = tell(f"👑 CBFX | PAPER TEST RESULT (London breakout and retest)\n{pos['side']} from {pos['entry']:.2f} closed ({how}): {R:+.2f}R, {pl:+.2f} dollars at 0.01 lot\n🧪 Paper test, not a recommendation")
            return out(f'{pos["side"]} closed ({how}): {R:+.2f}R, {pl:+.2f} dollars at 0.01 lot (paper test, Telegram {tg})')
        st['open'] = pos
        return out(f'{pos["side"]} open from {pos["entry"]:.1f}, stop {pos["stop"]:.1f}, {pos["legs_hit"]} of 3 targets hit (paper)')
    if not (now.weekday() < 5 and 7 <= now.hour < 13): return out('entries 07:00-13:00 London weekdays only')
    raw = candles('15m', 7)
    if not raw or st.get('last_bar') == raw[-1]['t']: return out('waiting for the next closed 15m candle')
    st['last_bar'] = raw[-1]['t']
    m15 = prepare([dict(ts=dt.datetime.fromtimestamp(x['t'] / 1000, dt.timezone.utc), o=x['o'], h=x['h'], l=x['l'], c=x['c']) for x in raw])
    h1, h4 = prepare(resample(m15, 60)), prepare(resample(m15, 240))
    sig = [s for s in signals(m15, h1, h4) if s['setup'] == '2 retest' and s['i'] == len(m15) - 1]
    if not sig: return out('no breakout retest on the last 15m candle')
    s = sig[0]; sg = 1 if s['side'] == 'BUY' else -1; e = round(s['entry'], 1); stop = round(s['stop'], 1); R1 = abs(e - stop)
    tps = [round(e + sg * m * R1, 1) for m in (0.5, 1.0, 1.5)]; opened = now.strftime('%Y-%m-%d %H:%M')
    rs = rows(); rs.append(dict(opened=opened, side=s['side'], entry=f'{e:.1f}', stop=f'{stop:.1f}', tp1=tps[0], tp2=tps[1], tp3=tps[2], risk=f'{R1:.2f}')); save(rs)
    st['open'] = dict(opened=opened, side=s['side'], entry=e, stop=stop, tps=tps, risk=round(R1, 2), got=0.0, left=1.0, legs_hit=0, checked_ms=raw[-1]['T'] + 1)
    tg = tell('\n'.join(['👑 CBFX | PAPER TEST SETUP (London breakout and retest)',
                          f"{'🟢 BUY' if s['side'] == 'BUY' else '🔴 SELL'} XAUUSD (M15) · market at {e:.2f}", f'🛑 Stop {stop:.2f}',
                          f'🎯 Thirds at {tps[0]} / {tps[1]} / {tps[2]} (0.5R / 1R / 1.5R), stop to breakeven after the first', '',
                          '🧪 PAPER TEST: not yet checked on 3 years of broker prices. Information, not a recommendation.',
                          f'{opened[11:]} London · signal only, no order placed']))
    return out(f'SETUP {s["side"]} {e:.1f} stop {stop:.1f} targets {tps[0]} / {tps[1]} / {tps[2]} (paper test, Telegram {tg})')


if __name__ == '__main__':
    main()
