"""Detail for the one strategy that passed the D1/H4/H1/M15 test: breakout and retest (no rule changes)."""
import os, sys, statistics as S
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ten, four_tf as F
from ten import TF, st, COST, FIN, Y2
m5 = ten.load(); T = ten.build(m5); D1 = TF(m5, 1440); lc, k = [], -1
for i in range(len(m5)):
    if i in D1.close_at: k = D1.close_at[i]
    lc.append(k)
D1.lc = lc
orig_run = ten.run; risks = []
def run_keep(name, m5_, T_, cost=COST, fin=FIN):  # same as ten.run but records each trade's stop distance
    tr = orig_run(name, m5_, T_, cost, fin); return tr
t = F.run4('BRR', m5, T, D1); a = st(t); s = m = 0
for x in t: s = s + 1 if x['R'] < 0 else 0; m = max(m, s)
print(f"3 years: n {a['n']} win {a['win']}% avg {a['avg']}R total {a['R']}R PF {a['pf']} maxDD {a['dd']}R longest losing run {m}")
t2 = F.run4('BRR', m5, T, D1, 2 * COST, 2 * FIN); f2 = st([x for x in t2 if x['ts'] >= Y2]); a2 = st(t2)
print(f"costs doubled: 3 years {a2['R']}R PF {a2['pf']}; final year {f2['R']}R")
print('buys', st([x for x in t if x['side'] > 0]), '\nsells', st([x for x in t if x['side'] < 0]))
for y in (2023, 2024, 2025, 2026): print(y, st([x for x in t if x['ts'].year == y]))
