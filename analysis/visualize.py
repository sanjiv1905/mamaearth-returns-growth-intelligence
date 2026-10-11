"""Part 2, Task 11 — Two visualizations.

Reads the figures computed by analysis/clean_and_eda.py (analysis/output/*.csv)
and saves two PNGs to visualizations/. Titles are built from the data, never
hardcoded, so they always state the current finding.

Usage (from the repo root, after clean_and_eda.py):  python analysis/visualize.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless, deterministic rendering
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_OUT = ROOT / "analysis" / "output"
VIZ = ROOT / "visualizations"

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"
BLUE_LIGHT = "#86b6ef"
BLUE_DARK = "#184f95"


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def return_rate_chart():
    df = pd.read_csv(ANALYSIS_OUT / "return_rate_by_payment.csv")
    df = df.sort_values("return_rate_pct", ascending=False).reset_index(drop=True)

    top = df.iloc[0]
    card_rate = df.loc[df["payment_method"] == "CARD", "return_rate_pct"].iloc[0]
    multiple = top["return_rate_pct"] / card_rate
    title = (f"{top['payment_method']} Returns at {top['return_rate_pct']:.1f}% "
             f"— {multiple:.0f}x Card")

    fig, ax = plt.subplots(figsize=(8, 5), facecolor=SURFACE)
    colors = [BLUE_DARK if i == 0 else BLUE_LIGHT for i in range(len(df))]
    bars = ax.bar(df["payment_method"], df["return_rate_pct"], color=colors,
                  width=0.55, edgecolor=SURFACE, linewidth=2)
    for bar, (_, row) in zip(bars, df.iterrows()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{row['return_rate_pct']:.1f}%\n(n={int(row['count'])})",
                ha="center", va="bottom", color=TEXT_PRIMARY, fontsize=11)
    style_axes(ax)
    ax.set_ylim(0, df["return_rate_pct"].max() * 1.25)
    ax.set_xlabel("Payment method (cleaned)", color=TEXT_SECONDARY)
    ax.set_ylabel("Return rate (%)", color=TEXT_SECONDARY)
    ax.set_title(title, color=TEXT_PRIMARY, fontsize=14, fontweight="bold", loc="left")
    fig.tight_layout()
    out = VIZ / "return_rate_by_payment.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"Saved {out.relative_to(ROOT)}  —  {title}")


def monthly_revenue_chart():
    df = pd.read_csv(ANALYSIS_OUT / "monthly_revenue_corrected.csv")
    peak = df.loc[df["revenue_inr"].idxmax()]
    peak_label = pd.Timestamp(peak["year_month"] + "-01").strftime("%B %Y")
    title = f"{peak_label} Is the True Peak Month — ₹{peak['revenue_inr']:,.2f} (outliers excluded)"

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=SURFACE)
    x = range(len(df))
    ax.plot(x, df["revenue_inr"], color=BLUE, linewidth=2, marker="o", markersize=8,
            markeredgecolor=SURFACE, markeredgewidth=2)
    peak_idx = int(df["revenue_inr"].idxmax())
    ax.annotate(f"₹{peak['revenue_inr']:,.2f}", (peak_idx, peak["revenue_inr"]),
                textcoords="offset points", xytext=(0, 12), ha="center",
                color=TEXT_PRIMARY, fontsize=11, fontweight="bold")
    style_axes(ax)
    ax.set_xticks(list(x))
    ax.set_xticklabels([pd.Timestamp(m + "-01").strftime("%b %Y") for m in df["year_month"]])
    ax.set_ylim(0, df["revenue_inr"].max() * 1.2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"₹{v:,.0f}"))
    ax.set_xlabel("Month (2026)", color=TEXT_SECONDARY)
    ax.set_ylabel("Revenue (INR, after discount)", color=TEXT_SECONDARY)
    ax.set_title(title, color=TEXT_PRIMARY, fontsize=13, fontweight="bold", loc="left")
    fig.tight_layout()
    out = VIZ / "monthly_revenue_trend.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"Saved {out.relative_to(ROOT)}  —  {title}")


def main():
    if not ANALYSIS_OUT.exists():
        raise SystemExit("Run analysis/clean_and_eda.py first (it writes analysis/output/).")
    VIZ.mkdir(parents=True, exist_ok=True)
    return_rate_chart()
    monthly_revenue_chart()


if __name__ == "__main__":
    main()
