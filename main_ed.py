import queue

from data.downloader import download_data
from data.loader import load_data
from engine.data_handler import DataHandler
from engine.event_loop import EventLoop
from portfolio.portfolio_ed import Portfolio
from strategies.ma_crossover_ed import MACrossoverStrategy
from broker.execution import SimulatedBroker
from analytics.metrics import max_drawdown, sharpe_ratio

def main():
    # data
    df = load_data(download_data('AAPL', '2020-01-01', '2023-01-01'))

    # the ONE shared queue every component talks through
    events = queue.Queue()

    # build components, all sharing the same queue
    data_handler = DataHandler(df, 'AAPL', events)
    strategy = MACrossoverStrategy(data_handler, events, symbol='AAPL')
    portfolio = Portfolio(data_handler, events)
    broker = SimulatedBroker(data_handler, events)

    # run
    loop = EventLoop(data=data_handler, strategy=strategy,
                     portfolio=portfolio, broker=broker, events=events)
    loop.run()

    # report
    print(f"Total return: {portfolio.total_return():.2%}")
    print(f"Max drawdown: {max_drawdown(portfolio.equity_curve):.2%}")
    print(f"Sharpe ratio: {sharpe_ratio(portfolio.equity_curve):.2f}")


if __name__ == "__main__":
    main()