"""Synthetic-fixture checks for the PeMS screening pipeline. No agency data."""

import gzip
from datetime import date

import pandas as pd
import pytest
import yaml

from adaptive_ramp_metering.data import pems

CFG = yaml.safe_load(open("configs/pems.yaml", encoding="utf-8"))
DAY = date(2022, 10, 17)


def _row(station, minute, obs, flow, occ, speed, lane_type="OR"):
    ts = f"10/17/2022 {minute // 60:02d}:{minute % 60:02d}:00"
    return f"{ts},{station},7,405,S,{lane_type},.5,10,{obs},{flow},{occ},{speed},1,2\n"


def _fixture(tmp_path):
    raw = tmp_path / "d07_text_station_5min_2022_10_17.txt.gz"
    with gzip.open(raw, "wt") as f:
        for i in range(288):  # full on-ramp day, 100% observed
            f.write(_row(716744, 5 * i, 100, 12, ".05", ""))
        for i in range(100):  # mainline: imputed zeros then a gap
            f.write(_row(717816, 5 * i, 0, 0, ".0", "65", "ML"))
        f.write(_row(999999, 0, 100, 1, ".0", "60"))  # outside corridor
    return raw


def test_stage_days_are_weekdays():
    days = pems.stage_days(CFG, 2)
    assert date(2022, 10, 8) not in days and date(2022, 10, 3) in days
    assert all(d.weekday() < 5 for d in days)


def test_parse_catalog_both_shapes():
    payload = {
        "10": [{"file_name": "d07_text_station_5min_2022_10_17.txt.gz", "url": "/x"}],
        "k": {
            "format": {
                "text": {"file_name": "d07_text_meta_2022_09_01.txt", "url": "/m"}
            }
        },
        "junk": [{"file_name": "readme.txt", "url": "/r"}],
    }
    files = pems.parse_catalog(payload)
    assert set(files) == {
        "d07_text_station_5min_2022_10_17.txt.gz",
        "d07_text_meta_2022_09_01.txt",
    }
    assert files["d07_text_meta_2022_09_01.txt"] == "https://pems.dot.ca.gov/m"


def test_extract_screen_rank_export(tmp_path):
    raw = _fixture(tmp_path)
    interim = tmp_path / "interim.csv"
    assert pems.extract_day(raw, {716744, 717816}, interim) == 388
    frame = pd.read_csv(interim, dtype=str)
    screened = pems.screen_day(frame, DAY, CFG["thresholds"]).set_index("station")
    ramp, main = screened.loc[716744], screened.loc[717816]
    assert ramp["expected_intervals"] == 288 and ramp["missing_pct"] == 0
    assert ramp["meets_thresholds"] and ramp["speed_reported"] == 0
    assert ramp["suspicious"]  # constant flow 12 all day -> stuck run
    assert main["zero_flow_unobserved"] == 100 and main["flow_observed"] == 0
    assert not main["meets_thresholds"] and main["mean_observed_pct"] == 0

    periods, days = pems.rank_periods(screened.reset_index(), CFG)
    assert len(periods) == 1 and not periods.loc[0, "qualifies"]
    assert periods.loc[0, "incident_days"] == 1  # 2022-10-17 is a reported incident

    si = pems.to_si(frame)
    first = si[si["sensor_id"] == 716744].iloc[0]
    assert str(first["interval_start_utc"]) == "2022-10-17 07:00:00+00:00"
    assert first["flow_veh_per_s"] == 12 / 300 and pd.isna(first["mean_speed_mps"])
    assert first["quality_flag"] == "observed"
    assert si[si["sensor_id"] == 717816]["quality_flag"].eq("imputed").all()


def test_rank_weeks_prefers_full_ramp_coverage():
    rows = []
    for i in range(9):  # 9 screened days; ramp dips on Oct 2, mainline always fails
        for station, obs in ((716744, 50 if i == 1 else 100), (717816, 0)):
            rows.append(
                {
                    "station": station,
                    "date": date(2022, 10, 1) + pd.Timedelta(days=i).to_pytimedelta(),
                    "mean_observed_pct": obs,
                    "pct_intervals_ge90": obs,
                    "meets_thresholds": obs >= 90,
                    "suspicious": False,
                }
            )
    weeks = pems.rank_weeks(pd.DataFrame(rows), CFG)
    assert len(weeks) == 3  # starts Oct 1, 2, 3
    assert weeks.loc[0, "start_date"] == date(2022, 10, 3)  # only window without Oct 2
    assert (
        weeks.loc[0, "ramp_days_passing"] == 7
        and weeks.loc[1, "ramp_days_passing"] == 6
    )


def test_day_without_station_rows_is_ranked_as_failing(tmp_path):
    """A stored empty day must not stop the ranking of every other day."""
    raw = _fixture(tmp_path)
    interim = tmp_path / "interim.csv"
    pems.extract_day(raw, {716744, 717816}, interim)
    good = pems.screen_day(pd.read_csv(interim, dtype=str), DAY, CFG["thresholds"])
    store = tmp_path / "quality_screening.csv"
    pems._upsert(store, good, ["station", "date"])
    empty = pems.empty_day(date(2022, 10, 18), CFG)
    pems._upsert(store, empty, ["station", "date"])
    screening = pd.read_csv(store)  # as `arm-pems rank` reads it
    periods, days = pems.rank_periods(screening, CFG)
    by_day = days.set_index("date")
    assert not by_day.loc[date(2022, 10, 18), "qualifies"]
    assert by_day.loc[date(2022, 10, 18), "suspicious_stations"] == ""
    assert by_day.loc[DAY, "station_types"] == "OR,ML"
    assert len(pems.rank_weeks(screening, CFG)) == 0  # two days, no 7-day window


def test_interrupted_extract_leaves_no_day_file(tmp_path):
    """Scan skips days whose file exists, so a partial file must not get that name."""
    raw = _fixture(tmp_path)
    raw.write_bytes(raw.read_bytes()[:-200])  # archive cut off mid-stream
    interim = tmp_path / "station_5min_2022_10_17.csv"
    with pytest.raises(EOFError):
        pems.extract_day(raw, {716744, 717816}, interim)
    assert not interim.exists()
