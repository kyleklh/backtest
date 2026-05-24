"""Historical data handler.

Loads OHLCV CSVs from market_data/ and replays them bar-by-bar, emitting a
MarketEvent per new bar. Exposes the latest (and trailing) bars so components
can read prices without ever peeking at future data.
"""

import pandas as pd

def load_data(filepath):
    # yfinance writes a 3-row header (Price / Ticker / Date); skip the
    # Ticker and Date rows so only real date-indexed bars remain.
    df = pd.read_csv(filepath, index_col=0, skiprows=[1, 2])

    df.index = pd.to_datetime(df.index)

    # remove missing rows
    df.dropna(inplace=True)

    # ensure data is sorted by date
    df.sort_index(inplace=True)

    # standardize column names to lowercase
    df.columns = [col.lower() for col in df.columns]

    return df