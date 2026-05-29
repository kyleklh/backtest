"""Entry point: wire components together and run backtests.

    python main.py

Runs each strategy through the event-driven engine with its own fresh set of
components (data handler, portfolio, broker) sharing one event queue, prints a
performance report, and plots the equity curves for comparison.
"""

import queue

from data.downloader import download_data
from data.loader import load_data
from engine.data_handler import DataHandler
from engine.event_loop import EventLoop
from portfolio.portfolio import Portfolio
from broker.execution import SimulatedBroker
from strategies.buy_and_hold import BuyAndHoldStrategy
from strategies.ma_crossover import MACrossoverStrategy
from analytics.metrics import max_drawdown, sharpe_ratio
from analytics.plot import plot_equity_curve


def run_backtest(df, strategy_factory, symbol="AAPL"):
    """Run one strategy through a fresh engine. strategy_factory is called with
    (data_handler, events, symbol) so each run gets isolated components."""
    events = queue.Queue()
    data_handler = DataHandler(df, symbol, events)
    strategy = strategy_factory(data_handler, events, symbol)
    portfolio = Portfolio(data_handler, events)
    broker = SimulatedBroker(data_handler, events)

    loop = EventLoop(data=data_handler, strategy=strategy,
                     portfolio=portfolio, broker=broker, events=events)
    loop.run()
    return portfolio


def report(label, portfolio):
    print(f"\n{label}")
    print(f"  Total return: {portfolio.total_return():.2%}")
    print(f"  Max drawdown: {max_drawdown(portfolio.equity_curve):.2%}")
    print(f"  Sharpe ratio: {sharpe_ratio(portfolio.equity_curve):.2f}")


def main():
    df = load_data(download_data("AAPL", "2020-01-01", "2023-01-01"))

    bh = run_backtest(df, BuyAndHoldStrategy)
    ma = run_backtest(df, MACrossoverStrategy)

    report("Buy & Hold", bh)
    report("MA Crossover", ma)

    plot_equity_curve({
        "Buy & Hold": bh.equity_curve,
        "MA Crossover": ma.equity_curve,
    })


if __name__ == "__main__":
    main()
