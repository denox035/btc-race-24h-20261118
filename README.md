# BTC trend bot — make.fun btc-race-24h-20261118-1444

A long-only trading bot for Coinbase Wrapped BTC (cbBTC) on 1-minute
on-chain bars, built for the make.fun bounty "Race a BTC trading bot live
for 24 hours".

## Strategy

Hourly momentum, nothing else:

- **Signal:** the 60-minute return of the close,
  `r60 = close / close_60_bars_ago - 1`. In the published dev window the
  60-minute return predicts the next 60 minutes (correlation about +0.27),
  while 1-minute noise is far smaller than the ~30 bps a full round trip
  costs — so the bot only acts on the hourly scale.
- **Entry:** r60 stays above **+0.5% for 3 consecutive bars** (the
  confirmation filters one-bar noise spikes). Buys 100% of cash.
- **Exit:** r60 falls below **-0.5%** (the hourly trend has turned), or the
  close falls **0.8% below the highest close since entry** (trailing stop
  that caps how much of a run-up is given back). Sells the whole position.
- Every order carries `max_slippage_bps` 200, so a fill more than 2% away
  from the last close (a violent gap) is rejected instead of chased.
- No trades in the first 60 bars (no history yet) or during a warm-up.

All comparisons are integer arithmetic, so two runs on the same data give
byte-identical replies.

## Local dev-window result

Replayed through an exact port of the kit harness's fill model
(fee 4 bps, slippage 2 bps, constant-product impact against each bar's
open depth, 1-bar fill latency) on the kit's frozen 24h dev window
(1,440 bars, BTC −2.80% over the window):

- **Net PnL: +$13.32** (buy-and-hold on the same window: −$31.63)
- **Trades: 2** (one round trip: bought the recovery, sold near the top)
- **Max drawdown: 0.68%** (guardrail: ≤ 25%)

## Run

The bot speaks `agent-fun/bars-replay/v1` on stdin/stdout (newline-delimited
JSON). Python 3.13, standard library only:

```sh
python3 main.py
```

It reads `hello`, then one reply per `batch`, and exits on `done`.
To grade it locally against the kit:

```sh
node cli/makefun.mjs grade-local --kit <kit-dir> --bot <this-repo> --driver docker
```

## Files

- `main.py` — the bot (entrypoint)
- `README.md` — this file
- `LICENSE` — MIT
