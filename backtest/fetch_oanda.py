"""Fetch XAU_USD 15m mid candles from OANDA (practice API, read-only candles endpoint; the proxy adds the key).
Writes backtest/data/xau_15m_oanda.json in the same shape as xau_15m.json: {tf, tz, bars: [[utc 'Y-m-d H:M:S', o, h, l, c], ...]}.
Never places orders."""
import json, sys, datetime as dt, requests, os
U = 'https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles'
start = dt.datetime.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else '2023-11-25').replace(tzinfo=dt.timezone.utc)
end = dt.datetime.now(dt.timezone.utc); bars = []; t = start
while t < end:
    r = requests.get(U, params={'granularity': 'M15', 'price': 'M', 'from': t.strftime('%Y-%m-%dT%H:%M:%SZ'), 'count': 5000},
                     headers={'Authorization': 'Bearer x'}, timeout=60)
    r.raise_for_status(); cs = r.json()['candles']
    if not cs: break
    for c in cs:
        if not c['complete']: continue
        ts = dt.datetime.fromisoformat(c['time'][:19]).strftime('%Y-%m-%d %H:%M:%S'); m = c['mid']
        bars.append([ts, float(m['o']), float(m['h']), float(m['l']), float(m['c'])])
    t = dt.datetime.fromisoformat(cs[-1]['time'][:19]).replace(tzinfo=dt.timezone.utc) + dt.timedelta(minutes=15)
    print(len(bars), bars[-1][0], flush=True)
out = os.path.join(os.path.dirname(__file__), 'data', 'xau_15m_oanda.json')
json.dump({'tf': '15m', 'tz': 'UTC', 'source': 'OANDA XAU_USD mid', 'bars': bars}, open(out, 'w'))
print('saved', out, len(bars))
