#!/bin/bash
# Runs auto_scan.py 20 s after every 5m candle close. Exits when a setup message is written,
# so the session wakes up and sends it to Telegram. No Claude usage while nothing fires.
D=/home/user/cbf-gold-desk/scan
G=/home/user/gold-desk
while true; do
  now=$(date +%s); next=$(( (now / 300 + 1) * 300 + 20 )); sleep $(( next - now ))
  python3 "$D/auto_scan.py" >> "$G/scan_loop.log" 2>&1
  if [ -f "$G/scan_msg.txt" ]; then echo "SETUP FIRED"; cat "$G/scan_msg.txt"; exit 0; fi
done
