"""Synthetic checks for the I-405 demand ablation, its boundary and the Caltrans rule.

No agency data: the PeMS extract here is a hand-written fixture.
"""

import copy
import math
from pathlib import Path

import pandas as pd
import pytest
import yaml

from adaptive_ramp_metering.control.metering import decide
from adaptive_ramp_metering.simulation import ablation, micro

HEADER = (
    "timestamp,station,district,freeway,direction,lane_type,station_length,samples,"
    "percent_observed,total_flow,average_occupancy,average_speed,lane_values"
)


def extract(
    path: Path,
    minutes: int = 10,
    ramp_observed: int = 100,
    speed: int = 60,
    lane_observed: int = 1,
) -> Path:
    """Ramp 30 veh and five-lane mainline 500 veh per 5 minutes; lane 5 carries 80."""
    lanes = "|".join(
        f"10|{flow}|.1|{speed}|{lane_observed}" for flow in (120, 110, 100, 90, 80)
    )
    rows = [HEADER]
    for i in range(minutes // 5):
        stamp = f"10/11/2022 05:{5 * i:02d}:00"
        rows.append(f"{stamp},716744,7,405,S,OR,,10,{ramp_observed},30,.05,,x")
        rows.append(f"{stamp},717816,7,405,S,ML,.5,50,100,500,.1,{speed},{lanes}")
    path.write_text("\n".join(rows) + "\n")
    return path


@pytest.fixture
def cfg(tmp_path):
    cfg = yaml.safe_load(Path("configs/i405.yaml").read_text())
    cfg["demand"].update(pems_file=str(extract(tmp_path / "day.csv")), end="05:10")
    cfg["micro"].update(duration_s=600, seeds=[1])
    return cfg


def test_profile_balances_lanes_and_rejects_imputed_or_missing_data(cfg, tmp_path):
    profile = ablation.historical_profile(cfg["demand"])
    assert profile["ramp_veh_per_s"].tolist() == [0.1, 0.1]
    # Merge lane carries (500 + 30) / 5 per 5 min; its through traffic is that less ramp.
    assert profile["merge_lane_veh_per_s"].iloc[0] == pytest.approx(106 / 300)
    assert profile["mainline_veh_per_s"].iloc[0] == pytest.approx(76 / 300)
    assert profile["station_speed_mps"].iloc[0] == pytest.approx(26.8224)
    imputed = {**cfg["demand"], "pems_file": str(extract(tmp_path / "i.csv", 10, 0))}
    with pytest.raises(ValueError, match="imputed"):
        ablation.historical_profile(imputed)
    short = {**cfg["demand"], "pems_file": str(extract(tmp_path / "s.csv", 5))}
    with pytest.raises(ValueError, match="incomplete"):
        ablation.historical_profile(short)


def test_multiplier_shapes():
    m = ablation.multiplier
    assert m({"kind": "scale", "factor": 3.0}, 100, 1000) == 3.0
    for kind in ("log", "exp"):
        assert m({"kind": kind, "final": 2.0}, 0, 1000) == pytest.approx(1.0)
        assert m({"kind": kind, "final": 2.0}, 1000, 1000) == pytest.approx(2.0)
    # Logarithmic growth is ahead of exponential growth mid-window.
    assert m({"kind": "log", "final": 2.0}, 500, 1000) > m(
        {"kind": "exp", "final": 2.0}, 500, 1000
    )
    wave = {"kind": "sine", "amplitude": 0.5, "period_s": 600}
    assert m(wave, 150, 1000) == pytest.approx(1.5)
    assert m(wave, 450, 1000) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        m({"kind": "step"}, 0, 1)


def test_persistent_congestion_needs_a_run_of_congested_intervals():
    rule = {"speed_below_mps": 20.0, "occupancy_above": 0.26, "min_intervals": 3}

    def station(values):  # (speed, occupancy) per 30 s interval
        return [
            {
                "sensor_id": "mainline_upstream",
                "interval_start_s": 30 * i,
                "interval_end_s": 30 * i + 30,
                "mean_speed_mps": speed,
                "occupancy_fraction": occupancy,
            }
            for i, (speed, occupancy) in enumerate(values)
        ]

    slow, free, blocked, missing = (10, 0.2), (27, 0.05), (None, 0.9), (None, None)
    minutes = ablation.persistent_minutes
    # Two slow intervals are a disturbance; three in a row are persistent.
    assert (
        minutes(station([slow, slow, free, slow, slow]), "mainline_upstream", rule) == 0
    )
    assert minutes(station([free, slow, slow, slow]), "mainline_upstream", rule) == 1.5
    # No vehicle crossed but the loop is covered: congested by occupancy.
    assert minutes(station([slow, blocked, blocked]), "mainline_upstream", rule) == 1.5
    # A missing interval is not evidence of congestion and ends the run.
    assert minutes(station([slow, slow, missing, slow]), "mainline_upstream", rule) == 0
    assert minutes(station([slow] * 3), "mainline_merge", rule) == 0  # other sensor


def test_exit_boundary_discharges_the_equilibrium_flow_of_its_speed(cfg):
    sim_cfg = copy.deepcopy(cfg["micro"])
    speed = ablation.discharge_speed(0.35, sim_cfg)
    idm, v0 = sim_cfg["vehicle"]["idm"], sim_cfg["mainline"]["desired_speed_mps"]
    assert micro.equilibrium_flow(speed, v0, 5.0, idm) == pytest.approx(0.35, rel=1e-3)
    assert ablation.discharge_speed(5.0, sim_cfg) is None  # above lane capacity
    sim_cfg["duration_s"] = 1200
    scenario = {
        "id": "t",
        "name": "t",
        "description": "t",
        "periods": [
            {
                "until_s": 1200,
                "ramp_veh_per_s": 0.0,
                "mainline_veh_per_s": 0.7,
                "exit_speed_mps": speed,
            }
        ],
    }
    sim_cfg["scenarios"] = [scenario]
    micro.validate_config(sim_cfg)
    sim = micro.Simulation(sim_cfg, scenario, "none", 1)
    for _ in range(1200):
        sim.step()
    warm = sim.exited
    for _ in range(1200):
        sim.step()
    # Demand is twice the boundary flow; the queue discharges the boundary flow.
    assert (sim.exited - warm) / 600 == pytest.approx(0.35, rel=0.03)
    assert sim.nonpositive_gaps == 0


def test_caltrans_plan_is_stepwise_and_queue_override_steps_up(cfg):
    ctrl = cfg["micro"]["control"]
    obs = lambda occ: {"occupancy_fraction": occ, "interval_end_s": 30}  # noqa: E731

    def rate(occ, applied=0.3, queue=0.0):
        return decide(ctrl, "caltrans", 30, applied, obs(occ), 0, None, 30, 0.5, queue)

    assert rate(0.02)["value"] == pytest.approx(2 * 900 / 3600)
    assert rate(0.30)["value"] == pytest.approx(2 * 240 / 3600)
    # Level 7 of 0..14: 900 - 7 * (660 / 14) = 570 veh/h per lane.
    assert rate(0.126)["value"] == pytest.approx(2 * 570 / 3600)
    assert rate(0.126)["value"] == rate(0.134)["value"]  # same step
    override = rate(0.30, applied=0.2, queue=0.8)
    assert override["reason"] == "queue_override"
    assert override["value"] == pytest.approx(0.2 + 2 * 120 / 3600)
    assert rate(0.30, applied=0.49, queue=0.8)["value"] == ctrl["max_rate_veh_per_s"]
    cleared = rate(0.30, applied=0.45, queue=0.1)
    assert cleared["reason"] == "plan_rate"
    assert cleared["value"] == pytest.approx(2 * 240 / 3600)
    assert decide(ctrl, "caltrans", 0, None, None, 0, None, None, 0.5)["reason"] == (
        "startup_fixed_rate"
    )


def test_gap_counter_sees_overlaps_and_leaders_straddling_the_stop_line(cfg):
    sim_cfg = ablation.build_config(cfg, ablation.historical_profile(cfg["demand"]))
    scenario = sim_cfg["scenarios"][0]
    stop = sim_cfg["meter"]["stop_line_m"]
    # Two vehicles overlapping in one lane must be counted, not skipped.
    sim = micro.Simulation(sim_cfg, scenario, "none", 1)
    sim.vehicles = [
        micro.Vehicle(0, sim.F, 200.0, 20.0, 5.0, "mainline", sim.typical),
        micro.Vehicle(1, sim.F, 203.0, 0.0, 5.0, "mainline", sim.typical),
    ]
    sim._move()
    assert sim.nonpositive_gaps == 1
    # A queued vehicle must stop behind a leader whose body is still across the stop
    # line, not drive up to the line through it.
    sim = micro.Simulation(sim_cfg, scenario, "fixed", 1)
    leader = micro.Vehicle(
        0, 1, stop + 1.4, 0.0, 5.0, "ramp", sim.typical, released=True
    )
    follower = micro.Vehicle(1, 1, stop - 12.0, 5.0, 5.0, "ramp", sim.typical)
    sim.vehicles = [leader, follower]
    for _ in range(40):
        sim._move()
        leader.x, leader.v = stop + 1.4, 0.0  # hold the leader in place
    assert follower.x < leader.x - leader.length
    assert sim.nonpositive_gaps == 0


def test_small_ablation_conserves_vehicles_and_writes_records(cfg, tmp_path):
    cfg["ablation"]["variants"] = [
        {"id": "historical", "kind": "scale", "factor": 1.0},
        {"id": "x3", "kind": "scale", "factor": 3.0},
        {"id": "wave", "kind": "sine", "amplitude": 0.5, "period_s": 300},
    ]
    cfg["ablation"]["controllers"] = ["none", "caltrans"]
    config_path = tmp_path / "i405.yaml"
    config_path.write_text(yaml.safe_dump(cfg))
    output = ablation.run_ablation(cfg, config_path, tmp_path / "out", workers=1)
    rows = pd.read_csv(output / "evaluation.csv")
    assert len(rows) == 6
    assert (
        rows["requested_ramp_veh"] + rows["requested_mainline_veh"]
        == rows["exited_veh"]
        + rows["internal_veh"]
        + rows["boundary_ramp_veh"]
        + rows["boundary_mainline_veh"]
    ).all()
    assert (rows["nonpositive_gap_events"] == 0).all()
    # The same seed gives each controller the same realized demand.
    demand = rows.groupby("variant")["requested_ramp_veh"].nunique()
    assert (demand == 1).all()
    by = rows.set_index(["variant", "controller"])["requested_ramp_veh"]
    assert by["x3", "none"] > 2 * by["historical", "none"]
    assert rows["congested_min"].between(0, 10).all()  # a 10-minute window
    figures = "inputs baseline scale_sweep congestion fundamental shapes".split()
    for name in ("summary.csv", *(f"{figure}.png" for figure in figures)):
        assert (output / name).stat().st_size > 0
    assert math.isfinite(pd.read_csv(output / "summary.csv")["served_pct_mean"].min())


def test_spread_config_differs_from_the_site_config_only_where_intended():
    base = yaml.safe_load(Path("configs/i405.yaml").read_text())
    spread = yaml.safe_load(Path("configs/i405_spread.yaml").read_text())
    by_id = {v["id"]: v for v in base["ablation"]["variants"]}
    assert all(by_id[v["id"]] == v for v in spread["ablation"]["variants"])
    assert spread["micro"]["vehicle"].pop("spread")
    base["ablation"].pop("variants"), spread["ablation"].pop("variants")
    assert base == spread


def test_mix_variant_scales_each_origin_and_can_use_the_shoulder_lane(cfg, tmp_path):
    cfg["demand"]["shoulder_lane"] = 5
    profile = ablation.historical_profile(cfg["demand"])
    assert profile["shoulder_veh_per_s"].tolist() == pytest.approx([80 / 300] * 2)
    cfg["ablation"]["variants"] = [
        {"id": "both", "kind": "scale", "factor": 0.75},
        {
            "id": "cell",
            "kind": "scale",
            "factor": 1.0,
            "ramp_factor": 0.75,
            "mainline_factor": 0.75,
        },
        {
            "id": "split",
            "kind": "scale",
            "factor": 1.0,
            "ramp_factor": 1.25,
            "mainline_factor": 0.5,
        },
        {"id": "lane5", "kind": "scale", "factor": 1.0, "mainline": "shoulder_lane"},
    ]
    scenarios = ablation.build_config(cfg, profile)["scenarios"]
    by = {s["id"]: s["periods"] for s in scenarios}
    # Equal factors give exactly the demand of a plain scale variant, so its runs repeat.
    assert by["cell"] == by["both"]
    assert by["split"][0]["ramp_veh_per_s"] == pytest.approx(1.25 * 0.1)
    assert by["split"][0]["mainline_veh_per_s"] == pytest.approx(0.5 * 76 / 300)
    assert by["lane5"][0]["ramp_veh_per_s"] == pytest.approx(0.1)
    assert by["lane5"][0]["mainline_veh_per_s"] == pytest.approx(80 / 300)
    imputed = extract(tmp_path / "lane.csv", lane_observed=0)
    with pytest.raises(ValueError, match="shoulder lane"):
        ablation.historical_profile({**cfg["demand"], "pems_file": str(imputed)})
    cfg["ablation"]["variants"] = [
        {"id": "x", "kind": "scale", "factor": 1.0, "mainline": "lane_9"}
    ]
    with pytest.raises(ValueError, match="unknown mainline source"):
        ablation.build_config(cfg, profile)


def test_analytic_table_queues_what_the_exit_refuses_and_times_the_cap(cfg, tmp_path):
    # 30 mph at the station: the exit takes the observed 106 veh per 5 minutes and no more.
    cfg["demand"]["pems_file"] = str(extract(tmp_path / "slow.csv", speed=30))
    more = {"kind": "scale", "factor": 1.0, "mainline_factor": 1.5}
    cfg["ablation"]["variants"] = [
        {"id": "day", "kind": "scale", "factor": 1.0},
        {"id": "more", **more},
        {"id": "free", **more, "free_exit": True},
    ]
    profile = ablation.historical_profile(cfg["demand"])
    table = ablation.analytic_table(cfg, profile).set_index("variant")
    sim = cfg["micro"]  # the capacity is the peak of the configured equilibrium curve
    v0, speeds = sim["mainline"]["desired_speed_mps"], [x / 10 for x in range(1, 290)]
    peak = max(
        micro.equilibrium_flow(v, v0, sim["vehicle"]["length_m"], sim["vehicle"]["idm"])
        for v in speeds
        if v < v0
    )
    assert table["capacity_veh_h"].iloc[0] == pytest.approx(3600 * peak, rel=0.001)
    assert (table["intervals_over_capacity"] == 0).all()
    # The observed day asks for exactly what the exit takes: no queue, the cap holds no one.
    assert table.loc["day", "dd1_unserved_veh"] == pytest.approx(0)
    assert table.loc["day", "capping_active_min"] == 0
    assert table.loc["day", "capping_spill"] == ""
    # 114 through vehicles alone exceed the 106: 38 more wait every 5 minutes, the cap
    # admits no ramp vehicle and the 30 arriving fill the storage in about 4 minutes.
    storage = 72.5 * 3 / 8.84
    assert table.loc["more", "peak_demand_veh_h"] == pytest.approx(12 * 144)
    assert table.loc["more", "dd1_unserved_veh"] == pytest.approx(2 * 38)
    assert table.loc["more", "storage_veh"] == pytest.approx(storage)
    assert table.loc["more", "capping_active_min"] == pytest.approx(storage / 30 * 5)
    assert table.loc["more", "capping_spill"] == "05:04"
    # With a free exit the lane's capacity is the service rate and nothing waits.
    assert table.loc["free", "dd1_unserved_veh"] == 0
    assert table.loc["free", "capping_active_min"] == 0


def test_mix_report_pairs_rules_and_cells_by_seed(cfg, tmp_path):
    cfg["micro"]["seeds"] = [1, 2]
    control = cfg["micro"]["control"]  # a fixed rate below the doubled ramp demand
    control["fixed_rate_veh_per_s"] = control["min_rate_veh_per_s"]
    cfg["demand"]["shoulder_lane"] = 5
    cfg["ablation"].update(
        controllers=["none", "fixed"],
        decision={"congested_min": 5, "ramp_exits_pct": 2},
        contrasts=[["more", "day"]],
        variants=[
            {"id": "day", "kind": "scale", "factor": 1.0, "ramp_factor": 1.0},
            {
                "id": "more",
                "kind": "scale",
                "factor": 1.0,
                "ramp_factor": 2.0,
                "mainline": "shoulder_lane",
            },
        ],
    )
    config_path = tmp_path / "mix.yaml"
    config_path.write_text(yaml.safe_dump(cfg))
    output = ablation.run_ablation(cfg, config_path, tmp_path / "out", workers=1)
    exits = (
        pd.read_csv(output / "evaluation.csv")
        .set_index(["variant", "controller", "seed"])["exited_ramp_origin_veh"]
        .sort_index()
    )
    cells = pd.read_csv(output / "mix_cells.csv").set_index(["variant", "controller"])
    cells = cells.sort_index()
    effects = pd.read_csv(output / "mix_effects.csv").set_index(
        ["variant", "controller"]
    )
    contrasts = pd.read_csv(output / "mix_contrasts.csv").set_index(
        ["cell", "controller"]
    )
    assert cells.loc[("day", "none"), "exit"] == "limited"
    assert cells.loc[("more", "none"), "mainline"] == "shoulder lane"
    assert cells.loc[("more", "none"), "ramp_exits"] == exits["more", "none"].mean()
    # A rule's effect is rule minus no meter in the same seed, averaged over the seeds:
    # the slow meter lets fewer ramp vehicles out of the window.
    effect = effects.loc[("more", "fixed")]
    assert effect["ramp_exits_diff"] < 0
    assert effect["ramp_exits_diff"] == pytest.approx(
        (exits["more", "fixed"] - exits["more", "none"]).mean()
    )
    assert effect["ramp_exits_pct"] == pytest.approx(
        100 * effect["ramp_exits_diff"] / exits["more", "none"].mean()
    )
    assert effect["ramp_exits_low"] <= effect["ramp_exits_diff"]
    assert effect["ramp_exits_diff"] <= effect["ramp_exits_high"]
    assert effects["congested_min_counts"].dtype == bool
    # A contrast is cell minus cell in the same seed; twice the ramp demand, more exits.
    contrast = contrasts.loc[("more", "none")]
    assert contrast["minus"] == "day"
    assert contrast["ramp_exits_diff"] == pytest.approx(
        (exits["more", "none"] - exits["day", "none"]).mean()
    )
    assert contrast["ramp_exits_diff"] > 0
    assert (output / "analytic.csv").stat().st_size > 0
    assert not (output / "scale_sweep.png").exists()  # no multiplier to sweep
    cfg["ablation"]["contrasts"] = [["more", "nowhere"]]
    with pytest.raises(ValueError, match="contrast"):
        ablation.run_ablation(cfg, config_path, tmp_path / "bad", workers=1)


def test_mix_study_file_is_the_site_scenario_with_its_own_cells():
    site = yaml.safe_load(Path("configs/i405.yaml").read_text())
    assert ablation.load_config(Path("configs/i405.yaml")) == site
    study = ablation.load_config(Path("configs/i405_mix.yaml"))
    variants = study["ablation"]["variants"]
    ids = [v["id"] for v in variants]
    assert len(ids) == len(set(ids)) == 24 and ids[0] == "lim_r1_m1"
    assert all(set(pair) <= set(ids) for pair in study["ablation"]["contrasts"])
    assert all(v["kind"] == "scale" and v["factor"] == 1.0 for v in variants)
    assert all(v["id"].startswith("free") == bool(v.get("free_exit")) for v in variants)
    levels = {
        (
            bool(v.get("free_exit")),
            v["ramp_factor"],
            v.get("mainline", v.get("mainline_factor")),
        )
        for v in variants
    }
    assert levels == {
        (free, ramp, mainline)
        for free in (False, True)
        for ramp in (0.75, 1.0, 1.25)
        for mainline in (0.75, 1.0, 1.25, "shoulder_lane")
    }
    # Everything else is the site scenario.
    assert study.pop("site") == "configs/i405.yaml"
    assert study["micro"].pop("seeds") == list(range(1, 11)) and site["micro"].pop(
        "seeds"
    )
    assert study["demand"].pop("shoulder_lane") == 5
    for key in ("variants", "decision", "contrasts"):
        study["ablation"].pop(key), site["ablation"].pop(key, None)
    assert study == site
