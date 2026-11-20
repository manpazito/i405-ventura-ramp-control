"""Synthetic analytical, accounting and interface checks for the microscopic demo."""

import copy
import csv
import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from adaptive_ramp_metering.control.metering import decide
from adaptive_ramp_metering.simulation import micro
from adaptive_ramp_metering.simulation.micro import (
    CONTROLLERS,
    ballistic_step,
    build_lanes,
    export_runs,
    idm_acceleration,
    simulate,
    validate_config,
)


@pytest.fixture
def cfg():
    return yaml.safe_load(Path("configs/micro.yaml").read_text())


def constant(cfg, ramp, main, duration=300):
    cfg["duration_s"] = duration
    cfg["seeds"] = [1]
    cfg["scenarios"] = [
        {
            "id": "test",
            "name": "Test",
            "description": "Synthetic test",
            "periods": [
                {
                    "until_s": duration,
                    "ramp_veh_per_s": ramp,
                    "mainline_veh_per_s": main,
                }
            ],
        }
    ]
    return cfg


def test_idm_equilibrium_gap_matches_closed_form(cfg):
    p = cfg["vehicle"]["idm"]
    v, v0 = 10.0, 20.0
    s_eq = (p["s0_m"] + v * p["time_gap_s"]) / math.sqrt(1 - (v / v0) ** p["delta"])
    assert idm_acceleration(v, v0, s_eq, 0.0, p) == pytest.approx(0.0, abs=1e-12)
    assert idm_acceleration(0.0, v0, math.inf, 0.0, p) == pytest.approx(p["a_mps2"])
    assert idm_acceleration(v0, v0, math.inf, 0.0, p) == pytest.approx(0.0)


def test_ballistic_step_stops_exactly_at_zero_speed():
    x, v = ballistic_step(
        np.array([0.0, 0.0]), np.array([1.0, 10.0]), np.array([-4.0, -4.0]), 0.5
    )
    assert v.tolist() == [0.0, 8.0]
    assert x.tolist() == pytest.approx([1 / 8, 4.5])


def test_lane_topology_follows_three_two_one(cfg):
    lanes, ends = build_lanes(cfg)
    assert ends == [120, 390, 600]
    assert [(ln["id"], ln["end"], ln["target"]) for ln in lanes] == [
        ("ramp_0", 600, 3),
        ("ramp_1", 390, 0),
        ("ramp_2", 120, 1),
        ("freeway_0", 900, None),
    ]


def test_zero_demand_stays_empty(cfg):
    result = simulate(constant(cfg, 0.0, 0.0), "test", "alinea", 1)
    m = result["metrics"]
    assert m["requested_ramp_veh"] == m["exited_veh"] == 0
    assert m["total_time_veh_s"] == 0
    assert all(
        o["count"] == 0 and o["occupancy_fraction"] == 0 for o in result["observations"]
    )


@pytest.mark.parametrize("controller", CONTROLLERS)
def test_conservation_gaps_and_paired_demand(cfg, controller):
    result = simulate(constant(cfg, 0.3, 0.4), "test", controller, 7)
    m = result["metrics"]
    assert m["requested_ramp_veh"] + m["requested_mainline_veh"] == (
        m["exited_veh"]
        + m["internal_veh"]
        + m["boundary_ramp_veh"]
        + m["boundary_mainline_veh"]
    )
    assert m["nonpositive_gap_events"] == 0 and m["min_gap_m"] > 0
    # The same seed yields the same realized demand for every controller.
    assert (m["requested_ramp_veh"], m["requested_mainline_veh"]) == (
        simulate(constant(copy.deepcopy(cfg), 0.3, 0.4), "test", "none", 7)["metrics"][
            "requested_ramp_veh"
        ],
        simulate(constant(copy.deepcopy(cfg), 0.3, 0.4), "test", "none", 7)["metrics"][
            "requested_mainline_veh"
        ],
    )


def test_meter_is_a_service_ceiling_and_ddl_reference_tracks_queue(cfg):
    cfg["control"]["fixed_rate_veh_per_s"] = 0.1
    result = simulate(constant(cfg, 0.5, 0.0, duration=600), "test", "fixed", 3)
    m = result["metrics"]
    assert m["meter_releases"] <= 0.1 * 600 + 1
    assert m["exited_ramp_origin_veh"] <= m["meter_releases"]
    assert m["ramp_queue_max_veh"] > 40
    # Vertical D/D/1 queue and the spatial ramp queue agree to within the ramp travel time.
    assert m["ddl_queue_mae_veh"] < 15


