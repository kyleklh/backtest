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


def _mk(values, dates):
    return pd.DataFrame({"open": values, "high": values, "low": values,
                         "close": values, "volume": [1] * len(values)}, index=dates)


def test_union_timeline_emits_only_real_bars():
    # AAA trades all 4 days; BBB is missing the 2nd day
    idx = pd.date_range("2020-01-01", periods=4)
    data = {"AAA": _mk([10, 11, 12, 13], idx),
            "BBB": _mk([50, 53, 60], idx[[0, 2, 3]])}
    events = queue.Queue()
    handler = DataHandler(data, ["AAA", "BBB"], events)

    assert len(handler.timeline) == 4           # union keeps every date (intersection = 3)

    emitted = {"AAA": 0, "BBB": 0}
    while handler.continue_backtest:
        handler.update_bars()
        while not events.empty():
            emitted[events.get().symbol] += 1

    assert emitted["AAA"] == 4                   # one MarketEvent per real bar
    assert emitted["BBB"] == 3                   # no fabricated bar on BBB's gap day


def test_valuation_forward_fills_on_a_gap():
    idx = pd.date_range("2020-01-01", periods=3)
    data = {"AAA": _mk([10, 11, 12], idx),
            "BBB": _mk([50, 60], idx[[0, 2]])}   # BBB skips the middle day
    handler = DataHandler(data, ["AAA", "BBB"], queue.Queue())
    handler.update_bars()
    handler.update_bars()                        # cursor -> 1 (BBB's gap)

    # no real bar to trade...
    assert handler.data["BBB"].iloc[1].isna().any()
    # ...but the position can still be valued at the last-known close
    assert handler.get_value("BBB", "close") == 50
