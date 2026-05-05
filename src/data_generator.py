"""Synthetic financial data generator for transactions and settlements.

Generates realistic payment platform data for a single calendar month.
Output is two pandas DataFrames: transactions (platform's own records)
and settlements (what the bank reports as actually arrived).
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from faker import Faker

# A realistic mix of merchant categories for a payments platform
DEFAULT_MERCHANTS: list[tuple[str, str, str]] = [
    ("M001", "Bluefin Coffee Co.", "food_beverage"),
    ("M002", "Northwind Apparel", "retail"),
    ("M003", "Stellar Electronics", "retail"),
    ("M004", "Greenleaf Grocers", "grocery"),
    ("M005", "Riverside Bookshop", "retail"),
    ("M006", "Apex Auto Parts", "automotive"),
    ("M007", "Lumen Home Goods", "retail"),
    ("M008", "Pacific Pet Supply", "specialty"),
    ("M009", "Helios Health Pharmacy", "healthcare"),
    ("M010", "Crescent Travel Co.", "travel"),
]


@dataclass
class GeneratorConfig:
    """Configuration for synthetic data generation."""
    seed: int = 42
    num_transactions: int = 600
    month: int = 4
    year: int = 2026
    refund_ratio: float = 0.08  # ~8% of transactions are refunds
    min_amount: float = 5.00
    max_amount: float = 5000.00


class DataGenerator:
    """Generate synthetic but realistic transactions and settlements."""

    def __init__(self, config: GeneratorConfig | None = None) -> None:
        self.config = config or GeneratorConfig()
        self.faker = Faker()
        Faker.seed(self.config.seed)
        random.seed(self.config.seed)
        np.random.seed(self.config.seed)

    def generate(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Generate transactions and matching settlements.

        Returns
        -------
        transactions : pd.DataFrame
            Platform's own transaction records.
        settlements : pd.DataFrame
            Bank's settlement records (one per transaction at this stage).
        """
        transactions = self._generate_transactions()
        settlements = self._generate_settlements(transactions)
        return transactions, settlements

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _days_in_month(self) -> int:
        if self.config.month == 12:
            next_start = datetime(self.config.year + 1, 1, 1)
        else:
            next_start = datetime(self.config.year, self.config.month + 1, 1)
        month_start = datetime(self.config.year, self.config.month, 1)
        return (next_start - month_start).days

    def _generate_transactions(self) -> pd.DataFrame:
        days = self._days_in_month()
        num_sales = int(self.config.num_transactions * (1 - self.config.refund_ratio))
        num_refunds = self.config.num_transactions - num_sales

        # Sales
        sales: list[dict] = []
        for _ in range(num_sales):
            day = random.randint(1, days)
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            ts = datetime(self.config.year, self.config.month, day, hour, minute, second)
            mid, mname, mcat = random.choice(DEFAULT_MERCHANTS)
            amount = round(random.uniform(self.config.min_amount, self.config.max_amount), 2)
            sales.append({
                "transaction_id": str(uuid.uuid4()),
                "timestamp": ts,
                "merchant_id": mid,
                "merchant_name": mname,
                "merchant_category": mcat,
                "amount": amount,
                "currency": "USD",
                "transaction_type": "sale",
                "original_transaction_id": None,
                "status": "completed",
            })

        sales_df = pd.DataFrame(sales)

        # Refunds linked to a real prior sale (within month)
        refunds: list[dict] = []
        for _ in range(num_refunds):
            original = sales_df.sample(1, random_state=random.randint(0, 10_000)).iloc[0]
            orig_ts: datetime = original["timestamp"]
            refund_ts = orig_ts + timedelta(days=random.randint(1, 5),
                                            hours=random.randint(0, 23))
            # Skip if refund would land in next month
            if refund_ts.month != self.config.month:
                continue
            refunds.append({
                "transaction_id": str(uuid.uuid4()),
                "timestamp": refund_ts,
                "merchant_id": original["merchant_id"],
                "merchant_name": original["merchant_name"],
                "merchant_category": original["merchant_category"],
                "amount": -float(original["amount"]),
                "currency": "USD",
                "transaction_type": "refund",
                "original_transaction_id": original["transaction_id"],
                "status": "completed",
            })

        df = pd.concat([sales_df, pd.DataFrame(refunds)], ignore_index=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    def _generate_settlements(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Generate one settlement per transaction with realistic T+1/T+2 lag."""
        records: list[dict] = []
        for _, txn in transactions.iterrows():
            # Bank settles 1-2 days later (occasional T+3 due to weekend skew)
            lag_days = random.choices([1, 2, 3], weights=[0.4, 0.5, 0.1], k=1)[0]
            settle_ts = txn["timestamp"] + timedelta(days=lag_days)
            settle_date = settle_ts.date()
            records.append({
                "settlement_id": str(uuid.uuid4()),
                "transaction_id": txn["transaction_id"],
                "settled_amount": float(txn["amount"]),
                "settlement_date": settle_date,
                "batch_id": f"BATCH-{settle_date.strftime('%Y%m%d')}",
                "currency": "USD",
                "lag_days": lag_days,
            })
        df = pd.DataFrame(records).sort_values("settlement_date").reset_index(drop=True)
        return df


def save_to_csv(transactions: pd.DataFrame, settlements: pd.DataFrame,
                out_dir: Path) -> tuple[Path, Path]:
    """Persist both DataFrames to disk."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    txn_path = out_dir / "transactions.csv"
    set_path = out_dir / "settlements.csv"
    transactions.to_csv(txn_path, index=False)
    settlements.to_csv(set_path, index=False)
    return txn_path, set_path
