"""Power: keseimbangan Feed A vs B, kehilangan redundansi, utilisasi rack > 80%."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import config as C, data, ui

df = ui.context()
st.title("⚡ Power")

lost = df[df["redundancy_lost"]]
runs = data.consecutive_runs(df, "redundancy_lost")
util = df.groupby(["rack_id", "hall_id", "rack_type"]).agg(
    rata=("rack_utilization_pct", "mean"), puncak=("rack_utilization_pct", "max"),
    jam_tinggi=("rack_utilization_pct", lambda s: int((s > C.UTIL_LIMIT).sum())), n=("rack_utilization_pct", "size"),
).reset_index()
util["pct_tinggi"] = 100 * util["jam_tinggi"] / util["n"]
dual = df[~df["redundancy_lost"]]

k = st.columns(4)
ui.kpi(k[0], "Rack-jam tanpa redundansi", f"{len(lost)}", f"{lost['rack_id'].nunique()} rack · {len(runs)} rentetan kejadian")
ui.kpi(k[1], f"Rack util > {C.UTIL_LIMIT:.0f}%", f"{(util['jam_tinggi'] > 0).sum()}",
       f"{(util['pct_tinggi'] > 50).sum()} rack di atas batas > 50% waktu")
ui.kpi(k[2], "Rata-rata |A − B|", f"{dual['feed_imbalance_pct'].abs().mean():.1f}%", "dari total beban rack (hanya saat dual feed)")
ui.kpi(k[3], "Beban IT total (rata-rata)", f"{df.groupby('timestamp')['it_load_kw'].sum().mean():.0f} kW")

tab1, tab2, tab3 = st.tabs(["⚖️ Keseimbangan Feed A vs B", "🛑 Kehilangan redundansi", f"📊 Utilisasi > {C.UTIL_LIMIT:.0f}%"])

# ---- Tab 1: keseimbangan feed --------------------------------------------------
with tab1:
    rk = dual.groupby(["rack_id", "hall_id", "rack_type"]).agg(
        feed_a=("feed_a_kw", "mean"), feed_b=("feed_b_kw", "mean"), imb=("feed_imbalance_pct", "mean"),
        sd=("feed_imbalance_pct", "std"), rated=("rated_kw", "first"),
        jam_tdk_seimbang=("feed_imbalance_pct", lambda s: 100 * (s.abs() > C.FEED_IMB_LIMIT).mean()),
    ).reset_index()
    lim = st.slider("Ambang ketidakseimbangan (%)", 2.0, 20.0, C.FEED_IMB_LIMIT, 1.0, key="imb_lim")
    c1, c2 = st.columns(2)
    with c1:
        mx = float(max(rk["feed_a"].max(), rk["feed_b"].max()) * 1.05)
        fig = px.scatter(rk, x="feed_b", y="feed_a", color="hall_id", size="rated", hover_name="rack_id",
                         color_discrete_map=C.HALL_COLORS,
                         labels={"feed_a": "Feed A rata-rata (kW)", "feed_b": "Feed B rata-rata (kW)", "hall_id": "Hall"})
        fig.add_trace(go.Scatter(x=[0, mx], y=[0, mx], mode="lines", line=dict(dash="dash", color="#94a3b8"),
                                 name="A = B", hoverinfo="skip"))
        fig.update_layout(title="Rata-rata Feed A vs Feed B per rack (ukuran = rated kW)")
        ui.plot(fig, height=380)
    with c2:
        s = rk.sort_values("imb")
        fig = px.bar(s, x="imb", y="rack_id", color="hall_id", orientation="h", color_discrete_map=C.HALL_COLORS,
                     labels={"imb": "Selisih rata-rata (A − B) / total (%)", "rack_id": "", "hall_id": "Hall"})
        for v in (-lim, lim):
            fig.add_vline(x=v, line_dash="dash", line_color="#dc2626")
        fig.update_layout(title="Bias beban per rack (+ = Feed A lebih berat)", yaxis=dict(categoryorder="array", categoryarray=s["rack_id"]))
        ui.plot(fig, height=380)
    over = rk[rk["imb"].abs() > lim]
    if over.empty:
        st.success(f"Tidak ada rack dengan bias rata-rata melebihi ±{lim:.0f}%. Bias terbesar: "
                   f"{rk.loc[rk['imb'].abs().idxmax(), 'rack_id']} ({rk['imb'].abs().max():.1f}%).")
    else:
        st.warning(f"{len(over)} rack melewati ±{lim:.0f}%: " + ", ".join(over["rack_id"]))
    st.caption("Bias per rack stabil dari jam ke jam (simpangan baku kecil), menandakan ketidakseimbangan sistematis "
               "(distribusi PSU/PDU), bukan fluktuasi acak.")

    st.markdown("**Lihat deret waktu satu rack**")
    r = st.selectbox("Rack", sorted(df["rack_id"].unique()), key="feed_rack")
    rr = df[df["rack_id"] == r]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rr["timestamp"], y=rr["feed_a_kw"], name="Feed A", line=dict(color="#2563eb", width=1)))
    fig.add_trace(go.Scatter(x=rr["timestamp"], y=rr["feed_b_kw"], name="Feed B", line=dict(color="#f59e0b", width=1)))
    fig.update_layout(yaxis_title="kW", legend=dict(orientation="h", y=1.15))
    ui.plot(fig, height=280)

# ---- Tab 2: kehilangan redundansi -------------------------------------------------
with tab2:
    st.markdown(
        "Redundansi dianggap hilang bila **flag `power_redundancy` = Single Feed (N)** *atau* salah satu feed "
        f"< {C.LOSS_RATIO * 100:.0f}% dari beban IT rack. Kedua kriteria dibandingkan untuk validasi."
    )
    mism = int((df["power_redundancy"].ne("Dual Feed (2N)") != df["lost_feed"].ne("")).sum())
    st.caption(f"Validasi silang flag vs angka feed: {mism} baris tidak konsisten.")
    if runs.empty:
        st.success("Tidak ada kehilangan redundansi pada rentang/filter ini.")
    else:
        rows = []
        for r in runs.itertuples():
            seg = df[(df["rack_id"] == r.rack_id) & df["timestamp"].between(r.start, r.end)]
            feed = seg["lost_feed"].replace("", np.nan).mode().iloc[0] if seg["lost_feed"].ne("").any() else "?"
            surv = "feed_a_kw" if feed == "B" else "feed_b_kw"
            pre = df[(df["rack_id"] == r.rack_id) & df["timestamp"].between(r.start - 24 * data.HOUR, r.start - data.HOUR)]
            surge = seg[surv].mean() / pre[surv].mean() if len(pre) and pre[surv].mean() > 0 else np.nan
            rows.append({"Rack": r.rack_id, "Hall": seg["hall_id"].iloc[0], "Feed hilang": feed, "Mulai": r.start,
                         "Selesai": r.end + data.HOUR, "Durasi (jam)": r.hours,
                         "Beban IT tanpa proteksi (kW)": seg["it_load_kw"].mean(),
                         "Lonjakan feed tersisa (×)": surge, "Alarm": seg["alarm_level"].max()})
        ev = pd.DataFrame(rows)
        a, b, c = st.columns(3)
        a.metric("Kejadian (rentetan)", len(ev))
        b.metric("Total rack-jam", int(ev["Durasi (jam)"].sum()))
        c.metric("Beban IT terdampak (kW)", f"{ev.groupby(['Hall', 'Mulai'])['Beban IT tanpa proteksi (kW)'].sum().max():.1f}",
                 help="Jumlah beban IT rack yang kehilangan redundansi secara bersamaan (kejadian terbesar).")
        st.dataframe(ev, hide_index=True, width="stretch",
                     column_config={"Mulai": st.column_config.DatetimeColumn(format="DD MMM YYYY HH:mm"),
                                    "Selesai": st.column_config.DatetimeColumn(format="DD MMM YYYY HH:mm"),
                                    "Beban IT tanpa proteksi (kW)": st.column_config.NumberColumn(format="%.2f"),
                                    "Lonjakan feed tersisa (×)": st.column_config.NumberColumn(format="%.2f")})
        fig = px.timeline(ev, x_start="Mulai", x_end="Selesai", y="Rack", color="Feed hilang",
                          color_discrete_map={"A": "#2563eb", "B": "#dc2626", "?": "#94a3b8"})
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(title="Rentang waktu rack tanpa redundansi")
        ui.plot(fig, height=260)
        st.caption("‘Lonjakan feed tersisa’ = rata-rata beban feed yang masih hidup dibanding 24 jam sebelumnya: "
                   "mendekati 2× berarti feed tersisa memikul seluruh beban rack.")

# ---- Tab 3: utilisasi tinggi -------------------------------------------------------
with tab3:
    hi = util[util["jam_tinggi"] > 0].sort_values("pct_tinggi", ascending=False)
    if hi.empty:
        st.success(f"Tidak ada rack di atas {C.UTIL_LIMIT:.0f}% pada rentang ini.")
    else:
        c1, c2 = st.columns([3, 2])
        with c1:
            fig = px.bar(hi, x="pct_tinggi", y="rack_id", color="hall_id", orientation="h", color_discrete_map=C.HALL_COLORS,
                         labels={"pct_tinggi": f"% waktu util > {C.UTIL_LIMIT:.0f}%", "rack_id": "", "hall_id": "Hall"})
            fig.update_layout(title="Rack dengan utilisasi tinggi", yaxis=dict(categoryorder="array", categoryarray=hi["rack_id"][::-1]))
            ui.plot(fig, height=340)
        with c2:
            t = hi.rename(columns={"rack_id": "Rack", "hall_id": "Hall", "rata": "Rata-rata (%)", "puncak": "Puncak (%)",
                                   "jam_tinggi": "Jam > batas", "pct_tinggi": "% waktu"})
            st.dataframe(t[["Rack", "Hall", "Rata-rata (%)", "Puncak (%)", "Jam > batas", "% waktu"]], hide_index=True,
                         width="stretch", height=340,
                         column_config={c: st.column_config.NumberColumn(format="%.1f") for c in ["Rata-rata (%)", "Puncak (%)", "% waktu"]})
        sel = st.multiselect("Rack untuk deret waktu", hi["rack_id"].tolist(), default=hi["rack_id"].head(3).tolist())
        if sel:
            fig = px.line(df[df["rack_id"].isin(sel)], x="timestamp", y="rack_utilization_pct", color="rack_id",
                          labels={"rack_utilization_pct": "Utilisasi (%)", "timestamp": "", "rack_id": "Rack"})
            fig.add_hline(y=C.UTIL_LIMIT, line_dash="dash", line_color="#dc2626", annotation_text=f"{C.UTIL_LIMIT:.0f}%")
            ui.plot(fig, height=300)
    with st.expander("Beban UPS per hall (catatan kapasitas)"):
        u = data.hall_hourly(df).groupby(["date", "hall_id"])["ups_load_pct"].mean().reset_index()
        fig = px.line(u, x="date", y="ups_load_pct", color="hall_id", color_discrete_map=C.HALL_COLORS,
                      labels={"ups_load_pct": "UPS load (%)", "date": "", "hall_id": "Hall"})
        fig.add_hline(y=50, line_dash="dot", line_color="#94a3b8", annotation_text="50% (acuan 2N)")
        ui.plot(fig, height=280)
        st.caption("Asumsi (perlu diverifikasi): jika `ups_load_pct` adalah beban terhadap kapasitas satu sisi UPS pada sistem 2N, "
                   "beban > 50% berarti kehilangan satu sisi dapat membebani sisi yang tersisa melebihi 100%.")
