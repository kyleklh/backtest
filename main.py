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


def main():

    portfolio = Portfolio()
    # get historical data
    csv_path = download_data('AAPL', '2020-01-01', '2023-01-01')

    # clean data
    df = load_data(csv_path)

    # strategy
    strategy = BuyAndHoldStrategy()

    # event loop
    event_loop = EventLoop(data = df, strategy=strategy, portfolio=portfolio, broker=None, event_queue=None)

    # run simulation
    event_loop.run()

    print(f"Total return: {portfolio.total_return():.2%}")

if __name__ == "__main__":
    main()