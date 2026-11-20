"""Synthetic checks for the driver-population study: pairing, differences, records.

No agency data: the PeMS extract here is a hand-written fixture.
"""

import copy
import math
from pathlib import Path

import pandas as pd
import pytest
import yaml

from adaptive_ramp_metering.simulation import ablation, drivers, micro

HEADER = (
    "timestamp,station,district,freeway,direction,lane_type,station_length,samples,"
    "percent_observed,total_flow,average_occupancy,average_speed,lane_values"
)


@pytest.fixture
def study(tmp_path):
    """Three driver cases on a 10-minute site scenario; `same` repeats `fixed`."""
    rows = [HEADER]
    for i in range(2):
        stamp = f"10/11/2022 05:{5 * i:02d}:00"
        rows.append(f"{stamp},716744,7,405,S,OR,,10,100,30,.05,,x")
        rows.append(f"{stamp},717816,7,405,S,ML,.5,50,100,500,.1,60,x")
    (tmp_path / "day.csv").write_text("\n".join(rows) + "\n")
    site = yaml.safe_load(Path("configs/i405.yaml").read_text())
    site["demand"].update(pems_file=str(tmp_path / "day.csv"), end="05:10")
    site["micro"]["duration_s"] = 600
    (tmp_path / "site.yaml").write_text(yaml.safe_dump(site))
    return {
        "site": str(tmp_path / "site.yaml"),
        "seeds": [1, 2, 3],
        "variants": ["x3"],
        "controllers": ["none", "alinea"],
        "decision": {"metric": "time_per_veh_min", "at_least": 0.01},
        "contrasts": [["skewed", "same"]],
        "cases": [
            {"id": "fixed"},
            {"id": "same", "spread": {"a": 0.0}},
            {
                "id": "skewed",
                "spread": {"v0": 0.1, "time_gap": 0.2, "a": 0.3},
                "shape": "lognormal",
            },
        ],
    }


def test_interval_is_the_paired_t_interval():
    # sd 1.29099 (n - 1) and t(0.975, 3) = 3.18245: half-width 3.18245 x 1.29099 / 2.
    assert drivers.interval([1.0, 2.0, 3.0, 4.0]) == pytest.approx(
        (2.5, 0.4457, 4.5543), abs=1e-4
    )
    assert drivers.interval([0.0, 0.0, 0.0]) == (0.0, 0.0, 0.0)
    assert math.isnan(drivers.interval([1.0])[1])  # one seed gives no interval


