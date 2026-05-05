"""Tests for the synthetic data generator."""
from __future__ import annotations

import pandas as pd
import pytest

from src.data_generator import DataGenerator, GeneratorConfig


def _make(num: int = 200, month: int = 4, year: int = 2026) -> tuple:
    cfg = GeneratorConfig(seed=42, num_transactions=num,
                          month=month, year=year)
    return DataGenerator(cfg).generate()


def test_returns_two_dataframes() -> None:
    txn, setl = _make(200)
    assert isinstance(txn, pd.DataFrame)
    assert isinstance(setl, pd.DataFrame)


def test_transactions_are_in_target_month() -> None:
    txn, _ = _make(200, month=4, year=2026)
    assert (txn["timestamp"].dt.month == 4).all()
    assert (txn["timestamp"].dt.year == 2026).all()


def test_settlements_one_to_one_with_transactions() -> None:
    txn, setl = _make(200)
    assert len(setl) == len(txn)
    assert set(setl["transaction_id"]) == set(txn["transaction_id"])


def test_sale_amounts_in_valid_range() -> None:
    txn, _ = _make(300)
    sales = txn[txn["transaction_type"] == "sale"]
    assert sales["amount"].min() >= 5.00
    assert sales["amount"].max() <= 5000.00


def test_refunds_have_negative_amount() -> None:
    txn, _ = _make(300)
    refunds = txn[txn["transaction_type"] == "refund"]
    if not refunds.empty:
        assert (refunds["amount"] < 0).all()


def test_refunds_link_to_real_originals() -> None:
    txn, _ = _make(300)
    refunds = txn[txn["transaction_type"] == "refund"]
    sales = txn[txn["transaction_type"] == "sale"]
    if not refunds.empty:
        assert refunds["original_transaction_id"].isin(
            sales["transaction_id"]
        ).all()


def test_currency_is_usd() -> None:
    txn, setl = _make(100)
    assert (txn["currency"] == "USD").all()
    assert (setl["currency"] == "USD").all()


def test_seed_is_deterministic() -> None:
    a_txn, _ = _make(200)
    b_txn, _ = _make(200)
    pd.testing.assert_series_equal(
        a_txn["amount"].reset_index(drop=True),
        b_txn["amount"].reset_index(drop=True),
    )


def test_settlement_lag_is_realistic() -> None:
    _, setl = _make(200)
    assert setl["lag_days"].min() >= 1
    assert setl["lag_days"].max() <= 3


def test_minimum_volume_for_meaningful_analysis() -> None:
    """Brief mandates ≥500 transactions for meaningful analysis."""
    txn, _ = _make(600)
    assert len(txn) >= 500
