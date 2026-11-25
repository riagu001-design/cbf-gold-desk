#!/usr/bin/env python3
"""CROWNBEARER NEURAL BRAIN: the single decision and signal authority of the gold desk.

Every strategy engine (H1 EMA 9/21, M15 entry, 4H EMA 9/21, daily swing) is an INTELLIGENCE PROVIDER only: when its
rules see a setup it calls submit(proposal) and keeps paper-tracking the idea (so the brain learns from rejected ideas
too). The brain alone decides:
  1. market context      features.py (H4 + daily trend, H4 ADX, volatility, stretch, liquidity room, RSI, session)
  2. evidence score      score.py (0-100, percentile of expected R from 396 historical setups; see calibration)
  3. mandatory gates     market open, high-impact news (+-5 min), freshness, stop sanity, daily loss limit,
                         duplicate and conflicting signals (Signal Registry)
  4. verdict             score >= 85 and all gates pass -> SENT to Telegram now as A-GRADE (full size);
                         75-84 -> WATCHLIST, also sent as B-GRADE (half size) since 18 Nov 2026 (Woody); else REJECTED
  5. journal             every proposal, decision, reason, outcome, MFE/MAE, TP1/TP2 and post-trade review is
                         appended to /home/user/gold-desk/brain/journal.jsonl (persists across restarts)
No order is ever placed: signals only.
CLI: core.py status   (prints the decision summary and writes brain/status.json for the dashboard and Crown)
"""
import datetime as dt, json, os, sys, time, uuid
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from features import features, L
import score as S
import publisher

B = os.environ.get('BRAIN_DIR', '/home/user/gold-desk/brain')
REG, JOURNAL, CONFIG, STATUS = f'{B}/registry.json', f'{B}/journal.jsonl', f'{B}/config.json', f'{B}/status.json'
LINE = '━━━━━━━━━━━━━━━━'
DEFAULT = dict(version=2, score_features=['h4', 'session'], send_min=85, watch_min=75, daily_loss_R=-3.0, min_stop_atr=0.3, max_stop_atr=12.0, fresh_s=900,
               balance=182.34, risk=0.01, risk_usd=50.0, note='v2 18 Nov 2026 (Woody: apply all needed improvements): score = strategy base + H4 trend + session evidence; see scan/brain/README.md')
NAMES = {'H1': 'H1 EMA 9/21 cross', 'M15': 'M15 entry with H1 confirmation', '4H': '4H EMA 9/21 cross', 'SWING': 'Daily swing pullback', 'ASIA': 'Asia range breakout (04:00-09:00)'}


PB_SCORE = 80  # B-grade (75-84): sent at half size. Review after 20 live PB trades.

def cfg():
    os.makedirs(B, exist_ok=True)
    if not os.path.exists(CONFIG):
        json.dump(DEFAULT, open(CONFIG, 'w'), indent=1)
    c = dict(DEFAULT); c.update(json.load(open(CONFIG))); return c


def load_reg():
    try: return json.load(open(REG))
    except (OSError, ValueError): return {'active': {}, 'open': {}}


def save_reg(r):
    tmp = REG + '.tmp'; json.dump(r, open(tmp, 'w'), indent=1); os.replace(tmp, REG)


def journal(rec):
    os.makedirs(B, exist_ok=True)
    with open(JOURNAL, 'a') as f: f.write(json.dumps(rec) + '\n')


def read_journal():
    if not os.path.exists(JOURNAL): return []
    return [json.loads(l) for l in open(JOURNAL) if l.strip()]


def ldn(ts): return dt.datetime.fromtimestamp(ts, dt.timezone.utc).astimezone(L)