def test_unmetered_run_has_no_commands_and_metered_run_logs_causal_trace(cfg):
    constant(cfg, 0.2, 0.3)
    assert simulate(cfg, "test", "none", 1)["commands"] == []
    result = simulate(cfg, "test", "alinea", 1)
    for c in result["commands"]:
        assert c["apply_time_s"] > c["issue_time_s"]
        assert c["min_value"] <= c["value"] <= c["max_value"]
        assert (
            c["observation_end_s"] is None
            or c["observation_end_s"] <= c["issue_time_s"]
        )
    assert result["commands"][0]["reason"] == "startup_fixed_rate"
    assert any(c["reason"] == "alinea" for c in result["commands"])


def test_detector_fault_triggers_hold_then_fallback(cfg):
    constant(cfg, 0.2, 0.3, duration=600)
    cfg["scenarios"][0]["detector_fault"] = {
        "sensor_id": "mainline_merge",
        "from_s": 120,
        "until_s": 420,
    }
    result = simulate(cfg, "test", "alinea", 1)
    missing = [o for o in result["observations"] if o["quality_flag"] == "missing"]
    assert missing and all(
        o["occupancy_fraction"] is None and o["count"] is None for o in missing
    )
    reasons = [
        c["reason"] for c in result["commands"] if 150 <= c["issue_time_s"] <= 420
    ]
    assert reasons[:2] == ["hold_last_valid_command", "hold_last_valid_command"]
    assert all(r == "fixed_rate_fallback" for r in reasons[2:])


def test_decide_bounds_and_queue_control():
    ctrl = {
        "interval_s": 30,
        "min_rate_veh_per_s": 0.1,
        "max_rate_veh_per_s": 0.5,
        "fixed_rate_veh_per_s": 0.2,
        "alinea": {"gain_veh_per_s_per_occupancy": 1.0, "target_occupancy": 0.15},
        "queue_target_veh": 40,
        "fault_hold_s": 60,
    }
    obs = {"occupancy_fraction": 0.05, "interval_end_s": 30}
    assert decide(ctrl, "alinea", 30, 0.3, obs, 0, 0.1, 30, 0.5)[
        "value"
    ] == pytest.approx(0.4)
    assert (
        decide(
            ctrl, "alinea", 30, 0.3, {**obs, "occupancy_fraction": 0.9}, 0, 0.1, 30, 0.5
        )["value"]
        == 0.1
    )
    relief = decide(
        ctrl, "alinea", 30, 0.1, {**obs, "occupancy_fraction": 0.5}, 70, 0.2, 30, 0.5
    )
    assert relief["reason"] == "queue_control" and relief["value"] == pytest.approx(0.5)
    assert decide(ctrl, "fixed", 0, None, None, 0, None, None, 0.5)["value"] == 0.2


def test_half_step_changes_results_only_moderately(cfg):
    constant(cfg, 0.2, 0.35, duration=600)
    coarse = simulate(cfg, "test", "fixed", 2)["metrics"]
    fine_cfg = copy.deepcopy(cfg)
    fine_cfg["step_s"] = 0.25
    fine = simulate(fine_cfg, "test", "fixed", 2)["metrics"]
    assert fine["requested_ramp_veh"] > 0
    assert fine["exited_veh"] == pytest.approx(coarse["exited_veh"], rel=0.15)
    assert fine["nonpositive_gap_events"] == 0


@pytest.mark.parametrize(
    "path,value",
    [
        (("step_s",), 2),
        (("vehicle", "idm", "a_mps2"), 0),
        (("ramp", "sections", 2, "lanes"), 2),
        (("meter", "stop_line_m"), 700),
        (("control", "fixed_rate_veh_per_s"), 0.9),
        (("control", "alinea", "target_occupancy"), 1.5),
        (("scenarios", 0, "periods", 0, "until_s"), 1799),
        (("scenarios", 2, "detector_fault", "sensor_id"), "nowhere"),
    ],
)
def test_invalid_config_fails_before_running(cfg, path, value):
    node = cfg
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValueError):
        validate_config(cfg)


