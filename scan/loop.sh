#!/bin/bash
# Runs auto_scan.py 20 s after every 5m candle close, forever (start it detached with scan/start_checker.sh).
# auto_scan.py sends setups to Telegram itself; if that send fails it leaves scan_msg.txt and skips new scans until it is sent.
# scan/wait_msg.sh (a session background task) wakes the session when scan_msg.txt appears.
D=/home/user/cbf-gold-desk/scan
G=/home/user/gold-desk
echo $$ > "$G/scan_loop.pid"
while true; do
  now=$(date +%s); next=$(( (now / 300 + 1) * 300 + 20 )); sleep $(( next - now ))
  # 23 Nov 2026 (Woody): "Delete all of them". The six old engines (H1 EMA cross, M15 pullback, 4H cross, Asia breakout,
  # trend pullback PB, daily swing) are switched off. Their code stays in git history. The four new setups (H4 trend
  # pullback, breakout-retest, failed breakout, range) go live here only after they pass the backtest
  # (backtest/research_2026-11-23/four_setups.py).
  # 23 Nov 2026 19:00 (Woody: "Do want is best for the system"): the best-tested engine runs live at half size,
  # the best of the four new setups is paper-tracked (not sent) until 20 paper trades.
  python3 "$D/pb_scan.py" >> "$G/scan_loop.log" 2>&1    # PAPER since 28 Nov 2026: trend pullback (lost 60R on 3 years of broker prices)
  python3 "$D/br_scan.py" >> "$G/scan_loop.log" 2>&1
  python3 "$D/d20_scan.py" >> "$G/scan_loop.log" 2>&1   # PAPER since 28 Nov 2026: daily 20-day breakout (the only candidate that passed the 3-year test)    # PAPER: London breakout and retest, thirds + breakeven
  python3 "$D/updates.py" >> "$G/scan_loop.log" 2>&1   # 18 Nov (Woody): daily market updates (Asia range, London/NY plans, Market flips)
done
