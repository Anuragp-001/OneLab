"""End-to-end tests verifying that planted gaps are detected.

Each of the 4 mandatory gap types from the brief has a dedicated test.
The tests confirm that the gap is BOTH planted (input correct) AND
detected (output correct) with the same transaction_id.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data_generator import DataGenerator, GeneratorConfig
from src.gap_types import plant_gaps
from src.reconciliation import reconcile


@pytest.fixture(scope="module")
def planted():
    """Generate + plant gaps once for all tests in the module."""
    cfg = GeneratorConfig(seed=42, num_transactions=600,
                          month=4, year=2026)
    txn, setl = DataGenerator(cfg).generate()
    txn, setl, gaps = plant_gaps(txn, setl, month=4, year=2026)
    result = reconcile(txn, setl, recon_month=4, recon_year=2026)
    return txn, setl, gaps, result


# ------------------------------------------------------------------
# Gap 1 — Late settlement
# ------------------------------------------------------------------
def test_gap1_late_settlement_planted_in_settlements(planted) -> None:
    _, setl, gaps, _ = planted
    row = setl[setl["transaction_id"] == gaps.late_settlement_txn_id].iloc[0]
    settle_date = pd.to_datetime(row["settlement_date"])
    assert settle_date.month != 4, "Planted late settlement should be outside April"


def test_gap1_late_settlement_detected(planted) -> None:
    _, _, gaps, result = planted
    detected_ids = result.late_settlements["transaction_id"].tolist()
    assert gaps.late_settlement_txn_id in detected_ids
    assert result.summary["gap_late_settlement"] >= 1


# ------------------------------------------------------------------
# Gap 2 — Rounding difference
# ------------------------------------------------------------------
def test_gap2_rounding_diff_planted(planted) -> None:
    txn, setl, gaps, _ = planted
    t = txn[txn["transaction_id"] == gaps.rounding_diff_txn_id].iloc[0]
    s = setl[setl["transaction_id"] == gaps.rounding_diff_txn_id].iloc[0]
    diff = abs(float(t["amount"]) - float(s["settled_amount"]))
    assert 0.001 < diff < 1.0, f"Expected sub-dollar diff, got {diff}"


def test_gap2_rounding_diff_detected(planted) -> None:
    _, _, gaps, result = planted
    detected_ids = result.rounding_diffs["transaction_id"].tolist()
    assert gaps.rounding_diff_txn_id in detected_ids
    assert result.summary["gap_rounding_diff"] >= 1


def test_gap2_amount_difference_visible_when_summed(planted) -> None:
    """The brief says the rounding error is 'visible only when summed'."""
    _, _, _, result = planted
    assert abs(result.summary["amount_difference"]) > 0.0


# ------------------------------------------------------------------
# Gap 3 — Duplicate entry
# ------------------------------------------------------------------
def test_gap3_duplicate_planted(planted) -> None:
    _, setl, gaps, _ = planted
    count = (setl["transaction_id"] == gaps.duplicate_settlement_txn_id).sum()
    assert count == 2, f"Expected exactly 2 settlement rows, got {count}"


def test_gap3_duplicate_detected(planted) -> None:
    _, _, gaps, result = planted
    detected_ids = result.duplicates["transaction_id"].tolist()
    assert gaps.duplicate_settlement_txn_id in detected_ids
    assert result.summary["gap_duplicates"] >= 2  # both rows reported


# ------------------------------------------------------------------
# Gap 4 — Orphan refund
# ------------------------------------------------------------------
def test_gap4_orphan_refund_planted(planted) -> None:
    txn, _, gaps, _ = planted
    orphan = txn[txn["transaction_id"] == gaps.orphan_refund_txn_id].iloc[0]
    assert orphan["transaction_type"] == "refund"
    # The original it points to must NOT be in transactions
    assert gaps.orphan_refund_fake_original_id not in set(txn["transaction_id"])


def test_gap4_orphan_refund_detected(planted) -> None:
    _, _, gaps, result = planted
    detected_ids = result.orphan_refunds["transaction_id"].tolist()
    assert gaps.orphan_refund_txn_id in detected_ids
    assert result.summary["gap_orphan_refunds"] >= 1


# ------------------------------------------------------------------
# Combined integrity tests
# ------------------------------------------------------------------
def test_all_four_gap_types_present(planted) -> None:
    _, _, _, result = planted
    s = result.summary
    assert s["gap_late_settlement"] >= 1
    assert s["gap_rounding_diff"]   >= 1
    assert s["gap_duplicates"]      >= 2  # both duplicate rows reported
    assert s["gap_orphan_refunds"]  >= 1


def test_planted_gap_ids_are_distinct(planted) -> None:
    _, _, gaps, _ = planted
    ids = [
        gaps.late_settlement_txn_id,
        gaps.rounding_diff_txn_id,
        gaps.duplicate_settlement_txn_id,
        gaps.orphan_refund_txn_id,
    ]
    assert len(set(ids)) == 4, "All planted gap IDs must be distinct"


def test_match_rate_is_high_but_below_perfect(planted) -> None:
    """Match rate should be high but below 100% — many end-of-month
    transactions naturally settle in the following month due to T+1/T+2
    bank settlement lag, on top of the four planted gaps."""
    _, _, _, result = planted
    rate = result.summary["match_rate_pct"]
    assert 85.0 < rate < 100.0
