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

def cagr(equity_curve, periods_per_year=252):
    """Compound annual growth rate — the constant yearly rate that turns the
    starting equity into the ending equity over the backtest's length."""
    equity = pd.Series(dict(equity_curve), dtype=float)
    if len(equity) < 2:
        return 0.0
    years = len(equity) / periods_per_year
    total_growth = equity.iloc[-1] / equity.iloc[0]
    return total_growth ** (1 / years) - 1

def annualized_volatility(equity_curve, periods_per_year=252):
    """Standard deviation of daily returns, scaled to a yearly figure."""
    equity = pd.Series(dict(equity_curve), dtype=float)
    daily_returns = equity.pct_change().dropna()
    return daily_returns.std() * np.sqrt(periods_per_year)

def avg_win_loss(trades):
    """Average PnL of winning trades and of losing trades, as a pair.
    Pairs with win rate: a low win rate is fine if avg win >> avg loss."""
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    return avg_win, avg_loss

