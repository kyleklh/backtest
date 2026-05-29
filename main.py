"""Entry point: wire components together and run a backtest.

    python main.py

Builds the data handler, strategy, portfolio, broker, and performance tracker,
hands them to the event loop, runs it, then prints the performance report.
"""


from data.downloader import download_data
from data.loader import load_data
from engine.event_loop import EventLoop
from portfolio.portfolio import Portfolio
from strategies.buy_and_hold import BuyAndHoldStrategy
from strategies.ma_crossover import MACrossoverStrategy
from analytics.metrics import max_drawdown, sharpe_ratio
from analytics.plot import plot_equity_curve


def run_backtest(df, strategy):
    """Run one strategy through the engine with its own fresh portfolio."""
    portfolio = Portfolio()
    event_loop = EventLoop(data=df, strategy=strategy, portfolio=portfolio, broker=None, event_queue=None)
    event_loop.run()
    return portfolio


def report(label, portfolio):
    print(f"\n{label}")
    print(f"  Total return: {portfolio.total_return():.2%}")
    print(f"  Max drawdown: {max_drawdown(portfolio.equity_curve):.2%}")
    print(f"  Sharpe ratio: {sharpe_ratio(portfolio.equity_curve):.2f}")


def main():
    # get + clean historical data
    csv_path = download_data('AAPL', '2020-01-01', '2023-01-01')
    df = load_data(csv_path)

    # run each strategy through its own backtest
    bh = run_backtest(df, BuyAndHoldStrategy())
    ma = run_backtest(df, MACrossoverStrategy())

    # report metrics
    report("Buy & Hold", bh)
    report("MA Crossover", ma)

    # plot both equity curves on one chart
    plot_equity_curve({
        "Buy & Hold": bh.equity_curve,
        "MA Crossover": ma.equity_curve,
    })


if __name__ == "__main__":
    main()