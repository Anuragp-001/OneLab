"""Gap planting module.

Injects exactly four reconciliation-breaking gaps into the dataset.
Each planted gap returns a transaction_id so tests can verify
the engine detects exactly the seeded ones.

The four gaps (per assessment brief):
    1. A transaction that settled the following month (cross-month lag)
    2. A rounding difference visible only when summed
    3. A duplicate entry in one dataset (settlements)
    4. A refund with no matching original transaction
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple

import pandas as pd


@dataclass
class PlantedGaps:
    """The IDs of the planted gap transactions for end-to-end verification."""
    late_settlement_txn_id: str
    rounding_diff_txn_id: str
    duplicate_settlement_txn_id: str
    orphan_refund_txn_id: str
    orphan_refund_fake_original_id: str

    def as_dict(self) -> dict:
        return {
            "late_settlement": self.late_settlement_txn_id,
            "rounding_difference": self.rounding_diff_txn_id,
            "duplicate_settlement": self.duplicate_settlement_txn_id,
            "orphan_refund": self.orphan_refund_txn_id,
        }


def plant_gaps(
    transactions: pd.DataFrame,
    settlements: pd.DataFrame,
    month: int = 4,
    year: int = 2026,
) -> Tuple[pd.DataFrame, pd.DataFrame, PlantedGaps]:
    """Plant exactly four gap types and return updated frames + gap registry."""
    txns = transactions.copy()
    setl = settlements.copy()

    # ---------------------------------------------------------------
    # Gap 1 — Late settlement (transaction settled following month)
    # Pick a transaction near the end of the month and shift its
    # settlement date 5 days forward, crossing into the next month.
    # ---------------------------------------------------------------
    end_of_month = txns[
        (txns["timestamp"].dt.month == month)
        & (txns["timestamp"].dt.day >= 28)
        & (txns["transaction_type"] == "sale")
    ].sort_values("timestamp")
    if end_of_month.empty:
        raise RuntimeError("No end-of-month sales to plant Gap 1 — increase volume.")
    gap1_id = str(end_of_month.iloc[-1]["transaction_id"])
    mask1 = setl["transaction_id"] == gap1_id
    if mask1.any():
        original_date = setl.loc[mask1, "settlement_date"].iloc[0]
        new_date = (pd.Timestamp(original_date) + pd.Timedelta(days=5)).date()
        setl.loc[mask1, "settlement_date"] = new_date
        setl.loc[mask1, "batch_id"] = f"BATCH-{new_date.strftime('%Y%m%d')}"
        setl.loc[mask1, "lag_days"] = (
            new_date - end_of_month.iloc[-1]["timestamp"].date()
        ).days

    # ---------------------------------------------------------------
    # Gap 2 — Rounding difference (settled amount $0.01 lower)
    # Pick a different transaction and reduce its settled_amount
    # by one cent so that totals don't match when summed.
    # ---------------------------------------------------------------
    eligible_g2 = txns[
        (txns["transaction_type"] == "sale")
        & (txns["transaction_id"] != gap1_id)
    ]
    if len(eligible_g2) < 50:
        raise RuntimeError("Not enough sales for Gap 2 — increase volume.")
    gap2_id = str(eligible_g2.iloc[len(eligible_g2) // 3]["transaction_id"])
    mask2 = setl["transaction_id"] == gap2_id
    if mask2.any():
        current = float(setl.loc[mask2, "settled_amount"].iloc[0])
        setl.loc[mask2, "settled_amount"] = round(current - 0.01, 2)

    # ---------------------------------------------------------------
    # Gap 3 — Duplicate settlement (same txn, two settlement rows)
    # ---------------------------------------------------------------
    eligible_g3 = txns[
        (txns["transaction_type"] == "sale")
        & (~txns["transaction_id"].isin([gap1_id, gap2_id]))
    ]
    if len(eligible_g3) < 100:
        raise RuntimeError("Not enough sales for Gap 3 — increase volume.")
    gap3_id = str(eligible_g3.iloc[len(eligible_g3) // 2]["transaction_id"])
    dup_row = setl[setl["transaction_id"] == gap3_id].iloc[0].copy()
    dup_row["settlement_id"] = str(uuid.uuid4())  # new settlement_id, same txn_id
    setl = pd.concat([setl, pd.DataFrame([dup_row])], ignore_index=True)

    # ---------------------------------------------------------------
    # Gap 4 — Orphan refund (refund without a matching original sale)
    # The original_transaction_id points to a UUID that does not exist.
    # ---------------------------------------------------------------
    fake_original_id = str(uuid.uuid4())
    orphan_refund_id = str(uuid.uuid4())
    orphan_amount = -127.50
    orphan_ts = datetime(year, month, 15, 14, 30, 0)
    orphan_txn = {
        "transaction_id": orphan_refund_id,
        "timestamp": orphan_ts,
        "merchant_id": "M005",
        "merchant_name": "Riverside Bookshop",
        "merchant_category": "retail",
        "amount": orphan_amount,
        "currency": "USD",
        "transaction_type": "refund",
        "original_transaction_id": fake_original_id,
        "status": "completed",
    }
    orphan_settle = {
        "settlement_id": str(uuid.uuid4()),
        "transaction_id": orphan_refund_id,
        "settled_amount": orphan_amount,
        "settlement_date": (orphan_ts + timedelta(days=2)).date(),
        "batch_id": f"BATCH-{(orphan_ts + timedelta(days=2)).strftime('%Y%m%d')}",
        "currency": "USD",
        "lag_days": 2,
    }
    txns = pd.concat([txns, pd.DataFrame([orphan_txn])], ignore_index=True)
    setl = pd.concat([setl, pd.DataFrame([orphan_settle])], ignore_index=True)

    txns = txns.sort_values("timestamp").reset_index(drop=True)
    setl = setl.sort_values("settlement_date").reset_index(drop=True)

    gaps = PlantedGaps(
        late_settlement_txn_id=gap1_id,
        rounding_diff_txn_id=gap2_id,
        duplicate_settlement_txn_id=gap3_id,
        orphan_refund_txn_id=orphan_refund_id,
        orphan_refund_fake_original_id=fake_original_id,
    )
    return txns, setl, gaps
