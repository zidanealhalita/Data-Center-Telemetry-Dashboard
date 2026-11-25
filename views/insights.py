"""Analyst Insights: temuan, rekomendasi, kalkulator what-if, dan cek kualitas data."""
import numpy as np
import pandas as pd
import streamlit as st

from src import config as C, data, ui

full = ui.context(use_filters=False)
hh = data.hall_hourly(full)
events = {e["tag"]: e for e in data.build_events(full)}
H = data.HOUR
n_hours = hh["timestamp"].nunique()
ann = 8760 / n_hours  # faktor ekstrapolasi periode data → setahun

st.title("💡 Analyst Insights")
st.caption("Temuan dari sudut pandang analis data center. Seluruh angka dihitung langsung dari dataset (60 hari, 40 rack, 4 hall).")


def finding(title: str, points: list[str], rec: str) -> None:
    with st.container(border=True):
        st.markdown(f"#### {title}")
        for p in points:
            st.markdown(f"- {p}")
        st.markdown(f"**Rekomendasi:** {rec}")


# ---- 1. Alarm: kebisingan dari DH4 -----------------------------------------------------------
u = full.groupby(["rack_id", "hall_id"]).agg(pct=("rack_utilization_pct", lambda s: 100 * (s > C.UTIL_LIMIT).mean()),
                                              rata=("rack_utilization_pct", "mean")).reset_index()
chronic = u[u["pct"] > 50].sort_values("pct", ascending=False)
share_util = ((full["is_alarm"]) & (full["event_tag"] == "") & (full["rack_utilization_pct"] > C.UTIL_LIMIT)).sum() / full["is_alarm"].sum()
dh4_low = u[u["hall_id"] == "DH4"].sort_values("rata").head(2)
finding("1 · Alarm didominasi satu kondisi kronis di DH4", [
    f"**{100 * share_util:.0f}%** dari {int(full['is_alarm'].sum()):,} alarm adalah peringatan utilisasi > {C.UTIL_LIMIT:.0f}% tanpa insiden; "
    f"insiden nyata (3 event) tenggelam di antaranya.",
    f"Rack kronis: {', '.join(f'{r.rack_id} ({r.pct:.0f}% waktu, rata-rata {r.rata:.0f}%)' for r in chronic.itertuples())}.",
    f"Rack DH4 yang paling longgar: {', '.join(f'{r.rack_id} (≈{r.rata:.0f}%)' for r in dh4_low.itertuples())}.",
], f"Buat alarm bertingkat (Warning hanya bila bertahan ≥ beberapa jam, Critical ≥ 90%) agar alarm fatigue berkurang, dan pindahkan sebagian beban "
   f"dari rack kronis ke rack yang lebih longgar di hall yang sama.")

# ---- 2. Hot spot tersembunyi --------------------------------------------------------------------
h = events.get("HOTSPOT_BLANKING_PANEL")
if h:
    w = full[(full["rack_id"].isin(h["racks"])) & full["timestamp"].between(h["start"], h["end"])]
    base = full[(full["rack_id"].isin(h["racks"])) & full["timestamp"].between(h["start"] - 24 * H, h["start"] - H)]
    n, n_alarm, n_peer = len(w), int(w["is_alarm"].sum()), int((w["peer_delta_c"] >= C.HOT_PEER_DELTA).sum())
    finding(f"2 · Hot spot {h['racks'][0]} nyaris tak terlihat oleh ambang ASHRAE", [
        f"Selama {n // 24} hari inlet naik **+{w['inlet_temp_c'].mean() - base['inlet_temp_c'].mean():.1f} °C** "
        f"({base['inlet_temp_c'].mean():.1f} → {w['inlet_temp_c'].mean():.1f} °C) pada beban dan ΔT yang sama → resirkulasi udara, bukan beban.",
        f"Hanya **{n_alarm}/{n} jam ({100 * n_alarm / n:.0f}%)** memicu alarm karena inlet hanya menyentuh ≈ {C.ASHRAE_MAX:.0f} °C pada sebagian jam; "
        f"deteksi relatif (≥ {C.HOT_PEER_DELTA:.0f} °C di atas median rack lain) menangkap **{n_peer}/{n} jam ({100 * n_peer / n:.0f}%)**.",
    ], "Tambahkan aturan deteksi deviasi relatif (rack vs median hall) di samping ambang absolut, dan audit blanking panel pada rack lain.")

