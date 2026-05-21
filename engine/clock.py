"""Simulation clock.

Tracks the current "now" of the backtest as it advances through historical
bars. All components should read time from here, never the wall clock.
"""
