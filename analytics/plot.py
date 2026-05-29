"""curves: dict of {label: equity_curve}, where equity_curve is the
    portfolio's [(timestamp, equity), ...] list."""

import pandas as pd
import matplotlib.pyplot as plt

def plot_equity_curve(curves):
    for label, curve in curves.items():
        equity = pd.Series(dict(curve), dtype=float)
        equity.plot(label=label)


    plt.title("Equity Curve Comparison")
    plt.xlabel("Date")
    plt.ylabel("Portfolio Value ($)")
    plt.legend()
    plt.grid(True)
    plt.show()