def test_export_writes_records_and_figures(cfg, tmp_path):
    constant(cfg, 0.2, 0.3, duration=90)
    cfg["snapshot_interval_s"] = 10
    config_path = tmp_path / "micro.yaml"
    config_path.write_text(yaml.safe_dump(cfg))
    out = export_runs(cfg, config_path, tmp_path / "runs")
    with (out / "evaluation.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert {(r["scenario_id"], r["controller"]) for r in rows} == {
        ("test", c) for c in CONTROLLERS
    }
    with (out / "vehicle_states.csv").open() as stream:
        header = next(csv.reader(stream))
    assert header[3:] == [
        "time_s",
        "vehicle_id",
        "lane_id",
        "position_m",
        "speed_mps",
        "acceleration_mps2",
    ]
    assert (out / "test.png").exists() and (out / "commands.csv").exists()
    assert (out / "source" / "micro.py").read_bytes() == Path(
        micro.__file__
    ).read_bytes()


def test_slower_section_is_anticipated_and_braking_is_bounded(cfg):
    sim = micro.Simulation(
        constant(cfg, 0.4, 0.4), cfg["scenarios"][0], "none", 3, True
    )
    sections, b = cfg["ramp"]["sections"], cfg["vehicle"]["idm"]["b_mps2"]
    loop_start, v_loop = sections[0]["length_m"], sections[1]["desired_speed_mps"]
    assert sim.desired_speed(0, 0.0) == sections[0]["desired_speed_mps"]  # far upstream
    for x in (loop_start - 10, loop_start - 1):
        assert sim.desired_speed(0, x) == pytest.approx(
            math.sqrt(v_loop**2 + 2 * b * (loop_start - x))
        )
    assert sim.desired_speed(0, loop_start + 1) == v_loop
    states = sim.run()["trace"]["states"]
    assert min(s[5] for s in states) >= -micro.MAX_DECEL_MPS2


IDM = {"a_mps2": 2.0, "b_mps2": 3.0, "time_gap_s": 1.0, "s0_m": 4.0, "delta": 4}


def sample(spread, shape, n, seed=0):
    rng = np.random.default_rng(seed)
    return [micro.Driver.sample(IDM, spread, shape, rng) for _ in range(n)]


def moments(x):
    """Mean, standard deviation, skewness and kurtosis (3 for a normal)."""
    z = (x - x.mean()) / x.std()
    return x.mean(), x.std(), (z**3).mean(), (z**4).mean()


# Every shape must give the configured mean and coefficient of variation exactly, so
# that shapes differ only in symmetry and tails. Lowest and highest value are in units
# of the configured sd; skewness and kurtosis are the closed-form values of a normal
# truncated at 2 sd (kurtosis 2.366, bound 2 / 0.8796) and of a uniform (1.8, sqrt 3).
@pytest.mark.parametrize(
    "shape,low,high,skew,kurtosis",
    [
        ("normal", -2.2737, 2.2737, 0.0, 2.366),
        ("uniform", -1.7321, 1.7321, 0.0, 1.8),
        ("lognormal", None, None, None, None),  # right-skewed: checked below
    ],
)
def test_each_shape_has_the_configured_mean_and_spread(
    shape, low, high, skew, kurtosis
):
    # a and s0 stay fixed
    spread = {"v0": 0.05, "time_gap": 0.10, "b": 0.20, "b_safe": 0.10}
    drivers = sample(spread, shape, 20000)
    want = {
        "v0_factor": (1.0, 0.05),
        "time_gap_s": (1.0, 0.10),
        "b_mps2": (3.0, 0.60),
        "b_safe_factor": (1.0, 0.10),
    }
    for field, (mean, sd) in want.items():
        x = np.array([getattr(d, field) for d in drivers])
        got_mean, got_sd, got_skew, got_kurtosis = moments(x)
        assert got_mean == pytest.approx(mean, abs=0.03 * sd)
        assert got_sd == pytest.approx(sd, rel=0.03)
        assert x.min() > 0
        if shape == "lognormal":
            # Mean above median, longer upper tail; b (cv 0.2) is skewed the most.
            assert np.median(x) < got_mean and mean - x.min() < x.max() - mean
            assert got_skew > (0.3 if field == "b_mps2" else 0.07)
        else:
            assert x.min() == pytest.approx(mean + low * sd, abs=0.03 * sd)
            assert x.max() == pytest.approx(mean + high * sd, abs=0.03 * sd)
            assert got_skew == pytest.approx(skew, abs=0.06)
            assert got_kurtosis == pytest.approx(kurtosis, abs=0.1)
    assert {(d.a_mps2, d.s0_m, d.delta) for d in drivers} == {(2.0, 4.0, 4)}


