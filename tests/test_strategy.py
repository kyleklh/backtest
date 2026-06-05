"""Tests for strategies: signal timing on MA crossover."""

import pandas as pd
import queue
from engine.data_handler import DataHandler
from strategies.ma_crossover import MACrossoverStrategy


def run_strategy(closes, short_window, long_window):
    """Drive the strategy bar-by-bar over a price series; return the list of
    SignalEvents it emitted, in order."""
    df = pd.DataFrame({
        "open": closes, "high": closes, "low": closes,
        "close": closes, "volume": [1000] * len(closes),
    }, index=pd.date_range("2020-01-01", periods=len(closes)))

    events = queue.Queue()
    handler = DataHandler({"TEST": df}, ["TEST"], events)
    strategy = MACrossoverStrategy(handler, events, "TEST",
                                   short_window=short_window, long_window=long_window)

    signals = []
    while handler.continue_backtest:
        handler.update_bars()
        if not handler.continue_backtest:
            break
        # drain the queue: feed MARKET events to the strategy, collect SIGNALs
        while not events.empty():
            e = events.get()
            if e.type == "MARKET":
                strategy.calculate_signals(e)
            elif e.type == "SIGNAL":
                signals.append(e)
    return signals


def test_crossover_fires_only_on_the_cross():
    signals = run_strategy([10, 9, 8, 12, 13, 14, 7, 6],
                           short_window=2, long_window=3)

    assert len(signals) == 2
    assert signals[0].direction == "LONG"
    assert signals[1].direction == "EXIT"


