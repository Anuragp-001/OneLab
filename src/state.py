"""Shared Streamlit helpers: session state, theming, KPI cards."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.data_generator import DataGenerator, GeneratorConfig
from src.gap_types import plant_gaps, PlantedGaps
from src.reconciliation import reconcile, ReconciliationResult

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ----- Custom CSS injected on every page -----
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background:
        radial-gradient(circle at 20% 0%, rgba(0,212,255,0.06) 0%, transparent 40%),
        radial-gradient(circle at 80% 100%, rgba(179,136,255,0.06) 0%, transparent 40%),
        #0E1117;
}

/* KPI Card */
.kpi-card {
    background: linear-gradient(135deg, #1A1F2E 0%, #232A3D 100%);
    border-radius: 14px;
    padding: 20px 22px;
    border: 1px solid rgba(255,255,255,0.06);
    box-shadow: 0 6px 24px rgba(0,0,0,0.35);
    height: 100%;
    transition: transform 0.2s, border-color 0.2s;
}
.kpi-card:hover {
    transform: translateY(-2px);
    border-color: rgba(0,212,255,0.3);
}
.kpi-label {
    color: #8892A6; font-size: 12px; font-weight: 500;
    text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 8px;
}
.kpi-value {
    color: #FAFAFA; font-size: 30px; font-weight: 700;
    line-height: 1.1; letter-spacing: -0.5px;
}
.kpi-delta {
    color: #7AE582; font-size: 13px; font-weight: 500; margin-top: 6px;
}
.kpi-delta.bad { color: #FF6B9D; }
.kpi-delta.warn { color: #FFB86B; }

/* Page hero */
.hero {
    padding: 28px 30px;
    border-radius: 16px;
    background: linear-gradient(135deg,
        rgba(0,212,255,0.10) 0%,
        rgba(179,136,255,0.10) 100%);
    border: 1px solid rgba(255,255,255,0.07);
    margin-bottom: 24px;
}
.hero h1 {
    color: #FAFAFA; font-size: 32px; font-weight: 800; margin: 0 0 6px 0;
    letter-spacing: -0.8px;
}
.hero p {
    color: #B7C0D3; font-size: 14px; margin: 0;
}

/* Pill / badge */
.pill {
    display: inline-block; padding: 4px 12px; border-radius: 999px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.6px;
    text-transform: uppercase;
}
.pill-ok    { background: rgba(122,229,130,0.18); color: #7AE582; }
.pill-warn  { background: rgba(255,184,107,0.18); color: #FFB86B; }
.pill-bad   { background: rgba(255,107,157,0.18); color: #FF6B9D; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0A0E16 !important;
    border-right: 1px solid rgba(255,255,255,0.05);
}
section[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }

/* Tables */
.dataframe {
    border-radius: 10px !important; overflow: hidden;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #00D4FF 0%, #0085C7 100%);
    color: #0E1117; border: none; font-weight: 600;
    border-radius: 10px; padding: 8px 18px;
    transition: transform 0.15s, box-shadow 0.15s;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(0,212,255,0.35);
    color: #0E1117;
}

/* Tabs */
.stTabs [data-baseweb="tab"] {
    background: rgba(255,255,255,0.04); border-radius: 8px 8px 0 0;
    padding: 8px 16px; font-weight: 500;
}
.stTabs [aria-selected="true"] {
    background: rgba(0,212,255,0.12) !important;
    color: #00D4FF !important;
}

/* Hide default streamlit branding */
#MainMenu, footer { visibility: hidden; }
</style>
"""


def inject_styles() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def page_setup(title: str, icon: str = "🧮") -> None:
    """Standard page setup — call at the top of every page."""
    st.set_page_config(page_title=f"{title} — Onelab Recon",
                       page_icon=icon, layout="wide",
                       initial_sidebar_state="expanded")
    inject_styles()


