"""Aggregation and summary statistics for the reconciliation dashboard."""
from __future__ import annotations

import pandas as pd

from src.reconciliation import ReconciliationResult


def daily_volume(transactions: pd.DataFrame, settlements: pd.DataFrame) -> pd.DataFrame:
    """Daily transaction count + amount vs daily settlement count + amount."""
    txns = transactions.copy()
    setl = settlements.copy()
    txns["date"] = pd.to_datetime(txns["timestamp"]).dt.date
    setl["settlement_date"] = pd.to_datetime(setl["settlement_date"]).dt.date

    txn_agg = (
        txns.groupby("date")
        .agg(transaction_count=("transaction_id", "count"),
             transaction_amount=("amount", "sum"))
        .reset_index()
        .rename(columns={"date": "day"})
    )
    setl_agg = (
        setl.groupby("settlement_date")
        .agg(settlement_count=("settlement_id", "count"),
             settled_amount=("settled_amount", "sum"))
        .reset_index()
        .rename(columns={"settlement_date": "day"})
    )
    merged = txn_agg.merge(setl_agg, on="day", how="outer").fillna(0)
    merged = merged.sort_values("day").reset_index(drop=True)
    return merged


def gap_distribution(result: ReconciliationResult) -> pd.DataFrame:
    """Count records in each gap category (for donut chart)."""
    rows = [
        ("Late settlement",  result.summary["gap_late_settlement"]),
        ("Rounding diff",    result.summary["gap_rounding_diff"]),
        ("Duplicate entry",  result.summary["gap_duplicates"]),
        ("Orphan refund",    result.summary["gap_orphan_refunds"]),
        ("Unsettled (other)", result.summary["gap_unsettled"]),
    ]
    return pd.DataFrame(rows, columns=["gap_type", "count"])


def merchant_breakdown(transactions: pd.DataFrame) -> pd.DataFrame:
    """Per-merchant transaction stats."""
    return (
        transactions.groupby(["merchant_id", "merchant_name"])
        .agg(transaction_count=("transaction_id", "count"),
             total_amount=("amount", "sum"),
             avg_amount=("amount", "mean"))
        .round(2)
        .reset_index()
        .sort_values("total_amount", ascending=False)
    )


def settlement_lag_matrix(transactions: pd.DataFrame, settlements: pd.DataFrame
                          ) -> pd.DataFrame:
    """Heatmap-ready: rows = day of month, cols = lag days, values = count."""
    txns = transactions[["transaction_id", "timestamp"]].copy()
    setl = settlements[["transaction_id", "settlement_date"]].copy()
    txns["timestamp"] = pd.to_datetime(txns["timestamp"])
    setl["settlement_date"] = pd.to_datetime(setl["settlement_date"])

    merged = txns.merge(setl, on="transaction_id", how="inner")
    merged["day_of_month"] = merged["timestamp"].dt.day
    merged["lag_days"] = (
        merged["settlement_date"] - merged["timestamp"].dt.normalize()
    ).dt.days

    # Cap lag at 7 for display
    merged["lag_days"] = merged["lag_days"].clip(lower=0, upper=7)
    pivot = (
        merged.groupby(["day_of_month", "lag_days"]).size()
        .reset_index(name="count")
        .pivot(index="day_of_month", columns="lag_days", values="count")
        .fillna(0)
    )
    return pivot


def waterfall_data(result: ReconciliationResult) -> pd.DataFrame:
    """Build the components for an amount-mismatch waterfall chart."""
    s = result.summary
    rows = [
        ("Transaction total",  s["total_transaction_amount"], "absolute"),
        ("Late settlements",   -float(result.late_settlements["amount"].sum())
            if not result.late_settlements.empty else 0.0, "relative"),
        ("Rounding diffs",     -float(result.rounding_diffs["amount_diff"].sum())
            if not result.rounding_diffs.empty else 0.0, "relative"),
        ("Duplicate inflow",   float(
            result.duplicates.groupby("transaction_id").size().sub(1).sum()
            * result.duplicates["settled_amount"].mean()
        ) if not result.duplicates.empty else 0.0, "relative"),
        ("Orphan refunds",     -float(result.orphan_refunds["settled_amount"].sum())
            if not result.orphan_refunds.empty else 0.0, "relative"),
        ("Settled total",      s["total_settled_amount"], "total"),
    ]
    return pd.DataFrame(rows, columns=["label", "value", "kind"])
