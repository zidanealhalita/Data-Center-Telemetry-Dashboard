"""Pemuatan data, fitur turunan, dan helper deteksi untuk dashboard."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from . import config as C

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "dataset1_dc_power_cooling_telemetry.csv"
HOUR = pd.Timedelta(hours=1)


@st.cache_data(show_spinner="Memuat telemetri…")
def load_data(path: str = str(DATA_PATH)) -> pd.DataFrame:
    """Baca CSV (1 baris = 1 rack × 1 jam) dan tambahkan fitur turunan."""
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["event_tag"] = df["event_tag"].fillna("")
    df["date"] = df["timestamp"].dt.normalize()
    df["hour"] = df["timestamp"].dt.hour

    # Alarm
    df["is_alarm"] = df["alarm_level"].ne("Normal")
    df["is_critical"] = df["alarm_level"].eq("Critical")

    # Daya: keseimbangan feed & deteksi kehilangan redundansi (dari angka feed,
    # bukan hanya dari flag power_redundancy, agar bisa saling memverifikasi)
    df["feed_sum_kw"] = df["feed_a_kw"] + df["feed_b_kw"]
    df["feed_imbalance_pct"] = np.where(
        df["feed_sum_kw"] > 0,
        (df["feed_a_kw"] - df["feed_b_kw"]) / df["feed_sum_kw"] * 100,
        np.nan,
    )
    thr = C.LOSS_RATIO * df["it_load_kw"]
    df["lost_feed"] = np.select(
        [df["feed_a_kw"] < thr, df["feed_b_kw"] < thr], ["A", "B"], default=""
    )
    df["redundancy_lost"] = df["lost_feed"].ne("") | df["power_redundancy"].ne("Dual Feed (2N)")

    # Termal: batas ASHRAE & deviasi terhadap median rack lain di hall/jam yang sama
    df["over_ashrae"] = df["inlet_temp_c"] > C.ASHRAE_MAX
    df["under_ashrae"] = df["inlet_temp_c"] < C.ASHRAE_MIN
    hall_median = df.groupby(["timestamp", "hall_id"])["inlet_temp_c"].transform("median")
    df["hall_median_inlet_c"] = hall_median
    df["peer_delta_c"] = df["inlet_temp_c"] - hall_median

    # Dew point (rumus Magnus) dari suhu inlet & RH
    gamma = np.log(df["humidity_rh_pct"] / 100) + 17.62 * df["inlet_temp_c"] / (243.12 + df["inlet_temp_c"])
    df["dew_point_c"] = 243.12 * gamma / (17.62 - gamma)

    return df.sort_values(["timestamp", "rack_id"]).reset_index(drop=True)


def hall_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Ringkasan 1 baris = 1 hall × 1 jam (kolom hall_* sama untuk semua rack)."""
    out = (
        df.groupby(["timestamp", "hall_id"], as_index=False)
        .agg(
            hall_it_kw=("hall_it_kw", "first"),
            hall_cooling_kw=("hall_cooling_kw", "first"),
            hall_total_kw=("hall_total_kw", "first"),
            hall_pue=("hall_pue", "first"),
            outside_temp_c=("outside_temp_c", "first"),
            ups_load_pct=("ups_load_pct", "first"),
            inlet_mean=("inlet_temp_c", "mean"),
            inlet_max=("inlet_temp_c", "max"),
            n_alarm=("is_alarm", "sum"),
        )
    )
    out["date"] = out["timestamp"].dt.normalize()
    out["hour"] = out["timestamp"].dt.hour
    return out


def consecutive_runs(df: pd.DataFrame, flag: str, key: str = "rack_id") -> pd.DataFrame:
    """Rentetan jam berurutan (flag=True) per `key` → start, end, hours."""
    d = df.loc[df[flag], [key, "timestamp"]].sort_values([key, "timestamp"]).copy()
    if d.empty:
        return pd.DataFrame(columns=[key, "start", "end", "hours"])
    new_run = (d[key] != d[key].shift()) | (d["timestamp"].diff() != HOUR)
    d["run"] = new_run.cumsum()
    return (
        d.groupby("run")
        .agg(**{key: (key, "first")}, start=("timestamp", "min"), end=("timestamp", "max"), hours=("timestamp", "size"))
        .reset_index(drop=True)
    )


def build_events(df: pd.DataFrame) -> list[dict]:
    """Bentuk daftar event dari kolom event_tag (satu event = satu rentetan per hall)."""
    tagged = df[df["event_tag"] != ""]
    events: list[dict] = []
    for tag, g in tagged.groupby("event_tag"):
        g = g.assign(_f=True)
        runs = consecutive_runs(g.drop_duplicates(["hall_id", "timestamp"]), "_f", "hall_id")
        for r in runs.itertuples():
            w = g[(g["hall_id"] == r.hall_id) & g["timestamp"].between(r.start, r.end)]
            meta = C.EVENTS.get(tag, {"label": tag, "icon": "•", "desc": ""})
            severity = "Critical" if w["is_critical"].any() else ("Warning" if w["is_alarm"].any() else "Normal")
            events.append(
                {
                    "tag": tag, "hall": r.hall_id, "start": r.start, "end": r.end,
                    "hours": int(r.hours), "racks": sorted(w["rack_id"].unique()),
                    "severity": severity, "label": meta["label"], "icon": meta["icon"], "desc": meta["desc"],
                }
            )
    return sorted(events, key=lambda e: e["start"])
