#!/usr/bin/env python3
"""CrownBearer Neural Brain: learning, mistake prevention and controlled improvement.

  python3 learn.py review     -> recommendations.json: mistake patterns, strategy health, backtested improvements
  python3 learn.py apply X    -> add feature X to the live score, ONLY if review's backtest passed (versioned)
  python3 learn.py rollback   -> restore the previous config version

Rules it follows (17 Nov 2026 directive):
- Nothing changes the live rules automatically. review() only RECOMMENDS; apply() needs a passed backtest.
- No strategy or feature is judged on one trade: a live pattern needs at least MIN_N outcomes and a clear gap
  (at least GAP R per trade, t-stat beyond 2) before it becomes a learning rule candidate.
- Every proposal the engines made is used, approved or not (engines keep paper-tracking rejected ideas), so the brain
  also learns whether its rejections were right.
"""
import datetime as dt, json, math, os, shutil, sys
sys.path.insert(0, os.path.dirname(__file__))
import score as S
from features import FEATURES
from core import read_journal, cfg, B, CONFIG, L

MIN_N, GAP = 20, 0.25
REC, HIST = f'{B}/recommendations.json', f'{B}/history'
MISTAKES = {'entry premature': 'Entering before confirmation', 'stop hit after reaching +1R': 'Stop not moved after the trade worked',
            'h4=against': 'Trading against the higher-timeframe trend', 'stretch=stretched': 'Chasing price after a large move',
            'room=tight': 'Entering into nearby liquidity', 'vol=high': 'Trading in unsuitable volatility', 'rsi=extreme': 'Entering at an RSI extreme',
            'direction wrong': 'Market direction misread'}


def tstat(x, base):
    if len(x) < 2: return 0.0
    m = sum(x) / len(x); sd = math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1)) or 1e-9
    return (m - base) / (sd / math.sqrt(len(x)))


def backtest_feature(feat):
    """Fit the score with the current features plus `feat` on the train half; compare unseen-half bands with the current model."""
    ev = json.load(open(S.EVIDENCE)); tr = [t for t in ev['trades'] if t['half'] == 'train']; te = [t for t in ev['trades'] if t['half'] == 'test']
    cur = list(S.SCORE_FEATURES); res = {}
    for name, feats in (('current', cur), ('proposed', cur + [feat])):
        S.SCORE_FEATURES[:] = feats; m = S.fit(tr); res[name] = S.calibrate(m, te)
    S.SCORE_FEATURES[:] = cur
    top = lambda c: (c['85+']['avgR'] if c['85+']['n'] >= 15 and c['85+']['avgR'] is not None else -9)
    passed = top(res['proposed']) > top(res['current']) + 0.05 and res['proposed']['85+']['n'] >= 15
    return dict(feature=feat, current=res['current'], proposed=res['proposed'], passed=passed,
                rule='proposed 85+ band must hold at least 15 unseen setups and beat the current 85+ band by 0.05R per trade')


def review():
    J = read_journal(); out = [r for r in J if r.get('type') == 'outcome']; items = []
    allR = [r['R'] for r in out]; base = sum(allR) / len(allR) if allR else 0
    # 1. mistake patterns (sent signals and shadow-tracked ideas)
    counts = {}
    for r in out:
        for note in r.get('review', []):
            for key, label in MISTAKES.items():
                if note.startswith(key) or key in note: counts.setdefault(label, []).append(r['R'])
    for label, rs in sorted(counts.items(), key=lambda kv: -len(kv[1])):
        items.append(dict(kind='mistake pattern', what=label, n=len(rs), avgR=round(sum(rs) / len(rs), 2),
                          action='learning rule candidate' if len(rs) >= MIN_N and sum(rs) / len(rs) < base - GAP else f'watching (needs {MIN_N}+ cases)'))
    # 2. feature evidence on live outcomes (all proposals)
    for f in FEATURES:
        groups = {}
        for r in out: groups.setdefault(r.get('features', {}).get(f, 'unknown'), []).append(r['R'])
        for v, rs in groups.items():
            if len(rs) >= MIN_N:
                t = tstat(rs, base); avg = sum(rs) / len(rs)
                if abs(avg - base) >= GAP and abs(t) >= 2:
                    items.append(dict(kind='live feature effect', what=f'{f}={v}', n=len(rs), avgR=round(avg, 2), vs_all=round(base, 2), t=round(t, 1),
                                      action='candidate for the score: run the backtest below before applying'))
    # 3. strategy health: last 20 live outcomes per strategy against its evidence
    m, ev = S.load_model()
    for s in ('H1', 'M15', '4H', 'ASIA', 'SWING'):
        rs = [r['R'] for r in out if r['strategy'] == s][-20:]
        exp = m['base'].get(s) if s != 'SWING' else None
        if rs:
            avg = sum(rs) / len(rs)
            flag = 'deteriorating: review before trusting it' if len(rs) >= 20 and avg < 0 and (exp or 0) > 0 else 'in line or too few trades to judge'
            items.append(dict(kind='strategy health', what=s, n=len(rs), avgR=round(avg, 2), evidence_R=round(exp, 2) if exp else None, action=flag))
    # 4. controlled improvement: backtest every feature not yet in the score
    tests = [backtest_feature(f) for f in FEATURES if f not in S.SCORE_FEATURES]
    for t in tests:
        items.append(dict(kind='improvement backtest', what=f'add {t["feature"]} to the score', passed=t['passed'],
                          unseen_85_current=t['current']['85+'], unseen_85_proposed=t['proposed']['85+'],
                          action='can be applied with: learn.py apply ' + t['feature'] if t['passed'] else 'rejected by backtest: not applied'))
    rec = dict(updated=dt.datetime.now(L).strftime('%Y-%m-%d %H:%M'), live_outcomes=len(out), base_R=round(base, 2), config_version=cfg()['version'],
               items=items, tests=tests)
    json.dump(rec, open(REC, 'w'), indent=1)
    return rec


def apply(feat):
    rec = json.load(open(REC)); t = next((x for x in rec['tests'] if x['feature'] == feat), None)
    if not t or not t['passed']:
        raise SystemExit(f'not applied: {feat} has no passed backtest in {REC} (run learn.py review)')
    c = cfg(); os.makedirs(HIST, exist_ok=True); shutil.copy(CONFIG, f'{HIST}/config_v{c["version"]}.json')
    c['score_features'] = list(c.get('score_features', ['h4'])) + [feat]; c['version'] += 1
    c['note'] = f'v{c["version"]} {dt.date.today()}: added {feat} after backtest {t["proposed"]["85+"]} vs {t["current"]["85+"]}'
    json.dump(c, open(CONFIG, 'w'), indent=1); print('applied', c['note'])


def rollback():
    c = cfg(); prev = f'{HIST}/config_v{c["version"] - 1}.json'
    if not os.path.exists(prev): raise SystemExit('no earlier version to roll back to')
    shutil.copy(CONFIG, f'{HIST}/config_v{c["version"]}_rolledback.json'); shutil.copy(prev, CONFIG); print('rolled back to', prev)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'review'
    if cmd == 'review':
        r = review(); print(f"{r['live_outcomes']} live outcomes, config v{r['config_version']}")
        for i in r['items']: print('-', i['kind'], '|', i['what'], '|', i.get('n', ''), i.get('avgR', ''), '|', i['action'])
    elif cmd == 'apply': apply(sys.argv[2])
    elif cmd == 'rollback': rollback()
