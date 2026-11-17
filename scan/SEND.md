# Sending a Neural Brain signal when brain/publisher.py could not send it itself (used by the watchdog scans and when scan/wait_msg.sh finishes with "SETUP WAITING TO BE SENT")
The CrownBearer Neural Brain (scan/brain/core.py) is the only signal authority. It already scored the setup (85+), checked news, freshness, stop, daily loss, duplicates and conflicts before writing scan_msg.txt. This file only delivers that exact text; never edit it, never send anything the brain did not write.
1. `mv /home/user/gold-desk/scan_msg.txt /home/user/gold-desk/scan_msg.sending` - if the mv fails, another run is already sending: stop.
2. Freshness: if the text's signal time is more than 15 minutes old, send it anyway with an extra last line "⚠️ Delayed delivery: check price before entering".
3. Send scan_msg.sending's exact text as ONE Telegram message: mcp__claude-code-remote__create_session in env_01N2nUJa5bbsKyUvG6B2uDSH whose prompt writes the text to /tmp/msg.txt with a quoted heredoc (<<'EOF') and runs
   curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" --data-urlencode "chat_id=${TELEGRAM_ALLOWED_ID:-1192966973}" --data-urlencode text@/tmp/msg.txt | python3 -c "import sys,json;d=json.load(sys.stdin);print('ok',d['result']['message_id']) if d.get('ok') else print('FAILED',d.get('description'))"
   replying with only that line. Poll list_events kinds ["result"] until it has a result, then archive_session it. Never print the token.
4. ok: delete scan_msg.sending. FAILED: mv it back to scan_msg.txt so the next watchdog retries.
5. Make sure the checker runs: bash /home/user/cbf-gold-desk/scan/start_checker.sh. Re-arm the send watcher: Bash run_in_background (timeout 7200000): bash /home/user/cbf-gold-desk/scan/wait_msg.sh
6. Tell the trader the setup text and the Telegram result (London times).

# Sending a trade result (scan_result.txt: brain/publisher.py writes it when a trade hits its stop, target or time exit and the direct send fails)
1. `mv /home/user/gold-desk/scan_result.txt /home/user/gold-desk/scan_result.sending` - if the mv fails, another run is already sending: stop.
2. No news check. Send its exact text as ONE Telegram message the same way as step 3 above (child session, quoted heredoc, curl, archive).
3. ok: delete scan_result.sending. FAILED: append its text back to scan_result.txt so the next watchdog retries.
4. Re-arm the send watcher as in step 5 above, and tell the trader the result (London times).
