"""BTC trend bot for make.fun btc-race-24h-20261118-1444.

Strategy (designed from the kit's dev dataset, first principles only):
  - One asset, CBBTC, long only, at most one open position, full-size trades.
  - Signal: the 60-minute return of the close, r60 = close / close_60_bars_ago - 1.
    Hourly momentum persists in this market (the dev window's 60-minute
    returns correlate about +0.27 with the next 60 minutes), while 1-minute
    noise is far smaller than the ~30 bps a full round trip costs, so the bot
    only acts on the hourly scale.
  - Entry: r60 stays above +0.5% for 3 consecutive bars (the 3-bar
    confirmation filters one-bar noise spikes). Buy 100% of cash.
  - Exit: r60 falls below -0.5% (the hourly trend has turned), or the close
    falls 0.8% below the highest close since entry (trailing stop that caps
    how much of a run-up is given back). Sell the whole position.
  - Every order carries max_slippage_bps 200, so a fill more than 2% away
    from the last close (a violent gap) is rejected instead of chased.
  - No trades in the first 60 bars (no history yet) or during a warm-up.

All comparisons are integer arithmetic, so two runs on the same data give
byte-identical replies. Standard library only; no network, no clock, no
files. Speaks agent-fun/bars-replay/v1: hello, then one reply per batch.
"""

import json
import sys

SYMBOL = "CBBTC"

# Strategy constants (all integer math; a percent is parts per 1000 here).
LOOKBACK = 60            # bars back for the momentum return
ENTRY_BPS = 5            # +0.5% in tenths of a percent (5/1000)
EXIT_BPS = 5             # -0.5%
CONFIRM_BARS = 3         # consecutive bars the entry signal must hold
TRAIL_BPS = 8            # 0.8% trailing stop from the peak close
MAX_SLIPPAGE_BPS = 200   # 2% cap on how far a fill may sit from the last close


def main():
    closes = []          # CBBTC closes (ints), in bar order
    peak = None          # highest close since the current position opened
    was_in_position = False  # position state on the previous batch
    consec = 0           # consecutive bars with r60 above the entry threshold
    warmup_bars = 0
    order_no = 0

    inp = sys.stdin
    out = sys.stdout

    for line in inp:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        kind = msg.get("type")

        if kind == "hello":
            warmup_bars = int(msg.get("warmup_bars") or 0)
            continue

        if kind == "done":
            break

        if kind != "batch":
            continue

        seq = msg["seq"]
        account = msg["account"]
        cash = int(account["cash_quote_units"])
        positions = account.get("positions") or []
        qty = 0
        for p in positions:
            if p["symbol"] == SYMBOL:
                qty = int(p["qty"])
                break

        bar = None
        for b in msg.get("bars") or []:
            if b["symbol"] == SYMBOL:
                bar = b
                break

        orders = []
        if bar is not None:
            close = int(bar["c"])
            closes.append(close)

            if qty > 0:
                # Track the peak close since entry from the account's own
                # position state, so a rejected sell never loses the peak.
                if not was_in_position:
                    peak = close
                elif peak is not None and close > peak:
                    peak = close
                # Exit: hourly trend turned, or trailing stop hit.
                exit_now = False
                if len(closes) > LOOKBACK:
                    old = closes[-LOOKBACK - 1]
                    # r60 < -0.5%  <=>  1000*close < 995*old
                    if 1000 * close < (1000 - EXIT_BPS) * old:
                        exit_now = True
                # close < peak * (1 - 0.8%)  <=>  1000*close < 992*peak
                if peak is not None and 1000 * close < (1000 - TRAIL_BPS) * peak:
                    exit_now = True
                if exit_now:
                    order_no += 1
                    orders.append({
                        "side": "sell",
                        "client_id": "s%d" % order_no,
                        "symbol": SYMBOL,
                        "qty": str(qty),
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    })
            else:
                peak = None
                # Entry: r60 above +0.5% for CONFIRM_BARS consecutive bars.
                if len(closes) > LOOKBACK and seq >= warmup_bars:
                    old = closes[-LOOKBACK - 1]
                    # r60 > +0.5%  <=>  1000*close > 1005*old
                    if 1000 * close > (1000 + ENTRY_BPS) * old:
                        consec += 1
                    else:
                        consec = 0
                    if consec >= CONFIRM_BARS and cash > 0:
                        order_no += 1
                        orders.append({
                            "side": "buy",
                            "client_id": "b%d" % order_no,
                            "symbol": SYMBOL,
                            "notional_quote_units": str(cash),
                            "max_slippage_bps": MAX_SLIPPAGE_BPS,
                        })
                        consec = 0
        # A batch with no CBBTC bar (a gap minute): no signal update, no orders.
        was_in_position = qty > 0

        out.write(json.dumps(
            {"type": "reply", "seq": seq, "orders": orders},
            separators=(",", ":")) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
