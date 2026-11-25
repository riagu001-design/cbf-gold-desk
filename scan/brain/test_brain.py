#!/usr/bin/env python3
"""Acceptance tests for the CrownBearer Neural Brain (17 Nov 2026 directive). Runs in a temporary brain folder with
SCAN_TEST=1, so nothing reaches Telegram and the live registry and journal are untouched. Uses live prices for the
post-trade path check only."""
import importlib, os, subprocess, sys, tempfile, time
tmp = tempfile.mkdtemp(prefix='brain_test_'); os.environ['BRAIN_DIR'] = tmp; os.environ['SCAN_TEST'] = '1'
HERE = os.path.dirname(os.path.abspath(__file__)); SCAN = os.path.dirname(HERE)
sys.path[:0] = [HERE, SCAN]
import core as Bm
Bm.market_open = lambda t: True  # tests run at any hour
ok = []
def check(name, cond, detail=''):
    ok.append(cond); print(('PASS ' if cond else 'FAIL ') + name + (f'  [{detail}]' if detail else ''))
def ctx(h4):
    return ({'h4': h4, 'd1': 'with', 'adx4': 'strong', 'vol': 'normal', 'stretch': 'near', 'room': 'open', 'rsi': 'ok', 'session': 'newyork'},
            {'atr1h': 15.0, 'adx4': 35.0, 'room_atr': 2.0})
now = time.time()
p = lambda s, side, e, st, ts=None: dict(strategy=s, side=side, entry=e, stop=st, exit_rule='test exit', ts=ts or now)
r1 = Bm.submit(p('H1', 'BUY', 4000, 3970), ctx('with'))
check('H1 with the H4 trend scores 85+ and is SENT immediately', r1['verdict'] == 'SENT' and r1['score'] >= 85 and r1.get('telegram') == 'test', f"score {r1['score']}")
r1b = Bm.submit(p('H1', 'BUY', 4000, 3970), ctx('with'))
check('the same proposal again is blocked as a duplicate', r1b['verdict'] == 'DUPLICATE')
r2 = Bm.submit(dict(p('4H', 'BUY', 4001, 3940), ts=now + 60), ctx('with'))
check('a second BUY from another engine is blocked while one BUY is active', r2['verdict'] == 'REJECTED' and any('duplicate' in x for x in r2['reasons']), '; '.join(r2['reasons']))
r3 = Bm.submit(dict(p('H1', 'SELL', 3999, 4030), ts=now + 120), ctx('with'))
check('a conflicting SELL is resolved centrally (rejected while the BUY is active)', r3['verdict'] == 'REJECTED' and any('conflict' in x for x in r3['reasons']))
r4 = Bm.submit(dict(p('M15', 'SELL', 3999, 4030), ts=now + 180), ctx('against'))
check('a low-confidence setup never reaches Telegram', r4['verdict'] == 'REJECTED' and not r4.get('telegram'), f"score {r4['score']}")
r5 = Bm.submit(dict(p('H1', 'BUY', 4000, 3970), ts=now - 3600), ctx('with'))
check('a stale setup (entry conditions an hour old) is rejected', r5['verdict'] == 'REJECTED' and any('fresh' in x for x in r5['reasons']))
o = Bm.close(r1['id'], 4030, 'TEST EXIT', now + 600)
check('closing a sent signal records the outcome, review and result message', o and o['sent'] and o['R'] > 0 and o.get('telegram') == 'test' and 'review' in o, f"R {o['R']}, review {o['review']}")
check('the registry has no active signal after the close', not Bm.load_reg()['active'])
Bm.close(r4['id'], 3990, 'TEST EXIT', now + 600)
J = Bm.read_journal()
check('every proposal and outcome is journaled (approved, rejected and shadow-tracked)', sum(r['type'] == 'decision' for r in J) == 5 and sum(r['type'] == 'outcome' for r in J) == 2)
importlib.reload(Bm); J2 = Bm.read_journal()
check('learning records persist after a restart (reloaded from disk)', len(J2) == len(J))
import ema_scan, auto_scan, swing_daily
for mod in (ema_scan, swing_daily):
    try: mod.send('x', 'y'); res = False
    except PermissionError: res = True
    check(f'{mod.__name__} cannot publish to Telegram', res)
try: auto_scan.send_telegram('x'); res = False
except PermissionError: res = True
check('the retired auto_scan sender cannot publish', res)
g = subprocess.run(['grep', '-rln', 'api.telegram' + '.org', SCAN, '--include=*.py'], capture_output=True, text=True).stdout.split()
check('only scan/brain/publisher.py can reach Telegram', [os.path.relpath(x, SCAN) for x in g] == ['brain/publisher.py'], str(g))
import learn; learn.REC = os.path.join(tmp, 'rec.json'); rec = learn.review()
check('the learning review runs and backtests improvements without applying them', all(t['feature'] not in learn.S.SCORE_FEATURES for t in rec['tests']))
st = Bm.status()
check('status for the dashboard and Crown is written', os.path.exists(os.path.join(tmp, 'status.json')) and st['counts']['proposals'] == 5)
# 18 Nov 2026: B-grade signals (75-84) are sent at half size; an A-grade setup may replace a same-side B-grade signal.
r6 = Bm.submit(p('M15', 'SELL', 4000, 4030, now - 1), ctx('with'))
check('a 75-84 setup is sent as a B-GRADE half-size signal', r6['verdict'] == 'WATCHLIST' and r6.get('grade') == 'B' and r6.get('telegram') == 'test'
      and 'B-grade, half size' in Bm.signal_text(r6, Bm.cfg()) and Bm.lots_for(12, Bm.cfg(), 'B')[1] <= Bm.cfg()['risk_usd'] / 2, f"score {r6['score']}")
r7 = Bm.submit(p('H1', 'SELL', 4000, 4030, now - 2), ctx('with'))
check('an A-grade setup is not blocked by an active same-side B-grade signal', r7['verdict'] == 'SENT' and r7.get('grade') == 'A', f"{r7['verdict']} {r7['reasons']}")
print(f"\n{sum(ok)}/{len(ok)} acceptance tests passed (temp brain folder {tmp})")
sys.exit(0 if all(ok) else 1)
