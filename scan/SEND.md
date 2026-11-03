# Sending a setup (used by the watchdog scans and when loop.sh exits with "SETUP FIRED")
1. `mv /home/user/gold-desk/scan_msg.txt /home/user/gold-desk/scan_msg.sending` - if the mv fails, another run is already sending: stop.
2. News check: load mcp__FMP__calendar with ToolSearch; high-impact USD release (CPI, NFP, PCE, FOMC, GDP, Fed chair, jobless claims, ISM, retail sales) within 15 min either side of now?
   - Yes: do not send. Delete scan_msg.sending, set that trade's result in /home/user/gold-desk/live_log.csv to "SKIPPED news", set "open" to null in /home/user/gold-desk/scan_state.json.
   - Calendar unreadable: send anyway with an extra last line "News calendar not checked".
3. Send scan_msg.sending's exact text as ONE Telegram message: mcp__claude-code-remote__create_session in env_01N2nUJa5bbsKyUvG6B2uDSH whose prompt writes the text to /tmp/msg.txt with a quoted heredoc (<<'EOF') and runs
   curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" --data-urlencode "chat_id=${TELEGRAM_ALLOWED_ID:-1192966973}" --data-urlencode text@/tmp/msg.txt | python3 -c "import sys,json;d=json.load(sys.stdin);print('ok',d['result']['message_id']) if d.get('ok') else print('FAILED',d.get('description'))"
   replying with only that line. Poll list_events kinds ["result"] until it has a result, then archive_session it. Never print the token.
4. ok: delete scan_msg.sending. FAILED: mv it back to scan_msg.txt so the next watchdog retries.
5. Restart the checker if `bash /home/user/cbf-gold-desk/scan/checker_ok.sh` prints STOPPED: Bash run_in_background, timeout 7200000: bash /home/user/cbf-gold-desk/scan/loop.sh
6. Tell the trader the setup text and the Telegram result (London times).
