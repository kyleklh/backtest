"""E2E smoke test: full backtest thru the real event loop"""

"""End-to-end smoke test: a full backtest through the real event loop."""

import pandas as pd
import queue
from engine.data_handler import DataHandler
from engine.event_loop import EventLoop
from portfolio.portfolio import Portfolio
from broker.execution import SimulatedBroker
from strategies.buy_and_hold import BuyAndHoldStrategy


def test_buy_and_hold_end_to_end():
    df = pd.DataFrame({
        "open":  [10, 10, 15],
        "high":  [10, 15, 20],
        "low":   [10, 10, 15],
        "close": [10, 15, 20],
        "volume": [1000, 1000, 1000],
    }, index=pd.date_range("2020-01-01", periods=3))

    events = queue.Queue()
    handler = DataHandler({"TEST": df}, ["TEST"], events)
    strategy = BuyAndHoldStrategy(handler, events, "TEST")
    # zero costs so the final number is hand-computable
    portfolio = Portfolio(handler, events, ["TEST"], initial_capital=1000,
                          commission_rate=0, slippage_rate=0)
    broker = SimulatedBroker(handler, events, commission_rate=0, slippage_rate=0)

    loop = EventLoop(data=handler, strategies=[strategy],
                     portfolio=portfolio, broker=broker, events=events)
    loop.run()
    assert portfolio.equity_curve[-1][1] == 2000  # final equity
    assert portfolio.position["TEST"] == 100
    assert portfolio.cash == 0
    assert portfolio.total_return() == 1.0