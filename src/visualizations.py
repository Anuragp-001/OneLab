"""All Plotly chart builders used by the Streamlit pages."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# ---- Theme tokens ---------------------------------------------------
BG = "rgba(0,0,0,0)"
FG = "#FAFAFA"
GRID = "rgba(255,255,255,0.08)"
ACCENT = "#00D4FF"
ACCENT_2 = "#FF6B9D"
ACCENT_3 = "#7AE582"
ACCENT_4 = "#FFB86B"
ACCENT_5 = "#B388FF"

GAP_COLOURS = {
    "Late settlement":   "#FF6B9D",
    "Rounding diff":     "#FFB86B",
    "Duplicate entry":   "#7AE582",
    "Orphan refund":     "#B388FF",
    "Unsettled (other)": "#FF5470",
}


def _style(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=FG, family="Inter, sans-serif", size=12),
        height=height,
        margin=dict(l=20, r=20, t=50, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def daily_volume_chart(daily_df: pd.DataFrame) -> go.Figure:
    """Dual-line chart: daily transaction vs settlement amount."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily_df["day"], y=daily_df["transaction_amount"],
        mode="lines+markers", name="Transactions",
        line=dict(color=ACCENT, width=3), fill="tozeroy",
        fillcolor="rgba(0,212,255,0.10)",
        hovertemplate="<b>%{x}</b><br>Txn $%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily_df["day"], y=daily_df["settled_amount"],
        mode="lines+markers", name="Settlements",
        line=dict(color=ACCENT_2, width=3, dash="dot"),
        hovertemplate="<b>%{x}</b><br>Settled $%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="Daily Transaction vs Settlement Volume (USD)",
        xaxis_title="Date", yaxis_title="Amount (USD)",
        hovermode="x unified",
    )
    return _style(fig, height=420)


def gap_distribution_donut(gap_df: pd.DataFrame) -> go.Figure:
    """Donut chart of gap counts by type."""
    df = gap_df[gap_df["count"] > 0].copy()
    if df.empty:
        df = pd.DataFrame([{"gap_type": "No gaps", "count": 1}])
    colours = [GAP_COLOURS.get(t, ACCENT) for t in df["gap_type"]]
    fig = go.Figure(go.Pie(
        labels=df["gap_type"], values=df["count"], hole=0.6,
        marker=dict(colors=colours, line=dict(color="#0E1117", width=2)),
        textinfo="label+percent", textposition="outside",
        hovertemplate="<b>%{label}</b><br>%{value} records<extra></extra>",
    ))
    fig.update_layout(title="Gap Type Distribution",
                      annotations=[dict(
                          text=f"<b>{int(df['count'].sum())}</b><br>gaps",
                          x=0.5, y=0.5, font=dict(size=20, color=FG),
                          showarrow=False)])
    return _style(fig, height=420)


def amount_waterfall(waterfall_df: pd.DataFrame) -> go.Figure:
    """Waterfall: how the transaction total reconciles to settled total."""
    fig = go.Figure(go.Waterfall(
        x=waterfall_df["label"],
        measure=waterfall_df["kind"],
        y=waterfall_df["value"],
        connector=dict(line=dict(color="rgba(255,255,255,0.25)")),
        increasing=dict(marker=dict(color=ACCENT_3)),
        decreasing=dict(marker=dict(color=ACCENT_2)),
        totals=dict(marker=dict(color=ACCENT)),
        text=[f"${v:,.2f}" for v in waterfall_df["value"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Amount Reconciliation Waterfall (USD)",
        yaxis_title="Amount (USD)", showlegend=False,
    )
    return _style(fig, height=460)


def settlement_lag_heatmap(matrix: pd.DataFrame) -> go.Figure:
    """Heatmap: day of month (rows) × lag days (cols)."""
    if matrix.empty:
        fig = go.Figure()
        fig.update_layout(title="Settlement Lag Heatmap (no data)")
        return _style(fig, height=420)

    fig = go.Figure(go.Heatmap(
        z=matrix.values,
        x=[f"T+{int(c)}" for c in matrix.columns],
        y=[f"Day {int(d)}" for d in matrix.index],
        colorscale=[[0, "#0E1117"], [0.3, "#1B3A5B"],
                    [0.6, "#0085C7"], [1, ACCENT]],
        hovertemplate="<b>%{y}</b><br>%{x}<br>%{z} txns<extra></extra>",
        colorbar=dict(title="Count"),
    ))
    fig.update_layout(
        title="Settlement Lag Heatmap — Day of Month vs T+N",
        xaxis_title="Settlement Lag", yaxis_title="Transaction Day",
    )
    return _style(fig, height=520)


def merchant_bar(merchant_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart: total amount per merchant."""
    df = merchant_df.head(10).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=df["total_amount"], y=df["merchant_name"], orientation="h",
        marker=dict(color=df["total_amount"], colorscale=[
            [0, "#1B3A5B"], [0.5, "#0085C7"], [1, ACCENT]
        ], showscale=False),
        text=[f"${v:,.0f}" for v in df["total_amount"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="Top Merchants by Transaction Volume",
        xaxis_title="Amount (USD)", yaxis_title="",
    )
    return _style(fig, height=420)


def match_rate_gauge(match_rate_pct: float) -> go.Figure:
    """Speedometer-style gauge of overall match rate."""
    colour = ACCENT_3 if match_rate_pct >= 95 else (
        ACCENT_4 if match_rate_pct >= 80 else ACCENT_2
    )
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=match_rate_pct,
        delta=dict(reference=100, decreasing=dict(color=ACCENT_2)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor=FG),
            bar=dict(color=colour, thickness=0.3),
            steps=[
                dict(range=[0, 80], color="rgba(255,107,157,0.18)"),
                dict(range=[80, 95], color="rgba(255,184,107,0.18)"),
                dict(range=[95, 100], color="rgba(122,229,130,0.18)"),
            ],
            threshold=dict(line=dict(color=FG, width=3),
                           thickness=0.85, value=match_rate_pct),
            bgcolor="rgba(0,0,0,0)",
        ),
        number=dict(suffix="%", font=dict(size=42, color=FG)),
        title=dict(text="Reconciliation Match Rate",
                   font=dict(size=14, color=FG)),
    ))
    return _style(fig, height=320)
