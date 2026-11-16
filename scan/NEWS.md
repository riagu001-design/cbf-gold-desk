# Refreshing today's news block (watchdog step)
If /home/user/gold-desk/news_today.json is missing or its "date" is not today's London date:
1. If /home/user/gold-desk/news_week.json has today's date under "events", write
   {"date": "YYYY-MM-DD", "events": <that list>} to news_today.json. Done.
2. Otherwise (new week, or the file is missing) load the week from Forex Factory through Firecrawl:
   mcp__Firecrawl__alexandria_library_read with calls
   [{"provider": "forexfactory-com", "capability": "economic-calendar/list_events",
     "options": {"currencies": ["USD"], "date": "<today YYYY-MM-DD>", "impacts": ["high"], "view": "week"}}]
   (about 5 Firecrawl credits). Use each event's datetime_utc converted to London time (GMT in winter, BST in summer),
   write news_week.json {"week_start", "source", "events": {"YYYY-MM-DD": [["HH:MM", "name"], ...], ...}} for every
   weekday of that week (empty lists where none), then write news_today.json from it.
auto_scan.py blocks new entries from 5 min before to 5 min after each listed time (16 Nov rule, Woody) and adds a
news warning to setups 6-15 min either side. FMP has no economic calendar on this plan, so do not use it.
If the calendar cannot be read, do not write the file (setups then carry "News calendar not checked").

Also on every watchdog run: if it is after 22:00 London (not Saturday) and swing_state.json levels.day is not today, follow scan/SWING.md.
