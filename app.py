"""Entry point Streamlit: navigasi multi-halaman + filter global."""
import streamlit as st

st.set_page_config(page_title="DC Telemetry Dashboard", page_icon="🏢", layout="wide")

from src import data, ui  # noqa: E402

ui.inject_css()
ui.sidebar_filters(data.load_data())

pages = [
    st.Page("views/overview.py", title="Overview", icon="🏢", default=True),
    st.Page("views/thermal.py", title="Thermal", icon="🌡️"),
    st.Page("views/power.py", title="Power", icon="⚡"),
    st.Page("views/efficiency.py", title="Efficiency", icon="📈"),
    st.Page("views/incident_replay.py", title="Incident Replay", icon="🎞️"),
    st.Page("views/insights.py", title="Analyst Insights", icon="💡"),
]
st.navigation(pages).run()