def test_a_driver_sits_at_the_same_percentile_under_every_shape():
    spread = {"time_gap": 0.2, "a": 0.2}
    gaps = {
        shape: [d.time_gap_s for d in sample(spread, shape, 200, seed=4)]
        for shape in ("normal", "uniform", "lognormal")
    }
    order = np.argsort(gaps["normal"]).tolist()
    assert len(set(gaps["normal"])) == 200
    assert np.argsort(gaps["uniform"]).tolist() == order
    assert np.argsort(gaps["lognormal"]).tolist() == order
    assert gaps["normal"] != gaps["uniform"] != gaps["lognormal"] != gaps["normal"]
    # A shape may also be set per parameter; the others keep theirs.
    accel = {
        shape: [d.a_mps2 for d in sample(spread, shape, 200, seed=4)]
        for shape in ("normal", "lognormal")
    }
    mixed = sample(spread, {"a": "lognormal"}, 200, seed=4)
    assert [d.time_gap_s for d in mixed] == gaps["normal"]
    assert [d.a_mps2 for d in mixed] == accel["lognormal"] != accel["normal"]


def test_adding_spread_to_one_parameter_keeps_every_other_draw():
    def time_gaps(spread):
        return [d.time_gap_s for d in sample(spread, "normal", 50, seed=3)]

    alone = time_gaps({"time_gap": 0.1})
    assert len(set(alone)) > 40  # the drivers do differ
    assert time_gaps({"time_gap": 0.1, "v0": 0.05, "a": 0.1, "b": 0.2, "s0": 0.1}) == (
        alone
    )


def test_the_kth_driver_of_an_origin_depends_only_on_the_seed(cfg):
    cfg["vehicle"]["spread"] = {"v0": 0.05, "time_gap": 0.1, "b": 0.1}
    drivers = []
    # Another rule and other arrival times: the drivers must still come in one order.
    for controller, ramp in (("none", 0.3), ("alinea", 0.15)):
        constant(cfg, ramp, 0.3)
        validate_config(cfg)  # any subset of the IDM parameters may vary
        sim = micro.Simulation(cfg, cfg["scenarios"][0], controller, 5)
        seen = {}
        for _ in range(240):
            sim.step()
            seen.update({v.vid: v.driver for v in sim.vehicles if v.origin == "ramp"})
        drivers.append([seen[vid] for vid in sorted(seen)])
    n = min(map(len, drivers))
    assert n > 10 and len(set(drivers[0][:n])) == n  # the drivers do differ
    assert drivers[0][:n] == drivers[1][:n]


@pytest.mark.parametrize(
    "spread,shape",
    [
        ({"a": 0.6}, None),  # a normal that wide would reach negative values
        ({"b": -0.1}, None),
        ({"delta": 0.1}, None),
        ([0.1], None),
        ({"a": 0.2}, "triangular"),
        ({"a": 0.2}, {"delta": "uniform"}),
        ({"a": 0.6}, "uniform"),  # lowest value 1 - 0.6 sqrt(3) < 0
    ],
)
def test_invalid_spread_fails_before_running(cfg, spread, shape):
    cfg["vehicle"]["spread"] = spread
    if shape:
        cfg["vehicle"]["shape"] = shape
    with pytest.raises(ValueError, match="spread|shape"):
        validate_config(cfg)


def test_a_wide_spread_is_valid_when_the_shape_stays_positive(cfg):
    cfg["vehicle"]["spread"] = {"a": 0.6, "time_gap": 0.3}
    cfg["vehicle"]["shape"] = {"a": "lognormal"}
    validate_config(cfg)