def test_study_pairs_the_cases_and_reports_their_differences(study, tmp_path):
    config_path = tmp_path / "drivers.yaml"
    config_path.write_text(yaml.safe_dump(study))
    output = drivers.run_study(study, config_path, tmp_path / "out", workers=1)
    rows = pd.read_csv(output / "evaluation.csv")
    assert len(rows) == 3 * 1 * 2 * 3  # cases x variants x controllers x seeds
    assert (
        rows["requested_ramp_veh"] + rows["requested_mainline_veh"]
        == rows["exited_veh"]
        + rows["internal_veh"]
        + rows["boundary_ramp_veh"]
        + rows["boundary_mainline_veh"]
    ).all()
    # Every case meets the same arrivals in a given seed.
    assert (rows.groupby("seed")["requested_ramp_veh"].nunique() == 1).all()
    # The fixed case is the site scenario itself.
    site = yaml.safe_load(Path(study["site"]).read_text())
    sim_cfg = ablation.build_config(site, ablation.historical_profile(site["demand"]))
    direct = micro.simulate(sim_cfg, "x3", "alinea", 2)["metrics"]
    cell = rows[
        (rows.case == "fixed") & (rows.controller == "alinea") & (rows.seed == 2)
    ].iloc[0]
    assert cell["delay_veh_s"] == pytest.approx(direct["delay_veh_s"])
    assert cell["exited_veh"] == direct["exited_veh"]

    diff = pd.read_csv(output / "differences.csv").set_index(
        ["case", "against", "controller", "metric"]
    )
    # `same` is `fixed`, so it differs by nothing and `skewed` differs from both alike.
    zero = diff.xs(("same", "fixed"), level=("case", "against"))
    assert (zero[["difference", "low", "high"]] == 0).all().all()
    assert not zero["differs"].any()
    a = diff.loc[("skewed", "fixed", "none", "time_per_veh_min")]
    b = diff.loc[("skewed", "same", "none", "time_per_veh_min")]
    assert a["difference"] == b["difference"] != 0
    # Recomputed here from the run records: mean over seeds of the paired difference.
    per_seed = rows[rows.controller == "none"].pivot(
        index="seed", columns="case", values="time_per_veh_min"
    )
    want = (per_seed["skewed"] - per_seed["fixed"]).mean()
    assert a["difference"] == pytest.approx(want)
    assert a["low"] < a["difference"] < a["high"] and a["seeds"] == 3
    assert a["differs"] == (
        (a["low"] > 0 or a["high"] < 0) and abs(a["difference"]) >= 0.01
    )

    effect = pd.read_csv(output / "controller_effect.csv").set_index(
        ["case", "controller", "metric"]
    )
    alinea = rows.pivot_table(
        index=["case", "seed"], columns="controller", values="time_per_veh_min"
    )
    want = (alinea["alinea"] - alinea["none"]).groupby("case").mean()
    for case in ("fixed", "skewed"):
        got = effect.loc[(case, "alinea", "time_per_veh_min")]
        assert got["effect"] == pytest.approx(want[case])
    assert effect.loc[("same", "alinea", "time_per_veh_min"), "change"] == 0

    people = pd.read_csv(output / "populations.csv").set_index(["case", "parameter"])
    assert people.loc[("skewed", "time_gap"), "mean"] == pytest.approx(1.0, abs=0.01)
    assert people.loc[("skewed", "time_gap"), "cv"] == pytest.approx(0.2, rel=0.05)
    assert people.loc[("skewed", "a"), "skewness"] > 0.3
    assert people.loc[("fixed", "time_gap"), "cv"] == 0
    for name in ("populations.png", "differences.png", "controller_effect.png"):
        assert (output / name).stat().st_size > 0


@pytest.mark.parametrize(
    "change",
    [
        {"variants": ["x99"]},
        {"cases": [{"id": "fixed"}, {"id": "fixed"}]},
        {"contrasts": [["skewed", "nobody"]]},
        {"decision": {"metric": "speed", "at_least": 1}},
        # The next four drop the contrasts, which name cases they do not have, so that
        # each fails for its own reason.
        {"contrasts": [], "cases": [{"id": "wide", "spread": {"a": 0.9}}]},
        {
            "contrasts": [],
            "cases": [{"id": "typo", "set": {"micro.vehicle.idm.time_gap": 2.0}}],
        },
        {"contrasts": [], "cases": [{"id": "lost", "set": {"micro.nowhere.value": 1}}]},
        # A typo where the engine checks nothing: only the case runner can catch it.
        {
            "contrasts": [],
            "cases": [{"id": "typo", "set": {"demand.congested_below": 15.0}}],
        },
        {"rule_contrasts": [["alinea", "nobody"]]},
    ],
)
def test_invalid_study_fails_before_running(study, tmp_path, change):
    broken = {**copy.deepcopy(study), **change}
    with pytest.raises(ValueError):
        drivers.run_study(broken, tmp_path / "drivers.yaml", tmp_path / "out", 1)
    assert not (tmp_path / "out").exists()


def test_a_study_without_a_metering_rule_reports_differences_only(study, tmp_path):
    study.update(controllers=["none"], seeds=[1, 2], cases=study["cases"][::2])
    study["contrasts"] = []
    output = drivers.run_study(study, tmp_path / "drivers.yaml", tmp_path / "out", 1)
    diff = pd.read_csv(output / "differences.csv")
    assert set(diff["controller"]) == {"none"} and set(diff["case"]) == {"skewed"}
    assert (output / "differences.png").stat().st_size > 0
    assert not (output / "controller_effect.png").exists()


