"""Download historical OHLCV data and cache it as CSV under market_data/.

Intended to be runnable as a script, e.g.:
    python -m data.downloader AAPL --start 2020-01-01 --end 2023-01-01
"""
