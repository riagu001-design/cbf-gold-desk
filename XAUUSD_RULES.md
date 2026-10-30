# XAUUSD trading rules (Claude's, 30 Oct 2026)

Written from general gold-trading practice after the old desk rules were deleted. Not backtested yet.

## 1. Orders
- Market orders only: ENTER NOW at the live price. No limit or stop orders.
- If there is no entry right now, the answer is "No trade right now" and why.

## 2. Direction: trade with the 1H trend
- 1H bias = price vs the 1H EMA50 plus swing structure (higher highs/lows = up, lower highs/lows = down).
- Trade only in the 1H direction. If the 1H is flat or choppy, only setup C (sweep) at a session open.
- The 4H is context: a trade against the 4H trend takes half-size targets (TP2 at the next level, no runner).

## 3. Three entry setups (all on the 15m chart, confirmed by a closed candle)
- **A. Pullback:** in a trend, price pulls back into the 15m EMA20–EMA50 zone or a broken level (old support now resistance, or the reverse), and a 15m candle closes in the trend direction (close in the top/bottom third). Enter at market.
- **B. Break and retest:** a 15m close through a key level (prior-day high/low, Asian high/low, round $25 number, 1H swing), then the first retest holds and a 15m candle closes away from it. Enter at market.
- **C. Liquidity sweep:** at the London or New York open, price spikes through the prior-day or Asian high/low, then a 15m candle closes back inside with a long wick. Enter against the sweep. Stop beyond the wick.

## 4. No chasing
- Skip if the entry is more than 1.5 x 15m ATR from the 15m EMA20, or after a candle bigger than 2 x ATR in the trade direction. Wait for the next pullback.

## 5. Stop loss
- Behind the last swing or the rejection wick, plus $1.50 buffer (more if the broker spread is wide).
- Maximum stop $10 at 0.01 lot. A setup that needs a wider stop is skipped.

## 6. Targets
- Need at least 1.5R of room to the next opposing level, or skip.
- TP1 = 1R: close half, move the stop to entry.
- TP2 = 2R or the next key level, whichever comes first.
- Runner (optional): trail the stop behind each new 15m swing.

## 7. When to trade
- Best: London 07:00–10:30 and New York 13:00–16:30 (London time).
- Other hours: only setup A with a clean trend and normal spread.
- No new trades 21:00–00:00 London (rollover, thin market) or after 19:00 London on Fridays.

## 8. News
- No new entries 15 min before to 15 min after high-impact USD news (CPI, NFP, PCE, FOMC, GDP, Fed chair).
- Open trade ahead of news: move the stop to entry if it is in profit, otherwise keep the stop as is.

## 9. Risk limits
- One open trade at a time, 0.01 lot.
- Stop for the day after 2 losing trades or -$20.
- After 3 losing days in a row, halve trading (setups A and B only) until a winning day.

## 10. Every trade message
- Side, live entry, SL, TP1, TP2, risk in $, the setup letter, a one-line reason, and a "skip if price is beyond X" level.
- Levels are from the desk feed; if MT5 differs, use the same distances from the MT5 entry.

## 11. Review
- Log every trade. After 20 trades, review win rate and average R per setup and drop or tighten what does not work.
