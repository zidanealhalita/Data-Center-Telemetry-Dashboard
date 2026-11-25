"""Ambang batas, palet warna, dan metadata untuk dashboard."""

# --- Ambang batas operasional ---------------------------------------------
ASHRAE_MIN = 18.0        # °C, batas bawah rekomendasi ASHRAE (inlet server)
ASHRAE_MAX = 27.0        # °C, batas atas rekomendasi ASHRAE (inlet server)
RH_MAX = 60.0            # % RH, batas atas kelembapan relatif (ASHRAE recommended)
DEW_MAX = 15.0           # °C dew point, batas atas (ASHRAE recommended)
UTIL_LIMIT = 80.0        # % utilisasi rack yang dianggap tinggi
PUE_REF = 1.5            # PUE referensi (dapat diubah di UI)
FEED_IMB_LIMIT = 10.0    # % selisih Feed A vs B yang dianggap tidak seimbang
HOT_PEER_DELTA = 3.0     # °C di atas median rack lain di hall & jam yang sama
LOSS_RATIO = 0.05        # feed dianggap hilang bila < 5% dari beban IT rack

# --- Metadata hall ----------------------------------------------------------
HALL_DESC = {
    "DH1": "Compute",
    "DH2": "Network + Storage",
    "DH3": "Compute + Network",
    "DH4": "High-Density",
}
HALL_COLORS = {"DH1": "#2563eb", "DH2": "#16a34a", "DH3": "#f59e0b", "DH4": "#dc2626"}
LEVEL_COLORS = {"Normal": "#cbd5e1", "Warning": "#f59e0b", "Critical": "#dc2626"}

# Skala warna suhu: biru (dingin) → hijau (dalam ASHRAE) → kuning (batas) → merah
# titik 18 °C = 0.0, 27 °C = 0.75, 30 °C = 1.0 pada rentang 18–30 °C
TEMP_SCALE = [
    [0.00, "#2563eb"], [0.25, "#22c55e"], [0.50, "#86efac"],
    [0.75, "#facc15"], [1.00, "#dc2626"],
]
TEMP_RANGE = (18.0, 30.0)

# --- Metadata event insiden -------------------------------------------------
EVENTS = {
    "CRAH_FAILURE": {
        "label": "Kegagalan CRAH",
        "icon": "❄️",
        "desc": "Unit pendingin (CRAH) hall gagal: pasokan udara dingin turun dan "
                "suhu inlet seluruh rack di hall naik.",
    },
    "FEED_B_LOSS": {
        "label": "Kehilangan Feed B",
        "icon": "⚡",
        "desc": "Feed B terputus pada sekelompok rack: beban dipikul Feed A saja "
                "(Single Feed N), redundansi 2N hilang.",
    },
    "HOTSPOT_BLANKING_PANEL": {
        "label": "Hot spot (blanking panel)",
        "icon": "🔥",
        "desc": "Blanking panel hilang pada satu rack: udara panas bersirkulasi "
                "balik ke inlet sehingga suhu inlet rack lebih tinggi dari sekitarnya.",
    },
}
