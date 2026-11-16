# Daily swing check (session step, once a day after 22:00 London; skip Saturday)
Strategy and rules: scan/swing_daily.py docstring. Run this once a day when the last line of swing log state
(/home/user/gold-desk/swing_state.json "levels.day") is older than today's date, at or after 22:00 London.
1. Refresh daily gold bars: mcp__FMP__commodity endpoint commodities-historical-price-eod-full, symbol GCUSD,
   from_date = 60 days ago. Merge them into /home/user/gold-desk/gold_daily.json ("bars": [[date, open, high, low, close], ...],
   sorted, one row per date, newer rows replace older ones). Keep the full history (EMA200 needs it).
2. On Mondays (or if macro_weekly.json is over 8 days old) refresh the macro data with mcp__Firecrawl__alexandria_library_read:
   [{"provider":"fred","capability":"series/observations","options":{"series_id":"DFII10","observation_start":"<1 year ago>","frequency":"w","aggregation_method":"eop"}},
    {"provider":"fred","capability":"series/observations","options":{"series_id":"DTWEXBGS","observation_start":"<1 year ago>","frequency":"w","aggregation_method":"eop"}}]
   (2 credits) and merge into /home/user/gold-desk/macro_weekly.json {"ry": [[date, value]], "usd": [[date, value]]} (skip "." values).
3. Run: python3 /home/user/cbf-gold-desk/scan/swing_daily.py daily   (sends PAPER TEST messages to Telegram itself).
4. If it printed SETUP/closed, tell the trader in one line.
