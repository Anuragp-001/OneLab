"""Page 3 — Gap Analysis: drill-down on each of the 4 gap types."""
from __future__ import annotations

import streamlit as st

from src.state import (
    ensure_state, get_state, kpi, page_setup, render_hero, render_sidebar,
)
from src.analytics import gap_distribution
from src.visualizations import gap_distribution_donut


page_setup("Gap Analysis", icon="🔍")
ensure_state()
render_sidebar()

transactions, settlements, gaps_info, result = get_state()
s = result.summary

render_hero(
    "🔍  Gap Analysis",
    "Every record that didn't reconcile cleanly, classified by gap type. "
    "The four planted gap IDs are listed below for end-to-end traceability.",
)

# Distribution donut + planted IDs side by side
left, right = st.columns([1, 1])
with left:
    st.plotly_chart(gap_distribution_donut(gap_distribution(result)),
                    use_container_width=True)
with right:
    st.markdown("### 🌱 Planted gap IDs")
    st.caption("Used to verify end-to-end traceability of the engine.")
    info = gaps_info.as_dict()
    st.code(
        "\n".join(f"{k:<22} : {v}" for k, v in info.items()),
        language="text",
    )

# Tabs for each gap type
tabs = st.tabs([
    f"🌙  Late settlement ({s['gap_late_settlement']})",
    f"🪙  Rounding diff ({s['gap_rounding_diff']})",
    f"♻️  Duplicate entry ({s['gap_duplicates']})",
    f"🚫  Orphan refund ({s['gap_orphan_refunds']})",
])

# ----- Tab 1 — Late settlement -----------------------------------------
with tabs[0]:
    st.markdown(
        "**What it is:** A transaction that occurred in the reconciliation "
        "period but whose settlement crossed into the next month. "
        "On a strict month-end view, the platform shows revenue the bank "
        "hasn't yet acknowledged.\n\n"
        "**Detection:** `txn.month == period.month AND settlement.month != period.month`."
    )
    if not result.late_settlements.empty:
        df = result.late_settlements[[
            "transaction_id", "timestamp", "merchant_name", "amount",
            "settled_amount", "settlement_date", "lag_days",
        ]].copy()
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={
                         "amount": st.column_config.NumberColumn(format="$%.2f"),
                         "settled_amount": st.column_config.NumberColumn(format="$%.2f"),
                     })
        if gaps_info.late_settlement_txn_id in df["transaction_id"].values:
            st.success(
                f"✅ Planted late-settlement ID detected: "
                f"`{gaps_info.late_settlement_txn_id}`"
            )
        else:
            st.warning("Planted ID not found in detected late settlements.")
    else:
        st.info("No late settlements detected.")

# ----- Tab 2 — Rounding difference -------------------------------------
with tabs[1]:
    st.markdown(
        "**What it is:** Settled amount differs from the transaction amount "
        "by a sub-dollar value — invisible per-row, visible when summed.\n\n"
        "**Detection:** `0.001 < abs(amount − settled_amount) < 1.00`."
    )
    if not result.rounding_diffs.empty:
        df = result.rounding_diffs[[
            "transaction_id", "merchant_name", "amount",
            "settled_amount", "amount_diff",
        ]].copy()
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={
                         "amount": st.column_config.NumberColumn(format="$%.2f"),
                         "settled_amount": st.column_config.NumberColumn(format="$%.2f"),
                         "amount_diff": st.column_config.NumberColumn(format="$%.4f"),
                     })
        if gaps_info.rounding_diff_txn_id in df["transaction_id"].values:
            st.success(
                f"✅ Planted rounding-diff ID detected: "
                f"`{gaps_info.rounding_diff_txn_id}`"
            )
        else:
            st.warning("Planted ID not found in detected rounding diffs.")
    else:
        st.info("No rounding differences detected.")

# ----- Tab 3 — Duplicate entry -----------------------------------------
with tabs[2]:
    st.markdown(
        "**What it is:** Same transaction appears more than once in the "
        "settlement table — the bank double-counted.\n\n"
        "**Detection:** `settlements.groupby('transaction_id').size() > 1`."
    )
    if not result.duplicates.empty:
        df = result.duplicates[[
            "transaction_id", "settlement_id", "merchant_name", "amount",
            "settled_amount", "settlement_date", "batch_id",
        ]].copy()
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={
                         "amount": st.column_config.NumberColumn(format="$%.2f"),
                         "settled_amount": st.column_config.NumberColumn(format="$%.2f"),
                     })
        if gaps_info.duplicate_settlement_txn_id in df["transaction_id"].values:
            st.success(
                f"✅ Planted duplicate ID detected: "
                f"`{gaps_info.duplicate_settlement_txn_id}` "
                f"(appears {(df['transaction_id'] == gaps_info.duplicate_settlement_txn_id).sum()}× in settlements)"
            )
        else:
            st.warning("Planted ID not found in detected duplicates.")
    else:
        st.info("No duplicates detected.")

# ----- Tab 4 — Orphan refund -------------------------------------------
with tabs[3]:
    st.markdown(
        "**What it is:** A refund whose `original_transaction_id` doesn't "
        "match any sale in the transactions table. Money went out for a "
        "sale the platform has no record of.\n\n"
        "**Detection:** `refund AND original_transaction_id NOT IN sales.transaction_id`."
    )
    if not result.orphan_refunds.empty:
        df = result.orphan_refunds[[
            "transaction_id", "timestamp", "merchant_name",
            "amount", "original_transaction_id",
        ]].copy()
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={
                         "amount": st.column_config.NumberColumn(format="$%.2f"),
                     })
        if gaps_info.orphan_refund_txn_id in df["transaction_id"].values:
            st.success(
                f"✅ Planted orphan-refund ID detected: "
                f"`{gaps_info.orphan_refund_txn_id}` → "
                f"references missing original `{gaps_info.orphan_refund_fake_original_id}`"
            )
        else:
            st.warning("Planted ID not found in detected orphan refunds.")
    else:
        st.info("No orphan refunds detected.")
