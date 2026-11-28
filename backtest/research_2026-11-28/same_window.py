"""Same 12 months (6 Nov 2025 - 25 Nov 2026), live rules, on both feeds: Hyperliquid xyz:GOLD (the desk feed, trades 24/7)
and OANDA XAU_USD (the broker market, closed at weekends). Also OANDA with indicators warmed up on the earlier 2 years."""
import os, sys, datetime as dt, json
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '..', 'research_2026-11-23')); sys.path.insert(0, os.path.join(H, '..', 'research_2026-11-27'))
import reentry
from pullback import load, prepare, resample, stats, UTC
a0, a1 = dt.datetime(2025, 11, 6, 12, 30, tzinfo=UTC), dt.datetime(2026, 11, 25, 8, tzinfo=UTC)
def show(name, t):
    t = [x for x in t if a0 <= x['ts'] < a1]; s = stats(t)
    print(f"{name:46} n {s['n']:4} win {s['win']:3}% total {s['R']:7}R PF {s['pf']:5} maxDD {s['dd']:5}R")
for name, path, cut in (('Hyperliquid feed (desk)', 'xau_15m.json', True), ('OANDA, same window only', 'xau_15m_oanda.json', True), ('OANDA, warmed up on 2 earlier years', 'xau_15m_oanda.json', False)):
    m = load(os.path.join(H, '..', 'data', path))
    if cut: m = [x for x in m if x['ts'] >= a0]
    m = prepare(m); show(name, reentry.run(m, prepare(resample(m, 60)), prepare(resample(m, 240))))
hl = load(os.path.join(H, '..', 'data', 'xau_15m.json'))
wk = sum(1 for x in hl if x['ts'].weekday() == 5 or (x['ts'].weekday() == 6 and x['ts'].hour < 22) or (x['ts'].weekday() == 4 and x['ts'].hour >= 22))
print(f"Hyperliquid candles in the weekend (Fri 22:00 - Sun 22:00 UTC): {wk} of {len(hl)}")
