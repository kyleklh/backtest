# backtester

An event-driven backtesting engine for trading strategies.

## Architecture

The engine processes a chronological stream of events through a central loop:

```
MarketEvent → Strategy → SignalEvent → Portfolio → OrderEvent → Broker → FillEvent → Portfolio
```

| Module | Responsibility |
|--------|----------------|
| `data/` | Download and load historical market data, emit `MarketEvent`s |
| `engine/` | Event queue, simulation clock, event-type definitions |
| `strategies/` | Pluggable signal-generation logic |
| `broker/` | Order modeling, fill simulation, commission & slippage |
| `portfolio/` | Positions, cash, holdings, PnL tracking |
| `analytics/` | Performance metrics, equity curve, reporting |
| `utils/` | Logging and configuration |

## Quick start

```bash
pip install -r requirements.txt

# (optional) download data
python -m data.downloader AAPL --start 2020-01-01 --end 2023-01-01

# run a backtest
python main.py
```

## Adding a strategy

Subclass `BaseStrategy` and implement `calculate_signals(event)`:

```python
from strategies.base_strategy import BaseStrategy
from engine.events import SignalEvent

class MyStrategy(BaseStrategy):
    def calculate_signals(self, event):
        # inspect self.data, push SignalEvent(s) onto self.events
        ...
```

## Testing

```bash
pytest tests/
```
