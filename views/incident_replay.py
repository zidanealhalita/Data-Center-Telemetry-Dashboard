"""Incident Replay: pilih event, lihat linimasa kejadian."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src import config as C, data, ui

full = ui.context(use_filters=False)
events = data.build_events(full)
H = data.HOUR

st.title("🎞️ Incident Replay")
st.caption("Pilih event dari `event_tag` untuk melihat urutan kejadian: suhu, feed daya, pendinginan, PUE, dan alarm. "
           "Halaman ini memakai seluruh data (tidak terpengaruh filter global).")
if not events:
    st.info("Tidak ada event bertag pada dataset.")
    st.stop()

labels = [f"{e['icon']} {e['label']} · {e['hall']} · {e['start']:%d %b %H:%M} → {e['end'] + H:%d %b %H:%M}" for e in events]
c1, c2 = st.columns([3, 1])
idx = c1.selectbox("Event", range(len(events)), format_func=lambda i: labels[i])
pad = c2.slider("Konteks ± jam", 0, 24, 6)
ev = events[idx]
st.info(f"**{ev['label']}** — {ev['desc']}")

w0, w1 = ev["start"] - pad * H, ev["end"] + pad * H
d = full[(full["hall_id"] == ev["hall"]) & full["timestamp"].between(w0, w1)]
aff = d[d["rack_id"].isin(ev["racks"])]
inside = aff[aff["timestamp"].between(ev["start"], ev["end"])]
hall_ts = d.groupby("timestamp").first()
pre24 = full[(full["hall_id"] == ev["hall"]) & full["timestamp"].between(ev["start"] - 24 * H, ev["start"] - H)]
pre24_aff = pre24[pre24["rack_id"].isin(ev["racks"])]

# ---- KPI ringkas -------------------------------------------------------------------------
first_alarm = inside.loc[inside["is_alarm"], "timestamp"].min()
first_crit = inside.loc[inside["is_critical"], "timestamp"].min()
k = st.columns(5)
ui.kpi(k[0], "Durasi", f"{ev['hours']} jam", f"{ev['start']:%d %b %H:%M} – {ev['end'] + H:%H:%M}")
ui.kpi(k[1], "Rack terdampak", f"{len(ev['racks'])}", ", ".join(ev["racks"][:4]) + ("…" if len(ev["racks"]) > 4 else ""))
ui.kpi(k[2], "Alarm pertama",
       "—" if pd.isna(first_alarm) else f"{first_alarm:%H:%M}",
       "tidak ada alarm selama event" if pd.isna(first_alarm) else f"+{int((first_alarm - ev['start']) / H)} jam setelah event dimulai")
ui.kpi(k[3], "Puncak inlet", f"{inside['inlet_temp_c'].max():.1f} °C", f"{inside.loc[inside['inlet_temp_c'].idxmax(), 'rack_id']}")
ui.kpi(k[4], "Rack-jam alarm", f"{int(inside['is_alarm'].sum())}", f"{int(inside['is_critical'].sum())} critical")

# ---- Linimasa 4 panel ---------------------------------------------------------------------
fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.34, 0.22, 0.24, 0.20],
                    subplot_titles=("Suhu inlet rack terdampak (°C)", "Daya feed rack terdampak (kW, dijumlah)",
                                    "Pendinginan & beban IT hall (kW)", "PUE hall"))
x0, x1 = ev["start"].to_pydatetime(), (ev["end"] + H).to_pydatetime()
fig.add_hrect(y0=C.ASHRAE_MIN, y1=C.ASHRAE_MAX, fillcolor="#22c55e", opacity=0.07, line_width=0, row=1, col=1)
for r in ev["racks"][:12]:
    g = aff[aff["rack_id"] == r]
    fig.add_trace(go.Scatter(x=g["timestamp"], y=g["inlet_temp_c"], name=r, mode="lines", line=dict(width=1.3)), row=1, col=1)
fig.add_trace(go.Scatter(x=hall_ts.index, y=hall_ts["hall_median_inlet_c"], name="Median hall", line=dict(color="#64748b", dash="dot", width=2)), row=1, col=1)
fig.add_hline(y=C.ASHRAE_MAX, line_dash="dash", line_color="#f59e0b", row=1, col=1)
fd = aff.groupby("timestamp")[["feed_a_kw", "feed_b_kw", "it_load_kw"]].sum()
fig.add_trace(go.Scatter(x=fd.index, y=fd["feed_a_kw"], name="Feed A", line=dict(color="#2563eb", width=2)), row=2, col=1)
fig.add_trace(go.Scatter(x=fd.index, y=fd["feed_b_kw"], name="Feed B", line=dict(color="#f59e0b", width=2)), row=2, col=1)
fig.add_trace(go.Scatter(x=hall_ts.index, y=hall_ts["hall_cooling_kw"], name="Pendinginan", line=dict(color="#0ea5e9", width=2)), row=3, col=1)
fig.add_trace(go.Scatter(x=hall_ts.index, y=hall_ts["hall_it_kw"], name="Beban IT hall", line=dict(color="#94a3b8", dash="dot")), row=3, col=1)
fig.add_trace(go.Scatter(x=hall_ts.index, y=hall_ts["hall_pue"], name="PUE", line=dict(color="#7c3aed", width=2)), row=4, col=1)
for r_ in range(1, 5):
    fig.add_vrect(x0=x0, x1=x1, fillcolor="#ef4444", opacity=0.08, line_width=0, row=r_, col=1)
fig.update_layout(legend=dict(orientation="h", y=-0.06), hovermode="x unified")
ui.plot(fig, height=780)

# ---- Strip alarm --------------------------------------------------------------------------
st.subheader("Status alarm per rack")
lv = d.assign(kode=d["alarm_level"].map({"Normal": 0, "Warning": 1, "Critical": 2}))
pv = lv.pivot_table(index="rack_id", columns="timestamp", values="kode", aggfunc="max")
pv.index = [("● " if r in ev["racks"] else "   ") + r for r in pv.index]
cs = [[0, C.LEVEL_COLORS["Normal"]], [1 / 3, C.LEVEL_COLORS["Normal"]], [1 / 3, C.LEVEL_COLORS["Warning"]],
      [2 / 3, C.LEVEL_COLORS["Warning"]], [2 / 3, C.LEVEL_COLORS["Critical"]], [1, C.LEVEL_COLORS["Critical"]]]
sf = ui.heatmap(pv, "Abu-abu = Normal · Oranye = Warning · Merah = Critical (● = rack terdampak)", "", scale=cs, zmin=0, zmax=2,
                height=max(220, 26 * len(pv) + 90))
sf.update_traces(showscale=False)
ui.plot(sf)

# ---- Catatan analis -----------------------------------------------------------------------
st.subheader("Catatan analis")
notes: list[str] = []
tag = ev["tag"]
if tag == "CRAH_FAILURE" and not hall_ts.empty:
    prev = hall_ts.loc[ev["start"] - H] if (ev["start"] - H) in hall_ts.index else None
    first = hall_ts.loc[ev["start"]]
    if prev is not None:
        drop = 100 * (1 - first["hall_cooling_kw"] / prev["hall_cooling_kw"])
        lag = "tidak ada alarm" if pd.isna(first_alarm) else f"alarm pertama baru {int((first_alarm - ev['start']) / H)} jam kemudian ({first_alarm:%H:%M})"
        notes.append(f"Daya pendinginan hall turun **{drop:.0f}%** pada jam pertama ({prev['hall_cooling_kw']:.1f} → {first['hall_cooling_kw']:.1f} kW), "
                     f"sedangkan {lag}, yaitu saat suhu inlet melewati batas. Penurunan `cooling_kw` adalah sinyal deteksi dini yang tersedia lebih awal.")
        pue_in = hall_ts.loc[ev["start"]:ev["end"], "hall_pue"]
        notes.append(f"PUE justru **turun** ke {pue_in.min():.3f} (sebelum event {prev['hall_pue']:.3f}) karena konsumsi pendingin berkurang. "
                     "PUE yang ‘bagus’ saat pendingin gagal menunjukkan PUE tidak boleh dipakai sendirian sebagai indikator kesehatan.")
    n_over = inside.loc[inside["over_ashrae"], "rack_id"].nunique()
    notes.append(f"{n_over} dari {len(ev['racks'])} rack melewati {C.ASHRAE_MAX:.0f} °C; puncak {inside['inlet_temp_c'].max():.1f} °C. "
                 "Seluruh rack naik serempak → kegagalan bersifat tingkat-hall, bukan masalah rack tunggal.")
elif tag == "FEED_B_LOSS":
    lf = inside["lost_feed"].replace("", np.nan).mode().iloc[0]
    surv = "feed_a_kw" if lf == "B" else "feed_b_kw"
    surge = inside[surv].mean() / pre24_aff[surv].mean()
    it_in, it_pre = inside["it_load_kw"].mean(), pre24_aff["it_load_kw"].mean()
    notes.append(f"Feed {lf} hilang pada {len(ev['racks'])} rack ({', '.join(ev['racks'])}). Feed tersisa memikul **{surge:.1f}×** beban sebelumnya; "
                 f"beban IT per rack tetap ({it_pre:.1f} → {it_in:.1f} kW), jadi beban berjalan **tanpa proteksi** selama {ev['hours']} jam.")
    ups_pre, ups_in = pre24["ups_load_pct"].mean(), d[d["timestamp"].between(ev["start"], ev["end"])]["ups_load_pct"].mean()
    notes.append(f"`ups_load_pct` tingkat-hall hampir tidak bergerak ({ups_pre:.1f}% → {ups_in:.1f}%), sehingga pemantauan level hall tidak akan menangkap kejadian ini. "
                 "Diperlukan alarm per-feed.")
    notes.append("Rack terdampak berurutan dan serempak → dugaan penyebab bersama (satu PDU/jalur Feed B), bukan kegagalan independen.")
elif tag == "HOTSPOT_BLANKING_PANEL":
    r = ev["racks"][0]
    pr = pre24_aff
    notes.append(f"Inlet {r} rata-rata **{inside['inlet_temp_c'].mean():.1f} °C** vs {pr['inlet_temp_c'].mean():.1f} °C sebelum event "
                 f"(+{inside['inlet_temp_c'].mean() - pr['inlet_temp_c'].mean():.1f} °C); median rack lain di hall {inside['hall_median_inlet_c'].mean():.1f} °C.")
    notes.append(f"Beban IT ({pr['it_load_kw'].mean():.1f} → {inside['it_load_kw'].mean():.1f} kW) dan ΔT ({pr['delta_t_c'].mean():.1f} → {inside['delta_t_c'].mean():.1f} °C) "
                 "praktis tidak berubah → penyebabnya bukan beban, melainkan resirkulasi udara panas (konsisten dengan blanking panel yang hilang).")
    n_alarm = int(inside["is_alarm"].sum())
    n_peer = int((inside["peer_delta_c"] >= C.HOT_PEER_DELTA).sum())
    notes.append(f"Hanya **{n_alarm} dari {len(inside)} jam** ({100 * n_alarm / len(inside):.0f}%) memicu alarm (inlet mencapai ≈ {C.ASHRAE_MAX:.0f} °C), "
                 f"padahal {n_peer} jam ({100 * n_peer / len(inside):.0f}%) menyimpang ≥ {C.HOT_PEER_DELTA:.0f} °C dari rack lain. Hot spot berlangsung "
                 f"{ev['hours'] // 24} hari sebelum teratasi; deteksi berbasis deviasi relatif akan menangkapnya sejak jam pertama.")
for n in notes:
    st.markdown(f"- {n}")
if not notes:
    st.caption("Tidak ada catatan otomatis untuk jenis event ini.")

# ---- Log kejadian --------------------------------------------------------------------------
st.subheader("Log kejadian")
log = d.groupby("timestamp").agg(
    rack_alarm=("is_alarm", "sum"), critical=("is_critical", "sum"), inlet_maks=("inlet_temp_c", "max"),
    pendinginan_kw=("hall_cooling_kw", "first"), pue=("hall_pue", "first"),
    tag=("event_tag", lambda s: ", ".join(sorted({x for x in s if x}))),
).reset_index()
log["fase"] = np.select([log["timestamp"] < ev["start"], log["timestamp"] > ev["end"]], ["Sebelum", "Pemulihan"], default="Event")
only = st.checkbox("Hanya jam dengan alarm / event", value=True)
if only:
    log = log[(log["rack_alarm"] > 0) | (log["tag"] != "")]
st.dataframe(log.rename(columns={"timestamp": "Waktu", "rack_alarm": "Rack alarm", "critical": "Critical", "inlet_maks": "Inlet maks (°C)",
                                 "pendinginan_kw": "Pendinginan (kW)", "pue": "PUE", "tag": "Tag", "fase": "Fase"}),
             hide_index=True, width="stretch", height=320,
             column_config={"Waktu": st.column_config.DatetimeColumn(format="DD MMM HH:mm"),
                            "PUE": st.column_config.NumberColumn(format="%.3f")})