def test_a_case_can_set_a_value_or_replace_the_demand_and_rules_are_paired(
    study, tmp_path
):
    fault = {"sensor_id": "mainline_merge", "from_s": 60, "until_s": 600}
    study.update(
        seeds=[1, 2],
        controllers=["none", "fixed", "alinea"],
        contrasts=[],
        rule_contrasts=[["alinea", "fixed"]],
        cases=[
            {"id": "base"},
            {"id": "long_gap", "set": {"micro.vehicle.idm.time_gap_s": 2.0}},
            {
                "id": "less_ramp",
                "variant": {"kind": "scale", "factor": 3.0, "ramp_factor": 0.5},
            },
            {
                "id": "fault",
                "variant": {"kind": "scale", "factor": 3.0, "detector_fault": fault},
            },
            # Three times the ramp demand and a fixed rate well under it: the rules differ.
            {
                "id": "slow_meter",
                "set": {"micro.control.fixed_rate_veh_per_s": 0.134},
                "variant": {"kind": "scale", "factor": 1.0, "ramp_factor": 3.0},
            },
        ],
    )
    output = drivers.run_study(study, tmp_path / "cases.yaml", tmp_path / "out", 1)
    rows = pd.read_csv(output / "evaluation.csv")
    assert len(rows) == 5 * 1 * 3 * 2  # cases x variants x controllers x seeds
    cell = rows.set_index(["case", "controller", "seed"]).sort_index()
    # `set` reaches the model: a longer time gap changes every run of that case.
    assert (
        cell.loc["long_gap", "delay_veh_s"] != cell.loc["base", "delay_veh_s"]
    ).all()
    # `variant` replaces the demand: half the ramp arrivals, the same variant id.
    assert (rows["variant"] == "x3").all()
    ramp = cell["requested_ramp_veh"]
    assert (ramp.loc["less_ramp"] < 0.7 * ramp.loc["base"]).all()
    # A detector fault means nothing without a meter and sends ALINEA to its fallback.
    same = ["requested_ramp_veh", "exited_veh", "delay_veh_s"]
    assert (cell.loc[("fault", "none"), same] == cell.loc[("base", "none"), same]).all(
        axis=None
    )
    assert (cell.loc[("fault", "alinea"), "fallback_count"] > 0).all()
    assert (cell.loc[("base", "alinea"), "fallback_count"] == 0).all()
    # One rule against another, in the same case and seed.
    rule = pd.read_csv(output / "rule_differences.csv").set_index(
        ["case", "rule", "against", "metric"]
    )
    got = rule.loc[("slow_meter", "alinea", "fixed", "time_per_veh_min")]
    time = cell["time_per_veh_min"]
    slow = time.loc[("slow_meter", "alinea")] - time.loc[("slow_meter", "fixed")]
    assert (
        abs(slow.mean()) > 0.01
    )  # the two rules do differ here, so the sign is tested
    assert got["difference"] == pytest.approx(slow.mean())
    assert got["low"] <= got["difference"] <= got["high"]
    assert len(rule) == 5 * len(drivers.METRICS)


def test_rule_ablation_file_changes_one_thing_per_case():
    study = yaml.safe_load(Path("configs/i405_ablation.yaml").read_text())
    site = yaml.safe_load(Path(study["site"]).read_text())
    cases = study["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)) and cases[0] == {"id": "baseline"}
    for case in cases[1:]:
        changes = len(case.get("set", {})) + ("variant" in case) + ("spread" in case)
        assert changes == 1, case["id"]
        changed = drivers._case_config(site, case)  # a mistyped path raises here
        assert changed != drivers._case_config(site, cases[0]), case["id"]
    rules = set(study["controllers"])
    assert all(set(pair) <= rules for pair in study["rule_contrasts"])
    assert study["decision"]["metric"] in drivers.METRICS


def test_analytic_gives_the_course_formulas_for_every_case(study):
    study["cases"] = [
        {"id": "base"},
        {"id": "long_gap", "set": {"micro.vehicle.idm.time_gap_s": 3.0}},
    ]
    table = drivers.analytic(study).set_index("case")
    assert list(table.index) == ["base", "long_gap"]
    # A longer time gap lowers the static capacity and nothing else in the demand.
    assert table.loc["long_gap", "capacity_veh_h"] < table.loc["base", "capacity_veh_h"]
    assert (
        table.loc["long_gap", "peak_demand_veh_h"]
        == table.loc["base", "peak_demand_veh_h"]
    )
