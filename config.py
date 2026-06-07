"""Run configuration for backtests.

One place for every setting a run depends on — ticker, date range, starting
capital, and the cost model. Change a value here, or override just one at
construction (e.g. Config(ticker="MSFT")), instead of hunting through the code.

frozen=True makes a Config read-only after creation, so nothing can mutate the
run settings mid-backtest.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    tickers: tuple = ("AAPL",)
    start: str = "2020-01-01"
    end: str = "2023-01-01"
    initial_capital: float = 100_000
    commission_rate: float = 0.001
    slippage_rate: float = 0.0005
    max_participation: float = 1.0  # max fraction of a bar's volume one order can take
    risk_free_rate: float = 0.0     # annual; constant fallback if no rf series is loaded
    risk_free_symbol: str = "^IRX"  # 13-week T-bill yield — time-varying risk-free rate
    benchmark: str = "SPY"          # symbol to measure alpha/beta/info ratio against
