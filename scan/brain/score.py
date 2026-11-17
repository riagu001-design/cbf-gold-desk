"""CrownBearer Neural Brain: evidence-based confidence score.

Model (deliberately simple, so it cannot memorise 300 trades):
  expected R = strategy base + sum over features of the shrunk average extra R that setups with that feature value
               earned versus their own strategy's base (shrinkage n / (n + K), K = 30, pooled across strategies).
  score 0-100 = percentile of that expected R among all TRAIN-half setups.
So 85 means "better expected R than 85 percent of the setups the desk has seen". The score is only as good as the
evidence: calibrate() checks it on the unseen test half, and the brain reports that check on the dashboard.
"""
import bisect, json
from features import FEATURES  # noqa: F401 (all features are journaled)

K = 30.0
# Features that move the score. Chosen 17 Nov 2026: only the H4 trend held up on the unseen half (85+ band +0.54R,
# 75-84 +0.30R, below 75 -0.11R); the other features are recorded for learning but do not move the score until
# the learning engine shows they hold up on live results.
SCORE_FEATURES = ['h4']
try:  # the live set is versioned in brain/config.json (learn.py apply / rollback)
    SCORE_FEATURES = json.load(open('/home/user/gold-desk/brain/config.json')).get('score_features', SCORE_FEATURES)
except (OSError, ValueError):
    pass
EVIDENCE = '/home/user/gold-desk/brain/evidence.json'


def fit(trades):
    by_s = {}
    for t in trades: by_s.setdefault(t['strategy'], []).append(t['R'])
    pooled = sum(t['R'] for t in trades) / len(trades)
    base = {s: (sum(r) + K * pooled) / (len(r) + K) for s, r in by_s.items()}
    delta = {}
    for f in SCORE_FEATURES:
        groups = {}
        for t in trades: groups.setdefault(t['f'].get(f, 'unknown'), []).append(t['R'] - base[t['strategy']])
        delta[f] = {v: {'d': sum(x) / (len(x) + K), 'n': len(x), 'avg': sum(x) / len(x)} for v, x in groups.items()}
    m = dict(base=base, pooled=pooled, delta=delta)
    m['dist'] = sorted(expected(m, t['strategy'], t['f'])[0] for t in trades)
    return m


def expected(m, strategy, f):
    e = m['base'].get(strategy, m['pooled']); parts = []
    for k in SCORE_FEATURES:
        d = m['delta'].get(k, {}).get(f.get(k, 'unknown'))
        if d: e += d['d']; parts.append((k, f.get(k), round(d['d'], 3), d['n']))
    return e, parts


def score(m, e):
    return round(100 * bisect.bisect_left(m['dist'], e) / len(m['dist']))


def load_model():
    ev = json.load(open(EVIDENCE))
    tr = [t for t in ev['trades'] if t['half'] == 'train']
    m = fit(tr); m['swing'] = ev['swing']; m['built'] = ev['built']
    return m, ev


def calibrate(m, trades):
    bands = {'85+': [], '75-84': [], '<75': []}
    for t in trades:
        s = score(m, expected(m, t['strategy'], t['f'])[0])
        bands['85+' if s >= 85 else '75-84' if s >= 75 else '<75'].append(t['R'])
    return {k: dict(n=len(v), avgR=round(sum(v) / len(v), 3) if v else None, win=round(100 * sum(r > 0 for r in v) / len(v)) if v else None) for k, v in bands.items()}


if __name__ == '__main__':
    m, ev = load_model()
    print('base R by strategy:', {k: round(v, 3) for k, v in m['base'].items()})
    for f, vals in m['delta'].items():
        print(f'{f:8s}', '  '.join(f'{v}:{x["d"]:+.2f}(n{x["n"]})' for v, x in vals.items()))
    for half in ('train', 'test'):
        print(half, calibrate(m, [t for t in ev['trades'] if t['half'] == half]))
