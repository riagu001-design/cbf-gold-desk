# XAUUSD trading rules (Claude's, v3, 31 Oct 2026: candle trigger added)

Trial rules for chat answers only; the automatic scans stay off until about 20 live trades show they work.
Backtest (xyz:GOLD 15m, 8 Sep-30 Oct 2026, $0.35 cost, 0.01 lot): 46 trades, 54% wins, +$44, PF 1.31,
worst drop $44 (first half -$3, second half +$47). Unproven: small sample, uneven halves. Code: gold-desk/bt2/.

## 1. Orders
- Market orders only: ENTER NOW at the live price. No limit or stop orders.
- If there is no entry right now, the answer is "No trade right now" and why.

## 2. Direction: trade with the 1H trend
- 1H bias: UP when the 1H close is above the 1H EMA50 and the 1H swings are not lower-highs/lower-lows;
  DOWN when below the EMA50 and the swings are not higher-highs/higher-lows; otherwise FLAT = no trade.
- Trade only in the 1H direction.
- 4H close against the 4H EMA50: cap the target at 1.5R.

## 3. One setup: pullback (15m chart, closed candle)
- 15m EMA20 above EMA50 for a buy (below for a sell).
- The candle dips into the EMA20-EMA50 zone (or touches a key level within 0.25 x ATR) and closes back
  in the trend direction: beyond the EMA20, a bullish candle closing in its top third (bearish, bottom third for a sell).
- Also valid (Homma candle trigger, added 31 Oct): the dip candle is a bullish engulfing (body swallows the previous
  bearish body) or a pin bar (wick at least 2x the body and half the range, close in the top 40%), closing beyond the EMA20.
  Mirror for sells. Backtest: +$77.85, PF 1.53, 49 trades, both halves positive (vs +$44, PF 1.31 without).
- Enter at market on that close.
- Key levels: prior-day high/low, Asian high/low, 1H swing highs/lows, round $25 numbers.
- Break-and-retest and liquidity-sweep setups were dropped: 1-3 and 0-1 trades in 52 days, both losing.

## 4. No chasing
- Skip if the entry is more than 1.5 x 15m ATR from the 15m EMA20, or the signal candle is bigger than 2 x ATR.

## 5. Stop loss
- Beyond the low (buy) or high (sell) of the last 3 candles plus $1.50; at least 0.5 x 15m ATR from entry.
- Maximum stop $10 at 0.01 lot; a setup needing more is skipped.

## 6. Target
- Need at least 1R of room to the next opposing key level, or skip.
- One target: 2R or the next key level, whichever is closer. No stop move to entry
  (moving it at 1R cut the result from +$22 to +$2 in the backtest).
- Time exit: close after 8 hours, or at 21:00 London.

## 7. When to trade
- Best: London 07:00-10:30 and New York 13:00-16:30 (London time); other hours only in a clean trend.
- No new trades 21:00-01:00 London, at weekends, or after 19:00 London on Fridays.

## 8. News
- No new entries 15 min before to 15 min after high-impact USD news (CPI, NFP, PCE, FOMC, GDP, Fed chair).

## 9. Risk limits
- One open trade at a time, 0.01 lot.
- Stop for the day after 2 losing trades or -$20.

## 10. Every trade message
- Side, live entry, SL, TP, risk in $, a one-line reason, and a "skip if price is beyond X" level.
- Levels are from the desk feed; if MT5 differs, use the same distances from the MT5 entry.

## 11. Review
- Every setup given is logged in gold-desk/live_log.csv. After 20, compare with the backtest and decide whether to automate.
