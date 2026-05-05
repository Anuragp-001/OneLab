"""Onelab — Payments Reconciliation Dashboard.

Entry point for the multi-page Streamlit app.

Run locally:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from src.state import (
    ensure_state, get_state, kpi, page_setup, render_hero, render_sidebar,
)
from src.analytics import daily_volume, gap_distribution
from src.visualizations import (
    daily_volume_chart, gap_distribution_donut, match_rate_gauge,
)


def main() -> None:
    page_setup("Home", icon="🧮")
    ensure_state()
    render_sidebar()

    transactions, settlements, gaps_info, result = get_state()
    s = result.summary

    render_hero(
        "Payments Reconciliation Dashboard",
        "A payments company's books don't balance at month end. "
        "This system finds the gaps between what the platform recorded "
        "and what the bank actually settled.",
    )

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(kpi("Total transactions",
                        f"{s['total_transactions']:,}",
                        f"${s['total_transaction_amount']:,.2f} total"),
                    unsafe_allow_html=True)
    with col2:
        st.markdown(kpi("Settled records",
                        f"{s['total_settlements']:,}",
                        f"${s['total_settled_amount']:,.2f} settled"),
                    unsafe_allow_html=True)
    with col3:
        delta_class = "bad" if s['amount_difference'] != 0 else ""
        st.markdown(kpi("Amount difference",
                        f"${s['amount_difference']:+,.2f}",
                        "books don't balance"
                        if s['amount_difference'] != 0 else "perfectly matched",
                        delta_class),
                    unsafe_allow_html=True)
    with col4:
        st.markdown(kpi("Total gaps detected",
                        f"{s['total_gaps']:,}",
                        f"{s['match_rate_pct']:.1f}% match rate"),
                    unsafe_allow_html=True)

    st.markdown("")
    st.markdown("")

    # Match rate gauge + donut + summary text
    g1, g2 = st.columns([1, 1])
    with g1:
        st.plotly_chart(match_rate_gauge(s['match_rate_pct']),
                        use_container_width=True)
    with g2:
        st.plotly_chart(gap_distribution_donut(gap_distribution(result)),
                        use_container_width=True)

    # Daily flow chart full width
    st.plotly_chart(
        daily_volume_chart(daily_volume(transactions, settlements)),
        use_container_width=True,
    )

    # Quick navigation cards
    st.markdown("### Where to go next")
    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        st.markdown("""
        <div class='kpi-card'>
            <div class='kpi-label'>📥 Step 1</div>
            <div style='font-size:18px;font-weight:600;color:#FAFAFA;
                        margin-bottom:6px;'>Data Overview</div>
            <div style='color:#8892A6;font-size:13px;'>
                Inspect both datasets side by side.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with nav2:
        st.markdown("""
        <div class='kpi-card'>
            <div class='kpi-label'>⚙️ Step 2</div>
            <div style='font-size:18px;font-weight:600;color:#FAFAFA;
                        margin-bottom:6px;'>Reconciliation</div>
            <div style='color:#8892A6;font-size:13px;'>
                See how matching works and what slips through.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with nav3:
        st.markdown("""
        <div class='kpi-card'>
            <div class='kpi-label'>🔍 Step 3</div>
            <div style='font-size:18px;font-weight:600;color:#FAFAFA;
                        margin-bottom:6px;'>Gap Analysis</div>
            <div style='color:#8892A6;font-size:13px;'>
                Drill into each of the 4 gap types.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with nav4:
        st.markdown("""
        <div class='kpi-card'>
            <div class='kpi-label'>📊 Step 4</div>
            <div style='font-size:18px;font-weight:600;color:#FAFAFA;
                        margin-bottom:6px;'>Summary Report</div>
            <div style='color:#8892A6;font-size:13px;'>
                Executive summary + downloadable CSV.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    st.info(
        "Navigate using the sidebar (left) → pages are listed in the order "
        "you should walk through them.",
        icon="🧭",
    )


if __name__ == "__main__":
    main()
