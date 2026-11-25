# 🏢 Data Center Power & Cooling Telemetry Dashboard

Dashboard analitik berbasis **Streamlit** untuk memantau daya, pendinginan, dan efisiensi (PUE) data center
dari telemetri per-jam: **4 hall · 40 rack · 60 hari (1 Sep – 30 Okt 2026)**, 57.600 baris.

**Dibuat oleh:** Muhammad Zidane Alhalita

## Halaman

| Halaman | Isi |
|---|---|
| **Overview** | KPI (rata-rata PUE, jumlah alarm, rack single feed, % dalam ASHRAE, rack util > 80%), heatmap suhu per hall (tanggal/jam × maks/rata-rata), alarm per hall & per hari, ringkasan hall |
| **Thermal** | Heatmap rack × jam (inlet/outlet/ΔT; pola harian atau linimasa), deteksi hot spot (absolut > 27 °C **+** relatif vs median rack lain), kepatuhan ASHRAE 18–27 °C, kelembapan & dew point |
| **Power** | Keseimbangan Feed A vs B, deteksi kehilangan redundansi (flag **dan** angka feed, divalidasi silang), rack utilisasi > 80%, catatan beban UPS |
| **Efficiency** | PUE vs suhu luar Jakarta (regresi per hall), tren PUE per hall (jam/hari/minggu), pola harian, dekomposisi PUE, PUE per kelas suhu luar |
| **Incident Replay** | Pilih event (`event_tag`) → linimasa 4 panel (suhu, feed, pendinginan, PUE), status alarm per rack, catatan analis otomatis, log kejadian |
| **Analyst Insights** | 6 temuan + rekomendasi, kalkulator what-if penghematan PUE, pemeriksaan kualitas data |

Filter global (hall & rentang tanggal) ada di sidebar dan berlaku di semua halaman kecuali Incident Replay.

## Temuan utama (dari data ini)

1. **96% alarm** adalah satu kondisi kronis: utilisasi > 80% di DH4 (R01, R09, R10) — tiga insiden nyata tenggelam di antaranya.
2. **Hot spot DH2-R07** (8 hari) hanya memicu alarm di ±39% jamnya; deteksi relatif terhadap median rack lain menangkap ±99%.
3. **Kegagalan CRAH DH3**: pendinginan turun 39% di jam pertama, alarm baru menyala 1 jam kemudian; PUE malah *turun* ke 1,18 — PUE bukan indikator kesehatan tunggal.
4. **Feed B hilang di DH1** (R05–R08, 4 jam): ±28 kW tanpa redundansi; beban UPS tingkat-hall tidak berubah sehingga tak terdeteksi di level itu.
5. **PUE mengikuti suhu luar** (≈ +0,0126 per °C), bukan beban IT yang hampir datar sepanjang hari.
6. **DH4 (high-density)** ber-PUE ≈ 1,34 vs ≈ 1,29 hall lain (pendinginan 28% vs 23% beban IT).

## Menjalankan lokal

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Tes: `pip install pytest && pytest -q`

## Deploy

**Streamlit Community Cloud** (gratis): push repo ke GitHub → https://share.streamlit.io → *New app* →
pilih repo, branch `main`, **Main file path: `app.py`**. Dataset (±8 MB) ikut di repo (`data/`).

## Struktur

```
app.py                  # router navigasi + filter global
views/                  # satu file per halaman
src/config.py           # ambang batas (ASHRAE, util, PUE ref, dll.), warna, metadata event
src/data.py             # load + fitur turunan, hall_hourly, consecutive_runs, build_events
src/ui.py               # filter sidebar, helper grafik/KPI
data/                   # dataset1_dc_power_cooling_telemetry.csv
tests/test_app.py       # smoke test semua halaman + validasi fitur turunan
.github/workflows/ci.yml
```

## Definisi & asumsi

- **PUE** = `hall_total_kw / hall_it_kw`. KPI memakai rata-rata `hall_pue` per hall-jam; PUE tertimbang energi ditampilkan sebagai pembanding.
- **Alarm** = baris rack-jam dengan `alarm_level` ≠ Normal (mengikuti dataset).
- **ASHRAE**: inlet 18–27 °C (rekomendasi); kelembapan: RH ≤ 60% dan dew point ≤ 15 °C (hanya batas atas diperiksa).
- **Hot spot**: inlet > 27 °C **atau** ≥ 3 °C di atas median rack lain pada hall & jam yang sama, bertahan ≥ 3 jam (semua ambang dapat diubah di UI / `src/config.py`).
- **Kehilangan redundansi**: `power_redundancy` = Single Feed (N) **atau** salah satu feed < 5% beban IT rack.
- Selisih `total − IT − pendinginan` ≈ 6% beban IT di semua hall; diasumsikan rugi distribusi/UPS/lainnya (tidak dirinci di dataset).
- `ups_load_pct` diasumsikan beban tingkat-hall terhadap kapasitas satu sisi UPS; acuan 50% untuk 2N hanya indikatif.
- Kalkulator what-if mengekstrapolasi 60 hari ke setahun dan memakai tarif listrik asumsi yang bisa diubah; angkanya perkiraan kasar.

## Lisensi

MIT — lihat `LICENSE`.
