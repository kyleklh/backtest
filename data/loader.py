"""Historical data handler.

Loads OHLCV CSVs from market_data/ and replays them bar-by-bar, emitting a
MarketEvent per new bar. Exposes the latest (and trailing) bars so components
can read prices without ever peeking at future data.
"""
