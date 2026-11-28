"""3-year test of the LIVE trend pullback engine on OANDA XAU_USD 15m (Nov 2023 - Nov 2026), Woody 28 Nov 2026:
"run a 3 years backtest of the strategy and debug the whole system, rate it".
Rules = reentry.run(block=None): exactly the live pb_scan.py entry, stop, 2R target, 07:00-20:00 London, 3 a day, one at a
time, Friday 21:00 exit, B-grade when the H4 swings agree, C-grade otherwise. Also: costs x2, B-grade only, 2-loss stop,
per-year, per-side, per-session, losing streaks, and dollars with the live sizing (B half of $50 risk, C 0.01 lot)."""
import os, sys, datetime as dt, random
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '..', 'research_2026-11-23')); sys.path.insert(0, os.path.join(H, '..', 'research_2026-11-27'))
import pullback, reentry
from pullback import load, prepare, resample, stats, L

m15 = prepare(load(os.path.join(H, '..', 'data', 'xau_15m_oanda.json'))); h1 = prepare(resample(m15, 60)); h4 = prepare(resample(m15, 240))
print(f"OANDA XAU_USD 15m {m15[0]['ts']:%Y-%m-%d} to {m15[-1]['ts']:%Y-%m-%d}, {len(m15)} candles; gold {m15[0]['c']:.0f} -> {m15[-1]['c']:.0f}")

def line(name, t):
    a = stats(t); print(f"{name:34} n {a['n']:4}  win {a['win']:3}%  avg {a['avg']:6}R  total {a['R']:7}R  PF {a['pf']:5}  maxDD {a['dd']:5}R")
    return a

def streak(t):
    s = m = 0
    for x in t:
        s = s + 1 if x['R'] < 0 else 0; m = max(m, s)
    return m

base = reentry.run(m15, h1, h4)
print('\n== Live rules, all grades, 1R per trade, $0.40/oz cost =='); line('live rules', base)
print(f"{'':34} longest losing streak {streak(base)} trades; trades a week {len(base) / ((m15[-1]['ts'] - m15[0]['ts']).days / 7):.1f}")
for y in (2023, 2024, 2025, 2026):
    t = [x for x in base if x['ts'].year == y]
    if t: line(f'  {y}', t)
print('\n== Splits =='); line('  B-grade (H4 agrees)', [x for x in base if x['grade'] == 'B']); line('  C-grade (H4 mixed/against)', [x for x in base if x['grade'] == 'C'])
line('  buys', [x for x in base if x['side'] == 'BUY']); line('  sells', [x for x in base if x['side'] == 'SELL'])
for lab, a, b in (('London 07-12', 7, 12), ('New York 12-17', 12, 17), ('late 17-20', 17, 20)):
    line(f'  {lab}', [x for x in base if a <= x['ts'].astimezone(L).hour < b])
print('\n== Variants ==')
pullback.COST = reentry.COST = 0.80; line('costs doubled ($0.80/oz)', reentry.run(m15, h1, h4)); pullback.COST = reentry.COST = 0.40
line('stop after 2 losses a day', reentry.run(m15, h1, h4, 'two_losses'))
bonly = [x for x in base if x['grade'] == 'B']; print(f"{'B-grade only: longest losing streak':34} {streak(bonly)} trades")
first, second = [x for x in base if x['ts'].year < 2025 or (x['ts'].year == 2025 and x['ts'].month < 6)], None
mid = m15[len(m15) // 2]['ts']; line('first half', [x for x in base if x['ts'] < mid]); line('second half', [x for x in base if x['ts'] >= mid])
# dollars with the live sizing: B risks $25 (half of $50), C is 0.01 lot = 1 oz, so it risks the stop distance in dollars
# (risk is not stored per trade in reentry.run, so C dollars use the median 15m stop of about 1.5 ATR; see note in the report)
print('\n== Monte Carlo: 2000 reshuffles of the trade order (live rules) ==')
rs = [x['R'] for x in base]; dds = []
for _ in range(2000):
    random.shuffle(rs); eq = pk = dd = 0
    for r in rs: eq += r; pk = max(pk, eq); dd = max(dd, pk - eq)
    dds.append(dd)
dds.sort(); print(f"max drawdown: median {dds[1000]:.1f}R, 95th percentile {dds[1900]:.1f}R, worst {dds[-1]:.1f}R")
