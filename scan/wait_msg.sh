#!/bin/bash
# Session background task: exits (waking the session) as soon as an unsent setup (scan_msg.txt) or trade result (scan_result.txt) is waiting.
G=/home/user/gold-desk
until [ -f "$G/scan_msg.txt" ] || [ -f "$G/scan_result.txt" ]; do sleep 5; done
[ -f "$G/scan_msg.txt" ] && { echo "SETUP WAITING TO BE SENT:"; cat "$G/scan_msg.txt"; }
[ -f "$G/scan_result.txt" ] && { echo "TRADE RESULT WAITING TO BE SENT:"; cat "$G/scan_result.txt"; }
exit 0
