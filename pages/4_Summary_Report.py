"""Page 4 — Summary Report (executive view + CSV download)."""
from __future__ import annotations

import io
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from src.reconciliation import build_full_report
from src.state import (
    ensure_state, get_state, kpi, page_setup, render_hero, render_sidebar,
)


page_setup("Summary Report", icon="📊")
ensure_state()
render_sidebar()

transactions, settlements, gaps_info, result = get_state()
s = result.summary

render_hero(
    "📊  Executive Summary Report",
    "A one-page reconciliation summary you can share with finance, plus "
    "a full CSV export of every record (matched and gap-flagged).",
)

# Headline KPIs
hk1, hk2, hk3, hk4 = st.columns(4)
with hk1:
    st.markdown(kpi("Match rate",
                    f"{s['match_rate_pct']:.2f}%",
                    "of all transactions"),
                unsafe_allow_html=True)
with hk2:
    st.markdown(kpi("Total reconciled",
                    f"${s['total_settled_amount']:,.2f}",
                    "via bank settlement"),
                unsafe_allow_html=True)
with hk3:
    diff = s['amount_difference']
    cls = "bad" if diff != 0 else ""
    st.markdown(kpi("Amount unreconciled",
                    f"${diff:+,.2f}",
                    "non-zero ⇒ gap exists" if diff != 0 else "books balance",
                    cls),
                unsafe_allow_html=True)
with hk4:
    st.markdown(kpi("Records to investigate",
                    f"{s['total_gaps']:,}",
                    "across 4+ gap types", "warn"),
                unsafe_allow_html=True)

st.markdown("")

# Executive narrative
period_label = f"{int(st.session_state['month']):02d}/{int(st.session_state['year'])}"
status_pill = (
    "<span class='pill pill-bad'>BOOKS DON'T BALANCE</span>"
    if s['amount_difference'] != 0 or s['total_gaps'] > 0
    else "<span class='pill pill-ok'>FULLY RECONCILED</span>"
)
st.markdown(f"""
<div class='kpi-card'>
    <div style='display:flex;justify-content:space-between;align-items:center;'>
        <div>
            <div class='kpi-label'>Reconciliation Period</div>
            <div style='font-size:24px;font-weight:700;color:#FAFAFA;
                        margin:4px 0 0 0;'>{period_label}</div>
        </div>
        {status_pill}
    </div>
    <div style='margin-top:18px;color:#B7C0D3;font-size:14px;line-height:1.7;'>
    Of <b style='color:#FAFAFA;'>{s['total_transactions']:,}</b> processed transactions
    totaling <b style='color:#FAFAFA;'>${s['total_transaction_amount']:,.2f}</b>,
    the bank settled <b style='color:#FAFAFA;'>${s['total_settled_amount']:,.2f}</b> across
    <b style='color:#FAFAFA;'>{s['total_settlements']:,}</b> records — leaving an
    unreconciled difference of
    <b style='color:#FF6B9D;'>${s['amount_difference']:+,.2f}</b>.
    The reconciliation engine flagged
    <b style='color:#FFB86B;'>{s['total_gaps']:,}</b> records for review,
    achieving a clean match rate of
    <b style='color:#7AE582;'>{s['match_rate_pct']:.2f}%</b>.
    </div>
</div>
""", unsafe_allow_html=True)

# Gap breakdown table
st.markdown("### Gap breakdown")
breakdown_df = pd.DataFrame([
    {"Gap type": "🌙 Late settlement",
     "Count": s['gap_late_settlement'],
     "Description": "Transaction in period, settled in following month",
     "Example impact": "Revenue recognized in wrong period"},
    {"Gap type": "🪙 Rounding difference",
     "Count": s['gap_rounding_diff'],
     "Description": "Sub-dollar mismatch between txn amount and settled amount",
     "Example impact": "Aggregate totals diverge over time"},
    {"Gap type": "♻️ Duplicate settlement",
     "Count": s['gap_duplicates'],
     "Description": "Same transaction settled more than once",
     "Example impact": "Bank inflated reported revenue"},
    {"Gap type": "🚫 Orphan refund",
     "Count": s['gap_orphan_refunds'],
     "Description": "Refund references a non-existent original sale",
     "Example impact": "Cash leaving the platform without justification"},
    {"Gap type": "❓ Unsettled (other)",
     "Count": s['gap_unsettled'],
     "Description": "Transaction with no settlement record at all",
     "Example impact": "Funds owed but not yet received"},
])
st.dataframe(breakdown_df, use_container_width=True, hide_index=True)

# Download section
st.markdown("---")
st.markdown("### Downloads")

full_report = build_full_report(result)
csv_buf = io.StringIO()
full_report.to_csv(csv_buf, index=False)
ts_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

dl1, dl2, dl3 = st.columns(3)
with dl1:
    st.download_button(
        label="📥  Full reconciliation report (CSV)",
        data=csv_buf.getvalue(),
        file_name=f"reconciliation_report_{period_label.replace('/','-')}_{ts_str}.csv",
        mime="text/csv", use_container_width=True,
    )
with dl2:
    st.download_button(
        label="📥  Raw transactions (CSV)",
        data=transactions.to_csv(index=False),
        file_name=f"transactions_{ts_str}.csv",
        mime="text/csv", use_container_width=True,
    )
with dl3:
    st.download_button(
        label="📥  Raw settlements (CSV)",
        data=settlements.to_csv(index=False),
        file_name=f"settlements_{ts_str}.csv",
        mime="text/csv", use_container_width=True,
    )

with st.expander("Preview the full reconciliation report"):
    st.dataframe(full_report.head(200), use_container_width=True, hide_index=True)
    st.caption(f"Showing 200 of {len(full_report):,} rows.")

st.markdown("---")
st.markdown("### Production limitations (3 honest sentences)")
st.markdown("""
1. **Currency & FX**: This system reconciles only USD; in production a
   payments platform deals with multi-currency settlements where FX
   conversion timing, mid-rate vs settlement-rate spread, and rounding
   modes per ISO-4217 currency would create an entire additional class
   of gaps not handled here.
2. **Identifier fragility**: Real banks frequently don't echo the
   platform's `transaction_id` back — settlements arrive with a bank
   reference, an acquirer batch ID, or only an aggregated batch total,
   so a production engine needs fuzzy matching by amount + window +
   merchant + last-4 of card, with a tie-breaking ranker.
3. **State is missing**: This system models a single point-in-time
   reconciliation, but real money flows include chargebacks, partial
   refunds, fee deductions, hold-and-release patterns, and
   interchange/scheme fees that net against settlement amounts — none
   of which are modeled here.
""")
