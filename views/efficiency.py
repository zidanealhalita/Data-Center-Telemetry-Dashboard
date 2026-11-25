"""Efficiency: PUE vs suhu luar (Jakarta), tren PUE per hall."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src import config as C, data, ui

df = ui.context()
hh = data.hall_hourly(df)
st.title("📈 Efficiency")
st.caption("PUE = total daya fasilitas ÷ daya IT. Suhu luar = Jakarta (kolom `outside_temp_c`).")

slope, icpt = np.polyfit(hh["outside_temp_c"], hh["hall_pue"], 1)
r2 = np.corrcoef(hh["outside_temp_c"], hh["hall_pue"])[0, 1] ** 2
pue_w = hh["hall_total_kw"].sum() / hh["hall_it_kw"].sum()
by_hour = hh.groupby("hour")["hall_pue"].mean()
k = st.columns(4)
ui.kpi(k[0], "Rata-rata PUE", f"{hh['hall_pue'].mean():.3f}", f"Tertimbang energi {pue_w:.3f}")
ui.kpi(k[1], "Sensitivitas terhadap suhu luar", f"+{slope:.4f} /°C", f"≈ +{slope * 10:.2f} PUE per +10 °C · R² gabungan = {r2:.2f} (per hall di tabel)")
ui.kpi(k[2], "PUE terbaik – terburuk (jam)", f"{by_hour.min():.3f} – {by_hour.max():.3f}",
       f"jam {by_hour.idxmin():02d}:00 vs {by_hour.idxmax():02d}:00")
ui.kpi(k[3], "Suhu luar rata-rata", f"{hh['outside_temp_c'].mean():.1f} °C", f"rentang {hh['outside_temp_c'].min():.0f}–{hh['outside_temp_c'].max():.0f} °C")

# ---- PUE vs suhu luar ---------------------------------------------------------------
st.subheader("PUE vs suhu luar (Jakarta)")
fig = px.scatter(hh, x="outside_temp_c", y="hall_pue", color="hall_id", opacity=0.3, color_discrete_map=C.HALL_COLORS,
                 labels={"outside_temp_c": "Suhu luar (°C)", "hall_pue": "PUE", "hall_id": "Hall"})
fits = []
for h, g in hh.groupby("hall_id"):
    b, a = np.polyfit(g["outside_temp_c"], g["hall_pue"], 1)
    xs = np.array([g["outside_temp_c"].min(), g["outside_temp_c"].max()])
    fig.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines", name=f"{h} (fit)", line=dict(color=C.HALL_COLORS[h], width=3)))
    fits.append({"Hall": h, "Kemiringan (PUE/°C)": b, "Intersep": a, "R²": np.corrcoef(g["outside_temp_c"], g["hall_pue"])[0, 1] ** 2})
fig.add_hline(y=C.PUE_REF, line_dash="dot", line_color="#94a3b8", annotation_text=f"ref. {C.PUE_REF}")
ui.plot(fig, height=420)
st.dataframe(pd.DataFrame(fits), hide_index=True, width="stretch",
             column_config={"Kemiringan (PUE/°C)": st.column_config.NumberColumn(format="%.4f"),
                            "Intersep": st.column_config.NumberColumn(format="%.3f"), "R²": st.column_config.NumberColumn(format="%.2f")})

# ---- Tren PUE per hall --------------------------------------------------------------
st.subheader("Tren PUE per hall")
c1, c2 = st.columns([1, 3])
gran = c1.radio("Granularitas", ["Per jam", "Harian", "Mingguan"], index=1)
show_t = c1.checkbox("Tampilkan suhu luar", value=True)
rule = {"Per jam": None, "Harian": "D", "Mingguan": "W"}[gran]
base = hh.set_index("timestamp")
if rule:
    tr = base.groupby("hall_id")["hall_pue"].resample(rule).mean().reset_index()
    ot = base["outside_temp_c"].resample(rule).mean().reset_index()
else:
    tr, ot = hh[["hall_id", "timestamp", "hall_pue"]], hh.drop_duplicates("timestamp")[["timestamp", "outside_temp_c"]]
fig = make_subplots(specs=[[{"secondary_y": True}]])
for h, g in tr.groupby("hall_id"):
    fig.add_trace(go.Scatter(x=g["timestamp"], y=g["hall_pue"], name=h, line=dict(color=C.HALL_COLORS[h])), secondary_y=False)
if show_t:
    fig.add_trace(go.Scatter(x=ot["timestamp"], y=ot["outside_temp_c"], name="Suhu luar", line=dict(color="#94a3b8", dash="dot")), secondary_y=True)
fig.update_yaxes(title_text="PUE", secondary_y=False)
fig.update_yaxes(title_text="Suhu luar (°C)", secondary_y=True, showgrid=False)
fig.update_layout(legend=dict(orientation="h", y=1.12))
with c2:
    ui.plot(fig, height=380)

# ---- Pola harian + dekomposisi ----------------------------------------------------------
a, b = st.columns(2)
with a:
    st.subheader("Pola harian PUE")
    dh = hh.groupby(["hall_id", "hour"])["hall_pue"].mean().reset_index()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for h, g in dh.groupby("hall_id"):
        fig.add_trace(go.Scatter(x=g["hour"], y=g["hall_pue"], name=h, line=dict(color=C.HALL_COLORS[h])), secondary_y=False)
    oh = hh.groupby("hour")["outside_temp_c"].mean()
    fig.add_trace(go.Scatter(x=oh.index, y=oh.values, name="Suhu luar", line=dict(color="#94a3b8", dash="dot")), secondary_y=True)
    fig.update_xaxes(title_text="Jam", dtick=3)
    fig.update_yaxes(title_text="PUE", secondary_y=False)
    fig.update_yaxes(title_text="°C", secondary_y=True, showgrid=False)
    ui.plot(fig, height=340)
with b:
    st.subheader("Dekomposisi PUE per hall")
    rows = []
    for h, g in hh.groupby("hall_id"):
        it = g["hall_it_kw"].sum()
        rows += [{"Hall": h, "Komponen": "Beban IT", "Rasio": 1.0},
                 {"Hall": h, "Komponen": "Pendinginan", "Rasio": g["hall_cooling_kw"].sum() / it},
                 {"Hall": h, "Komponen": "Lainnya (distribusi, UPS, dll.)", "Rasio": (g["hall_total_kw"].sum() - g["hall_it_kw"].sum() - g["hall_cooling_kw"].sum()) / it}]
    dec = pd.DataFrame(rows)
    fig = px.bar(dec, x="Hall", y="Rasio", color="Komponen", text=dec["Rasio"].map("{:.3f}".format),
                 color_discrete_map={"Beban IT": "#cbd5e1", "Pendinginan": "#2563eb", "Lainnya (distribusi, UPS, dll.)": "#f59e0b"})
    fig.update_layout(yaxis_title="× beban IT (total = PUE)", legend=dict(orientation="h", y=-0.2))
    ui.plot(fig, height=340)

st.subheader("PUE menurut kelas suhu luar")
bins = [0, 26, 28, 30, 32, 50]
labels = ["< 26", "26–28", "28–30", "30–32", "≥ 32"]
bn = hh.assign(kelas=pd.cut(hh["outside_temp_c"], bins=bins, labels=labels, right=False))
bt = bn.groupby(["kelas", "hall_id"], observed=True).agg(PUE=("hall_pue", "mean"), jam=("hall_pue", "size")).reset_index()
fig = px.line(bt, x="kelas", y="PUE", color="hall_id", markers=True, color_discrete_map=C.HALL_COLORS,
              labels={"kelas": "Suhu luar (°C)", "hall_id": "Hall"})
ui.plot(fig, height=300)
