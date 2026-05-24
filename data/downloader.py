"""Download historical OHLCV data and cache it as CSV under market_data/.

Intended to be runnable as a script, e.g.:
    python -m data.downloader AAPL --start 2020-01-01 --end 2023-01-01
"""

import os

import yfinance as yf
import pandas as pd


def download_data(ticker, start, end):
    
    df = yf.download(ticker, start=start, end=end)

    if df is None or df.empty:
        raise ValueError(f"No data returned for ticker={ticker}, start={start}, end={end}")
    
    df.index = pd.to_datetime(df.index)  # Ensure index is datetime

    market_data_dir = os.path.join(os.path.dirname(__file__), 'market_data')
    os.makedirs(market_data_dir, exist_ok=True)
    
    csv_path = os.path.join(market_data_dir, f'{ticker}-{start}_{end}.csv')
    df.to_csv(csv_path)
    return csv_path
