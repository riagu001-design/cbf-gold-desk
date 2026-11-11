"""Dashboard bars and indicators from the checker's own Hyperliquid feed (11 Nov 2026).

Coinversa's candle tool went behind its paid Starter plan when the trial ended, so the dashboard's
Gold indicators and 1m/5m/15m bar panels stopped loading. This writes the same shapes those panels
read (Coinversa's `recent` columns/rows and an `indicators` block) into one file, from the same
Hyperliquid candles the checker trades on. The watchdog uploads it with desk.json.
Output: /home/user/gold-desk/crown/bars.json
"""
import json
import time
from datetime import datetime, timezone

import requests

API = 'https://api.hyperliquid.xyz/info'
OUT = '/home/user/gold-desk/crown/bars.json'


def snap(iv, minutes_back):
    for _ in range(3):
        try:
            r = requests.post(API, json={'type': 'candleSnapshot', 'req': {
                'coin': 'xyz:GOLD', 'interval': iv,
                'startTime': int((time.time() - minutes_back * 60) * 1000)}}, timeout=20).json()
            if r:
                return r
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2)
    raise SystemExit(f'no {iv} candles from Hyperliquid')


def recent(bars, n):
    rows = [[b['t'], float(b['o']), float(b['h']), float(b['l']), float(b['c'])] for b in bars[-n:]]
    return {'columns': ['t', 'o', 'h', 'l', 'c'], 'rows': rows}


def rsi(closes, n=14):
    if len(closes) <= n:
        return None
    g = l = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        g += max(d, 0); l += max(-d, 0)
    g /= n; l /= n
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        l = (l * (n - 1) + max(-d, 0)) / n
    return 100.0 if l == 0 else round(100 - 100 / (1 + g / l), 1)


def main():
    asof = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    b1 = snap('1m', 90)
    b5 = snap('5m', 6 * 60)
    b15 = snap('15m', 3 * 24 * 60)
    closes15 = [float(b['c']) for b in b15]
    r14 = rsi(closes15)
    read = ('overbought' if r14 is not None and r14 >= 70 else
            'oversold' if r14 is not None and r14 <= 30 else 'neutral')
    out = {
        'source': 'Hyperliquid xyz:GOLD (the checker feed)',
        'asOf': asof,
        'gold_1m': {'asOf': asof, 'recent': recent(b1, 60)},
        'gold_5m': {'asOf': asof, 'recent': recent(b5, 60)},
        'gold_15m': {'asOf': asof, 'recent': recent(b15, 40)},
        'technicals': {'interval': '15m', 'asOf': asof, 'last': {'close': closes15[-1]},
                       'indicators': {'rsi14': r14}, 'read': read},
    }
    with open(OUT, 'w') as f:
        json.dump(out, f)
    print(f'bars.json {asof}: 1m {len(b1)}, 5m {len(b5)}, 15m {len(b15)}, RSI14(15m) {r14}')


if __name__ == '__main__':
    main()