def test_a_vehicle_accelerates_by_its_own_drivers_values(cfg):
    sim = micro.Simulation(constant(cfg, 0.0, 0.0), cfg["scenarios"][0], "none", 1)
    own = micro.Driver(
        a_mps2=1.5, b_mps2=2.5, time_gap_s=1.2, s0_m=3.0, delta=4, v0_factor=1.1
    )
    typical = micro.Driver(**cfg["vehicle"]["idm"])
    follower = micro.Vehicle(1, sim.F, 715.0, 10.0, 5.0, "mainline", own)
    sim.vehicles = [
        micro.Vehicle(0, sim.F, 750.0, 6.0, 5.0, "mainline", typical),
        follower,
    ]
    sim._move()
    # IDM by hand: 30 m behind the leader, closing at 4 m/s, desired speed 1.1 x 22 m/s.
    s_star = 3.0 + 10 * 1.2 + 10 * 4 / (2 * math.sqrt(1.5 * 2.5))
    assert follower.acc == pytest.approx(
        1.5 * (1 - (10 / 24.2) ** 4 - (s_star / 30) ** 2)
    )


def test_a_driver_reaches_a_slower_section_at_its_own_speed_and_braking(cfg):
    sim = micro.Simulation(constant(cfg, 0.0, 0.0), cfg["scenarios"][0], "none", 1)
    driver = micro.Driver(**{**cfg["vehicle"]["idm"], "b_mps2": 1.0}, v0_factor=1.1)
    # Entry section 12 m/s up to 120 m, then the 9 m/s loop; freeway 22 m/s.
    assert sim.desired_speed(0, 0.0, driver) == pytest.approx(13.2)
    assert sim.desired_speed(0, 110.0, driver) == pytest.approx(
        math.sqrt(9.9**2 + 2 * 1.0 * 10)
    )
    assert sim.desired_speed(0, 121.0, driver) == pytest.approx(9.9)
    assert sim.desired_speed(sim.F, 700.0, driver) == pytest.approx(24.2)


def test_a_driver_enters_only_into_its_own_safe_gap(cfg):
    idm = cfg["vehicle"]["idm"]
    # 35 m are free behind a 10 m/s vehicle; a driver needs s0 + 10 T = 12 m or 42 m.
    for time_gap, entered in ((1.0, 1), (4.0, 0)):
        sim = micro.Simulation(constant(cfg, 0.0, 0.0), cfg["scenarios"][0], "none", 1)
        x = sim.lanes[sim.F]["start"] + 40.0
        sim.vehicles = [
            micro.Vehicle(0, sim.F, x, 10.0, 5.0, "mainline", micro.Driver(**idm))
        ]
        sim.next_driver[1] = micro.Driver(**{**idm, "time_gap_s": time_gap})
        sim.waiting[1] = 1
        sim._entries()
        assert sim.entered[1] == entered


def test_a_merge_needs_a_gap_that_both_drivers_own_values_accept(cfg):
    idm = cfg["vehicle"]["idm"]
    typical, cautious = micro.Driver(**idm), micro.Driver(**{**idm, "time_gap_s": 2.0})
    # 12 m behind a vehicle at the same speed, IDM asks for -2.4 m/s2 at T = 1 s and
    # -12.7 m/s2 at T = 2 s; the safety limit is -4 m/s2. At 567 m the freeway vehicle
    # is the new leader, 12 m ahead; at 533 m it is the new follower, 12 m behind.
    for merger, other_x, other, lane_after in (
        (typical, 567.0, typical, "freeway_0"),
        (cautious, 567.0, typical, "ramp_0"),
        (typical, 533.0, typical, "freeway_0"),
        (typical, 533.0, cautious, "ramp_0"),
    ):
        sim = micro.Simulation(constant(cfg, 0.0, 0.0), cfg["scenarios"][0], "none", 1)
        merging = micro.Vehicle(0, 0, 550.0, 15.0, 5.0, "ramp", merger)
        sim.vehicles = [
            merging,
            micro.Vehicle(1, sim.F, other_x, 15.0, 5.0, "mainline", other),
        ]
        sim._lane_changes()
        assert sim.lanes[merging.lane]["id"] == lane_after


