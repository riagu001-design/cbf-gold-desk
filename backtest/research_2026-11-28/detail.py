"""Detail for the candidates that passed the final check (no changes to rules): every D20 trade, x2-cost final year,
and losing streaks."""
import datetime as dt, candidates as C
b = C.load(); Y2 = dt.datetime(2025, 11, 1, tzinfo=C.UTC)
for name in ('D20', 'D20L', 'H4PB3'):
    t = C.run(name, b); t2 = C.run(name, b, cost=2 * C.COST, fin=2 * C.FIN)
    s = m = 0
    for x in t: s = s + 1 if x['R'] < 0 else 0; m = max(m, s)
    a = C.st(t); print(f"{name}: 3 years n {a['n']} win {a['win']}% total {a['R']}R PF {a['pf']} maxDD {a['dd']}R, longest losing run {m}; final year x2 cost {C.st([x for x in t2 if x['ts'] >= Y2])['R']}R")
print('\nD20 trades (entry at the daily close, UTC):')
D = C.resample(b, lambda t: t.date())
for x in C.run('D20', b): print(f"  {x['ts']:%Y-%m-%d}  {x['R']:+.2f}R")
