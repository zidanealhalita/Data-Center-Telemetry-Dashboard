"""Smoke test + validasi fitur turunan. Jalankan: pytest -q"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["app.py", "views/overview.py", "views/thermal.py", "views/power.py",
         "views/efficiency.py", "views/incident_replay.py", "views/insights.py"]


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=180).run()
    assert not at.exception, at.exception


def test_derived_features():
    import sys
    sys.path.insert(0, str(ROOT))
    from src import data

    df = data.load_data()
    assert len(df) == 40 * 1440
    # deteksi kehilangan redundansi dari angka feed konsisten dengan flag dataset
    assert ((df["power_redundancy"] != "Dual Feed (2N)") == (df["lost_feed"] != "")).all()
    # tiga event bertag terbentuk
    assert {e["tag"] for e in data.build_events(df)} == {"CRAH_FAILURE", "FEED_B_LOSS", "HOTSPOT_BLANKING_PANEL"}
