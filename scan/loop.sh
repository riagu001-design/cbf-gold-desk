#!/bin/bash
# Runs auto_scan.py 20 s after every 5m candle close. auto_scan.py sends setups to Telegram itself;
# if that send fails it leaves scan_msg.txt and this loop exits, so the session wakes up and sends it. No Claude usage while nothing fires.
D=/home/user/cbf-gold-desk/scan
G=/home/user/gold-desk
echo $$ > "$G/scan_loop.pid"
while true; do
  now=$(date +%s); next=$(( (now / 300 + 1) * 300 + 20 )); sleep $(( next - now ))
  python3 "$D/auto_scan.py" >> "$G/scan_loop.log" 2>&1
  # a setup the scan sent itself is logged; only an unsent one (scan_msg.txt) wakes the session
  if [ -f "$G/scan_msg.txt" ]; then echo "SETUP FIRED"; cat "$G/scan_msg.txt"; exit 0; fi
done
