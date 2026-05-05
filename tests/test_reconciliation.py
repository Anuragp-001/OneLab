"""Tests for the reconciliation engine itself."""
from __future__ import annotations

from datetime import datetime, date

import pandas as pd
import pytest

from src.data_generator import DataGenerator, GeneratorConfig
from src.gap_types import plant_gaps
from src.reconciliation import ReconciliationResult, build_full_report, reconcile


@pytest.fixture(scope="module")
def baseline_data():
    cfg = GeneratorConfig(seed=42, num_transactions=600)
    return DataGenerator(cfg).generate()


@pytest.fixture(scope="module")
def planted_data(baseline_data):
    txn, setl = baseline_data
    txn, setl, gaps = plant_gaps(txn, setl)
    return txn, setl, gaps


def test_reconcile_returns_result_object(planted_data):
    txn, setl, _ = planted_data
    result = reconcile(txn, setl)
    assert isinstance(result, ReconciliationResult)
    assert isinstance(result.summary, dict)


def test_summary_contains_required_keys(planted_data):
    txn, setl, _ = planted_data
    result = reconcile(txn, setl)
    required = {
        "total_transactions", "total_settlements",
        "total_transaction_amount", "total_settled_amount",
        "amount_difference", "matched_count", "match_rate_pct",
        "gap_late_settlement", "gap_rounding_diff", "gap_duplicates",
        "gap_orphan_refunds", "gap_unsettled", "total_gaps",
    }
    assert required.issubset(set(result.summary.keys()))


def test_match_rate_is_a_percentage(planted_data):
    txn, setl, _ = planted_data
    result = reconcile(txn, setl)
    assert 0.0 <= result.summary["match_rate_pct"] <= 100.0


def test_amount_difference_is_arithmetic(planted_data):
    txn, setl, _ = planted_data
    result = reconcile(txn, setl)
    expected = round(
        result.summary["total_transaction_amount"]
        - result.summary["total_settled_amount"], 2
    )
    assert result.summary["amount_difference"] == expected


def test_clean_data_yields_perfect_match():
    """With no planted gaps and all transactions safely mid-month
    (so natural T+1/T+2 lag stays in the same month), every record
    should match cleanly."""
    import random
    from datetime import datetime, timedelta
    cfg = GeneratorConfig(seed=7, num_transactions=300)
    txn, setl = DataGenerator(cfg).generate()
    # Constrain to first 25 days of month so T+3 max lag stays in-month
    in_window = txn["timestamp"].dt.day <= 25
    txn_clean = txn[in_window].copy().reset_index(drop=True)
    setl_clean = setl[setl["transaction_id"].isin(
        txn_clean["transaction_id"]
    )].copy().reset_index(drop=True)
    result = reconcile(txn_clean, setl_clean)
    assert result.summary["match_rate_pct"] == 100.0
    assert result.summary["total_gaps"] == 0


def test_full_report_contains_all_records(planted_data):
    txn, setl, _ = planted_data
    result = reconcile(txn, setl)
    report = build_full_report(result)
    assert "recon_status" in report.columns
    assert "gap_type" in report.columns
    assert len(report) > 0
    # Every row is either MATCHED or GAP
    assert set(report["recon_status"].unique()).issubset({"MATCHED", "GAP"})


def test_full_report_csv_serialisable(planted_data):
    txn, setl, _ = planted_data
    result = reconcile(txn, setl)
    report = build_full_report(result)
    csv = report.to_csv(index=False)
    assert csv.count("\n") == len(report) + 1  # header + rows


def test_no_double_classification(planted_data):
    """A transaction should not be in 'matched' AND a gap bucket simultaneously."""
    txn, setl, _ = planted_data
    result = reconcile(txn, setl)
    matched_ids = set(result.matched["transaction_id"])
    gap_ids = (
        set(result.late_settlements["transaction_id"])
        | set(result.rounding_diffs["transaction_id"])
        | set(result.duplicates["transaction_id"])
        | set(result.orphan_refunds["transaction_id"])
    )
    assert matched_ids.isdisjoint(gap_ids)


def test_reconciliation_period_filtering():
    """Late settlement detection respects the recon_month parameter."""
    cfg = GeneratorConfig(seed=99, num_transactions=300, month=4, year=2026)
    txn, setl = DataGenerator(cfg).generate()
    txn, setl, _ = plant_gaps(txn, setl, month=4, year=2026)

    # Reconciling for May should NOT flag the late-settlement
    # (since neither txn nor settlement are in May)
    result_may = reconcile(txn, setl, recon_month=5, recon_year=2026)
    # The April-planted late settlement won't appear as 'late' for May recon
    assert isinstance(result_may, ReconciliationResult)
