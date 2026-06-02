"""Tests for portfolio accounting: avg cost, realized PnL, win rate."""

import pandas as pd
import queue
from engine.events import FillEvent
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
    assert p.cash == 100510
    assert p.realized_pnl == 510
    assert [t.pnl for t in p.trades] == [748, -238]
    assert p.num_trades() == 2
    assert p.win_rate() == 0.5

    # the trade records carry the round-trip detail, not just the PnL
    first = p.trades[0]
    assert first.symbol == "TEST"
    assert first.shares == 20
    assert first.entry_price == 111.1     # avg cost of the two buys
    assert first.exit_price == 150        # the sell fill price

    # invariant: when flat, cash gained must equal cumulative realized PnL
    assert p.cash - p.initial_capital == p.realized_pnl

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
