#!/bin/bash
# Gold desk: restart the 5m checker whenever this cloud session starts or its worker restarts, so a restart
# cannot leave the desk without a checker until the next watchdog run (it was down 02:05 Thu - 09:05 Fri, 12-13 Nov).
# Idempotent: start_checker.sh does nothing if the checker is already running. Never places orders.
set -uo pipefail
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then exit 0; fi
S="${CLAUDE_PROJECT_DIR:-/home/user/cbf-gold-desk}/scan/start_checker.sh"
[ -f "$S" ] || exit 0
mkdir -p /home/user/gold-desk
bash "$S" >/dev/null 2>&1 || true
exit 0
