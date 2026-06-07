"""Tests for portfolio accounting: avg cost, realized PnL, win rate."""

import pandas as pd
import pytest
import queue
from engine.events import FillEvent, SignalEvent
from engine.data_handler import DataHandler
from portfolio.portfolio import Portfolio

def fill(direction, qty, price, comm):
    """Build a FillEvent directly so the portfolio is tested in isolation —
    no broker, no queue, no slippage model in the way."""
    return FillEvent("TEST", timestamp=None, quantity=qty,
                     direction=direction, fill_price=price, commission=comm)

def test_two_round_trips_one_win_one_loss():
    # on_fill never touches the data handler, so None is fine here.
    p = Portfolio(data_handler=None, events=queue.Queue(), symbols=["TEST"],
                  initial_capital=100000)

    p.on_fill(fill("BUY",  10, 100, 10))   # avg_cost -> 101.0
    p.on_fill(fill("BUY",  10, 120, 12))   # avg_cost -> 111.1
    p.on_fill(fill("SELL", 20, 150, 30))   # closes round-trip 1: +748
    p.on_fill(fill("BUY",  10, 200, 20))   # avg_cost -> 202.0
    p.on_fill(fill("SELL", 10, 180, 18))   # closes round-trip 2: -238

    assert p.position["TEST"] == 0
    assert p.cash == pytest.approx(100510)
    assert p.realized_pnl == pytest.approx(510)
    assert [t.pnl for t in p.trades] == pytest.approx([748, -238])
    assert p.num_trades() == 2
    assert p.win_rate() == 0.5

    # the trade records carry the round-trip detail, not just the PnL
    first = p.trades[0]
    assert first.symbol == "TEST"
    assert first.shares == 20
    assert first.entry_price == pytest.approx(111.1)   # avg cost of the two buys
    assert first.exit_price == 150                     # the sell fill price

    # invariant: when flat, cash gained must equal cumulative realized PnL
    assert p.cash - p.initial_capital == pytest.approx(p.realized_pnl)

def test_unrealized_pnl_uses_current_close():
    df = pd.DataFrame({
        "open":   [100, 130],
        "high":   [101, 131],
        "low":    [99,  129],
        "close":  [100, 130],
        "volume": [1000, 1000],
    }, index=pd.date_range("2020-01-01", periods=2))
    handler = DataHandler({"TEST": df}, ["TEST"], queue.Queue())
    handler.update_bars()
    handler.update_bars()                              # advance to bar 1
    assert handler.get_latest_bar_value("TEST", "close") == 130   # confirm cursor landed on bar 1

    p = Portfolio(data_handler=handler, events=queue.Queue(), symbols=["TEST"],
                  initial_capital=100000)
    p.on_fill(fill("BUY", 10, 100, 0))     # avg_cost = 100, position = 10

    assert p.unrealized_pnl() == 10 * (130 - 100)   # == 300


def test_short_round_trip_profits_when_price_falls():
    p = Portfolio(data_handler=None, events=queue.Queue(), symbols=["TEST"],
                  initial_capital=100000)

    p.on_fill(fill("SELL", 10, 100, 1))    # open short: avg = (10*100 - 1)/10 = 99.9
    p.on_fill(fill("BUY",  10, 90,  1))    # cover at 90: pnl = 10*(99.9 - 90) - 1 = 98

    assert p.position["TEST"] == 0
    assert p.realized_pnl == pytest.approx(98)
    assert [t.pnl for t in p.trades] == [pytest.approx(98)]
    # invariant holds for shorts too: flat -> cash gain equals realized PnL
    assert p.cash - p.initial_capital == pytest.approx(98)


def test_reversal_splits_into_two_orders():
    # going from long 10 to short 5 must close to flat, then open the short
    events = queue.Queue()
    p = Portfolio(data_handler=None, events=events, symbols=["TEST"],
                  initial_capital=100000)
    p.position["TEST"] = 10

    p._move_to_target("TEST", -5)

    o1, o2 = events.get(), events.get()
    assert events.empty()
    assert (o1.direction, o1.quantity) == ("SELL", 10)   # close the long
    assert (o2.direction, o2.quantity) == ("SELL", 5)    # open the short


def test_new_signal_cancels_working_orders():
    # a fresh signal must cancel any still-working order for that symbol first,
    # so a stale resting order can't fill late and corrupt the position
    events = queue.Queue()
    p = Portfolio(data_handler=None, events=events, symbols=["TEST"],
                  initial_capital=100000)
    p.open_orders["TEST"].add(7)                # pretend order 7 is still working

    p.on_signal(SignalEvent("TEST", None, "EXIT"))   # EXIT needs no price/sizer

    e = events.get()                           # first event must be the cancel
    assert e.type == "CANCEL"
    assert e.order_id == 7
