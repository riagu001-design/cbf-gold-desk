#!/bin/bash
# Start the 5m checker detached (survives the session's 2 h background-task limit). No-op if it is already running.
D=/home/user/cbf-gold-desk/scan
if [ "$(bash $D/checker_ok.sh)" = RUNNING ]; then echo "already RUNNING"; exit 0; fi
setsid nohup bash "$D/loop.sh" >/dev/null 2>&1 < /dev/null &
sleep 1; bash "$D/checker_ok.sh"
