"""Performance metrics computed from an equity curve.

e.g. total return, CAGR, Sharpe ratio, max drawdown, volatility.
"""

import numpy as np
import pandas as pd

def max_drawdown(equity_curve):
    equity = pd.Series(dict(equity_curve), dtype = float)
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max

    return drawdown.min()

def sharpe_ratio(equity_curve, periods_per_year=252):
    equity = pd.Series(dict(equity_curve), dtype = float)
    daily_returns = equity.pct_change().dropna()
    mean = daily_returns.mean()
    std = daily_returns.std()

    return (mean / std) *np.sqrt(periods_per_year)