def test_a_driver_yields_to_a_merging_vehicle_by_its_own_values(cfg):
    idm = cfg["vehicle"]["idm"]
    # 30 m behind a ramp vehicle 3 m/s slower, following it takes -2.4 m/s2 at T = 1 s
    # (yield) and -6.6 m/s2 at T = 2 s (pass: beyond the -4 m/s2 limit).
    for time_gap, yields in ((1.0, True), (2.0, False)):
        sim = micro.Simulation(constant(cfg, 0.0, 0.0), cfg["scenarios"][0], "none", 1)
        driver = micro.Driver(**{**idm, "time_gap_s": time_gap})
        through = micro.Vehicle(0, sim.F, 520.0, 20.0, 5.0, "mainline", driver)
        merging = micro.Vehicle(1, 0, 555.0, 17.0, 5.0, "ramp", micro.Driver(**idm))
        sim.vehicles = [through, merging]
        sim._move()
        assert (through.leader is merging) == yields


def test_a_merge_is_judged_by_the_merging_drivers_own_safety_limit(cfg):
    idm = cfg["vehicle"]["idm"]
    typical = micro.Driver(**idm)
    careful = micro.Driver(**idm, b_safe_factor=0.5)  # accepts 2 m/s2, not 4
    # 12 m to a vehicle at the same speed costs 2.4 m/s2: the merging driver behind a
    # new leader at 567 m, or the new follower at 533 m behind the merging driver.
    for merger, other_x, other, lane_after in (
        (typical, 567.0, careful, "freeway_0"),
        (careful, 567.0, typical, "ramp_0"),
        (typical, 533.0, careful, "freeway_0"),
        (careful, 533.0, typical, "ramp_0"),
    ):
        sim = micro.Simulation(constant(cfg, 0.0, 0.0), cfg["scenarios"][0], "none", 1)
        merging = micro.Vehicle(0, 0, 550.0, 15.0, 5.0, "ramp", merger)
        sim.vehicles = [
            merging,
            micro.Vehicle(1, sim.F, other_x, 15.0, 5.0, "mainline", other),
        ]
        sim._lane_changes()
        assert sim.lanes[merging.lane]["id"] == lane_after


def test_a_lane_end_is_braked_for_at_the_drivers_own_safety_limit(cfg):
    idm = cfg["vehicle"]["idm"]
    # 60 m before the end of ramp_0 at 16 m/s. Stopping takes 32 m at 4 m/s2 and 64 m at
    # 2 m/s2; s0 (2 m) and two steps of travel (16 m) are added to either.
    for factor, brakes in ((1.0, False), (0.5, True)):
        sim = micro.Simulation(constant(cfg, 0.0, 0.0), cfg["scenarios"][0], "none", 1)
        driver = micro.Driver(**idm, b_safe_factor=factor)
        sim.vehicles = [micro.Vehicle(0, 0, 540.0, 16.0, 5.0, "ramp", driver)]
        sim._move()
        assert (sim.vehicles[0].acc < 0) == brakes


@pytest.mark.parametrize(
    "path",
    [
        "configs/i405.yaml",
        "configs/i405_spread.yaml",
        "configs/micro.yaml",
    ],
)
def test_alinea_set_value_is_the_critical_occupancy_of_the_configured_model(path):
    # Papageorgiou et al. (1991): the set value is the occupancy at which flow is at
    # capacity. Here that is the peak of the IDM equilibrium curve seen by the loop, so
    # this fails until the value is recomputed whenever T, v0, s0 or a length changes.
    cfg = yaml.safe_load(Path(path).read_text())
    sim = cfg.get("micro", cfg)
    v0, length = sim["mainline"]["desired_speed_mps"], sim["vehicle"]["length_m"]
    speeds = np.linspace(0.01, 0.999 * v0, 20000)
    flows = micro.equilibrium_flow(speeds, v0, length, sim["vehicle"]["idm"])
    peak = int(flows.argmax())
    loop = sim["detectors"].get("loop_length_m", 0.0)
    critical = flows[peak] * (length + loop) / speeds[peak]  # density x covered length
    assert sim["control"]["alinea"]["target_occupancy"] == pytest.approx(
        critical, abs=0.005
    )
    if "ablation" in cfg:  # D016's occupancy line is the same point of the same curve
        assert cfg["ablation"]["congestion"]["occupancy_above"] == pytest.approx(
            critical, abs=0.005
        )
