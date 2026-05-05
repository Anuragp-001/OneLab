"""Core reconciliation engine.

Takes transactions + settlements and produces a structured result
identifying which records match cleanly and which fall into one of
the four gap categories.

Detection logic uses Pandas vectorised operations (no Python loops).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ReconciliationResult:
    """Structured output from a reconciliation run."""
    matched: pd.DataFrame
    late_settlements: pd.DataFrame      # Gap 1
    rounding_diffs: pd.DataFrame        # Gap 2
    duplicates: pd.DataFrame            # Gap 3
    orphan_refunds: pd.DataFrame        # Gap 4
    unsettled: pd.DataFrame             # any other unmatched
    summary: dict[str, Any] = field(default_factory=dict)


def reconcile(
    transactions: pd.DataFrame,
    settlements: pd.DataFrame,
    recon_month: int = 4,
    recon_year: int = 2026,
) -> ReconciliationResult:
    """Run the full reconciliation pipeline.

    Algorithm (in order):
        1. Identify duplicate settlements   (Gap 3)
        2. Deduplicate settlements for the join
        3. LEFT JOIN transactions ⟕ settlements on transaction_id
        4. Detect orphan refunds            (Gap 4)
        5. Detect late settlements          (Gap 1)
        6. Detect rounding differences      (Gap 2)
        7. Identify cleanly matched rows
        8. Compute summary statistics
    """
    txns = transactions.copy()
    setl = settlements.copy()

    # Normalise dtypes
    txns["timestamp"] = pd.to_datetime(txns["timestamp"])
    setl["settlement_date"] = pd.to_datetime(setl["settlement_date"]).dt.date

    # -----------------------------------------------------------------
    # Gap 3 — Duplicate settlements
    # -----------------------------------------------------------------
    dup_counts = (
        setl.groupby("transaction_id").size().reset_index(name="settlement_count")
    )
    dup_txn_ids = dup_counts.loc[
        dup_counts["settlement_count"] > 1, "transaction_id"
    ].tolist()
    duplicates = (
        setl[setl["transaction_id"].isin(dup_txn_ids)]
        .merge(
            txns[["transaction_id", "amount", "merchant_name", "timestamp"]],
            on="transaction_id",
            how="left",
        )
        .sort_values(["transaction_id", "settlement_date"])
        .reset_index(drop=True)
    )

    # Deduplicate settlements (keep first) for the main join
    setl_dedup = setl.drop_duplicates(subset="transaction_id", keep="first")

    # -----------------------------------------------------------------
    # LEFT JOIN: txn -> settlement
    # -----------------------------------------------------------------
    merged = txns.merge(setl_dedup, on="transaction_id", how="left",
                        suffixes=("", "_settle"))
    has_settle = merged["settlement_date"].notna()

    # -----------------------------------------------------------------
    # Gap 4 — Orphan refunds
    # -----------------------------------------------------------------
    valid_ids = set(txns["transaction_id"].tolist())
    refund_mask = merged["transaction_type"] == "refund"
    orig_in_set = merged["original_transaction_id"].apply(
        lambda x: x in valid_ids if pd.notna(x) else True
    )
    orphan_mask = refund_mask & ~orig_in_set
    orphan_refunds = merged[orphan_mask].copy()
    orphan_refund_ids = set(orphan_refunds["transaction_id"].tolist())

    # -----------------------------------------------------------------
    # Gap 1 — Late settlements (txn in recon period, settlement outside)
    # -----------------------------------------------------------------
    txn_in_period = (
        (merged["timestamp"].dt.month == recon_month)
        & (merged["timestamp"].dt.year == recon_year)
    )
    settle_in_period_series = merged["settlement_date"].apply(
        lambda d: (d.month == recon_month and d.year == recon_year)
        if pd.notna(d) else False
    )
    late_mask = txn_in_period & has_settle & ~settle_in_period_series
    late_settlements = merged[late_mask].copy()
    late_ids = set(late_settlements["transaction_id"].tolist())

    # -----------------------------------------------------------------
    # Gap 2 — Rounding differences
    # -----------------------------------------------------------------
    matched_with_settle = merged[has_settle].copy()
    matched_with_settle["amount_diff"] = (
        matched_with_settle["amount"] - matched_with_settle["settled_amount"]
    ).round(4)
    rounding_mask = (
        (matched_with_settle["amount_diff"].abs() > 0.001)
        & (matched_with_settle["amount_diff"].abs() < 1.00)
        & (~matched_with_settle["transaction_id"].isin(orphan_refund_ids))
    )
    rounding_diffs = matched_with_settle[rounding_mask].copy()
    rounding_ids = set(rounding_diffs["transaction_id"].tolist())

    # -----------------------------------------------------------------
    # Unsettled (no settlement record at all)
    # -----------------------------------------------------------------
    unsettled = merged[
        ~has_settle & ~merged["transaction_id"].isin(orphan_refund_ids)
    ].copy()

    # -----------------------------------------------------------------
    # Cleanly matched
    # -----------------------------------------------------------------
    excluded_ids = (
        set(dup_txn_ids) | late_ids | rounding_ids | orphan_refund_ids
    )
    matched = merged[
        has_settle & ~merged["transaction_id"].isin(excluded_ids)
    ].copy()

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------
    total_txn = len(txns)
    total_settle = len(setl)
    total_txn_amt = float(txns["amount"].sum())
    total_settle_amt = float(setl["settled_amount"].sum())

    summary: dict[str, Any] = {
        "total_transactions": total_txn,
        "total_settlements": total_settle,
        "total_transaction_amount": round(total_txn_amt, 2),
        "total_settled_amount": round(total_settle_amt, 2),
        "amount_difference": round(total_txn_amt - total_settle_amt, 2),
        "matched_count": len(matched),
        "match_rate_pct": round(100.0 * len(matched) / total_txn, 2)
        if total_txn else 0.0,
        "gap_late_settlement": len(late_settlements),
        "gap_rounding_diff": len(rounding_diffs),
        "gap_duplicates": len(duplicates),
        "gap_orphan_refunds": len(orphan_refunds),
        "gap_unsettled": len(unsettled),
        "total_gaps": (
            len(late_settlements) + len(rounding_diffs)
            + len(duplicates) + len(orphan_refunds) + len(unsettled)
        ),
    }

    return ReconciliationResult(
        matched=matched,
        late_settlements=late_settlements,
        rounding_diffs=rounding_diffs,
        duplicates=duplicates,
        orphan_refunds=orphan_refunds,
        unsettled=unsettled,
        summary=summary,
    )


def build_full_report(result: ReconciliationResult) -> pd.DataFrame:
    """Flatten the reconciliation result into a single CSV-ready report."""
    frames: list[pd.DataFrame] = []

    def tag(df: pd.DataFrame, status: str, gap_type: str) -> pd.DataFrame:
        if df.empty:
            return df
        out = df.copy()
        out["recon_status"] = status
        out["gap_type"] = gap_type
        return out

    frames.append(tag(result.matched, "MATCHED", "none"))
    frames.append(tag(result.late_settlements, "GAP", "late_settlement"))
    frames.append(tag(result.rounding_diffs, "GAP", "rounding_difference"))
    frames.append(tag(result.duplicates, "GAP", "duplicate_settlement"))
    frames.append(tag(result.orphan_refunds, "GAP", "orphan_refund"))
    frames.append(tag(result.unsettled, "GAP", "unsettled"))

    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    report = pd.concat(frames, ignore_index=True)
    # Stable column order
    front = ["recon_status", "gap_type", "transaction_id", "timestamp",
             "merchant_name", "amount", "settled_amount", "settlement_date",
             "transaction_type"]
    cols = [c for c in front if c in report.columns]
    rest = [c for c in report.columns if c not in cols]
    return report[cols + rest]
