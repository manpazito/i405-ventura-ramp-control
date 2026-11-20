"""Calibrate the car-following parameters that loop data can identify (D023).

Procedure, after FHWA Traffic Analysis Toolbox Vol. III (capacity first), Dervisoglu et
al. 2009 (fundamental diagram from PeMS 5-minute data) and Treiber and Kesting 2013
(calibrate only what the data cover):

1. Points: mainline station 717816, mean of its lanes, 5-minute intervals in which every
   lane is observed. Density is flow over the speed PeMS reports.
2. Free-flow speed `v0`: least squares through the origin on the points above 55 mph.
3. Capacity: the largest 5-minute flow per lane on the calibration days.
4. Time gap `T`: the value at which the capacity of the IDM equilibrium curve equals that
   capacity, for each acceleration exponent `delta`.
5. `delta`: the smallest value whose root-mean-square flow error on the calibration days
   is within 5 % of the best on the grid. It shapes the free-flow branch.

Not calibrated: `s0` and the vehicle length (the data hold no standstill), `a` and `b`
(no trajectories). Validation: the same errors on days not used above.

    uv run python scripts/calibrate_fd.py
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from adaptive_ramp_metering.simulation import micro

MPH = 0.44704  # m/s per mph
FREE_ABOVE_MPS = 55 * MPH  # Dervisoglu et al.: free-flow points are those above 55 mph
DELTAS = (4, 6, 8, 10, 12, 16, 20, 25, 30, 40, 60)
CALIBRATION = ("2022-10-10", "2022-10-11", "2022-10-12")
VALIDATION = ("2022-10-03", "2022-10-14", "2022-10-24", "2022-10-25", "2022-10-28")


def station_points(pems: Path, station: int, lanes: int, days) -> pd.DataFrame:
    """Flow (veh/s per lane), speed (m/s) and density (veh/m per lane) per interval."""
    frames = []
    for day in days:
        rows = pd.read_csv(
            pems / f"station_5min_{day.replace('-', '_')}.csv", dtype=str
        )
        rows = rows[rows["station"] == str(station)]
        lane = rows["lane_values"].str.split("|", expand=True)
        seen = np.stack([lane[5 * i + 4] == "1" for i in range(lanes)], axis=1).all(
            axis=1
        )
        rows = rows[seen]
        flow = pd.to_numeric(rows["total_flow"]) / 300 / lanes
        speed = pd.to_numeric(rows["average_speed"]) * MPH
        frames.append(pd.DataFrame({"day": day, "flow": flow, "speed": speed}))
    points = pd.concat(frames).dropna()
    points = points[(points["flow"] > 0) & (points["speed"] > 0)]
    return points.assign(density=points["flow"] / points["speed"])


def free_flow_speed(points: pd.DataFrame) -> float:
    """Slope of flow against density through the origin, free-flow points only."""
    free = points[points["speed"] > FREE_ABOVE_MPS]
    return float((free["flow"] * free["density"]).sum() / (free["density"] ** 2).sum())


def equilibrium(v0: float, idm: dict, length: float) -> tuple:
    """Speed, density and flow along the IDM equilibrium curve, fastest first."""
    speeds = np.linspace(0.999 * v0, 0.02, 4000)
    flows = micro.equilibrium_flow(speeds, v0, length, idm)
    return speeds, flows / speeds, flows


def headway_for_capacity(capacity: float, v0: float, idm: dict, length: float) -> float:
    """Time gap at which the equilibrium capacity equals `capacity` (veh/s)."""
    gaps = np.linspace(0.5, 3.0, 2501)
    peaks = [equilibrium(v0, {**idm, "time_gap_s": t}, length)[2].max() for t in gaps]
    if not peaks[-1] <= capacity <= peaks[0]:
        raise ValueError("capacity is outside what a time gap of 0.5 to 3 s can give")
    return float(np.interp(capacity, peaks[::-1], gaps[::-1]))


def flow_error(points: pd.DataFrame, v0: float, idm: dict, length: float) -> dict:
    """Root-mean-square error of flow at the observed densities, in veh/h per lane."""
    _, density, flow = equilibrium(v0, idm, length)
    error = 3600 * (np.interp(points["density"], density, flow) - points["flow"])
    free = (points["speed"] > FREE_ABOVE_MPS).to_numpy()

    def rms(e) -> float:
        return float(np.sqrt((e**2).mean())) if len(e) else float("nan")

    return {"all": rms(error), "free": rms(error[free]), "congested": rms(error[~free])}


def share_within_15pct(
    points: pd.DataFrame, v0: float, idm: dict, length: float
) -> dict:
    """Per cent of intervals whose flow the curve gives within 15 % (FHWA 2004, Table 4)."""
    _, density, flow = equilibrium(v0, idm, length)
    model = np.interp(points["density"], density, flow)
    close = np.abs(model - points["flow"]) <= 0.15 * points["flow"]
    free = points["speed"] > FREE_ABOVE_MPS
    return {
        "free": 100 * float(close[free].mean()),
        "congested": 100 * float(close[~free].mean()),
    }


def calibrate(
    points: pd.DataFrame, idm: dict, length: float
) -> tuple[dict, pd.DataFrame]:
    """`v0`, `T` and `delta` from the calibration points; the rest of `idm` is kept."""
    v0, capacity = free_flow_speed(points), float(points["flow"].max())
    rows = []
    for delta in DELTAS:
        trial = {**idm, "delta": delta}
        trial["time_gap_s"] = headway_for_capacity(capacity, v0, trial, length)
        speeds, _, flows = equilibrium(v0, trial, length)
        rows.append(
            {
                "delta": delta,
                "time_gap_s": trial["time_gap_s"],
                "critical_speed_mps": float(speeds[flows.argmax()]),
                **{
                    f"rmse_{k}": v
                    for k, v in flow_error(points, v0, trial, length).items()
                },
            }
        )
    table = pd.DataFrame(rows)
    chosen = table[table["rmse_all"] <= 1.05 * table["rmse_all"].min()].iloc[0]
    return {
        "desired_speed_mps": round(v0, 1),
        "time_gap_s": round(float(chosen["time_gap_s"]), 2),
        "delta": int(chosen["delta"]),
        "capacity_veh_per_h": round(3600 * capacity),
    }, table


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path, default=Path("configs/i405.yaml"))
    parser.add_argument("--pems", type=Path, default=Path("data/interim/pems"))
    parser.add_argument(
        "--out", type=Path, default=Path("data/processed/pems/fd_calibration.json")
    )
    args = parser.parse_args(argv)
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    sim, demand = cfg["micro"], cfg["demand"]
    idm, length = sim["vehicle"]["idm"], sim["vehicle"]["length_m"]
    station, lanes = demand["mainline_station"], demand["mainline_lanes"]
    cal = station_points(args.pems, station, lanes, CALIBRATION)
    val = station_points(args.pems, station, lanes, VALIDATION)
    found, table = calibrate(cal, idm, length)
    print("Candidates on the calibration days (flow error in veh/h per lane):")
    print(table.round(3).to_string(index=False))
    new = {**idm, "time_gap_s": found["time_gap_s"], "delta": found["delta"]}
    v0_new, v0_old = found["desired_speed_mps"], sim["mainline"]["desired_speed_mps"]
    report = {
        "calibrated": found,
        "calibration_days": CALIBRATION,
        "validation_days": VALIDATION,
    }
    rows = []
    for name, v0, params in (("configured", v0_old, idm), ("calibrated", v0_new, new)):
        speeds, _, flows = equilibrium(v0, params, length)
        row = {
            "parameters": name,
            "v0": v0,
            "T": params["time_gap_s"],
            "delta": params["delta"],
            "capacity": round(3600 * flows.max()),
            "critical_speed": round(float(speeds[flows.argmax()]), 1),
        }
        for label, points in (("cal", cal), ("val", val)):
            error = flow_error(points, v0, params, length)
            row |= {f"{label}_{k}": round(v) for k, v in error.items()}
            share = share_within_15pct(points, v0, params, length)
            row |= {f"{label}_within15_{k}": round(v) for k, v in share.items()}
        rows.append(row)
    report["errors_veh_per_h"] = rows
    daily = pd.concat([cal, val]).groupby("day")["flow"].max() * 3600
    report["daily_capacity_veh_per_h"] = {day: round(q) for day, q in daily.items()}
    print("\nFlow error at the observed densities, calibration and validation days:")
    print(pd.DataFrame(rows).to_string(index=False))
    print(
        "\nLargest 5-minute flow per lane by day:", report["daily_capacity_veh_per_h"]
    )
    print("Calibrated:", found)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(f"PeMS observations and an analytic curve, no simulation: {args.out}")


if __name__ == "__main__":
    main()
