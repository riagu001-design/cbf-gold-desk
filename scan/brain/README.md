# CrownBearer Neural Brain (17 Nov 2026)

ONE BRAIN. ONE DECISION. ONE AUTHORISED SIGNAL CHANNEL. Signals only: nothing here places orders or connects to MT5 or any broker.

## Flow
```
engines (intelligence providers only)          the brain (core.py)                         Telegram
ema_scan.py   H1 EMA 9/21 cross   ─┐       1 context      features.py                 publisher.py (the ONLY
m15_scan.py   M15 entry, H1 conf. ─┤ propose 2 score 0-100 score.py (evidence)      ──▶ file that can reach
h4_scan.py    4H EMA 9/21, 2R     ─┼──────▶ 3 gates        open, news, fresh, stop,       the Telegram API)
swing_daily   daily pullback      ─┘ (brain_ 4 verdict      daily loss, dup, conflict
                                     link)   5 journal      journal.jsonl, registry.json
```
- Engines call `brain_link.propose()` and keep paper-tracking every idea, approved or not, so the brain learns whether its rejections were right. They cannot send Telegram (`send()` raises PermissionError).
- Verdict: score >= 85 and every gate passes -> **SENT** immediately; 75-84 -> **WATCHLIST**; otherwise **REJECTED** with the reason.
- Message: instrument, side, entry, stop, TP1 (1R), TP2 (2R), runner rule, R:R, score with explanation, context, session.

## The score (score.py)
expected R = engine base R + shrunk (K=30) H4-trend effect, fitted on the train half (to 31 May 2026) of 396 replayed setups (evidence.py, 12 months of 15m XAU/USD in `backtest/data/xau_15m.json`, R after $0.40/oz cost). Score = percentile of that expected R among the train setups. Never manufactured: the dashboard shows the unseen-half check.

| unseen half (Jun-Nov 2026) | setups | avg R |
|---|---|---|
| 85+ | 22 | +0.54 |
| 75-84 | 18 | +0.30 |
| below 75 | 121 | -0.11 |

A model using all eight features failed this check at 85 (-0.08R), so only the H4 trend moves the score. In practice only H1 crosses with the H4 trend reach 85 (89): about one signal a week. 4H with the trend = 83 (watchlist); swing never reaches 85.

## Learning (learn.py)
`python3 scan/brain/learn.py review` -> `brain/recommendations.json`: mistake patterns (need 20+ cases and a 0.25R gap), live feature effects (t >= 2), strategy health (last 20), and a backtest of every feature not yet in the score. Nothing is applied automatically. `learn.py apply <feature>` works only after a passed backtest and saves `brain/history/config_v<n>.json`; `learn.py rollback` restores the previous version.
On 17 Nov only `session` passed (85+ band 0.79R on 21 vs 0.54R on 22). It is NOT applied: the unseen half was already used to choose H4, so it needs live confirmation first.

## Files (/home/user/gold-desk/brain)
config.json (versioned rules), evidence.json, registry.json (active signals + tracked ideas), journal.jsonl (every decision and outcome with MFE/MAE, TP1/TP2, review), status.json (dashboard + Crown), recommendations.json, history/.

## Running
- loop.sh runs the engines every 5 minutes; desk_json.py (watchdog, CROWN.md) runs `learn.review()` + `core.status()` and ships the status to the dashboard's Neural Brain panel.
- Tests: `cd scan/brain && python3 test_brain.py` (16 acceptance tests, temp BRAIN_DIR, nothing sent).
- Not implemented: SMC / FVG / order blocks / Fibonacci / Sakata inputs, spread and margin checks (no data source).
