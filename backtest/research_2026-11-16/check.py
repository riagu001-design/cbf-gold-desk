from others import *
print('London breakout, no stop cap:')
for so in ('opp','mid'):
    for tg in (1.0, 1.5, 2.0):
        a, t = stats(london_breakout(S, M, so, tg, maxR=999)), stats(london_breakout(M, E, so, tg, maxR=999))
        print(f'  stop={so} tgt={tg}  train {a["txt"]}\n  {"":18s}TEST  {t["txt"]}')
print('\n1H Donchian, both sides - neighbouring settings (all 12 months, then each quarter):')
Q = [(ts(2025,11,10),ts(2026,2,1)),(ts(2026,2,1),ts(2026,5,1)),(ts(2026,5,1),ts(2026,8,1)),(ts(2026,8,1),ts(2026,11,17))]
for n in (15, 20, 30, 40):
    for m in (2.5, 3.0, 3.5):
        tr = donchian(S, E, n=n, mult=m)
        q = ' '.join(f'{stats([x for x in tr if a<=x["t"]<b])["pl"]:+6.0f}' for a,b in Q)
        st = stats(tr); stops = sorted(x['R'] for x in tr)
        print(f'  n={n:2d} x{m}: {st["txt"]} | quarters {q} | median stop ${stops[len(stops)//2]:.0f}')
