"""Page 2 — Reconciliation engine in action."""
from __future__ import annotations

import streamlit as st

from src.state import (
    ensure_state, get_state, kpi, page_setup, render_hero, render_sidebar,
)
from src.analytics import settlement_lag_matrix, waterfall_data
from src.visualizations import (
    amount_waterfall, match_rate_gauge, settlement_lag_heatmap,
)


page_setup("Reconciliation", icon="⚙️")
ensure_state()
render_sidebar()

transactions, settlements, gaps_info, result = get_state()
s = result.summary

render_hero(
    "⚙️  Reconciliation Engine",
    "LEFT JOIN transactions ⟕ settlements on transaction_id, then run the "
    "four detection passes. Everything is vectorised in Pandas — no Python loops.",
)

# KPI band
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(kpi("Match rate", f"{s['match_rate_pct']:.2f}%",
                    f"{s['matched_count']:,} clean matches"),
                unsafe_allow_html=True)
with k2:
    st.markdown(kpi("Total flagged",
                    f"{s['total_gaps']:,}",
                    "across all gap types", "warn"),
                unsafe_allow_html=True)
with k3:
    diff = s['amount_difference']
    cls = "bad" if diff < 0 else ("warn" if diff > 0 else "")
    st.markdown(kpi("Δ Books vs Bank", f"${diff:+,.2f}",
                    "non-zero ⇒ books don't balance" if diff != 0
                    else "balanced", cls),
                unsafe_allow_html=True)
with k4:
    st.markdown(kpi("Recon period",
                    f"{int(st.session_state['month']):02d}/"
                    f"{int(st.session_state['year'])}",
                    "from sidebar"),
                unsafe_allow_html=True)

st.markdown("")

c1, c2 = st.columns([1, 2])
with c1:
    st.plotly_chart(match_rate_gauge(s['match_rate_pct']),
                    use_container_width=True)
with c2:
    st.plotly_chart(amount_waterfall(waterfall_data(result)),
                    use_container_width=True)

# Settlement lag heatmap
st.markdown("### Settlement lag pattern")
st.caption(
    "Shows when transactions occurred (rows) vs how long the bank took "
    "to settle them (columns). Anomalies near month-end can indicate "
    "late-settlement gaps."
)
st.plotly_chart(
    settlement_lag_heatmap(settlement_lag_matrix(transactions, settlements)),
    use_container_width=True,
)

# Algorithm explanation
st.markdown("---")
st.markdown("### How the engine works")
st.markdown("""
The reconciliation pipeline runs in this exact order:

1. **Detect duplicates** — `groupby(transaction_id).size() > 1` on the settlement table.
2. **Deduplicate** for the join — keep first settlement per transaction.
3. **LEFT JOIN** transactions onto deduplicated settlements via `transaction_id`.
4. **Detect orphan refunds** — refunds whose `original_transaction_id` is not in the transactions table.
5. **Detect late settlements** — transaction in the recon period, settlement outside it.
6. **Detect rounding diffs** — `abs(amount − settled_amount)` between $0.001 and $1.00.
7. **Compute match set** — has settlement, in-period, no rounding, no duplication, no orphan.
8. **Aggregate summary** statistics.
""")

with st.expander("👀  Sample matched rows (clean reconciliation)"):
    if not result.matched.empty:
        st.dataframe(
            result.matched[[
                "transaction_id", "timestamp", "merchant_name",
                "amount", "settled_amount", "settlement_date",
                "lag_days", "transaction_type",
            ]].head(50),
            use_container_width=True, hide_index=True,
            column_config={
                "amount": st.column_config.NumberColumn(format="$%.2f"),
                "settled_amount": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
    else:
        st.info("No cleanly matched rows in current dataset.")
