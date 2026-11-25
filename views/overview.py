"""Overview: KPI utama + heatmap suhu per hall."""
import pandas as pd
import plotly.express as px
import streamlit as st

from src import config as C, data, ui

df = ui.context()
hh = data.hall_hourly(df)

st.title("🏢 Overview")
st.caption(
    f"{df['timestamp'].min():%d %b %Y} – {df['timestamp'].max():%d %b %Y} · "
    f"{df['hall_id'].nunique()} hall · {df['rack_id'].nunique()} rack · resolusi per jam"
)

# ---- KPI ---------------------------------------------------------------------
pue_mean = hh["hall_pue"].mean()
pue_w = hh["hall_total_kw"].sum() / hh["hall_it_kw"].sum()
n_alarm, n_crit = int(df["is_alarm"].sum()), int(df["is_critical"].sum())
lost = df[df["redundancy_lost"]]
in_ashrae = 100 * (~(df["over_ashrae"] | df["under_ashrae"])).mean()
n_hi_util = df.loc[df["rack_utilization_pct"] > C.UTIL_LIMIT, "rack_id"].nunique()

k = st.columns(5)
ui.kpi(k[0], "Rata-rata PUE", f"{pue_mean:.3f}", f"Tertimbang energi: {pue_w:.3f} · ref. {C.PUE_REF}",
       help="Rata-rata hall_pue per hall-jam. PUE tertimbang energi = Σ total kW / Σ IT kW.")
ui.kpi(k[1], "Jumlah alarm", f"{n_alarm:,}", f"{n_alarm - n_crit:,} warning · {n_crit:,} critical (rack-jam)",
       help="Jumlah baris rack-jam dengan alarm_level ≠ Normal.")
ui.kpi(k[2], "Rack single feed", f"{lost['rack_id'].nunique()}", f"{len(lost)} rack-jam tanpa redundansi 2N",
       help="Rack yang pernah beroperasi dengan satu feed saja (Single Feed N).")
ui.kpi(k[3], "Suhu inlet dalam ASHRAE", f"{in_ashrae:.2f}%", f"Rekomendasi {C.ASHRAE_MIN:.0f}–{C.ASHRAE_MAX:.0f} °C")
ui.kpi(k[4], f"Rack util > {C.UTIL_LIMIT:.0f}%", f"{n_hi_util}", "rack yang pernah melewati batas")

st.write("")

# ---- Heatmap suhu per hall + alarm per hall -------------------------------------
left, right = st.columns([3, 2])
with left:
    st.subheader("Heatmap suhu inlet per hall")
    a, b = st.columns(2)
    axis = a.radio("Sumbu waktu", ["Tanggal", "Jam dalam sehari"], horizontal=True)
    stat = b.radio("Statistik", ["Maksimum", "Rata-rata"], horizontal=True)
    xcol = "date" if axis == "Tanggal" else "hour"
    vcol, agg = ("inlet_max", "max") if stat == "Maksimum" else ("inlet_mean", "mean")
    pv = hh.pivot_table(index="hall_id", columns=xcol, values=vcol, aggfunc=agg)
    pv.index = [ui.hall_label(h) for h in pv.index]
    fig = ui.heatmap(pv, f"Suhu inlet {stat.lower()} (°C)", "°C", text=(xcol == "hour"), height=330)
    ui.plot(fig)
    st.caption(f"Batas atas ASHRAE: {C.ASHRAE_MAX:.0f} °C. Mode *Tanggal + Maksimum* paling jelas menampakkan insiden suhu.")

with right:
    st.subheader("Alarm per hall")
    al = (df[df["is_alarm"]].groupby(["hall_id", "alarm_level"]).size().rename("jumlah").reset_index())
    if al.empty:
        st.success("Tidak ada alarm pada rentang ini.")
    else:
        fig = px.bar(al, x="hall_id", y="jumlah", color="alarm_level", color_discrete_map=C.LEVEL_COLORS,
                     labels={"hall_id": "Hall", "jumlah": "Rack-jam alarm", "alarm_level": "Level"},
                     category_orders={"alarm_level": ["Warning", "Critical"]})
        fig.update_layout(height=330, legend_title_text="")
        ui.plot(fig)
        top = al.groupby("hall_id")["jumlah"].sum().sort_values(ascending=False)
        st.caption(f"{top.index[0]} menyumbang {100 * top.iloc[0] / top.sum():.0f}% dari seluruh alarm.")

# ---- Alarm harian ----------------------------------------------------------------
st.subheader("Alarm per hari")
daily = df[df["is_alarm"]].groupby(["date", "alarm_level"]).size().rename("jumlah").reset_index()
if not daily.empty:
    fig = px.bar(daily, x="date", y="jumlah", color="alarm_level", color_discrete_map=C.LEVEL_COLORS,
                 labels={"date": "", "jumlah": "Rack-jam alarm", "alarm_level": "Level"},
                 category_orders={"alarm_level": ["Warning", "Critical"]})
    fig.update_layout(legend_title_text="")
    ui.plot(fig, height=280)

# ---- Ringkasan hall --------------------------------------------------------------
st.subheader("Ringkasan per hall")
rows = []
for h, g in df.groupby("hall_id"):
    x = hh[hh["hall_id"] == h]
    rows.append({
        "Hall": h, "Tipe": C.HALL_DESC.get(h, ""), "Rack": g["rack_id"].nunique(),
        "Beban IT rata-rata (kW)": x["hall_it_kw"].mean(), "PUE rata-rata": x["hall_pue"].mean(),
        "Inlet rata-rata (°C)": g["inlet_temp_c"].mean(), "Inlet maks (°C)": g["inlet_temp_c"].max(),
        "Alarm warning": int((g["alarm_level"] == "Warning").sum()), "Alarm critical": int(g["is_critical"].sum()),
        f"% rack-jam util > {C.UTIL_LIMIT:.0f}%": 100 * (g["rack_utilization_pct"] > C.UTIL_LIMIT).mean(),
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="%.2f")
                            for c in ["Beban IT rata-rata (kW)", "Inlet rata-rata (°C)", "Inlet maks (°C)",
                                      f"% rack-jam util > {C.UTIL_LIMIT:.0f}%"]}
             | {"PUE rata-rata": st.column_config.NumberColumn(format="%.3f")})
