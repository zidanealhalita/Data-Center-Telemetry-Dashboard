"""Komponen UI bersama: filter global, CSS, helper grafik & KPI."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import config as C, data

AUTHOR = "Muhammad Zidane Alhalita"

_CSS = """
<style>
.block-container {padding-top: 2.4rem; max-width: 1400px;}
div[data-testid="stMetricValue"] {font-size: 1.7rem;}
.small-note {color:#64748b; font-size:0.85rem;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def hall_label(h: str) -> str:
    return f"{h} · {C.HALL_DESC.get(h, '')}"


def sidebar_filters(df: pd.DataFrame) -> None:
    """Filter global (dirender di app.py pada setiap run agar state-nya persisten)."""
    halls = sorted(df["hall_id"].unique())
    d0, d1 = df["date"].min().date(), df["date"].max().date()
    with st.sidebar:
        st.markdown("### 🔎 Filter global")
        st.multiselect("Hall", halls, default=halls, key="f_halls", format_func=hall_label)
        st.date_input("Rentang tanggal", value=(d0, d1), min_value=d0, max_value=d1, key="f_dates")
        st.caption("Filter berlaku untuk semua halaman, kecuali Incident Replay.")
        st.divider()
        st.markdown(f"**Data Center Telemetry**  \nDibuat oleh **{AUTHOR}**")


def context(use_filters: bool = True) -> pd.DataFrame:
    """Dataset (terfilter) untuk halaman aktif."""
    df = data.load_data()
    if not use_filters:
        return df
    halls = st.session_state.get("f_halls") or sorted(df["hall_id"].unique())
    dates = st.session_state.get("f_dates")
    if isinstance(dates, (tuple, list)) and len(dates) == 2:
        lo, hi = pd.Timestamp(dates[0]), pd.Timestamp(dates[1])
    else:
        lo, hi = df["date"].min(), df["date"].max()
    out = df[df["hall_id"].isin(halls) & (df["date"] >= lo) & (df["date"] <= hi)]
    if out.empty:
        st.warning("Tidak ada data pada filter yang dipilih.")
        st.stop()
    return out


def plot(fig: go.Figure, height: int | None = None, key: str | None = None) -> None:
    fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=45, b=10))
    if height:
        fig.update_layout(height=height)
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except Exception:  # Streamlit versi lama
        st.plotly_chart(fig, use_container_width=True, key=key)


def kpi(col, label: str, value: str, caption: str = "", help: str | None = None) -> None:
    with col.container(border=True):
        st.metric(label, value, help=help)
        if caption:
            st.caption(caption)


def heatmap(pv: pd.DataFrame, title: str, cbar: str, *, scale="RdYlBu_r", zmin=None, zmax=None,
            text: bool = False, height: int = 360) -> go.Figure:
    """Heatmap generik dari pivot (index = baris, columns = sumbu x)."""
    fig = go.Figure(
        go.Heatmap(
            z=pv.values, x=list(pv.columns), y=list(pv.index), colorscale=scale, zmin=zmin, zmax=zmax,
            colorbar=dict(title=cbar), texttemplate="%{z:.1f}" if text else None,
            hovertemplate="%{y}<br>%{x}<br>%{z:.2f}<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed", type="category")
    fig.update_layout(title=title, height=height)
    return fig
