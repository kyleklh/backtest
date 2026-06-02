"""Tests for the data handler (loading, bar replay, no look-ahead)."""

import pandas as pd
import queue
from engine.data_handler import DataHandler


def make_handler(n_bars=10):
    """Build a tiny in-memory DataHandler so tests don't depend on real data."""
    df = pd.DataFrame({
        "open":   [10 + i for i in range(n_bars)],
        "high":   [11 + i for i in range(n_bars)],
        "low":    [9  + i for i in range(n_bars)],
        "close":  [10.5 + i for i in range(n_bars)],
        "volume": [1000] * n_bars,
    }, index=pd.date_range("2020-01-01", periods=n_bars))
    return DataHandler({"TEST": df}, ["TEST"], queue.Queue())


def test_get_latest_bars_never_returns_future_rows():
    handler = make_handler(n_bars=10)

    # advance to bar index 2 (three bars revealed: 0, 1, 2)
    handler.update_bars()
    handler.update_bars()
    handler.update_bars()

    # ask for 10 bars — we should only get 3 (no future data)
    bars = handler.get_latest_bars("TEST", 10)

    assert len(bars) == 3                       # only as many as revealed
    assert bars.iloc[-1]["close"] == handler.data["TEST"].iloc[2]["close"]   # last bar = cursor's bar