def bars(iv, days):
    from auto_scan import candles
    return [dict(o=x['o'], h=x['h'], l=x['l'], c=x['c'], T=(x['T'] + 1) // 1000) for x in candles(iv, days)]


def live_context(side, price, ts):
    return features(side, price, ts, bars('1h', 14), bars('4h', 60), bars('1d', 120))


def market_open(t):
    m = t.hour * 60 + t.minute; wd = t.weekday()
    return not (wd == 5 or (wd == 6 and m < 1380) or (wd == 4 and m >= 19 * 60) or 1320 <= m < 1380)


def submit(p, ctx=None):
    """p: strategy ('H1'|'M15'|'4H'|'ASIA'|'SWING'), side, entry, stop, exit_rule, ts (epoch s of the signal), optional
    target (fixed take-profit) and note. Returns the decision record."""
    c = cfg(); reg = load_reg(); now = time.time(); t = ldn(p['ts']); buy = p['side'] == 'BUY'
    risk = abs(p['entry'] - p['stop']); sg = 1 if buy else -1
    pid = f"{t.strftime('%y%m%d-%H%M')}-{p['strategy']}-{p['side'][0]}"
    for o in list(reg['open'].values()) + list(reg['active'].values()):
        if o.get('pid') == pid: return dict(o, verdict='DUPLICATE', reasons=['same proposal already submitted'])
    if ctx is None: f, raw = live_context(p['side'], p['entry'], p['ts'])
    else: f, raw = ctx
    m, ev = S.load_model()
    if p['strategy'] == 'SWING':
        e = ev['swing'][p['side']]['R']; parts = [('swing 20-year evidence', p['side'], round(e, 3), ev['swing'][p['side']]['n'])]
    elif p['strategy'] == 'PB':  # 23 Nov 2026 (Woody: "Yes switch it on"): trend pullback, B-grade half size until 20 live trades
        e = 0.24; parts = [('pullback + H4 structure test to 25 Nov 2026: 144 trades, PF 1.43, unseen half +12.3R', p['side'], e, 144)]
    else:
        e, parts = S.expected(m, p['strategy'], f)
    sc = PB_SCORE if p['strategy'] == 'PB' else S.score(m, e)
    gates = []  # (name, passed, detail)
    if p['strategy'] == 'SWING': gates.append(('market open', True, 'daily setup: enter at the next open'))
    else: gates.append(('market open', market_open(ldn(now)), t.strftime('%a %H:%M London')))
    try:
        from auto_scan import news_block
        blocked, note = news_block(ldn(now))
    except Exception as ex:  # news file unreadable
        blocked, note = False, f'news check failed ({type(ex).__name__})'
    gates.append(('news', not blocked, note or 'no high-impact news within 15 min'))
    gates.append(('fresh', now - p['ts'] <= c['fresh_s'], f'{int(now - p["ts"])} s old'))
    a1 = raw.get('atr1h') or 0
    ok_stop = risk > 0 and (not a1 or c['min_stop_atr'] * a1 <= risk <= c['max_stop_atr'] * a1)
    gates.append(('stop distance', ok_stop, f'${risk:.1f}/oz = {risk / a1:.1f} x 1H ATR' if a1 else f'${risk:.1f}/oz'))
    today = ldn(now).strftime('%Y-%m-%d')
    lost = sum(r.get('R', 0) for r in read_journal() if r.get('type') == 'outcome' and r.get('sent') and r.get('closed', '').startswith(today))
    gates.append(('daily loss limit', lost > c['daily_loss_R'], f'{lost:+.2f}R today on sent signals (limit {c["daily_loss_R"]}R)'))
    pre = S.score(m, e)  # an A-grade setup may replace a same-side B-grade signal; anything else is a duplicate
    same = [a for a in reg['active'].values() if a['side'] == p['side'] and not (a.get('grade') == 'B' and pre >= c['send_min'])]
    opp = [a for a in reg['active'].values() if a['side'] != p['side']]
    gates.append(('no duplicate', not same, f'{p["side"]} signal {same[0]["id"]} already active' if same else 'none active'))
    gates.append(('no conflict', not opp, f'{opp[0]["side"]} signal {opp[0]["id"]} active' if opp else 'none active'))
    failed = [g for g in gates if not g[1]]
    if failed: verdict = 'REJECTED'
    elif sc >= c['send_min']: verdict = 'SENT'
    elif sc >= c['watch_min']: verdict = 'WATCHLIST'
    else: verdict = 'REJECTED'
    reasons = [f'{g[0]}: {g[2]}' for g in failed]
    if not failed and verdict != 'SENT':
        reasons.append(f'score {sc} below {c["send_min"]} (expected {e:+.2f}R per trade from the evidence)')
    tp1, tp2 = round(p['entry'] + sg * risk, 1), round(p['entry'] + sg * 2 * risk, 1)
    rec = dict(type='decision', id=uuid.uuid4().hex[:8].upper(), pid=pid, at=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               ts=p['ts'], london=t.strftime('%Y-%m-%d %H:%M'), strategy=p['strategy'], side=p['side'], entry=p['entry'], stop=p['stop'],
               risk=round(risk, 2), tp1=tp1, tp2=tp2, target=p.get('target'), exit_rule=p.get('exit_rule'), session=f['session'],
               features=f, raw=raw, expected_R=round(e, 3), score=sc, evidence=parts, gates=[dict(name=g[0], ok=g[1], detail=g[2]) for g in gates],
               verdict=verdict, reasons=reasons, model=dict(version=c['version'], evidence_built=m['built']), note=p.get('note'))
    grade = 'A' if verdict == 'SENT' else 'B' if verdict == 'WATCHLIST' and c.get('send_b', True) else None
    if grade and p.get('grade') == 'C': grade = 'C'  # 25 Nov 2026: pullback with the H4 not confirmed, 0.01 lot minimum
    if grade:
        rec['grade'] = grade
        rec['telegram'] = publisher.publish(signal_text(rec, c, p.get('note')), 'signal')
        reg['active'][rec['id']] = rec
    reg['open'][rec['id']] = dict({k: rec[k] for k in ('id', 'pid', 'ts', 'strategy', 'side', 'entry', 'stop', 'risk', 'verdict')}, grade=grade)
    save_reg(reg); journal(rec)
    return rec


# Woody's Telegram layout (18 Nov 2026). Per engine: chart label, strategy name, timing note.
STYLE = {'H1': ('H1', 'EMA 9/21 Trend Cross', '1H EMA 9/21 cross · Market Entry · No Chasing'),
         'M15': ('M15', 'Trend Pullback Entry', '15m entry with 1H confirmation · No Chasing'),
         '4H': ('H4', 'H4 Trend Cross', '4H EMA 9/21 cross · Market Entry'),
         'ASIA': ('M15', 'Asia Range Breakout', 'Pre-London breakout of the Asia high/low · No Chasing'),
         'SWING': ('D1', 'Daily Swing Pullback', 'Daily pullback to the 21 EMA · enter at the open'),
         'PB': ('M15', 'Trend Pullback (H1 control)', '15m dip to the EMA20 in the 1H trend, H4 structure agrees · Market Entry · 2R')}


SESS = {'asia': 'Asia', 'london': 'London', 'newyork': 'New York', 'late': 'late US'}


GRADE_TXT = {'A': '🟢 A-grade, full size', 'B': '🟡 B-grade, half size', 'C': '⚪ C-grade, minimum 0.01 lot (H4 not confirmed)'}


def lots_for(risk_per_oz, c, grade='A'):
    """0.01 lot = 1 oz. Lots that risk at most the risk budget, never below the 0.01 minimum."""
    budget = (c.get('risk_usd') or c['balance'] * c['risk']) * {'B': 0.5, 'C': 0.0}.get(grade, 1)
    lots = max(0.01, int(budget / (risk_per_oz * 100) * 100) / 100) if risk_per_oz else 0.01
    return lots, round(lots * 100 * risk_per_oz, 2), budget


def control_line(side):
    """🧭 Control line (Woody 25 Nov 2026): who leads the DI on H4 / H1 / M15 from closed candles."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        from auto_scan import candles
        from bars_json import dmi
        now_ms = time.time() * 1000
        d = {k: dmi([x for x in candles(iv, days) if x['T'] < now_ms]) for k, iv, days in (('H4', '4h', 60), ('H1', '1h', 8), ('M15', '15m', 3))}
        sel = sum(1 for x in d.values() if x and x['control'] == 'sellers'); n = sum(1 for x in d.values() if x)
        head = '🔴 Sellers in Control' if sel * 2 > n else '🟢 Buyers in Control' if (n - sel) * 2 > n else '⚪ Mixed Control'
        parts = ' | '.join(f"{k}: {x['control'].capitalize()}" for k, x in d.items() if x)
        return f'🧭 Control: {head} ({parts})'
    except Exception as ex:
        return f'🧭 Control: not read ({type(ex).__name__})'


def signal_text(r, c, note=None):
    """Clean Telegram layout (Woody 25 Nov 2026). Market orders only: the entry is ENTER NOW at market, never a limit."""
    buy = r['side'] == 'BUY'; tf, name, timing = STYLE.get(r['strategy'], ('', r['strategy'], ''))
    tp = r.get('target') or r['tp2']; rr = abs(tp - r['entry']) / r['risk'] if r['risk'] else 2
    grade = r.get('grade', 'A'); lots, risk_usd, budget = lots_for(r['risk'], c, grade)
    if note: why = note
    else:
        f = r['features']
        why = f"{name}: H4 trend {f['h4']}, brain {r['score']}/100, {SESS.get(r['session'], r['session'])} session"
    lines = ['👑 CBFX | TRADE SETUP',
             f"{'🟢 BUY' if buy else '🔴 SELL'} XAUUSD ({tf}) · MARKET · ENTER NOW (Pullback · No Chasing)",
             f"Strategy: {name} · {GRADE_TXT.get(grade, GRADE_TXT['A'])}",
             control_line(r['side']), '',
             f"📍 Entry: {r['entry']:.2f} (market, enter now)", f"🛑 Stop Loss: {r['stop']:.2f}", f"🎯 Take Profit ({rr:.1f}R): {tp:.2f}"]
    if not r.get('target'): lines.append(f"🏃 TP1: {r['tp1']:.2f} (1R) · or exit on {r['exit_rule']}")
    lines += ['', f'📊 Lots: {lots:.2f} | R:R 1:{rr:.1f}', f'💰 Risk: ${risk_usd:,.0f} | Target: ${risk_usd * rr:,.0f}']
    if grade == 'C': lines.append('⚠️ H4 structure NOT confirmed: minimum size only (in the test these lost slightly over a year).')
    elif risk_usd > budget * 1.5:
        lines.append(f'❗ The 0.01 lot minimum risks ${risk_usd:,.0f}, more than the ${budget:,.0f} budget.')
    lines += ['', f'📝 Why: {why}', '',
              '⚠️ Risk Caution: Manage risk responsibly — size your position safely, adhere to your Stop Loss, and never risk more than you can afford to lose.',
              f"🆔 {r['id']} · {r['london'][11:]} London · signal only, no order placed"]
    return '\n'.join(lines)


def path_stats(r, close_ts):
    """MFE / MAE in R and TP1/TP2 touches from 5m candles between entry and close."""
    try:
        b = [x for x in bars('5m', 17) if r['ts'] < x['T'] <= close_ts + 300]
    except SystemExit:
        b = []
    buy = r['side'] == 'BUY'; R = r['risk'] or 1; mfe = mae = 0.0; first = None
    for x in b:
        fav = (x['h'] - r['entry']) if buy else (r['entry'] - x['l']); adv = (r['entry'] - x['l']) if buy else (x['h'] - r['entry'])
        mfe, mae = max(mfe, fav), max(mae, adv)
        if first is None and (mfe >= 0.5 * R or mae >= 0.5 * R): first = 'favourable' if mfe >= 0.5 * R else 'adverse'
    return dict(mfe=round(mfe / R, 2), mae=round(min(mae / R, 1.0) if mae else 0, 2), tp1=mfe >= R, tp2=mfe >= 2 * R, first_half_R=first, bars=len(b))


def review(o):
    """Post-trade analysis: plain findings for the journal and the learning engine."""
    f = o['features']; n = []
    n.append('direction right' if o['mfe'] >= 1 or o['R'] > 0 else 'direction wrong (never reached +1R)')
    if o['first_half_R'] == 'adverse' and o['R'] <= 0: n.append('entry premature: went half a risk against before half a risk for')
    if o['how'] == 'STOP' and o['mfe'] >= 1: n.append('stop hit after reaching +1R: a break-even rule would have saved this')
    if o['R'] > 0 and o['tp2'] and o['R'] < 1: n.append('reached 2R but gave most of it back: the runner exit is slow')
    for k, bad in (('h4', 'against'), ('stretch', 'stretched'), ('room', 'tight'), ('rsi', 'extreme'), ('vol', 'high')):
        if f.get(k) == bad: n.append(f'{k}={bad} at entry')
    return n


def close(rid, exit_price, how, close_ts):
    """A strategy engine reports that its idea (sent or not) has finished by its own exit rules."""
    reg = load_reg(); o = reg['open'].pop(rid, None)
    if o is None: return None
    dec = next((r for r in reversed(read_journal()) if r.get('type') == 'decision' and r['id'] == rid), o)
    sg = 1 if o['side'] == 'BUY' else -1; pl = sg * (exit_price - o['entry']); R = round((pl - 0.4) / o['risk'], 2) if o['risk'] else 0
    out = dict(type='outcome', id=rid, pid=o['pid'], strategy=o['strategy'], side=o['side'], sent=rid in reg['active'], grade=o.get('grade'), verdict=o['verdict'],
               score=dec.get('score'), features=dec.get('features', {}), entry=o['entry'], exit=exit_price, how=how, R=R, usd_per_oz=round(pl, 2),
               opened=ldn(o['ts']).strftime('%Y-%m-%d %H:%M'), closed=ldn(close_ts).strftime('%Y-%m-%d %H:%M'))
    out.update(path_stats(dec, close_ts)); out['review'] = review(out)
    if rid in reg['active']:
        c = cfg(); reg['active'].pop(rid)
        done = [r['R'] for r in read_journal() if r.get('type') == 'outcome' and r.get('sent')] + [R]
        lots, risk_usd, _ = lots_for(o['risk'], c, o.get('grade', 'A'))
        txt = '\n'.join(['👑 CBFX | TRADE RESULT', f"{'🟢 BUY' if o['side'] == 'BUY' else '🔴 SELL'} XAUUSD · {STYLE.get(o['strategy'], ('', o['strategy']))[1]}",
                         f"{'✅ WIN' if R > 0 else '❌ LOSS'} · {how} · {o.get('grade', 'A')}-grade", '',
                         f"📍 Entry: {o['entry']:.2f}  (sent {out['opened'][5:]} London)", f"🏁 Exit: {exit_price:.2f}  ({out['closed'][11:]} London)",
                         f"💰 Result: {R:+.2f}R = {'+' if R >= 0 else '−'}${abs(R) * risk_usd:,.2f} at {lots:.2f} lots",
                         f"📈 Best +{out['mfe']}R · worst −{out['mae']}R · TP1 {'hit' if out['tp1'] else 'missed'} · TP2 {'hit' if out['tp2'] else 'missed'}", '',
                         f"📝 Review: {'; '.join(out['review'])}",
                         f"📒 Brain signals so far: {len(done)}, {sum(done):+.1f}R · 🆔 {rid} · signal only, no order placed"])
        out['telegram'] = publisher.publish(txt, 'result')
    save_reg(reg); journal(out)
    return out


def now_view():
    """Live brain view for the dashboard and Crown: market context and the score each engine's setup would get now."""
    h1, h4, d1 = bars('1h', 14), bars('4h', 60), bars('1d', 120); px = h1[-1]['c']; ts = time.time()
    m, ev = S.load_model(); c = cfg(); rows = []
    ctx = {}
    for side in ('BUY', 'SELL'):
        f, raw = features(side, px, ts, h1, h4, d1); ctx[side] = (f, raw)
        for s in ('H1', 'M15', '4H', 'ASIA', 'SWING'):
            e = ev['swing'][side]['R'] if s == 'SWING' else S.expected(m, s, f)[0]; sc = S.score(m, e)
            rows.append(dict(strategy=s, side=side, score=sc, expected_R=round(e, 3),
                             band='SEND' if sc >= c['send_min'] else 'WATCHLIST' if sc >= c['watch_min'] else 'REJECT'))
    fb, raw = ctx['BUY']
    bias = 'UP' if fb['h4'] == 'with' else 'DOWN' if fb['h4'] == 'against' else 'UNKNOWN'
    regime = f"{'trending' if fb['adx4'] == 'strong' else 'building trend' if fb['adx4'] == 'building' else 'ranging'}, {fb['vol']} volatility"
    best = max(rows, key=lambda r: r['score'])
    support = {sd: [r['strategy'] for r in rows if r['side'] == sd and r['score'] >= c['watch_min']] for sd in ('BUY', 'SELL')}
    return dict(price=round(px, 1), bias=bias, regime=regime, session=fb['session'], context=fb, raw={k: (round(v, 2) if isinstance(v, float) else v) for k, v in raw.items()},
                scores=rows, best=best, support=support,
                conflict=bool(support['BUY'] and support['SELL']),
                explain=(f"H4 trend {bias.lower()}: {best['side']} {NAMES[best['strategy']]} setups score {best['score']} "
                         f"({best['expected_R']:+.2f}R per trade expected). The brain sends only at {c['send_min']}+, so it waits for that engine to fire."))


def status(write=True):
    c = cfg(); reg = load_reg(); J = read_journal(); m, ev = S.load_model()
    dec = [r for r in J if r.get('type') == 'decision']; outc = [r for r in J if r.get('type') == 'outcome']
    sent = [r for r in outc if r['sent']]
    by_s = {}
    for r in outc: by_s.setdefault(r['strategy'], []).append(r['R'])
    try: recs = json.load(open(f'{B}/recommendations.json'))
    except (OSError, ValueError): recs = {}
    st = dict(updated=dt.datetime.now(L).strftime('%Y-%m-%d %H:%M'), operational=True, version=c['version'], send_min=c['send_min'],
              active=[{k: a[k] for k in ('id', 'strategy', 'side', 'entry', 'stop', 'tp1', 'tp2', 'score', 'london')} for a in reg['active'].values()],
              tracking=len(reg['open']), last=[{k: r.get(k) for k in ('id', 'london', 'strategy', 'side', 'entry', 'score', 'verdict', 'reasons')} for r in dec[-8:]],
              counts=dict(proposals=len(dec), sent=sum(r['verdict'] == 'SENT' for r in dec), watchlist=sum(r['verdict'] == 'WATCHLIST' for r in dec),
                          rejected=sum(r['verdict'] == 'REJECTED' for r in dec)),
              sent_results=dict(n=len(sent), R=round(sum(r['R'] for r in sent), 2)),
              strategy_ranking=sorted([dict(strategy=s, n=len(v), R=round(sum(v), 2), avg=round(sum(v) / len(v), 2)) for s, v in by_s.items()], key=lambda x: -x['avg']),
              calibration_unseen=S.calibrate(m, [t for t in ev['trades'] if t['half'] == 'test']), recommendations=recs.get('items', []),
              evidence_ranking=sorted([dict(strategy=s, base_R=round(v, 3)) for s, v in m['base'].items()], key=lambda x: -x['base_R']),
              telegram='one channel: brain/publisher.py; last signal ' + next((r.get('telegram', '') for r in reversed(dec) if r.get('telegram')), 'none yet'))
    try: st['now'] = now_view()
    except Exception as ex: st['now'] = dict(error=type(ex).__name__)
    if write: json.dump(st, open(STATUS, 'w'), indent=1)
    return st


if __name__ == '__main__':
    if sys.argv[1:2] == ['status']:
        print(json.dumps(status(), indent=1))
