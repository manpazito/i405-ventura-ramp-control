"""The fundamental-diagram calibration on points drawn from a known curve (no agency data)."""

import importlib.util

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("calibrate_fd", "scripts/calibrate_fd.py")
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)

IDM = {"a_mps2": 2.0, "b_mps2": 2.0, "time_gap_s": 1.5, "s0_m": 2.0, "delta": 4}


def on_curve(v0: float, idm: dict, n: int = 400) -> pd.DataFrame:
    """Points of the equilibrium curve, evenly spread over its densities."""
    speed, density, flow = fd.equilibrium(v0, idm, 5.0)
    pick = np.interp(
        np.linspace(density[0], density[-1], n), density, np.arange(len(density))
    )
    i = pick.round().astype(int)
    return pd.DataFrame(
        {"day": "d", "flow": flow[i], "speed": speed[i], "density": density[i]}
    )


def test_free_flow_speed_is_the_slope_through_the_free_points():
    density = np.array([0.005, 0.01, 0.02, 0.08])
    speed = np.array([30.0, 30.0, 30.0, 5.0])  # the last point is congested and ignored
    points = pd.DataFrame({"flow": density * speed, "speed": speed, "density": density})
    assert fd.free_flow_speed(points) == pytest.approx(30.0)


def test_headway_reproduces_the_capacity_it_was_asked_for():
    capacity = fd.equilibrium(30.0, IDM, 5.0)[2].max()
    assert fd.headway_for_capacity(capacity, 30.0, IDM, 5.0) == pytest.approx(
        1.5, abs=0.002
    )
    with pytest.raises(ValueError, match="capacity"):
        fd.headway_for_capacity(2.0, 30.0, IDM, 5.0)  # 7,200 veh/h per lane


def test_flow_error_is_zero_on_the_curve_and_grows_off_it():
    points = on_curve(30.0, IDM)
    assert fd.flow_error(points, 30.0, IDM, 5.0)["all"] == pytest.approx(0, abs=1.0)
    off = fd.flow_error(points, 30.0, {**IDM, "time_gap_s": 1.0}, 5.0)
    assert off["all"] > 100 and off["congested"] > off["free"]


@pytest.mark.parametrize("delta", [4, 40])
def test_calibration_matches_capacity_and_follows_the_shape_of_the_free_branch(delta):
    truth = {**IDM, "delta": delta}
    points = on_curve(30.0, truth)
    found, table = fd.calibrate(points, {**IDM, "time_gap_s": 1.0, "delta": 4}, 5.0)
    assert found["capacity_veh_per_h"] == round(3600 * points["flow"].max())
    calibrated = {**IDM, "time_gap_s": found["time_gap_s"], "delta": found["delta"]}
    capacity = fd.equilibrium(found["desired_speed_mps"], calibrated, 5.0)[2].max()
    assert 3600 * capacity == pytest.approx(found["capacity_veh_per_h"], rel=0.01)
    # A flat free branch asks for a large exponent, a rounded one for a small exponent.
    assert (found["delta"] >= 16) == (delta == 40)
    assert list(table["delta"]) == list(fd.DELTAS)
    best = table["rmse_all"].min()
    chosen = table[table["delta"] == found["delta"]].iloc[0]
    assert chosen["rmse_all"] <= 1.05 * best
    assert (table[table["delta"] < found["delta"]]["rmse_all"] > 1.05 * best).all()


def test_share_within_15_per_cent_counts_each_branch():
    points = on_curve(30.0, IDM)
    assert fd.share_within_15pct(points, 30.0, IDM, 5.0) == {
        "free": 100.0,
        "congested": 100.0,
    }
    off = fd.share_within_15pct(points, 30.0, {**IDM, "time_gap_s": 1.0}, 5.0)
    assert (
        off["congested"] < 50 < off["free"]
    )  # a shorter gap mostly moves the congested branch
