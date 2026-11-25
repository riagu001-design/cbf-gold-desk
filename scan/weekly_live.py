#!/usr/bin/env python3
"""Weekly Telegram report (every Friday after the close).
24 Nov 2026: reports the engines that run now -
  LIVE   Trend Pullback with the H4 filter (pb_log.csv, B-grade, sent at half size)
  PAPER  London breakout and retest (br_log.csv, not sent)
  plus any rows still in the old live_log.csv.
  python3 weekly_live.py [YYYY-MM-DD any day of the week] [--dry]  -> writes /home/user/gold-desk/weekly_msg.txt and sends it."""
import csv, datetime as dt, os, sys
import auto_scan as a
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/brain')
import publisher  # the brain's single Telegram channel

G = '/home/user/gold-desk'
START = 194.74  # balance at the 30 Oct weekly report
args = [x for x in sys.argv[1:] if not x.startswith('--')]
day = dt.date.fromisoformat(args[0]) if args else dt.datetime.now(a.L).date()
mon = day - dt.timedelta(days=day.weekday()); fri = mon + dt.timedelta(days=4)
L = '━━━━━━━━━━━━━━━━'


def load(path):
    return list(csv.DictReader(open(path))) if os.path.exists(path) else []


def in_week(s):
    return str(mon) <= (s or '')[:10] <= str(fri)


def engine(rows, how_key):
    """Lines and totals for an engine log with opened/side/entry/closed/usd_001/R columns."""
    out, R, usd, w, l, before = [], 0.0, 0.0, 0, 0, 0.0
    for r in rows:
        if (r.get('opened') or '')[:10] < str(mon) and r.get('usd_001'):
            before += float(r['usd_001'])
        if not in_week(r.get('opened')):
            continue
        if not r.get('closed'):
            out.append(f"⏳ {r['opened'][5:]} {r['side']} {r['entry']}: still open"); continue
        rv, uv = float(r['R']), float(r['usd_001'])
        R += rv; usd += uv; w += rv > 0; l += rv <= 0
        out.append(f"{'✅' if rv > 0 else '❌'} {r['opened'][5:]} {r['side']} {r['entry']} → {r.get(how_key) or 'closed'}: {rv:+.2f}R, {uv:+.2f}$")
    return out, R, usd, w, l, before


pb_lines, pbR, pbU, pbW, pbL, pb_before = engine(load(f'{G}/pb_log.csv'), 'how')
br_lines, brR, brU, brW, brL, _ = engine(load(f'{G}/br_log.csv'), 'exit_note')

# old live log (rules v3.x), kept so nothing is lost
old = load(a.LOG)
val = lambda r: float(r['result'].split()[-1]) if r['result'] and not r['result'].startswith('SKIPPED') else None
old_before = sum(val(r) or 0 for r in old if r['given_at_london'][:10] < str(mon))
old_lines, old_pl = [], 0.0
for r in old:
    if in_week(r['given_at_london']) and val(r) is not None:
        old_pl += val(r); old_lines.append(f"• {r['given_at_london'][5:]} {r['side']} {r['entry']}: {val(r):+.2f}$")

n = pbW + pbL
week_usd = pbU + old_pl
acct_start = START + old_before + pb_before
msg = (f"📊 GOLD DESK · WEEKLY REPORT\nWeek {mon:%d %b}–{fri:%d %b %Y}\n{L}\n"
       f"🟢 LIVE · Trend Pullback + H4 filter (B-grade, half size)\n" + ("\n".join(pb_lines) or "No signals this week (the H4 filter waits for a clear trend).") +
       f"\nClosed: {n} · {pbW} wins, {pbL} losses ({round(100 * pbW / n) if n else 0}% wins) · {pbR:+.2f}R · {pbU:+.2f}$ at 0.01 lot\n{L}\n"
       f"📝 PAPER · London breakout and retest (not sent)\n" + ("\n".join(br_lines) or "No paper trades this week.") +
       f"\nPaper total: {brW + brL} closed · {brR:+.2f}R · {brU:+.2f}$ at 0.01 lot\n{L}\n" +
       (("Old rules log:\n" + "\n".join(old_lines) + f"\n{L}\n") if old_lines else "") +
       f"💼 Account: about ${acct_start + week_usd:.2f} (from ${acct_start:.2f} at the start of the week, 0.01 lot basis)\n"
       f"🎯 Review: after 20 live trades the result is compared with the test (+0.24R a trade).\n{L}\n"
       "ℹ️ R after a 0.40/oz cost allowance; broker prices run about $3–4 below the desk feed.")
open(f'{G}/weekly_msg.txt', 'w').write(msg)
print(msg); print('Telegram:', publisher.publish(msg, 'report') if '--dry' not in sys.argv else 'dry run')
