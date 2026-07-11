# Stop-Loss

Optional risk control for the DCA strategy. Disabled by default (`stop_loss_percent: 0`).

## How it works

When enabled, a stop-loss threshold is set relative to the trade's anchor price (the
reference high the DCA ladder was built from):

```
threshold = anchor_price * (1 - stop_loss_percent / 100)
```

If a candle's low touches that threshold while a position is open, the entire position
is closed immediately at the threshold price, and the loss is deducted from the
strategy's available budget.

## Execution order per candle

Within an open trade, each candle is evaluated in this order:

1. **DCA fills** — `candle.low <= level_price` fills the next ladder level.
2. **Stop-loss** — `candle.low <= threshold` closes the position at a loss.
3. **Take-profit** — `candle.high >= tp_price` closes the position at a profit.

Stop-loss is checked before take-profit, so if both would trigger on the same candle,
the stop-loss takes precedence (the pessimistic assumption).

## Configuration

```json
{
  "stop_loss_percent": 10.0
}
```

- `0` — disabled, behavior is identical to running without stop-loss at all.
- `> 0` — enabled; the strategy will cut a losing position once price drops
  `stop_loss_percent` below the anchor.

## Why anchor price, not last DCA fill

The threshold is measured from `anchor_price`, the same reference point the DCA
ladder itself is built from — not from the most recent filled level. This keeps
the stop-loss consistent with how take-profit is calculated (portfolio-level,
relative to the trade's origin), rather than reacting to whichever level happened
to fill last.
