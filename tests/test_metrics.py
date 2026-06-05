"""Tests for performance metrics — risk-free rate, Sortino, Calmar.

These assert relationships that must hold by definition, which is more robust
than hand-computing annualized figures (and catches the logic, not arithmetic)."""

import pandas as pd
import pytest
from analytics.metrics import (sharpe_ratio, sortino_ratio, calmar_ratio,
                               cagr, max_drawdown, beta, alpha, information_ratio)


def curve(values):
    """Build an equity_curve ([(timestamp, equity), ...]) from a list of values."""
    idx = pd.date_range("2020-01-01", periods=len(values))
    return list(zip(idx, values))


def test_sharpe_falls_as_risk_free_rate_rises():
    # a higher hurdle means less excess return, so Sharpe must drop
    ec = curve([100, 102, 101, 104, 103, 106])
    assert sharpe_ratio(ec, risk_free_rate=0.5) < sharpe_ratio(ec, risk_free_rate=0.0)


def test_sortino_exceeds_sharpe_when_downside_is_small():
    # big upside moves, tiny downside moves: total vol is large but downside
    # deviation is small, so Sortino (downside-only risk) must beat Sharpe
    rets = [0.2, -0.01, 0.2, -0.01, 0.2, -0.01]
    vals = [100.0]
    for r in rets:
        vals.append(vals[-1] * (1 + r))
    ec = curve(vals)
    assert sortino_ratio(ec) > sharpe_ratio(ec)


def test_calmar_is_cagr_over_max_drawdown():
    ec = curve([100, 120, 90, 130])          # peaks at 120, troughs at 90 -> 25% DD
    assert calmar_ratio(ec) == pytest.approx(cagr(ec) / abs(max_drawdown(ec)))


def _scaled_curve(levels, factor):
    """A curve whose per-period returns are `factor` times those of `levels`."""
    base = pd.Series(levels, dtype=float).pct_change().dropna()
    out = [100.0]
    for r in base:
        out.append(out[-1] * (1 + factor * r))
    return curve(out)


def test_beta_one_and_zero_alpha_against_itself():
    bench = curve([100, 110, 105, 115, 120])
    assert beta(bench, bench) == pytest.approx(1.0)
    assert alpha(bench, bench) == pytest.approx(0.0, abs=1e-9)


def test_beta_doubles_for_double_moves():
    bench = curve([100, 110, 105, 115, 120])
    strat = _scaled_curve([100, 110, 105, 115, 120], factor=2.0)
    assert beta(strat, bench) == pytest.approx(2.0)


def test_information_ratio_positive_when_consistently_outperforming():
    bench = curve([100, 110, 105, 115, 120])
    # strat returns = bench returns + a varying positive drift -> positive,
    # non-constant active return -> IR well-defined and > 0
    base = pd.Series([100, 110, 105, 115, 120], dtype=float).pct_change().dropna()
    drift = [0.01, 0.02, 0.005, 0.015]
    levels = [100.0]
    for r, d in zip(base, drift):
        levels.append(levels[-1] * (1 + r + d))
    assert information_ratio(curve(levels), bench) > 0
