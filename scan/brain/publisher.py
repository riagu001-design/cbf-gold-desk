"""CrownBearer Neural Brain: the ONE authorised Telegram channel.

Only brain.py (signals and their results) and the weekly account report call this module. Strategy engines,
scanners and indicators have no Telegram access: they submit proposals to brain.submit() instead.
Never prints the token.
"""
import os, requests

TG_ENV = '/root/.claude/channels/telegram/.env'
TG_CHAT = '1192966973'
FALLBACK = {'signal': '/home/user/gold-desk/scan_msg.txt', 'result': '/home/user/gold-desk/scan_result.txt'}


def _post(text):
    if os.environ.get('SCAN_TEST') == '1':
        print('TELEGRAM (test, not sent):\n' + text); return 'test'
    try:
        token = [l.split('=', 1)[1].strip() for l in open(TG_ENV) if l.startswith('TELEGRAM_BOT_TOKEN=')][0]
        r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', data={'chat_id': TG_CHAT, 'text': text}, timeout=15).json()
        return f"ok {r['result']['message_id']}" if r.get('ok') else f"FAILED {r.get('description')}"
    except Exception as e:  # blocked host, no token file, timeout
        return f'FAILED {type(e).__name__}'


def publish(text, kind):
    """kind 'signal' or 'result' (from brain.py) or 'report' (weekly account report). On failure, signals and
    results are left in scan_msg.txt / scan_result.txt for the watchdog to send (scan/SEND.md)."""
    assert kind in ('signal', 'result', 'report')
    r = _post(text)
    if not r.startswith(('ok', 'test')) and kind in FALLBACK:
        with open(FALLBACK[kind], 'a') as f: f.write(text + ('\n\n' if kind == 'result' else ''))
    return r
