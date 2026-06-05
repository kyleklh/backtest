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

def sharpe_ratio(equity_curve, periods_per_year=252, risk_free_rate=0.0):
    """Excess return per unit of total volatility, annualized. risk_free_rate
    is an annual rate; it's converted to a per-period hurdle and subtracted
    from each return before measuring reward-to-risk."""
    equity = pd.Series(dict(equity_curve), dtype = float)
    daily_returns = equity.pct_change().dropna()
    rf_period = risk_free_rate / periods_per_year
    excess = daily_returns - rf_period
    std = excess.std()
    if std == 0 or np.isnan(std):
        return float("nan")
    return (excess.mean() / std) * np.sqrt(periods_per_year)

def sortino_ratio(equity_curve, periods_per_year=252, risk_free_rate=0.0):
    """Like Sharpe, but only downside deviation counts as risk — upside
    volatility isn't penalized. Uses the target-downside-deviation form:
    sqrt(mean of squared shortfalls below the risk-free hurdle)."""
    equity = pd.Series(dict(equity_curve), dtype=float)
    daily_returns = equity.pct_change().dropna()
    rf_period = risk_free_rate / periods_per_year
    excess = daily_returns - rf_period
    shortfall = np.minimum(excess, 0.0)             # 0 on up days, negative on down days
    downside_dev = np.sqrt((shortfall ** 2).mean())
    if downside_dev == 0 or np.isnan(downside_dev):
        return float("nan")
    return (excess.mean() / downside_dev) * np.sqrt(periods_per_year)

def calmar_ratio(equity_curve, periods_per_year=252):
    """Annualized return per unit of worst-case pain: CAGR / |max drawdown|."""
    mdd = max_drawdown(equity_curve)
    if mdd == 0 or np.isnan(mdd):
        return float("nan")
    return cagr(equity_curve, periods_per_year) / abs(mdd)

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

def _aligned_returns(equity_curve, benchmark_curve):
    """Per-period returns of the strategy and the benchmark, aligned on the
    dates they share (inner join) so they're directly comparable."""
    strat = pd.Series(dict(equity_curve), dtype=float).pct_change()
    bench = pd.Series(dict(benchmark_curve), dtype=float).pct_change()
    df = pd.concat([strat, bench], axis=1, keys=["strat", "bench"]).dropna()
    return df["strat"], df["bench"]

def beta(equity_curve, benchmark_curve):
    """Sensitivity of the strategy's returns to the benchmark's:
    cov(strategy, benchmark) / var(benchmark)."""
    strat, bench = _aligned_returns(equity_curve, benchmark_curve)
    var = bench.var()
    if var == 0 or np.isnan(var):
        return float("nan")
    return strat.cov(bench) / var

def alpha(equity_curve, benchmark_curve, periods_per_year=252, risk_free_rate=0.0):
    """Annualized excess return not explained by market exposure (CAPM alpha):
    (strat - rf) - beta * (bench - rf), averaged per period and annualized."""
    strat, bench = _aligned_returns(equity_curve, benchmark_curve)
    var = bench.var()
    if var == 0 or np.isnan(var):
        return float("nan")
    b = strat.cov(bench) / var
    rf = risk_free_rate / periods_per_year
    alpha_period = (strat.mean() - rf) - b * (bench.mean() - rf)
    return alpha_period * periods_per_year

def information_ratio(equity_curve, benchmark_curve, periods_per_year=252):
    """Active return per unit of tracking error, annualized: like Sharpe but
    measured against the benchmark instead of the risk-free rate."""
    strat, bench = _aligned_returns(equity_curve, benchmark_curve)
    active = strat - bench
    te = active.std()
    if te == 0 or np.isnan(te):
        return float("nan")
    return (active.mean() / te) * np.sqrt(periods_per_year)

def avg_win_loss(trades):
    """Average PnL of winning trades and of losing trades, as a pair.
    Pairs with win rate: a low win rate is fine if avg win >> avg loss."""
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    return avg_win, avg_loss

