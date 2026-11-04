#!/bin/bash
# Runs auto_scan.py 20 s after every 5m candle close, forever (start it detached with scan/start_checker.sh).
# auto_scan.py sends setups to Telegram itself; if that send fails it leaves scan_msg.txt and skips new scans until it is sent.
# scan/wait_msg.sh (a session background task) wakes the session when scan_msg.txt appears.
D=/home/user/cbf-gold-desk/scan
G=/home/user/gold-desk
echo $$ > "$G/scan_loop.pid"
while true; do
  now=$(date +%s); next=$(( (now / 300 + 1) * 300 + 20 )); sleep $(( next - now ))
  python3 "$D/auto_scan.py" >> "$G/scan_loop.log" 2>&1
done