def render_hero(title: str, subtitle: str) -> None:
    st.markdown(f"""
    <div class='hero'>
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def kpi(label: str, value: str, delta: str | None = None,
        delta_class: str = "") -> str:
    delta_html = (f"<div class='kpi-delta {delta_class}'>{delta}</div>"
                  if delta else "")
    return f"""
    <div class='kpi-card'>
        <div class='kpi-label'>{label}</div>
        <div class='kpi-value'>{value}</div>
        {delta_html}
    </div>
    """


@st.cache_data(show_spinner=False)
def _generate_and_plant(seed: int, num_txn: int, month: int, year: int):
    cfg = GeneratorConfig(seed=seed, num_transactions=num_txn,
                          month=month, year=year)
    gen = DataGenerator(cfg)
    txns, setl = gen.generate()
    txns_p, setl_p, gaps = plant_gaps(txns, setl, month=month, year=year)
    return txns_p, setl_p, gaps


def ensure_state() -> None:
    """Generate data on first load OR when user clicks regenerate."""
    if "transactions" not in st.session_state:
        seed = int(os.getenv("DATA_SEED", "42"))
        n = int(os.getenv("NUM_TRANSACTIONS", "600"))
        m = int(os.getenv("RECON_MONTH", "4"))
        y = int(os.getenv("RECON_YEAR", "2026"))
        txns, setl, gaps = _generate_and_plant(seed, n, m, y)
        result = reconcile(txns, setl, recon_month=m, recon_year=y)
        st.session_state.update({
            "transactions": txns, "settlements": setl,
            "gaps_info": gaps, "recon_result": result,
            "seed": seed, "num_txn": n, "month": m, "year": y,
        })


def regenerate(seed: int, num_txn: int, month: int, year: int) -> None:
    """Regenerate data using fresh parameters and update session state."""
    _generate_and_plant.clear()
    txns, setl, gaps = _generate_and_plant(seed, num_txn, month, year)
    result = reconcile(txns, setl, recon_month=month, recon_year=year)
    st.session_state.update({
        "transactions": txns, "settlements": setl,
        "gaps_info": gaps, "recon_result": result,
        "seed": seed, "num_txn": num_txn,
        "month": month, "year": year,
    })


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### ⚙️ Controls")

        seed_val = st.number_input(
            "Random seed", min_value=0, max_value=999999,
            value=int(st.session_state.get("seed", 42)), step=1,
        )
        num_val = st.number_input(
            "Transactions", min_value=200, max_value=5000,
            value=int(st.session_state.get("num_txn", 600)), step=100,
        )
        month_val = st.selectbox(
            "Reconciliation month",
            options=list(range(1, 13)),
            format_func=lambda m: pd.Timestamp(2026, m, 1).strftime("%B"),
            index=int(st.session_state.get("month", 4)) - 1,
        )
        year_val = st.number_input(
            "Year", min_value=2020, max_value=2030,
            value=int(st.session_state.get("year", 2026)), step=1,
        )

        if st.button("🔄  Regenerate dataset", use_container_width=True):
            regenerate(int(seed_val), int(num_val),
                       int(month_val), int(year_val))
            st.success("Dataset regenerated.")
            st.rerun()

        st.divider()

        result: ReconciliationResult = st.session_state["recon_result"]
        s = result.summary
        st.markdown("### 📈 Live stats")
        st.markdown(
            f"""
            **Match rate:** `{s['match_rate_pct']:.2f}%`  
            **Transactions:** `{s['total_transactions']:,}`  
            **Total gaps:** `{s['total_gaps']:,}`  
            **Δ Amount:** `${s['amount_difference']:+,.2f}`
            """
        )

        st.divider()
        st.caption("🧪 Onelab Reconciliation · v1.0")


def get_state() -> tuple[pd.DataFrame, pd.DataFrame, PlantedGaps, ReconciliationResult]:
    return (
        st.session_state["transactions"],
        st.session_state["settlements"],
        st.session_state["gaps_info"],
        st.session_state["recon_result"],
    )
