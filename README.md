# backtester

A modular, event-driven backtesting engine for systematic trading strategies.
Components communicate only through events on a shared queue — data, strategy,
execution, and accounting stay cleanly separated, and no component can see prices
it shouldn't.

---

## Architecture

```
                 ┌─────────────┐
   price bars →  │ DataHandler │  emits MarketEvent (shared union timeline)
                 └─────────────┘
                        │ MarketEvent
                        ▼
   ┌────────────┐  SignalEvent  ┌───────────┐  OrderEvent  ┌────────┐  FillEvent
   │  Strategy  │ ────────────► │ Portfolio │ ───────────► │ Broker │ ──────────┐
   └────────────┘               └───────────┘              └────────┘           │
                                      ▲                                          │
                                      └──────────────────────────────────────────┘
                                              FillEvent (update cash + positions)
```

| Module | Responsibility |
|--------|----------------|
| `data/` | Download (`yfinance`, cached to CSV) and clean historical OHLCV |
| `engine/` | `DataHandler` (bar replay, no look-ahead), `EventLoop`, event definitions |
| `strategies/` | Pluggable signal logic (`BaseStrategy` interface) |
| `portfolio/` | Cash, per-symbol positions, average-cost accounting, realized PnL, sizing |
| `broker/` | Order execution, next-bar fills, commission & slippage, market/limit orders |
| `analytics/` | Performance metrics and equity-curve plotting |
| `config.py` | One `Config` dataclass holding all run settings |

---

## Features

- **Event-driven core** — `MarketEvent → SignalEvent → OrderEvent → FillEvent`
  flow through one central loop; no component polls another.
- **No look-ahead, by construction** — strategies read prices through a cursor
  that physically cannot reach future bars.
- **Realistic fills** — orders placed on bar *N* fill at bar *N+1*'s open, never
  at the close you just watched form.
- **Cost model** — configurable commission and slippage on every fill.
- **Whole-share sizing** with equal-split allocation across symbols, sized off
  current equity so gains compound.
- **Multi-symbol** — backtest a universe of tickers on one shared union timeline.
- **Market and limit orders** — limit orders rest until their price is reached.
- **Time-in-force** — GTC, DAY, and GTD order lifetimes with automatic expiry.
- **Performance analytics** — total return, CAGR, max drawdown, annualized
  volatility, Sharpe, time-in-market, realized PnL, win rate, avg win/loss,
  per-trade log, equity-curve plot.
- **Time-varying risk-free rate** — uses the 13-week T-bill yield (`^IRX`) for
  Sharpe; falls back to a constant if unavailable.
- **Tested** — unit tests for every component plus a full end-to-end smoke test.

---

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

`main.py` downloads (and caches) data, runs each strategy through a fresh engine,
prints a report, and plots the equity curves. Re-runs use the cached CSV.

### Configuring a run

All settings live in `config.py`:

```python
from config import Config

cfg = Config(
    tickers=("AAPL", "MSFT"),
    start="2019-01-01",
    initial_capital=50_000,
)
```

| Field | Default | Meaning |
|-------|---------|---------|
| `tickers` | `("AAPL",)` | symbols to backtest |
| `start` / `end` | `2020-01-01` / `2023-01-01` | date range |
| `initial_capital` | `100_000` | starting cash |
| `commission_rate` | `0.001` | fraction of notional per trade |
| `slippage_rate` | `0.0005` | fraction of price per fill |

### Example output

```
MA Crossover
  Total return:   45.12%
  CAGR:           13.22%
  Max drawdown:  -25.14%
  Ann. vol:       22.70%
  Sharpe ratio:    0.66
  Time in market: 55%
  Realized PnL:   45,124.81
  Win rate:       44%  (9 trades)
  Avg win/loss:   23,927.36 / -10,116.93
```

---

## Adding a strategy

Subclass `BaseStrategy`. A strategy receives the data handler, event queue, and
symbol; reads bars through the handler; and pushes `SignalEvent`s. It never
touches cash or orders — that is the Portfolio's job. Directions are `"BUY"` and
`"SELL"`.

```python
from strategies.base_strategy import BaseStrategy
from engine.events import SignalEvent

class MyStrategy(BaseStrategy):
    def __init__(self, data_handler, events, symbol):
        super().__init__()
        self.data_handler = data_handler
        self.events = events
        self.symbol = symbol

    def calculate_signals(self, event):
        if event.type != "MARKET":
            return
        bar = self.data_handler.get_latest_bar(self.symbol)
        # ... decide based on bar or trailing history ...
        self.events.put(SignalEvent(self.symbol, bar.name, "BUY"))
```

Pass the class to `run_backtest(data, MyStrategy, cfg)` in `main.py`.

---

## Testing

```bash
pytest
```

Covers the data handler (no look-ahead guarantee), broker (next-bar and limit
fills), portfolio (average-cost accounting, realized PnL), strategy (crossover
signal timing), and a full end-to-end smoke test.

---

## Design notes

These are deliberate simplifications, not oversights:

- **Union timeline** — the engine walks the union of all symbols' trading dates.
  A symbol only signals/trades on dates it printed a bar (no fabricated prices).
  Positions are marked to market at the last-known close on gap days.
