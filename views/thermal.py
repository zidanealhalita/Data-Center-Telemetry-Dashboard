"""Thermal: heatmap rack × jam, deteksi hot spot, batas ASHRAE."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import config as C, data, ui

df = ui.context()
st.title("🌡️ Thermal")
st.caption(f"Batas ASHRAE (rekomendasi) untuk suhu inlet server: **{C.ASHRAE_MIN:.0f}–{C.ASHRAE_MAX:.0f} °C**.")

# ---- KPI ----------------------------------------------------------------------
n_over, n_under = int(df["over_ashrae"].sum()), int(df["under_ashrae"].sum())
k = st.columns(4)
ui.kpi(k[0], "Inlet maksimum", f"{df['inlet_temp_c'].max():.1f} °C",
       f"{df.loc[df['inlet_temp_c'].idxmax(), 'rack_id']} · {df.loc[df['inlet_temp_c'].idxmax(), 'timestamp']:%d %b %H:%M}")
ui.kpi(k[1], f"Rack-jam > {C.ASHRAE_MAX:.0f} °C", f"{n_over:,}", f"{100 * n_over / len(df):.2f}% dari seluruh pengukuran")
ui.kpi(k[2], f"Rack-jam < {C.ASHRAE_MIN:.0f} °C", f"{n_under:,}", "Tidak ada kondisi terlalu dingin" if n_under == 0 else "")
ui.kpi(k[3], "Rata-rata ΔT (outlet − inlet)", f"{df['delta_t_c'].mean():.1f} °C")

# ---- Heatmap rack × jam ---------------------------------------------------------
st.subheader("Heatmap rack × jam")
halls = sorted(df["hall_id"].unique())
c1, c2, c3 = st.columns([1, 1, 2])
hall = c1.selectbox("Hall", halls, format_func=ui.hall_label)
metric = c2.selectbox("Metrik", ["Inlet", "Outlet", "ΔT (outlet − inlet)"])
mode = c3.radio("Tampilan", ["Pola harian · rata-rata", "Pola harian · maksimum", "Linimasa lengkap"], horizontal=True)

col = {"Inlet": "inlet_temp_c", "Outlet": "outlet_temp_c", "ΔT (outlet − inlet)": "delta_t_c"}[metric]
d = df[df["hall_id"] == hall]
if mode == "Linimasa lengkap":
    pv, text = d.pivot_table(index="rack_id", columns="timestamp", values=col, aggfunc="mean"), False
else:
    agg = "max" if "maksimum" in mode else "mean"
    pv, text = d.pivot_table(index="rack_id", columns="hour", values=col, aggfunc=agg), True
if metric == "Inlet":
    fig = ui.heatmap(pv, f"{metric} — {ui.hall_label(hall)} (°C)", "°C", scale=C.TEMP_SCALE,
                     zmin=C.TEMP_RANGE[0], zmax=C.TEMP_RANGE[1], text=text, height=380)
else:
    fig = ui.heatmap(pv, f"{metric} — {ui.hall_label(hall)} (°C)", "°C", scale="YlOrRd", text=text, height=380)
ui.plot(fig)
if metric == "Inlet":
    st.caption("Skala warna dikunci 18–30 °C: hijau = dalam rekomendasi ASHRAE, kuning ≈ 27 °C, merah = di atas batas.")

# ---- Deteksi hot spot -----------------------------------------------------------
st.subheader("Deteksi hot spot")
st.markdown(
    f"Dua pendekatan digabung: **(1) absolut** — inlet > {C.ASHRAE_MAX:.0f} °C (batas ASHRAE), dan "
    "**(2) relatif** — inlet jauh di atas median rack lain di hall & jam yang sama (menangkap hot spot "
    "lokal yang belum melewati batas absolut)."
)
p1, p2 = st.columns(2)
thr = p1.slider("Ambang deviasi vs median rack lain (°C)", 1.0, 6.0, C.HOT_PEER_DELTA, 0.5)
min_run = p2.slider("Durasi minimum berurutan (jam)", 1, 12, 3)

hd = df.assign(hot_abs=df["over_ashrae"], hot_peer=df["peer_delta_c"] >= thr)
hd["hot"] = hd["hot_abs"] | hd["hot_peer"]
runs = data.consecutive_runs(hd, "hot")
runs = runs[runs["hours"] >= min_run]

if runs.empty:
    st.success("Tidak ada hot spot yang memenuhi kriteria pada rentang/filter ini.")
else:
    stats = hd.groupby("rack_id").agg(
        hall=("hall_id", "first"), jam_abs=("hot_abs", "sum"), jam_peer=("hot_peer", "sum"),
        puncak=("inlet_temp_c", "max"), selisih_maks=("peer_delta_c", "max"),
    )
    g = runs.groupby("rack_id").agg(jam_terdeteksi=("hours", "sum"), run_terpanjang=("hours", "max"),
                                    mulai=("start", "min"), selesai=("end", "max"))
    tbl = g.join(stats).reset_index().sort_values("jam_terdeteksi", ascending=False)
    tbl["Tipe"] = np.select(
        [tbl["jam_peer"] > 0.5 * tbl["jam_terdeteksi"], tbl["jam_abs"] > 0],
        ["Lokal (outlier vs peer)", "Seluruh hall (absolut)"], default="Campuran")
    cl, cr = st.columns([3, 2])
    with cl:
        show = tbl.rename(columns={"rack_id": "Rack", "hall": "Hall", "jam_terdeteksi": "Jam terdeteksi",
                                   "run_terpanjang": "Run terpanjang (jam)", "jam_abs": f"Jam > {C.ASHRAE_MAX:.0f}°C",
                                   "jam_peer": "Jam outlier peer", "puncak": "Puncak inlet (°C)",
                                   "selisih_maks": "Selisih maks vs median (°C)", "mulai": "Mulai", "selesai": "Selesai"})
        st.dataframe(show[["Rack", "Hall", "Tipe", "Jam terdeteksi", "Run terpanjang (jam)", f"Jam > {C.ASHRAE_MAX:.0f}°C",
                           "Jam outlier peer", "Puncak inlet (°C)", "Selisih maks vs median (°C)", "Mulai", "Selesai"]],
                     hide_index=True, width="stretch", height=300,
                     column_config={"Mulai": st.column_config.DatetimeColumn(format="DD MMM HH:mm"),
                                    "Selesai": st.column_config.DatetimeColumn(format="DD MMM HH:mm"),
                                    "Puncak inlet (°C)": st.column_config.NumberColumn(format="%.1f"),
                                    "Selisih maks vs median (°C)": st.column_config.NumberColumn(format="%.1f")})
    with cr:
        sel = hd[hd["rack_id"].isin(tbl["rack_id"])]
        cat = np.select([sel["hot_abs"] & sel["hot_peer"], sel["hot_abs"], sel["hot_peer"]],
                        ["Keduanya", "Hanya absolut", "Hanya outlier peer"], default="")
        cnt = sel.assign(kategori=cat)[cat != ""].groupby(["rack_id", "kategori"]).size().rename("jam").reset_index()
        order = tbl["rack_id"].head(12).tolist()
        fig = px.bar(cnt[cnt["rack_id"].isin(order)], x="jam", y="rack_id", color="kategori", orientation="h",
                     category_orders={"rack_id": order[::-1]}, labels={"rack_id": "", "jam": "Jam", "kategori": ""},
                     color_discrete_map={"Keduanya": "#dc2626", "Hanya absolut": "#f59e0b", "Hanya outlier peer": "#2563eb"})
        fig.update_layout(title="Jam terdeteksi per metode", legend=dict(orientation="h", y=-0.2))
        ui.plot(fig, height=300)

    top = tbl.iloc[0]["rack_id"]
    st.markdown(f"**Rack teratas: {top}** — inlet vs median rack lain di hall-nya")
    rr = df[df["rack_id"] == top]
    fig = go.Figure()
    fig.add_hrect(y0=C.ASHRAE_MIN, y1=C.ASHRAE_MAX, fillcolor="#22c55e", opacity=0.08, line_width=0)
    fig.add_trace(go.Scatter(x=rr["timestamp"], y=rr["hall_median_inlet_c"], name="Median rack lain",
                             line=dict(color="#94a3b8", dash="dot")))
    fig.add_trace(go.Scatter(x=rr["timestamp"], y=rr["inlet_temp_c"], name=f"{top} inlet", line=dict(color="#dc2626", width=1.5)))
    fig.add_hline(y=C.ASHRAE_MAX, line_dash="dash", line_color="#f59e0b",
                  annotation_text=f"ASHRAE {C.ASHRAE_MAX:.0f} °C", annotation_position="top left")
    fig.update_layout(yaxis_title="°C", legend=dict(orientation="h", y=1.12))
    ui.plot(fig, height=300)

# ---- Kepatuhan ASHRAE per hall --------------------------------------------------
st.subheader("Kepatuhan ASHRAE per hall")
cmp_ = (df.assign(zona=np.select([df["under_ashrae"], df["over_ashrae"]],
                                 [f"< {C.ASHRAE_MIN:.0f} °C", f"> {C.ASHRAE_MAX:.0f} °C"],
                                 default=f"{C.ASHRAE_MIN:.0f}–{C.ASHRAE_MAX:.0f} °C"))
        .groupby(["hall_id", "zona"]).size().rename("n").reset_index())
cmp_["persen"] = 100 * cmp_["n"] / cmp_.groupby("hall_id")["n"].transform("sum")
a, b = st.columns(2)
with a:
    fig = px.bar(cmp_, x="hall_id", y="persen", color="zona", labels={"hall_id": "Hall", "persen": "% rack-jam", "zona": ""},
                 color_discrete_map={f"{C.ASHRAE_MIN:.0f}–{C.ASHRAE_MAX:.0f} °C": "#22c55e",
                                     f"> {C.ASHRAE_MAX:.0f} °C": "#dc2626", f"< {C.ASHRAE_MIN:.0f} °C": "#2563eb"})
    fig.update_yaxes(range=[90, 100.01]) if (cmp_.loc[cmp_["zona"].str.contains("–"), "persen"] > 90).all() else None
    fig.update_layout(title="Distribusi zona suhu (sumbu y dipotong bila > 90%)")
    ui.plot(fig, height=320)
with b:
    fig = px.box(df.sample(min(len(df), 20000), random_state=1), x="hall_id", y="inlet_temp_c", color="hall_id",
                 color_discrete_map=C.HALL_COLORS, labels={"hall_id": "Hall", "inlet_temp_c": "Inlet (°C)"})
    fig.add_hline(y=C.ASHRAE_MAX, line_dash="dash", line_color="#f59e0b")
    fig.add_hline(y=C.ASHRAE_MIN, line_dash="dash", line_color="#2563eb")
    fig.update_layout(title="Sebaran suhu inlet (sampel 20 rb baris)", showlegend=False)
    ui.plot(fig, height=320)

with st.expander("Kelembapan & dew point (batas atas ASHRAE: RH 60%, dew point 15 °C)"):
    m = st.columns(3)
    m[0].metric("Rack-jam RH > 60%", f"{int((df['humidity_rh_pct'] > C.RH_MAX).sum()):,}")
    m[1].metric("Rack-jam dew point > 15 °C", f"{int((df['dew_point_c'] > C.DEW_MAX).sum()):,}")
    m[2].metric("RH min – maks", f"{df['humidity_rh_pct'].min():.0f}% – {df['humidity_rh_pct'].max():.0f}%")
    st.caption("Dew point dihitung dari suhu inlet & RH (rumus Magnus). Hanya batas atas yang diperiksa.")
