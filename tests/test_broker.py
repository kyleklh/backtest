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


def test_day_order_cancelled_when_unfilled():
    """A DAY order that can't fill on its one eligible bar is cancelled, not rested."""
    handler, broker, events = build()
    handler.update_bars()
    events.get()                                     # drain bar 0's MarketEvent
    # limit far below any price -> can never fill
    broker.execute_order(OrderEvent("TEST", "LMT", quantity=1, direction="BUY",
                                    limit_price=1.0, order_id=1, tif="DAY"))

    handler.update_bars()
    broker.process_pending_orders(events.get())      # bar 1: unfilled -> DAY expires

    assert len(broker.pending_orders) == 0           # not resting
    status = events.get()
    assert status.type == "STATUS"
    assert status.status == "CANCELLED"
    assert status.order_id == 1


def test_cancel_removes_working_order():
    """broker.cancel pulls a resting order off the book and reports it cancelled."""
    handler, broker, events = build()
    handler.update_bars()
    events.get()
    broker.execute_order(OrderEvent("TEST", "LMT", quantity=1, direction="BUY",
                                    limit_price=1.0, order_id=5, tif="GTC"))
    assert len(broker.pending_orders) == 1

    broker.cancel(5)

    assert len(broker.pending_orders) == 0
    status = events.get()
    assert status.type == "STATUS"
    assert status.status == "CANCELLED"
    assert status.order_id == 5


def build_vol(volume, participation, n=4):
    """Flat-price fixture with a fixed per-bar volume, so a volume-participation
    cap forces partial fills. Zero costs to keep arithmetic clean."""
    prices = [100] * n
    df = pd.DataFrame({
        "open": prices, "high": [p + 1 for p in prices], "low": [p - 1 for p in prices],
        "close": prices, "volume": [volume] * n,
    }, index=pd.date_range("2020-01-01", periods=n))
    events = queue.Queue()
    handler = DataHandler({"TEST": df}, ["TEST"], events)
    broker = SimulatedBroker(handler, events, commission_rate=0.0, slippage_rate=0.0,
                             max_participation=participation)
    return handler, broker, events


def test_market_order_fills_partially_over_bars():
    handler, broker, events = build_vol(volume=100, participation=0.5)   # cap = 50/bar
    handler.update_bars()
    events.get()
    broker.execute_order(OrderEvent("TEST", "MKT", 120, "BUY", order_id=1, tif="GTC"))

    # bar 1: takes 50, no terminal status yet, rests with 50 filled
    handler.update_bars()
    broker.process_pending_orders(events.get())
    assert events.get().quantity == 50
    assert events.empty()
    assert broker.pending_orders[0].filled_qty == 50

    # bar 2: another 50
    handler.update_bars()
    broker.process_pending_orders(events.get())
    assert events.get().quantity == 50

    # bar 3: final 20 -> FILLED
    handler.update_bars()
    broker.process_pending_orders(events.get())
    assert events.get().quantity == 20
    status = events.get()
    assert status.status == "FILLED"
    assert len(broker.pending_orders) == 0


def test_ioc_fills_available_then_cancels_remainder():
    handler, broker, events = build_vol(volume=100, participation=0.5)   # cap = 50
    handler.update_bars()
    events.get()
    broker.execute_order(OrderEvent("TEST", "MKT", 120, "BUY", order_id=2, tif="IOC"))

    handler.update_bars()
    broker.process_pending_orders(events.get())
    assert events.get().quantity == 50                  # filled what it could
    assert events.get().status == "CANCELLED"           # remainder killed immediately
    assert len(broker.pending_orders) == 0


def test_fok_cancels_entirely_when_it_cannot_fill_all():
    handler, broker, events = build_vol(volume=100, participation=0.5)   # cap = 50 < 120
    handler.update_bars()
    events.get()
    broker.execute_order(OrderEvent("TEST", "MKT", 120, "BUY", order_id=3, tif="FOK"))

    handler.update_bars()
    broker.process_pending_orders(events.get())
    status = events.get()
    assert status.status == "CANCELLED"
    assert events.empty()                               # no partial fill happened
    assert len(broker.pending_orders) == 0


def test_fok_fills_when_capacity_allows():
    handler, broker, events = build_vol(volume=100, participation=1.0)   # cap = 100 >= 80
    handler.update_bars()
    events.get()
    broker.execute_order(OrderEvent("TEST", "MKT", 80, "BUY", order_id=4, tif="FOK"))

    handler.update_bars()
    broker.process_pending_orders(events.get())
    assert events.get().quantity == 80
    assert events.get().status == "FILLED"
