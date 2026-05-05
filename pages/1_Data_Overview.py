"""Page 1 — Data Overview.

Inspect the two raw datasets side by side. This is the input
to the reconciliation engine.
"""
from __future__ import annotations

import streamlit as st

from src.state import (
    ensure_state, get_state, kpi, page_setup, render_hero, render_sidebar,
)
from src.analytics import merchant_breakdown
from src.visualizations import merchant_bar


page_setup("Data Overview", icon="📥")
ensure_state()
render_sidebar()

transactions, settlements, gaps_info, result = get_state()

render_hero(
    "📥  Data Overview",
    "The two datasets we're trying to reconcile: what the platform "
    "recorded, and what the bank says actually settled.",
)

# KPI strip
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(kpi("Transactions (rows)",
                    f"{len(transactions):,}",
                    f"{transactions['merchant_id'].nunique()} merchants"),
                unsafe_allow_html=True)
with c2:
    st.markdown(kpi("Settlements (rows)",
                    f"{len(settlements):,}",
                    f"{settlements['batch_id'].nunique()} batches"),
                unsafe_allow_html=True)
with c3:
    refunds = (transactions['transaction_type'] == 'refund').sum()
    st.markdown(kpi("Refund txns",
                    f"{int(refunds):,}",
                    f"{100 * refunds / len(transactions):.1f}% of total"),
                unsafe_allow_html=True)
with c4:
    avg = float(transactions['amount'].abs().mean())
    st.markdown(kpi("Avg ticket size", f"${avg:,.2f}",
                    "absolute value"),
                unsafe_allow_html=True)

st.markdown("")

tabs = st.tabs(["💳  Transactions", "🏦  Settlements", "🛍  Merchants"])

with tabs[0]:
    st.markdown(
        "**Transactions** — every payment the platform processed. "
        "Column `original_transaction_id` links refunds back to their original sale."
    )
    st.dataframe(
        transactions.head(200),
        use_container_width=True, hide_index=True,
        column_config={
            "amount": st.column_config.NumberColumn(format="$%.2f"),
            "timestamp": st.column_config.DatetimeColumn(format="DD MMM YYYY HH:mm"),
        },
    )
    st.caption(f"Showing 200 of {len(transactions):,} rows. "
               f"Use the regenerate button to refresh data.")

with tabs[1]:
    st.markdown(
        "**Settlements** — the bank's record of what actually arrived. "
        "Settled 1–3 days after the original transaction (T+1 / T+2 / T+3)."
    )
    st.dataframe(
        settlements.head(200),
        use_container_width=True, hide_index=True,
        column_config={
            "settled_amount": st.column_config.NumberColumn(format="$%.2f"),
        },
    )
    st.caption(f"Showing 200 of {len(settlements):,} rows.")

with tabs[2]:
    mb = merchant_breakdown(transactions)
    cleft, cright = st.columns([3, 2])
    with cleft:
        st.plotly_chart(merchant_bar(mb), use_container_width=True)
    with cright:
        st.dataframe(
            mb, use_container_width=True, hide_index=True,
            column_config={
                "total_amount": st.column_config.NumberColumn(format="$%.2f"),
                "avg_amount": st.column_config.NumberColumn(format="$%.2f"),
            },
        )

st.markdown("---")
st.markdown("### Stated assumptions")
st.markdown("""
- **Currency**: All amounts are USD. No FX reconciliation.
- **Settlement lag**: Bank settles T+1 (40%), T+2 (50%), T+3 (10%).
- **Date range**: A single calendar month (configurable in the sidebar).
- **Transaction split**: ~92% sales, ~8% refunds linked to a real prior sale.
- **Amount range**: Sales are uniformly distributed between $5.00 and $5,000.00.
- **Merchants**: 10 named merchants across 6 categories.
- **One-to-one**: In a clean world, each transaction has exactly one settlement.
- **Planted gaps**: Exactly 4 gap types are seeded into every dataset. See Page 3.
""")
