"""Robustness sweep of the live pullback engine on 3 years of OANDA XAU_USD 15m: ADX threshold x reward target.
If no nearby setting is positive in both halves, the engine has no edge at the broker; a single positive cell is curve fit."""
import os, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '..', 'research_2026-11-23')); sys.path.insert(0, os.path.join(H, '..', 'research_2026-11-27'))
import reentry
from pullback import load, prepare, resample, stats
m15 = prepare(load(os.path.join(H, '..', 'data', 'xau_15m_oanda.json'))); h1 = prepare(resample(m15, 60)); h4 = prepare(resample(m15, 240))
mid = m15[len(m15) // 2]['ts']
print(f"{'ADX':>4} {'RR':>4} | {'n':>4} {'win%':>4} {'total R':>8} {'PF':>5} {'DD':>6} | {'1st half':>8} {'2nd half':>8} | {'B-grade R':>9}")
for adx in (20, 25, 30):
    for rr in (1.5, 2.0, 3.0):
        t = reentry.run(m15, h1, h4, adx_min=adx, rr=rr); a = stats(t)
        f = stats([x for x in t if x['ts'] < mid])['R']; s = stats([x for x in t if x['ts'] >= mid])['R']; b = stats([x for x in t if x['grade'] == 'B'])['R']
        print(f"{adx:4} {rr:4} | {a['n']:4} {a['win']:4} {a['R']:8} {a['pf']:5} {a['dd']:6} | {f:8} {s:8} | {b:9}")
