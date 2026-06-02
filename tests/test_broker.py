"""Tests for the simulated broker (fill timing, slippage, commission)."""

import pandas as pd
import queue
from engine.data_handler import DataHandler
from engine.events import OrderEvent, MarketEvent
from broker.execution import SimulatedBroker

def build():
    """Two-bar fixture: bar 0 close=100, bar 1 open=110. Big gap so the
    difference between same-bar and next-bar fill is unmistakable."""
    df = pd.DataFrame({
        "open":   [100, 110],
        "high":   [101, 111],
        "low":    [99,  109],
        "close":  [100, 110],
        "volume": [1000, 1000],
    }, index=pd.date_range("2020-01-01", periods=2))
    events = queue.Queue()
    handler = DataHandler({"TEST": df}, ["TEST"], events)
    broker = SimulatedBroker(handler, events, commission_rate=0.0, slippage_rate=0.0)
    return handler, broker, events

def test_order_fills_at_next_bar_open():
    handler, broker, events = build()

    # advance to bar 0 and drain its MarketEvent so the queue is clean
    handler.update_bars()
    events.get()

    # strategy submits an order on bar 0 (close=100)
    broker.execute_order(OrderEvent("TEST", "MKT", quantity=1, direction="BUY"))

    # broker should have NOT filled yet — same-bar fill would be the bug
    assert len(broker.pending_orders) == 1           # one order waiting
    assert events.qsize() == 0                       # broker pushed nothing

    # advance to bar 1 (open=110) and trigger the broker
    handler.update_bars()
    market_event = events.get()                      # drain bar 1's MarketEvent
    broker.process_pending_orders(market_event)

    # NOW the broker should have pushed a FillEvent at bar 1's open
    fill = events.get()
    assert fill.type == "FILL"
    assert fill.fill_price == 110                    # bar 1's open, no slippage in this fixture
    assert len(broker.pending_orders) == 0           # pending list cleared


def test_limit_buy_rests_until_price_reached():
    """A limit BUY rests on bars that never reach the limit, then fills at the
    limit once the bar trades down to it."""
    df = pd.DataFrame({
        "open":   [100, 100, 96],
        "high":   [101, 102, 97],
        "low":    [99,  98,  95],    # bar 1 bottoms at 98; bar 2 dips to 95
        "close":  [100, 101, 96],
        "volume": [1, 1, 1],
    }, index=pd.date_range("2020-01-01", periods=3))
    events = queue.Queue()
    handler = DataHandler({"TEST": df}, ["TEST"], events)
    broker = SimulatedBroker(handler, events, commission_rate=0.0, slippage_rate=0.0)

    handler.update_bars()                            # bar 0
    events.get()
    broker.execute_order(OrderEvent("TEST", "LMT", quantity=1, direction="BUY", limit_price=95.5))

    # bar 1: low=98 never reaches 95.5 -> order rests, nothing filled
    handler.update_bars()
    broker.process_pending_orders(events.get())
    assert events.qsize() == 0
    assert len(broker.pending_orders) == 1

    # bar 2: low=95 <= 95.5 -> fills. open=96 is above the limit, so fill AT the limit
    handler.update_bars()
    broker.process_pending_orders(events.get())
    fill = events.get()
    assert fill.type == "FILL"
    assert fill.fill_price == 95.5                   # limit price, not the open
    assert len(broker.pending_orders) == 0
