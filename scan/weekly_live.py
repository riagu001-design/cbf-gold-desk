#!/usr/bin/env python3
"""Weekly Telegram report from the live trade log (replaces the old desk's weekly_report.py).
  python3 weekly_live.py [YYYY-MM-DD any day of the week]  -> writes /home/user/gold-desk/weekly_msg.txt and sends it."""
import csv, datetime as dt, sys
import auto_scan as a

START = 194.74  # balance at the 30 Oct weekly report
day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.datetime.now(a.L).date()
mon = day - dt.timedelta(days=day.weekday()); fri = mon + dt.timedelta(days=4)
rows = list(csv.DictReader(open(a.LOG)))
L = '━━━━━━━━━━━━━━━━'
val = lambda r: float(r['result'].split()[-1]) if r['result'] and not r['result'].startswith('SKIPPED') else None
before = sum(val(r) or 0 for r in rows if r['given_at_london'][:10] < str(mon))
lines, pl, pips, w, l = [], 0, 0, 0, 0
for r in rows:
    if not (str(mon) <= r['given_at_london'][:10] <= str(fri)):
        continue
    res, e = r['result'], float(r['entry'])
    if not res:
        lines.append(f"⏳ {r['given_at_london'][5:]} {r['side']} {e}: still open"); continue
    if res.startswith('SKIPPED'):
        lines.append(f"⏭ {r['given_at_london'][5:]} {r['side']} {e}: skipped"); continue
    v = val(r); p = round(v * 10)  # 0.01 lot: $1 = 10 pips (gold pip $0.10)
    pl += v; pips += p; w += v > 0; l += v < 0
    lines.append(f"{'✅' if v > 0 else '❌'} {r['given_at_london'][5:]} {r['side']} {e} → {res.split()[0]}: {p:+d} pips, {v:+.2f}$")
n = w + l
msg = (f"📊 GOLD DESK · WEEKLY REPORT\nWeek {mon:%d %b}–{fri:%d %b %Y} · 0.01 lot\n{L}\n" + ("\n".join(lines) or "No setups this week.") +
       f"\n{L}\n🧮 Closed: {n} trades · {w} wins, {l} losses ({round(100 * w / n) if n else 0}% wins)\n📏 Pips: {pips:+d} (gold pip = $0.10)\n"
       f"💰 Result: {pl:+.2f}$\n💼 Account: about ${START + before + pl:.2f} (from ${START + before:.2f} at the start of the week)\n{L}\n"
       "ℹ️ Spread not included; MT5 prices run about $3–4 below the desk feed.")
open('/home/user/gold-desk/weekly_msg.txt', 'w').write(msg)
print(msg); print('Telegram:', a.send_telegram(msg) if '--dry' not in sys.argv else 'dry run')
