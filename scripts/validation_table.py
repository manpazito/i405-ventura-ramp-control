"""Simulated against observed, day by day (D023, step 2).

Reads a run folder of `uv run arm-study --config configs/i405_validation.yaml`, in which
every case is one observed weekday, and compares three quantities the model does not
take as given: the vehicles that get through the merge lane in the window, the ramp
vehicles among them, and the minutes the mainline station spends below the congestion
line. Acceptance follows the example of FHWA (2004, Table 4): within 15 %, and GEH below
5 for flows, with GEH = sqrt(2 (E - V)^2 / (E + V)) on hourly flows.

    uv run python scripts/validation_table.py results/validation/<timestamp>
"""

import math
import sys
from pathlib import Path

import pandas as pd
import yaml

from adaptive_ramp_metering.simulation import ablation, drivers


def geh(model: float, count: float) -> float:
    """GEH statistic of a modeled against a counted hourly flow."""
    return math.sqrt(2 * (model - count) ** 2 / (model + count))


def observed(demand: dict) -> dict:
    """What PeMS shows for one day's window, in the units of the run records."""
    profile = ablation.historical_profile(demand)
    slow = profile["station_speed_mps"] < demand["congested_below_mps"]
    return {
        "exited_veh": 300 * profile["merge_lane_veh_per_s"].sum(),
        "ramp_veh": 300 * profile["ramp_veh_per_s"].sum(),
        "congested_min": 5.0 * slow.sum(),
    }


def main(argv: list[str] | None = None) -> None:
    run = Path((argv or sys.argv[1:])[0])
    cfg = yaml.safe_load((run / "config.yaml").read_text())
    study, site = cfg["study"], cfg["site"]
    rows = pd.read_csv(run / "evaluation.csv")
    hours = site["micro"]["duration_s"] / 3600
    table = []
    for case in study["cases"]:
        field = observed(drivers._case_config(site, case)["demand"])
        runs = rows[rows["case"] == case["id"]]
        model = {
            "exited_veh": runs["exited_veh"].mean(),
            "ramp_veh": runs["exited_ramp_origin_veh"].mean(),
            "congested_min": runs["congested_min"].mean(),
        }
        row = {
            "day": case["id"].split()[0],
            "a_mps2": case.get("set", {}).get("micro.vehicle.idm.a_mps2"),
            "split": case.get("split", ""),
            "seeds": len(runs),
        }
        for key, counted in field.items():
            row |= {
                f"{key}_observed": counted,
                f"{key}_model": model[key],
                f"{key}_error_pct": 100 * (model[key] - counted) / counted,
            }
            if key != "congested_min":
                row[f"{key}_geh"] = geh(model[key] / hours, counted / hours)
        table.append(row)
    table = pd.DataFrame(table)
    table.to_csv(run / "validation.csv", index=False)
    errors = [c for c in table.columns if c.endswith("_error_pct")]
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(table.round(1).to_string(index=False))
        print("\nMean absolute error in per cent, by value of a and by split:")
        mean = table[errors].abs().groupby([table["a_mps2"], table["split"]]).mean()
        print(mean.round(1).to_string())
    print(
        f"Simulated (uncertain) against observed PeMS values: {run / 'validation.csv'}"
    )


if __name__ == "__main__":
    main()