- **Equal-split sizing** — allocates `current_equity / N` per symbol from one
  shared cash pool.
- **Partial fills not modeled** — an order fills in full at next bar's open, or
  not at all. Volume participation is not simulated.

---

## Roadmap

Items are roughly ordered from most foundational to most advanced.

### 1 — Time-series momentum strategy (TSMOM)

> **Reference:** Moskowitz, Ooi & Pedersen (2012), *"Time Series Momentum"*,
> Journal of Financial Economics 104(2), 228–250. [SSRN 2089463](https://ssrn.com/abstract=2089463).

The paper documents significant return continuation across equity index, currency,
commodity, and bond futures for 1–12 months, followed by partial reversal — consistent
with initial under-reaction and delayed over-reaction. A diversified TSMOM portfolio
delivered a Sharpe ratio greater than 1 over 1985–2009 with little exposure to standard
risk factors, and performed best during extreme market moves (the "trend smile").

**Implementation plan:** for each symbol, compute the sign of its 12-month
(252-day) trailing excess return; go long when positive, flat (or short) when
negative; scale each position's size inversely to its ex-ante volatility so every
symbol targets equal risk (the paper uses a 60-day exponentially-weighted variance).
Rebalance monthly.

Key details to get right:
- Skip the most-recent month when computing the lookback return (avoids the
  1-month reversal bias documented by Jegadeesh & Titman 1993).
- Use the existing `SignalEvent` / `PositionSizer` plumbing; the vol-scaling here
  is a preview of roadmap item 3.
- The paper's benchmark: position size = 40% / σₜ, giving ~12% annualised vol
  for the diversified portfolio.

### 2 — Fractional share sizing

The current `PositionSizer` floors to whole shares, which can leave significant
cash idle in small-capital or high-price-stock runs. Add a `fractional=True` flag
in `Config` that allows the broker to fill fractional quantities, matching the
behavior of modern brokers.

### 3 — Volatility-targeted position sizing

Replace the flat equal-split allocator with a volatility-parity sizer: scale each
symbol's allocation so its annualized dollar-volatility contribution equals a
target (e.g. 10% of equity). This makes position risk comparable across
high- and low-vol names and is the standard sizing scheme in trend-following funds.

### 4 — Benchmark comparison and alpha/beta metrics

Run a passive buy-and-hold of the universe (or SPY) alongside every strategy and
compute alpha, beta, information ratio, and tracking error relative to the
benchmark. Output a side-by-side table and plot both equity curves on the same
axes.

### 5 — Extended analytics

Add the metrics that practitioners actually monitor:

- **Sortino ratio** (downside deviation only)
- **Calmar ratio** (CAGR / max drawdown)
- **Rolling Sharpe** (e.g. 252-day window plotted over time)
- **Monthly return heatmap** (year × month grid, color-coded)
- **Underwater / drawdown duration chart**

### 6 — Walk-forward validation

Implement a walk-forward test harness: split the full history into expanding
in-sample windows plus a fixed out-of-sample window, re-optimize strategy
parameters on each in-sample period, then record the out-of-sample performance.
This surfaces overfitting that a single in-sample backtest cannot detect.

### 7 — Parameter optimization

Add a grid-search (or random-search) runner that sweeps strategy hyperparameters,
runs a backtest for each combination, and returns a ranked results table. Include
an overfitting guard: only accept parameters whose out-of-sample Sharpe is within
a tolerance of the in-sample Sharpe.

### 8 — Realistic transaction cost model

Upgrade the current flat-rate model to separate components:

- **Half-spread** based on bid-ask (can be approximated from OHLCV)
- **Market impact** that scales with order size relative to average volume
- **Borrowing cost** for short positions (annualized rate applied daily)

### 9 — Partial fills and volume participation

Model the constraint that large orders cannot be filled instantly. Cap each bar's
fill at a configurable fraction of that bar's reported volume (e.g. 10%). Unfilled
remainder stays on the order book as a pending order.

### 10 — Cross-sectional (relative) momentum strategy

Extend the engine to rank all symbols in the universe each month by trailing
return, go long the top-N quintile, and short (or simply avoid) the bottom-N
quintile. This is the classic Jegadeesh–Titman cross-sectional momentum strategy
and requires the multi-symbol infrastructure already in place.

### 11 — Live trading bridge

Add a thin `LiveBroker` adapter that implements the same `execute_order` interface
as `SimulatedBroker` but routes orders to a real broker API (e.g. Alpaca). The
rest of the system — strategy, portfolio, analytics — remains unchanged, so the
same strategy that ran in backtest can paper-trade live with no modification.

---

## References

| Paper | Where used |
|-------|-----------|
| Moskowitz, T., Ooi, Y.H. & Pedersen, L.H. (2012). *Time Series Momentum.* Journal of Financial Economics 104(2), 228–250. [SSRN 2089463](https://ssrn.com/abstract=2089463). | Roadmap item 1 — TSMOM strategy |
| Jegadeesh, N. & Titman, S. (1993). *Returns to Buying Winners and Selling Losers.* Journal of Finance 48, 65–91. | Roadmap items 1 & 10 — momentum lookback, cross-sectional momentum |
