"""Part 2 — Python/Pandas data wrangling & EDA.

Runs directly on the raw CSVs in data/ (independent of the SQL database),
prints every intermediate result, and finishes by exporting the verified
figures to narrator/findings.json for Part 3.

Usage (from the repo root):  python analysis/clean_and_eda.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ANALYSIS_OUT = ROOT / "analysis" / "output"
FINDINGS_PATH = ROOT / "narrator" / "findings.json"

NATURAL_KEY = [
    "customer_id", "product_id", "order_date", "quantity",
    "discount_pct", "payment_method", "rating", "returned",
]


def header(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def inr(x):
    return f"₹{x:,.2f}"


def corr_band(r):
    a = abs(r)
    if a < 0.2:
        return "negligible"
    if a < 0.4:
        return "weak"
    if a < 0.7:
        return "moderate"
    return "strong"


def add_order_value(df):
    df = df.copy()
    df["order_value"] = df["quantity"] * df["price"] * (1 - df["discount_pct"].fillna(0) / 100)
    return df


def main():
    pd.set_option("display.width", 120)

    # ------------------------------------------------------------------
    header("Task 1 — Load and inspect")
    customers = pd.read_csv(DATA / "customers.csv")
    products = pd.read_csv(DATA / "products.csv")
    orders = pd.read_csv(DATA / "orders.csv")
    print(f"customers.shape = {customers.shape}")
    print(f"products.shape  = {products.shape}")
    print(f"orders.shape    = {orders.shape}   (raw, before any cleaning)")
    print("\nMissing values in raw orders:")
    print(orders.isnull().sum().to_string())

    # ------------------------------------------------------------------
    header("Task 2 — Standardize payment_method casing")
    raw_values = orders["payment_method"].unique()
    print(f"Raw distinct values ({len(raw_values)}): {list(raw_values)}")
    orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
    clean_values = orders["payment_method"].value_counts()
    print(f"After .str.strip().str.upper() ({len(clean_values)} values):")
    print(clean_values.to_string())

    # ------------------------------------------------------------------
    header("Task 3 — Remove duplicate orders")
    dup_mask = orders.duplicated(subset=NATURAL_KEY, keep="first")
    dropped = orders[dup_mask].copy()
    print(f"Duplicate rows flagged on natural key: {dup_mask.sum()}")
    print(f"Dropped order_ids: {dropped['order_id'].tolist()}")
    orders_clean = orders[~dup_mask].copy()
    print(f"orders_clean.shape = {orders_clean.shape}")

    # ------------------------------------------------------------------
    header("Task 4 — Impute missing values (on the deduplicated frame)")
    n_disc = orders_clean["discount_pct"].isnull().sum()
    orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
    print(f"discount_pct: {n_disc} NaN rows filled with 0 (no promo code applied)")

    rating_median = orders_clean["rating"].median()
    n_rating = orders_clean["rating"].isnull().sum()
    print(f"rating median (non-null, deduplicated) = {rating_median}")
    orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)
    print(f"rating: {n_rating} NaN rows filled with median {rating_median}")

    print("\nRemaining nulls after imputation:")
    print(orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())

    # ------------------------------------------------------------------
    header("Task 5 — Merge and reconcile against Part 1")
    merged = (
        orders_clean
        .merge(products, on="product_id", how="left")
        .merge(customers, on="customer_id", how="left")
    )
    merged = add_order_value(merged)
    cleaned_total = round(merged["order_value"].sum(), 2)
    print(f"Merged shape: {merged.shape}")
    print(f"Cleaned total order_value (175 rows): {cleaned_total:.2f}")

    # Independent recomputation of the raw total and of the dropped rows.
    raw_valued = add_order_value(orders.merge(products, on="product_id", how="left"))
    raw_total = round(raw_valued["order_value"].sum(), 2)
    dropped_valued = add_order_value(dropped.merge(products, on="product_id", how="left"))
    dup_total = round(dropped_valued["order_value"].sum(), 2)
    delta = round(raw_total - cleaned_total, 2)

    print(f"Raw total order_value (180 rows, = Part 1 Report a): {raw_total:.2f}")
    print(f"Delta (raw - cleaned): {delta:.2f}")
    print("\nOrder value of the 5 dropped duplicate rows:")
    print(dropped_valued[["order_id", "customer_id", "product_id", "quantity",
                          "discount_pct", "price", "order_value"]].to_string(index=False))
    print(f"Sum of dropped rows' order_value: {dup_total:.2f}")
    assert abs(delta - dup_total) < 0.005, "Reconciliation failed"

    print(
        "\nRECONCILIATION NOTE: The cleaned pandas total of "
        f"{inr(cleaned_total)} is {inr(delta)} lower than Part 1 Report (a)'s raw SQL "
        f"total of {inr(raw_total)}. This entire delta is explained by the 5 duplicate "
        f"orders removed in Task 3 ({', '.join(dropped['order_id'])}), whose combined "
        f"order_value, summed independently above, is exactly {inr(dup_total)}. "
        "The discount/rating imputation in Task 4 does not contribute: the SQL report "
        "already treated a NULL discount as 0% via COALESCE (the same value we impute), "
        "and rating does not enter the order_value formula at all. The casing fix in "
        "Task 2 changes labels only, not amounts."
    )

    # ------------------------------------------------------------------
    header("Task 6 — IQR outlier detection on quantity")
    q1 = merged["quantity"].quantile(0.25)
    q3 = merged["quantity"].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    print(f"Q1 = {q1}, Q3 = {q3}, IQR = {iqr}, lower = {lower}, upper = {upper}")
    merged["is_outlier"] = (merged["quantity"] < lower) | (merged["quantity"] > upper)
    outliers = merged[merged["is_outlier"]]
    print(f"Outlier rows: {len(outliers)} (flagged with is_outlier, NOT dropped)")
    print(outliers[["order_id", "order_date", "customer_id", "product_name",
                    "quantity", "order_value"]].to_string(index=False))

    # ------------------------------------------------------------------
    header("Task 7 — Hypothesis: COD orders have a higher return rate")
    print("H: Cash-on-Delivery (COD) orders are returned at a higher rate than "
          "prepaid (CARD / UPI) orders.")
    pay = merged.groupby("payment_method")["returned"].agg(["count", "mean"])
    pay["return_rate_pct"] = (pay["mean"] * 100).round(1)
    pay = pay.sort_values("return_rate_pct", ascending=False)
    print(pay.to_string())
    rate = pay["return_rate_pct"].to_dict()
    confirmed = rate["COD"] > rate["CARD"] and rate["COD"] > rate["UPI"]
    verdict = "Confirmed" if confirmed else "Busted"
    print(f"\nVerdict: {verdict} — COD returns at {rate['COD']}% vs CARD {rate['CARD']}% "
          f"and UPI {rate['UPI']}% ({rate['COD'] / rate['CARD']:.1f}x Card).")

    # ------------------------------------------------------------------
    header("Task 8 — Multi-level segmentation: payment_method x city_tier")
    seg = merged.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"])
    seg["return_rate_pct"] = (seg["mean"] * 100).round(1)
    print(seg.to_string())
    (top_pm, top_tier) = seg["return_rate_pct"].idxmax()
    top_rate = seg.loc[(top_pm, top_tier), "return_rate_pct"]
    top_n = int(seg.loc[(top_pm, top_tier), "count"])
    cod_t1 = seg.loc[("COD", 1)]
    cod_t2 = seg.loc[("COD", 2)]
    print(f"\nHighest-risk segment: {top_pm} + Tier-{top_tier} cities at {top_rate}% "
          f"({top_n} orders).")
    print(f"COD risk is not uniform: {int(cod_t1['count'])} Tier-1 COD orders return at "
          f"{cod_t1['return_rate_pct']}%, versus {int(cod_t2['count'])} Tier-2 COD orders at "
          f"{cod_t2['return_rate_pct']}%. The blended COD rate of {rate['COD']}% hides "
          "where the problem is concentrated.")

    # ------------------------------------------------------------------
    header("Task 9 — Correlation analysis")
    cols = ["rating", "returned", "discount_pct", "quantity"]
    corr = merged[cols].corr()
    print(corr.round(3).to_string())
    print("\nBands: negligible 0-0.19 | weak 0.2-0.39 | moderate 0.4-0.69 | strong 0.7-1.0")
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.loc[a, b]
            print(f"  {a:>12} vs {b:<12} r = {r:+.3f}  -> {corr_band(r)}")
    r_disc = corr.loc["discount_pct", "returned"]
    disc_verdict = "Busted" if abs(r_disc) < 0.2 else "Supported"
    print(f"\nHypothesis 'higher discounts reduce returns': {disc_verdict} "
          f"(discount_pct vs returned r = {r_disc:+.2f}, {corr_band(r_disc)}).")

    # ------------------------------------------------------------------
    header("Task 10 — Outlier-corrected monthly revenue")
    merged["order_date"] = pd.to_datetime(merged["order_date"])
    merged["year_month"] = merged["order_date"].dt.strftime("%Y-%m")
    monthly_all = merged.groupby("year_month")["order_value"].sum().round(2)
    monthly_clean = merged[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
    print("(1) Including outlier orders:")
    print(monthly_all.map("{:.2f}".format).to_string())
    print("\n(2) Excluding outlier orders (outlier-corrected):")
    print(monthly_clean.map("{:.2f}".format).to_string())

    inflated_month = monthly_all.idxmax()
    peak_month = monthly_clean.idxmax()
    peak_name = pd.Timestamp(peak_month + "-01").strftime("%B")
    inflated_name = pd.Timestamp(inflated_month + "-01").strftime("%B")
    outlier_desc = ", ".join(
        f"{r.order_id} on {r.order_date:%Y-%m-%d}" for r in outliers.assign(
            order_date=pd.to_datetime(outliers["order_date"])).itertuples()
    )
    print(f"\n{inflated_name}'s apparent lead ({monthly_all[inflated_month]:.2f}) is an artifact "
          f"of the two bulk outlier orders landing in {inflated_name} ({outlier_desc}). "
          f"Excluding them, {inflated_name} drops to {monthly_clean[inflated_month]:.2f} and "
          f"{peak_name} ({peak_month}) is the genuine peak month at {monthly_clean[peak_month]:.2f}.")

    # ------------------------------------------------------------------
    header("Export — intermediate data for visualize.py and findings.json for Part 3")
    ANALYSIS_OUT.mkdir(parents=True, exist_ok=True)
    pay[["count", "return_rate_pct"]].to_csv(ANALYSIS_OUT / "return_rate_by_payment.csv")
    monthly_clean.rename("revenue_inr").to_csv(ANALYSIS_OUT / "monthly_revenue_corrected.csv")
    print(f"Wrote {(ANALYSIS_OUT / 'return_rate_by_payment.csv').relative_to(ROOT)}")
    print(f"Wrote {(ANALYSIS_OUT / 'monthly_revenue_corrected.csv').relative_to(ROOT)}")

    findings = {
        "cleaned_total_revenue_inr": cleaned_total,
        "raw_total_revenue_inr": raw_total,
        "duplicate_reconciliation_delta_inr": delta,
        "return_rate_by_payment": {k: float(rate[k]) for k in ["COD", "CARD", "UPI"]},
        "highest_risk_segment": {
            "payment_method": top_pm,
            "city_tier": int(top_tier),
            "return_rate_pct": float(top_rate),
        },
        "true_peak_month": {
            "month": peak_month,
            "revenue_inr": float(monthly_clean[peak_month]),
        },
        "outlier_inflated_month": {
            "month": inflated_month,
            "apparent_revenue_inr": float(monthly_all[inflated_month]),
            "corrected_revenue_inr": float(monthly_clean[inflated_month]),
        },
    }
    FINDINGS_PATH.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {FINDINGS_PATH.relative_to(ROOT)}:")
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
