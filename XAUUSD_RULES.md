## v3.8 (9 Nov 2026, trader: "use the best one")
v3.7 plus no new trades 00:00-06:00 London (open trades are still managed). Trading windows: Sun 23:00-24:00, then
06:00-22:00 and 23:00-24:00 Mon-Thu, Fri 06:00-20:00. Daily stop 5 losses or -$40, target 1.5R, stop >= 1 ATR (max $10),
15m + 1H + 4H trends must agree. Backtest 13 Oct-6 Nov: 82 trades (4.3/day), 55% wins, +$131, PF 1.95, worst drop $29.

## v3.7 (9 Nov 2026, edge review the trader asked for: "check why it produces losing signals and fix them")
Findings (backtest 13 Oct-6 Nov, all 133 v3.6 trades): losers came mostly from (1) trading against the 4H trend,
(2) stops only 0.5 ATR away that normal 5m noise hit within ~4 candles, (3) a coding error in the bearish engulfing check
(it compared the wrong candle prices, so some non-engulfing candles counted), (4) 00:00-06:00 London (9+18 trades, 22-33% wins, -$47).
Buys lost in every version (36-41% wins) while sells won 57-67%: mostly the falling market of the test period, not a code error.
Fixes now live: 4H trend must agree with the 15m and 1H; stop at least 1 x 5m ATR (still max $10); bearish engulfing fixed.
Backtest 24h + 5 losses/-$40: v3.6 132 trades 48% +$92 PF 1.30 -> v3.7 93 trades 53% +$116 PF 1.62 (4-6 Nov -$13 -> -$2).
Not applied (needs the trader's ok, conflicts with 24/7): pausing 00:00-06:00 London -> 82 trades 55% +$131 PF 1.95, worst drop $29.

## v3.6 (from Mon 9 Nov 2026, trader: "Switch it on")
- Same setup as v3.5 (15m EMAs + 1H trend agree, 5m dip trigger, stop max $10, target 1.5R, 1R room, one trade at a time).
- Hours: around the clock while MT5 gold is open, Sunday 23:00 to Friday 20:00 London, skipping the daily 22:00-23:00 break.
- Exit after 8 hours (Friday: by 21:00 at the latest). Daily stop: 5 losses or -$40 (London calendar day).
- Backtest warning given before switching (13 Oct-6 Nov): 24h + 5 losses/-$40 = 133 trades 7/day, 48% wins, +$88, PF 1.29;
  night trades 20:00-07:00 = 62 trades, 35% wins, -$42. v3.5 on the same data: +$142, 61% wins.

## v3.5 (from Mon 9 Nov 2026; trader chose "the best" on 6 Nov)
- Direction: buy or sell only when the 15m EMA20 vs EMA50 AND the 1H trend agree (1H flat or against = no trade).
- Entry unchanged: 5m candle within 0.5 x 5m ATR of the 5m EMA20, closing as strong close / engulfing / pin bar; no chasing > 1.5 x ATR.
- Stop unchanged (last 3 candles +$1.50, max $10). Target 1.5R or the next level (was 2R). At least 1R of room.
- Hours 07:00-20:00 London weekdays (was 16:30; Fridays until 19:00). Exit after 8h or at 21:00.
- Daily stop: 2 losses or -$20 (back from 5). No news block (setups near news carry a warning).
- Backtest 13 Oct-6 Nov (bt_loose.py, h1='hard', tgt 1.5, hours 07:00-20:00, 2-loss): 64 trades 3.4/day, 61% wins, +$142.45,
  PF 2.07, worst drop $22.55; 4-6 Nov alone 9 trades 44% wins +$3.65. v3.4 on the same data: 56 trades 50% +$108.80.
  Sells +, buys slightly - in this falling market. Review after 20 live trades on v3.5 with no rule changes.

## v3.4 (6 Nov 2026, trader's call)
The 15m EMA20 vs EMA50 alone sets buy or sell; the 1H trend no longer blocks a trade (it is shown in each setup: "✅ 1H trend agrees"
or "⚠️ 1H trend is flat/against: direction from the 15m trend only"). Everything else as v3.3.
Backtest 13 Oct-6 Nov (bt_loose.py h1): 1H hard block 40 trades +$116 PF 2.14; 1H soft (15m decides only when 1H flat) 44 trades +$130 PF 2.17;
15m only (chosen) 47 trades 53% wins +$107 PF 1.80, worst drop $26. Trader was told the hard block tested slightly better.

## v3.3 (5 Nov 2026, trader asked for more setups and said yes)
Same trend-day dip as v3.2 with three changes: (A) the 5m EMA20 no longer has to be on the trend side of the 5m EMA50;
(B) the dip counts when the 5m candle comes within 0.5 x 5m ATR of the 5m EMA20 (was 0.25); (D) the desk trades 07:00-16:30
London straight (lunch included). Everything else unchanged (1H trend + 15m EMAs, trigger candle, stop, 1R room, 2R target, limits, news blackout).
Backtest 13 Oct-5 Nov (/home/user/gold-desk/bt5/bt_loose.py): v3.2 22 trades 1.2/day +$65.60 PF 2.02 dd $28.10;
v3.3 39 trades 2.2/day 56% wins +$123.15 PF 2.29 dd $26.40, halves +40/+83. Backtest has no news filter. Small sample: review after 20 live trades.
Setup messages now start with a siren emoji; results start with a tick, cross or clock.

# XAUUSD trading rules (Claude's, v3.2, 4 Nov 2026: trend-day dip to the 5m EMA20)

Automatic scan ON (trader said yes, 3 Nov): scan/loop.sh checks every 5m candle 07:00-16:30 London (v3.3, 5 Nov) and sends Telegram only when a setup fires; the :01/:16/:31/:46 scheduled scans keep it running.
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
- v3.2 (4 Nov, trader's yes) REPLACES the zone entry: with the 1H trend and the 15m EMA20/EMA50 agreeing, the closed 5m candle
  must dip to the 5m EMA20 (within 0.25 x 5m ATR), with the 5m EMA20 on the trend side of the 5m EMA50, and close as a strong
  close / engulfing / pin bar beyond it. No chasing beyond 1.5 x 5m ATR from the 5m EMA20. Stop beyond the last 3 five minute
  candles +$1.50 (min 0.5 x 5m ATR, max $10). Room and target use prior-day high/low and 1H swings; target 2R or the next level.
  Backtest 13 Oct-4 Nov: 19 trades, 63% wins, +$88.75, PF 3.17, worst drop $8, both halves +$43/+$46, +$82 at double costs;
  the zone entry made 24 trades +$59 PF 2.13; running both made 34 trades +$67 PF 1.78 (worse). Small sample: unproven.
- Homma / Sakata five methods tested 4 Nov (San-zan, San-sen, San-ku, San-pei, San-po): about 8 trades in 3.5 weeks in total,
  mostly losing without the trend filter; not used. The candle triggers above already carry Homma's single-candle signals.
- v3.1 (3 Nov, trader's yes): the trigger candle is the 5m candle. The 1H trend and the 15m EMA20/EMA50 zone still decide
  direction and place; the closed 5m candle must dip into the zone and give the strong close / engulfing / pin bar.
  Stop: beyond the last 3 x 5m candles +$1.50, at least 0.5 x 5m ATR; signal candle no bigger than 2 x 5m ATR.
  Backtest 13 Oct-3 Nov (sessions): 28 trades, 54% wins, +$47, PF 1.81, avg risk $4.40, vs 15m trigger 10 trades +$23.
  Raising the $10 stop cap instead made it worse ($15 cap: -$15, PF 0.79). Only 3 weeks of 5m data: unproven.
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
- No news block since 6 Nov (Woody's call). Setups within 15 min of high-impact USD news (CPI, NFP, PCE, FOMC, GDP, Fed chair) are still sent, with a ⚠️ NEWS WINDOW warning (wide spreads, fast spikes).

## 9. Risk limits
- One open trade at a time, 0.01 lot.
- Stop for the day after 2 losing trades or -$20 (v3.5; was 5 on 6 Nov only).

## 10. Every trade message
- Side, live entry, SL, TP, risk in $, a one-line reason, and a "skip if price is beyond X" level.
- Levels are from the desk feed; if MT5 differs, use the same distances from the MT5 entry.

## 11. Review
- Every setup given is logged in gold-desk/live_log.csv. After 20, compare with the backtest and decide whether to automate.

## Rules freeze (9 Nov 2026)
v3.8 runs unchanged until it has 20 closed live trades (3 closed at the freeze: 2 wins, 1 loss, +$16.10).
Then review: if it is losing over those 20, it has no edge in this market and is switched off.
