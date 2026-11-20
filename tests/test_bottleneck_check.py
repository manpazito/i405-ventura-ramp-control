"""The PeMS bottleneck check on hand-written rows (no agency data)."""

import importlib.util

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("check", "scripts/bottleneck_check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def series(values) -> pd.Series:
    index = pd.date_range("2022-10-11 06:00", periods=len(values), freq="5min")
    return pd.Series(values, index=index, dtype=float)


def test_speed_and_flow_use_observed_lanes_only():
    # Lanes as (flow per 5 min, occupancy, mph, observed); lane 3 is imputed by PeMS.
    lanes = [(100, 0.1, 60, 1), (50, 0.2, 30, 1), (200, 0.3, 10, 0)]
    row = {i: [np.nan] for i in range(52)}
    for i, (flow, occupancy, mph, observed) in enumerate(lanes):
        row |= dict(
            zip(range(13 + 5 * i, 17 + 5 * i), ([flow], [occupancy], [mph], [observed]))
        )
    out = check.observed_lanes(pd.DataFrame(row)).iloc[0]
    assert out["lanes_observed"] == 2
    assert out["mph"] == pytest.approx((100 * 60 + 50 * 30) / 150)  # flow-weighted
    assert out["veh_h_lane"] == pytest.approx(12 * 150 / 2)
    assert out["occupancy"] == pytest.approx(0.15)


def test_onset_is_the_first_of_three_slow_intervals():
    assert (
        check.onset(series([60, 40, 60, 40, 40, 40, 60])).strftime("%H:%M") == "06:15"
    )
    assert check.onset(series([60, 40, 40, 60, 40, 40, 60])) is None


def test_bottleneck_needs_a_slow_upstream_and_a_much_faster_downstream():
    slow = series([30] * 7)
    hit, active = check.chen_active(slow, series([55] * 5 + [45] * 2))
    assert hit.sum() == 5 and active  # 5 of 7 intervals
    assert not check.chen_active(slow, series([55] * 4 + [45] * 3))[1]  # only 4 of 7
    assert not check.chen_active(slow, series([45] * 7))[
        1
    ]  # downstream as slow: a queue
    assert not check.chen_active(series([45] * 7), series([70] * 7))[
        1
    ]  # upstream moving


def test_shockwave_reproduces_the_lecture_examples():
    # Lecture 03: 55 mph at 20 veh/mi meets a stopped queue of 240 veh/mi.
    assert check.shockwave(55 * 20, 20, 0, 240) == pytest.approx(-5)
    # Lecture 03: 40 mph at 45 veh/mi stopped by a signal, jam density 211 veh/mi.
    assert check.shockwave(40 * 45, 45, 0, 211) == pytest.approx(-10.84, abs=0.01)
