# backtester

A modular, event-driven backtesting engine for trading strategies, built for
correctness first. Components communicate only through events on a shared queue,
so data, strategy, execution, and accounting stay cleanly separated.

## Features

- **Event-driven core** — `MarketEvent → SignalEvent → OrderEvent → FillEvent`
  flow through one central loop.
- **No look-ahead, by construction** — strategies read prices only through a
  cursor that physically cannot reach future bars.
- **Realistic fills** — orders placed on bar *N* fill at bar *N+1*'s open, never
  at the close you just saw form.
- **Cost model** — configurable commission and slippage on every fill.
- **Whole-share sizing** with an equal-split allocation across symbols, sized off
  current equity (so gains compound).
- **Multi-symbol** — backtest a universe of symbols on one shared timeline.
- **Market and limit orders** — limit orders rest until their price is reached.
- **Performance analytics** — total return, CAGR, max drawdown, annualized
  volatility, Sharpe, time-in-market, realized PnL, win rate, average win/loss,
  and a per-trade log.
- **Tested** — every component plus an end-to-end smoke test (`pytest`).

## Architecture

```
                 ┌─────────────┐
   price bars →  │ DataHandler │  emits MarketEvent (one shared cursor/timeline)
                 └─────────────┘
                        │ MarketEvent
                        ▼
   ┌────────────┐  SignalEvent  ┌───────────┐  OrderEvent  ┌────────┐  FillEvent
   │  Strategy  │ ────────────► │ Portfolio │ ───────────► │ Broker │ ──────────┐
   └────────────┘               └───────────┘              └────────┘           │
                                      ▲                                          │
                                      └──────────────────────────────────────────┘
                                          FillEvent (apply cash/position)
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

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

`main.py` downloads (and caches) the data, runs each strategy through a fresh
engine, prints a report, and plots the equity curves. Re-runs use the cached CSV.

### Configuring a run

All run settings live in one place — `config.py`. Override any field at
construction:

```python
from config import Config

cfg = Config(tickers=("AAPL", "MSFT"), start="2019-01-01", initial_capital=50_000)
```

| Field | Default | Meaning |
|-------|---------|---------|
| `tickers` | `("AAPL",)` | symbols to backtest (a universe of one or more) |
| `start` / `end` | `2020-01-01` / `2023-01-01` | date range |
| `initial_capital` | `100_000` | starting cash |
| `commission_rate` | `0.001` | per-trade commission |
| `slippage_rate` | `0.0005` | per-fill slippage |

### Example output

```
MA Crossover
  Total return:   45.12%
  CAGR:           13.22%
  Max drawdown:   -25.14%
  Ann. vol:       22.70%
  Sharpe ratio:   0.66
  Time in market: 55%
  Realized PnL:   45,124.81
  Win rate:       44% (9 trades)
  Avg win/loss:   23,927.36 / -10,116.93
```

## Adding a strategy

Subclass `BaseStrategy`. A strategy receives `(data_handler, events, symbol)`,
reads prices through the data handler, and pushes `SignalEvent`s — it never
touches cash or orders (that's the Portfolio's job). Signal directions are
`"BUY"` and `"SELL"`.

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
        # ...decide based on bar / trailing history...
        self.events.put(SignalEvent(self.symbol, bar.name, "BUY"))
```

Run it by passing the class to `run_backtest(data, MyStrategy, cfg)` in `main.py`.

## Testing

```bash
pytest
```

Covers the data handler (no look-ahead), broker (next-bar + limit fills),
portfolio (average-cost accounting, realized PnL), strategy (crossover signal
timing), and a full end-to-end smoke test.

## Design notes & simplifications

These are deliberate MVP choices, not oversights:

- **Shared-timeline alignment** uses the *intersection* of symbols' dates —
  correct-by-construction (never fabricates a price) but lossy across mismatched
  calendars. True mixed-frequency support would use per-symbol event streams.
- **Equal-split sizing** allocates `current_equity / N` per symbol. A single cash
  pool, not per-symbol sub-accounts.
- **Limit orders rest GTC** (good-till-cancelled) — they never expire.
- **Sharpe assumes a 0% risk-free rate.**