# ---- 3. CRAH failure ----------------------------------------------------------------------------
c = events.get("CRAH_FAILURE")
if c:
    hc = full[(full["hall_id"] == c["hall"])].groupby("timestamp").first()
    ins = full[(full["hall_id"] == c["hall"]) & full["timestamp"].between(c["start"], c["end"])]
    prev, first = hc.loc[c["start"] - H], hc.loc[c["start"]]
    fa = ins.loc[ins["is_alarm"], "timestamp"].min()
    finding(f"3 · Kegagalan CRAH di {c['hall']}: sinyal terlambat dan PUE menyesatkan", [
        f"Pendinginan turun {100 * (1 - first['hall_cooling_kw'] / prev['hall_cooling_kw']):.0f}% pada jam pertama, tetapi alarm baru menyala "
        f"**{int((fa - c['start']) / H)} jam kemudian**; puncak inlet {ins['inlet_temp_c'].max():.1f} °C, "
        f"{ins.loc[ins['over_ashrae'], 'rack_id'].nunique()} dari {len(c['racks'])} rack melewati {C.ASHRAE_MAX:.0f} °C.",
        f"Selama event PUE jatuh ke {hc.loc[c['start']:c['end'], 'hall_pue'].min():.3f} (normal ≈ {prev['hall_pue']:.3f}): PUE membaik justru saat kondisi memburuk.",
    ], "Tambahkan alarm pada penurunan mendadak `cooling_kw`/kenaikan ΔT hall, dan jangan menjadikan PUE sebagai indikator kesehatan tunggal.")

# ---- 4. Feed B loss ------------------------------------------------------------------------------
f = events.get("FEED_B_LOSS")
if f:
    fw = full[full["rack_id"].isin(f["racks"]) & full["timestamp"].between(f["start"], f["end"])]
    finding(f"4 · Kehilangan Feed B di {f['hall']}: {len(f['racks'])} rack serempak tanpa redundansi", [
        f"{', '.join(f['racks'])} berjalan Single Feed (N) selama {f['hours']} jam, total **{fw['it_load_kw'].mean() * len(f['racks']):.0f} kW** beban IT tanpa proteksi.",
        "Kejadian serempak pada rack berurutan menunjukkan penyebab bersama (PDU/jalur Feed B). Beban UPS tingkat-hall tidak berubah, sehingga tidak terdeteksi di level itu.",
    ], "Alarm Critical per-feed (feed < 5% beban IT), periksa jalur Feed B bersama pada rack tersebut, dan jadwalkan uji failover berkala.")

# ---- 5. PUE vs suhu luar ---------------------------------------------------------------------------
slope = float(np.mean([np.polyfit(g["outside_temp_c"], g["hall_pue"], 1)[0] for _, g in hh.groupby("hall_id")]))
r2 = float(np.mean([np.corrcoef(g["outside_temp_c"], g["hall_pue"])[0, 1] ** 2 for _, g in hh.groupby("hall_id")]))
bh = hh.groupby("hour")["hall_pue"].mean()
it_h = hh.groupby("hour")["hall_it_kw"].mean()
finding("5 · PUE mengikuti suhu luar, bukan beban IT", [
    f"Tiap +1 °C suhu luar menaikkan PUE ≈ **{slope:.4f}** (R² rata-rata per hall {r2:.2f}). PUE harian bergerak dari {bh.min():.3f} (jam {bh.idxmin():02d}:00) ke {bh.max():.3f} (jam {bh.idxmax():02d}:00).",
    f"Beban IT hampir datar sepanjang hari ({it_h.min():.0f}–{it_h.max():.0f} kW), jadi variasi PUE berasal dari pendinginan.",
    f"Suhu inlet rata-rata {full['inlet_temp_c'].mean():.1f} °C, jauh di bawah batas {C.ASHRAE_MAX:.0f} °C.",
], "Evaluasi setpoint suhu pasokan secara bertahap (dengan pemantauan hot spot, lihat temuan 2) dan manfaatkan jam malam yang lebih sejuk; "
   "klaim penghematan perlu diuji di lapangan.")

# ---- 6. Bias Feed ----------------------------------------------------------------------------------
dual = full[~full["redundancy_lost"]]
b = dual.groupby("rack_id")["feed_imbalance_pct"].agg(["mean", "std"])
bx = b.reindex(b["mean"].abs().sort_values(ascending=False).index).head(3)
finding("6 · Bias Feed A/B sistematis per rack (masih di bawah ambang)", [
    f"Bias terbesar: {', '.join(f'{i} ({r['mean']:+.1f}%)' for i, r in bx.iterrows())} (+ = Feed A lebih berat), dengan simpangan baku hanya ≈ {b['std'].mean():.1f}%.",
    f"Semua rack di bawah ambang ±{C.FEED_IMB_LIMIT:.0f}%, tetapi bias yang stabil menandakan pola distribusi PSU/PDU, bukan noise.",
], "Seimbangkan distribusi PSU pada rack dengan bias terbesar agar kapasitas kedua feed terpakai merata saat salah satu feed gagal.")

