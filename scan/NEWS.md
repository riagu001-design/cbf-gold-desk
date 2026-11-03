# Refreshing today's news blackout (watchdog step)
If /home/user/gold-desk/news_today.json is missing or its "date" is not today's London date:
load mcp__FMP__calendar with ToolSearch, read today's economic calendar, keep high-impact USD releases
(CPI, NFP, PCE, FOMC, GDP, Fed chair, jobless claims, ISM, retail sales) and write
{"date": "YYYY-MM-DD", "events": [["HH:MM", "name"], ...]} with times in London time (empty list if none).
auto_scan.py then skips any setup within 15 min of those times without calling Claude.
If the calendar cannot be read, do not write the file (setups then carry "News calendar not checked").
