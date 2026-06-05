"""Entry point: wire components together and run backtests.

    python main.py

Runs each strategy through the event-driven engine with its own fresh set of
components (data handler, portfolio, broker) sharing one event queue, prints a
performance report, and plots the equity curves for comparison.
"""

import queue

import pandas as pd

from config import Config
from data.downloader import download_data
from data.loader import load_data
from engine.data_handler import DataHandler
from engine.event_loop import EventLoop
from portfolio.portfolio import Portfolio
from broker.execution import SimulatedBroker
from strategies.buy_and_hold import BuyAndHoldStrategy
from strategies.ma_crossover import MACrossoverStrategy
from analytics.metrics import (max_drawdown, sharpe_ratio, sortino_ratio,
                               calmar_ratio, cagr, annualized_volatility,
                               avg_win_loss, beta, alpha, information_ratio)
from analytics.plot import plot_equity_curve


def run_backtest(data, strategy_factory, cfg):
    """Run one strategy across all symbols through a fresh engine. data is a
    dict[symbol -> df]; strategy_factory is called once per symbol with
    (data_handler, events, symbol). All run settings come from cfg."""
    events = queue.Queue()
    symbols = list(data.keys())
    data_handler = DataHandler(data, symbols, events)
    strategies = [strategy_factory(data_handler, events, s) for s in symbols]
    portfolio = Portfolio(data_handler, events, symbols,
                          initial_capital=cfg.initial_capital,
                          commission_rate=cfg.commission_rate,
                          slippage_rate=cfg.slippage_rate)
    broker = SimulatedBroker(data_handler, events,
                             commission_rate=cfg.commission_rate,
                             slippage_rate=cfg.slippage_rate)

    loop = EventLoop(data=data_handler, strategies=strategies,
                     portfolio=portfolio, broker=broker, events=events)
    loop.run()
    return portfolio


def report(label, portfolio, risk_free_rate: "float | pd.Series" = 0.0,
           benchmark_curve=None, show_trades=False):
    ec = portfolio.equity_curve
    print(f"\n{label}")
    print(f"  Total return:   {portfolio.total_return():.2%}")
    print(f"  CAGR:           {cagr(ec):.2%}")
    print(f"  Max drawdown:   {max_drawdown(ec):.2%}")
    print(f"  Ann. vol:       {annualized_volatility(ec):.2%}")
    print(f"  Sharpe ratio:   {sharpe_ratio(ec, risk_free_rate=risk_free_rate):.2f}")
    print(f"  Sortino ratio:  {sortino_ratio(ec, risk_free_rate=risk_free_rate):.2f}")
    print(f"  Calmar ratio:   {calmar_ratio(ec):.2f}")
    if benchmark_curve is not None:
        print(f"  Alpha (ann.):   {alpha(ec, benchmark_curve, risk_free_rate=risk_free_rate):.2%}")
        print(f"  Beta:           {beta(ec, benchmark_curve):.2f}")
        print(f"  Info ratio:     {information_ratio(ec, benchmark_curve):.2f}")
    print(f"  Time in market: {portfolio.time_in_market():.0%}")
    print(f"  Realized PnL:   {portfolio.realized_pnl:,.2f}")

    wr = portfolio.win_rate()
    if wr is not None:
        avg_win, avg_loss = avg_win_loss(portfolio.trades)
        print(f"  Win rate:       {wr:.0%} ({portfolio.num_trades()} trades)")
        print(f"  Avg win/loss:   {avg_win:,.2f} / {avg_loss:,.2f}")
    else:
        print(f"  Win rate:       N/A (0 trades)")

    if show_trades and portfolio.trades:
        print("  Trades:")
        print(f"    {'symbol':<8}{'shares':>10}{'entry':>10}{'exit':>10}{'pnl':>12}")
        for t in portfolio.trades:
            print(f"    {t.symbol:<8}{t.shares:>10.0f}{t.entry_price:>10.2f}"
                  f"{t.exit_price:>10.2f}{t.pnl:>12.2f}")


def main():
    cfg = Config()
    data = {t: load_data(download_data(t, cfg.start, cfg.end)) for t in cfg.tickers}

    # benchmark price series (e.g. SPY) for alpha / beta / information ratio
    bench_df = load_data(download_data(cfg.benchmark, cfg.start, cfg.end))
    benchmark_curve = list(zip(bench_df.index, bench_df["close"]))

    # time-varying risk-free rate: 13-week T-bill yield (^IRX), percent -> decimal
    rf_df = load_data(download_data(cfg.risk_free_symbol, cfg.start, cfg.end))
    risk_free = rf_df["close"] / 100.0

    bh = run_backtest(data, BuyAndHoldStrategy, cfg)
    ma = run_backtest(data, MACrossoverStrategy, cfg)

    report("Buy & Hold", bh, risk_free_rate=risk_free,
           benchmark_curve=benchmark_curve)
    report("MA Crossover", ma, risk_free_rate=risk_free,
           benchmark_curve=benchmark_curve, show_trades=True)

    plot_equity_curve({
        "Buy & Hold": bh.equity_curve,
        "MA Crossover": ma.equity_curve,
    })


if __name__ == "__main__":
    main()