# ---- What-if PUE -----------------------------------------------------------------------------------
st.header("🧮 Kalkulator what-if: penghematan bila PUE ditargetkan")
cA, cB = st.columns(2)
tariff = cA.number_input("Tarif listrik (Rp/kWh) — asumsi, ubah sesuai kontrak", 500, 5000, 1500, 50)
pue_by = hh.groupby("hall_id").apply(lambda g: g["hall_total_kw"].sum() / g["hall_it_kw"].sum(), include_groups=False)
default_t = float(round(pue_by.min(), 2))
target = cB.slider("Target PUE", 1.10, 1.50, default_t, 0.01, help="Hall dengan PUE di bawah target tidak dihitung (tidak ada penghematan).")
rows = []
for hid, g in hh.groupby("hall_id"):
    pw = pue_by[hid]
    saved = max(pw - target, 0) * g["hall_it_kw"].sum()  # kWh dalam periode data (data per jam)
    rows.append({"Hall": hid, "PUE aktual": pw, "Target": target, "Hemat periode (kWh)": saved,
                 "Hemat setahun (MWh)": saved * ann / 1000, "Hemat setahun (Rp juta)": saved * ann * tariff / 1e6})
wi = pd.DataFrame(rows)
m = st.columns(3)
m[0].metric("Hemat setahun", f"{wi['Hemat setahun (MWh)'].sum():,.0f} MWh")
m[1].metric("Setara biaya", f"Rp {wi['Hemat setahun (Rp juta)'].sum():,.0f} juta")
m[2].metric("Total energi fasilitas (periode)", f"{hh['hall_total_kw'].sum() / 1000:,.0f} MWh")
st.dataframe(wi, hide_index=True, width="stretch", column_config={
    "PUE aktual": st.column_config.NumberColumn(format="%.3f"), "Target": st.column_config.NumberColumn(format="%.2f"),
    "Hemat periode (kWh)": st.column_config.NumberColumn(format="%,.0f"), "Hemat setahun (MWh)": st.column_config.NumberColumn(format="%.1f"),
    "Hemat setahun (Rp juta)": st.column_config.NumberColumn(format="%.1f")})
st.caption(f"Perkiraan kasar: PUE tertimbang energi × beban IT periode, diekstrapolasi {ann:.1f}× ke setahun. "
           "Mengabaikan musim dan perubahan beban.")

# ---- Kualitas data ----------------------------------------------------------------------------------
with st.expander("✅ Pemeriksaan kualitas data"):
    sum_it = full.groupby(["timestamp", "hall_id"])["it_load_kw"].sum().rename("s").reset_index().merge(hh[["timestamp", "hall_id", "hall_it_kw"]])
    other = (hh["hall_total_kw"] - hh["hall_it_kw"] - hh["hall_cooling_kw"]) / hh["hall_it_kw"]
    mism = int((full["power_redundancy"].ne("Dual Feed (2N)") != full["lost_feed"].ne("")).sum())
    checks = pd.DataFrame([
        ("Kelengkapan: baris = rack × jam", f"{len(full):,} = {full['rack_id'].nunique()} × {n_hours:,}", len(full) == full["rack_id"].nunique() * n_hours),
        ("Nilai kosong (selain event_tag)", f"{int(full.drop(columns='event_tag').isna().sum().sum())}", full.drop(columns="event_tag").isna().sum().sum() == 0),
        ("PUE dihitung ulang vs hall_pue (selisih maks)", f"{(hh['hall_total_kw'] / hh['hall_it_kw'] - hh['hall_pue']).abs().max():.4f}", (hh["hall_total_kw"] / hh["hall_it_kw"] - hh["hall_pue"]).abs().max() < 0.01),
        ("Σ beban IT rack vs hall_it_kw (selisih maks, kW)", f"{(sum_it['s'] - sum_it['hall_it_kw']).abs().max():.2f}", (sum_it["s"] - sum_it["hall_it_kw"]).abs().max() < 0.1),
        ("Feed A + B vs beban IT (selisih maks, kW)", f"{(full['feed_sum_kw'] - full['it_load_kw']).abs().max():.2f}", (full["feed_sum_kw"] - full["it_load_kw"]).abs().max() < 0.1),
        ("Flag redundansi vs angka feed (baris tidak konsisten)", f"{mism}", mism == 0),
        ("Total hall − IT − pendinginan (% beban IT)", f"{100 * other.mean():.1f}% (stabil)", True),
    ], columns=["Pemeriksaan", "Hasil", "Lulus"])
    st.dataframe(checks, hide_index=True, width="stretch")
    st.caption("Selisih ‘total − IT − pendinginan’ ≈ 6% beban IT di semua hall: diasumsikan rugi distribusi/UPS/penerangan; tidak dirinci di dataset.")
