"""I-405 SB Ventura on-ramp: PeMS-driven demand and the demand ablation.

Builds one observed weekday of ramp and outer-lane demand from the PeMS Station
5-Minute extract, reshapes it per ablation variant, and runs every variant, controller
and seed on the microscopic engine (`simulation/micro.py`). Design record, sources and
limits: docs/i405_ablation.md. Run `uv run arm-ablation`.

A study file (`site:` plus its own seeds and variants) can scale ramp and mainline
demand separately; `configs/i405_mix.yaml` is the ramp/mainline mix study, recorded in
experiments/ramp_mainline_mix.md.
"""

import argparse
import copy
import hashlib
import json
import math
import os
import platform
import subprocess
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from adaptive_ramp_metering.simulation import micro
from adaptive_ramp_metering.simulation.micro import plt

MPH = 0.44704
# Controller identity: fixed colour and marker everywhere (validated categorical set).
STYLE = {
    "none": ("No meter", "#2a78d6", "o"),
    "fixed": ("Fixed rate (time of day)", "#eb6834", "s"),
    "caltrans": ("Caltrans local responsive", "#1baf7a", "^"),
    "alinea": ("ALINEA + queue control", "#eda100", "D"),
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
STATS = ("min", "max", "mean")
# Keys that give a variant its own ramp and mainline level (ramp/mainline mix study).
MIX_KEYS = {"ramp_factor", "mainline_factor", "mainline"}


def _seconds(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 3600 + int(minutes) * 60


def historical_profile(d: dict) -> pd.DataFrame:
    """Observed 5-minute station flows and speed, and the merge-lane demand, in SI.

    The engine models one freeway lane. Drivers balance lanes downstream of the merge,
    so that lane carries (mainline + ramp) / lanes; its through traffic is that share
    minus the ramp flow. Raises instead of filling: a missing or PeMS-imputed interval
    is not a measurement.
    """
    frame = pd.read_csv(d["pems_file"], dtype=str)
    stamp = pd.to_datetime(frame["timestamp"], format="%m/%d/%Y %H:%M:%S")
    frame["start_s"] = (
        stamp.dt.hour * 3600 + stamp.dt.minute * 60 - _seconds(d["start"])
    )
    span = _seconds(d["end"]) - _seconds(d["start"])
    frame = frame[(frame["start_s"] >= 0) & (frame["start_s"] < span)]

    def station(sid: int) -> pd.DataFrame:
        rows = frame[frame["station"] == str(sid)].sort_values("start_s")
        if rows["start_s"].tolist() != list(range(0, span, 300)):
            raise ValueError(
                f"station {sid}: incomplete 5-minute coverage of the window"
            )
        if not (pd.to_numeric(rows["percent_observed"]) == 100).all():
            raise ValueError(f"station {sid}: window has imputed intervals")
        return rows.reset_index(drop=True)

    ramp, main = station(d["ramp_station"]), station(d["mainline_station"])
    out = pd.DataFrame(
        {
            "start_s": ramp["start_s"],
            "ramp_veh_per_s": pd.to_numeric(ramp["total_flow"]) / 300,
            "station_veh_per_s": pd.to_numeric(main["total_flow"]) / 300,
            "station_speed_mps": pd.to_numeric(main["average_speed"]) * MPH,
        }
    )
    out["merge_lane_veh_per_s"] = (
        out["ramp_veh_per_s"] + out["station_veh_per_s"]
    ) / d["mainline_lanes"]
    out["mainline_veh_per_s"] = (
        out["merge_lane_veh_per_s"] - out["ramp_veh_per_s"]
    ).clip(lower=0)
    if "shoulder_lane" in d:  # the lane next to the ramp as observed: an upper bound
        lane = main["lane_values"].str.split("|", expand=True)
        at = 5 * (d["shoulder_lane"] - 1)  # samples, flow, occupancy, speed, observed
        if at + 4 >= lane.shape[1] or not (lane[at + 4] == "1").all():
            raise ValueError(
                "shoulder lane: missing or imputed intervals in the window"
            )
        out["shoulder_veh_per_s"] = pd.to_numeric(lane[at + 1]) / 300
    if out.isna().any(axis=None):
        raise ValueError("historical window contains missing values")
    return out


def multiplier(variant: dict, time_s: float, duration_s: float) -> float:
    """Demand multiplier at `time_s` into a window of `duration_s`."""
    kind, t = variant["kind"], time_s / duration_s
    if kind == "scale":
        return variant["factor"]
    if kind == "log":
        return 1 + (variant["final"] - 1) * math.log1p(9 * t) / math.log(10)
    if kind == "exp":
        return variant["final"] ** t
    if kind == "sine":
        return 1 + variant["amplitude"] * math.sin(
            2 * math.pi * time_s / variant["period_s"]
        )
    raise ValueError(f"unknown variant kind: {kind}")


def discharge_speed(flow: float, sim_cfg: dict) -> float | None:
    """Congested-branch speed at which the modeled lane discharges `flow` (veh/s).

    None when the flow is at or above the lane's IDM capacity (no restriction).
    """
    v0 = sim_cfg["mainline"]["desired_speed_mps"]
    speeds = np.linspace(0.01, 0.999 * v0, 2000)
    flows = micro.equilibrium_flow(
        speeds, v0, sim_cfg["vehicle"]["length_m"], sim_cfg["vehicle"]["idm"]
    )
    peak = int(flows.argmax())
    if flow >= flows[peak]:
        return None
    return float(np.interp(flow, flows[: peak + 1], speeds[: peak + 1]))


def build_config(cfg: dict, profile: pd.DataFrame) -> dict:
    """Micro config with one scenario per variant.

    Downstream boundary: in intervals PeMS shows as congested, the exit discharges the
    observed merge-lane flow (flow-matched; see the design record). It is exogenous,
    so it is computed from the historical flows and never rescaled. A variant may scale
    each origin on its own (`ramp_factor`, `mainline_factor`) and take its through
    traffic from the observed shoulder lane (`mainline: shoulder_lane`).
    """
    out = copy.deepcopy(cfg["micro"])
    duration, step = out["duration_s"], cfg["demand"]["resolution_s"]
    congested = profile["station_speed_mps"] < cfg["demand"]["congested_below_mps"]
    profile["exit_speed_mps"] = [
        discharge_speed(q, out) if jam else None
        for q, jam in zip(profile["merge_lane_veh_per_s"], congested)
    ]
    if duration != 300 * len(profile) or 300 % step:
        raise ValueError(
            "duration_s must match the demand window; resolution must divide 300"
        )
    out["scenarios"] = []
    for variant in cfg["ablation"]["variants"]:
        periods = []
        through = _through(variant)
        for start in range(0, duration, step):
            row = profile.iloc[start // 300]
            m = multiplier(variant, start + step / 2, duration)
            if m < 0:
                raise ValueError(f"{variant['id']}: negative demand multiplier")
            period = {
                "until_s": start + step,
                "ramp_veh_per_s": float(
                    row["ramp_veh_per_s"] * m * variant.get("ramp_factor", 1)
                ),
                "mainline_veh_per_s": float(
                    row[through] * m * variant.get("mainline_factor", 1)
                ),
            }
            if pd.notna(row["exit_speed_mps"]) and not variant.get("free_exit"):
                period["exit_speed_mps"] = float(row["exit_speed_mps"])
            periods.append(period)
        scenario = {
            "id": variant["id"],
            "name": variant["id"],
            "description": json.dumps(variant),
            "periods": periods,
        }
        if "detector_fault" in variant:  # a degraded-information case
            scenario["detector_fault"] = variant["detector_fault"]
        out["scenarios"].append(scenario)
    micro.validate_config(out)
    return out


def _through(variant: dict) -> str:
    """Profile column a variant takes its merge-lane through traffic from."""
    source = variant.get("mainline", "lane_balance")
    if source not in ("lane_balance", "shoulder_lane"):
        raise ValueError(f"{variant['id']}: unknown mainline source {source}")
    return "shoulder_veh_per_s" if source == "shoulder_lane" else "mainline_veh_per_s"


def analytic_table(cfg: dict, profile: pd.DataFrame) -> pd.DataFrame:
    """What the course's formulas say of each variant before any run (5-minute steps).

    Capacity is the peak of the IDM equilibrium flow (the static capacity). Service is
    the exit allowance where the boundary restricts and that capacity elsewhere, so a
    deterministic D/D/1 queue leaves `dd1_unserved_veh` at the end of the window. The
    capping strategy admits max(0, Q_c - Q_in) from the ramp while its queue is below
    the storage upstream of the stop line: `capping_active_min` is how long it holds
    vehicles back until that queue first fills the storage (`capping_spill`).
    """
    sim, duration = cfg["micro"], cfg["micro"]["duration_s"]
    v0 = sim["mainline"]["desired_speed_mps"]
    capacity = micro.equilibrium_flow(
        np.linspace(0.01, 0.999 * v0, 2000),
        v0,
        sim["vehicle"]["length_m"],
        sim["vehicle"]["idm"],
    ).max()
    storage = sim["meter"]["stop_line_m"] * sim["ramp"]["sections"][0]["lanes"] / 8.84
    allowance = profile["merge_lane_veh_per_s"].to_numpy()
    restricted = (allowance < capacity) & (
        profile["station_speed_mps"] < cfg["demand"]["congested_below_mps"]
    ).to_numpy()
    start_s = _seconds(cfg["demand"]["start"])
    rows = []
    for variant in cfg["ablation"]["variants"]:
        m = np.array(
            [multiplier(variant, s + 150, duration) for s in profile["start_s"]]
        )
        ramp = profile["ramp_veh_per_s"].to_numpy() * m * variant.get("ramp_factor", 1)
        main = profile[_through(variant)].to_numpy() * m
        main = main * variant.get("mainline_factor", 1)
        service = np.where(
            restricted & (not variant.get("free_exit")), allowance, capacity
        )
        unserved = held = active = 0.0
        spill = None
        for i, start in enumerate(profile["start_s"]):
            unserved = max(0.0, unserved + 300 * (ramp[i] + main[i] - service[i]))
            growth = ramp[i] - max(0.0, service[i] - main[i])  # arrivals minus the cap
            if abs(growth) < 1e-9:  # equal up to rounding: nothing held or drained
                growth = 0.0
            if spill is not None or (growth <= 0 and held == 0):
                continue
            seconds = 300.0  # of this interval with a queue held at the meter
            if growth > 0:
                seconds = min(seconds, (storage - held) / growth)
            elif growth < 0:
                seconds = min(seconds, held / -growth)
            held = max(0.0, held + growth * seconds)
            active += seconds
            if held >= storage - 1e-9:
                spill = start_s + start + seconds
        rows.append(
            {
                "variant": variant["id"],
                "capacity_veh_h": 3600 * capacity,
                "peak_demand_veh_h": 3600 * (ramp + main).max(),
                "intervals_over_capacity": int((ramp + main > capacity).sum()),
                "dd1_unserved_veh": unserved,
                "storage_veh": storage,
                "capping_active_min": active / 60,
                "capping_spill": ""
                if spill is None
                else f"{int(spill // 3600):02d}:{int(spill % 3600 // 60):02d}",
            }
        )
    return pd.DataFrame(rows)


def persistent_minutes(observations: list[dict], sensor: str, rule: dict) -> float:
    """Minutes a detector spends in persistent congestion.

    An interval is congested when its mean speed is below `speed_below_mps` or its
    occupancy is above `occupancy_above`. It counts only inside a run of at least
    `min_intervals` consecutive congested intervals; a missing interval ends a run.
    """
    seconds, streak = 0.0, []
    for o in [*(o for o in observations if o["sensor_id"] == sensor), None]:
        speed, occupancy = (
            (None, None)
            if o is None
            else (o["mean_speed_mps"], o["occupancy_fraction"])
        )
        if (speed is not None and speed < rule["speed_below_mps"]) or (
            occupancy is not None and occupancy > rule["occupancy_above"]
        ):
            streak.append(o["interval_end_s"] - o["interval_start_s"])
            continue
        if len(streak) >= rule["min_intervals"]:
            seconds += sum(streak)
        streak = []
    return seconds / 60


def _run(task: tuple) -> dict:
    cfg, scenario_id, controller, seed, trace, rule = task
    run = micro.simulate(cfg, scenario_id, controller, seed, trace)
    key = {"variant": scenario_id, "controller": controller, "seed": seed}
    congested = persistent_minutes(run["observations"], "mainline_upstream", rule)
    return {
        "row": {**key, **run["metrics"], "congested_min": congested},
        "queue": [(*key.values(), *q) for q in run["trace"]["queue"]] if trace else [],
        "observations": [
            {**key, **o}
            for o in run["observations"]
            if trace and o["sensor_id"].startswith("mainline")
        ],
    }


def run_ablation(
    cfg: dict, config_path: Path, output_root: Path, workers: int | None = None
) -> Path:
    profile = historical_profile(cfg["demand"])
    sim_cfg = build_config(cfg, profile)
    seeds, rule = sim_cfg["seeds"], cfg["ablation"]["congestion"]
    if not (rule["speed_below_mps"] > 0 and 0 < rule["occupancy_above"] < 1) or (
        rule["min_intervals"] < 1
    ):
        raise ValueError("ablation.congestion needs positive thresholds")
    ids = [v["id"] for v in cfg["ablation"]["variants"]]
    if (
        len(set(ids)) != len(ids)
        or any(not set(c) <= set(ids) for c in cfg["ablation"].get("contrasts", []))
        or (
            any(MIX_KEYS & v.keys() for v in cfg["ablation"]["variants"])
            and "decision" not in cfg["ablation"]
        )
    ):
        raise ValueError(
            "ablation: repeated variant id, a contrast naming an unknown variant, or "
            "a mix study without `decision`"
        )
    tasks = [
        (sim_cfg, v["id"], controller, seed, seed == seeds[0], rule)
        for v in cfg["ablation"]["variants"]
        for controller in cfg["ablation"]["controllers"]
        for seed in seeds
    ]
    now = datetime.now(UTC)
    output = output_root / now.strftime("%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True, exist_ok=False)
    if workers == 1:
        results = [_run(t) for t in tasks]
    else:
        with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
            results = list(pool.map(_run, tasks))
    pd.DataFrame([r["row"] for r in results]).to_csv(
        output / "evaluation.csv", index=False
    )
    pd.DataFrame(
        [q for r in results for q in r["queue"]],
        columns=[
            "variant",
            "controller",
            "seed",
            "time_s",
            "ramp_queue_veh",
            "queue_estimate_veh",
            "ddl_queue_veh",
            "rate_veh_per_s",
        ],
    ).to_csv(output / "queue_trace.csv", index=False)
    pd.DataFrame([o for r in results for o in r["observations"]]).to_csv(
        output / "mainline_observations.csv", index=False
    )
    profile.to_csv(output / "historical_profile.csv", index=False)
    analytic_table(cfg, profile).to_csv(output / "analytic.csv", index=False)
    (output / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    report(output)
    sources = {
        "config": config_path,
        "pems_extract": Path(cfg["demand"]["pems_file"]),
        "ablation.py": Path(__file__),
        "micro.py": Path(micro.__file__),
        "metering.py": Path(micro.__file__).parents[1] / "control" / "metering.py",
    }
    if "site" in cfg:  # a study file: record the site configuration it was built on
        sources["site_config"] = Path(cfg["site"])
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    (output / "run.json").write_text(
        json.dumps(
            {
                "schema_version": "i405-demand-ablation-v1",
                "origin": "simulated from observed PeMS demand; model calibrated in part",
                "created_utc": now.isoformat(),
                "config": cfg,
                "source_sha256": {
                    k: hashlib.sha256(p.read_bytes()).hexdigest()
                    for k, p in sources.items()
                },
                "git_revision": git.stdout.strip() if git.returncode == 0 else None,
                "python_version": platform.python_version(),
                "runs": len(tasks),
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def _axes(fig, axes, title: str) -> None:
    for ax in np.atleast_1d(axes).ravel():
        ax.grid(color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8)
    fig.suptitle(title, fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout()


def _clock(ax, cfg: dict) -> None:
    start, hours = _seconds(cfg["demand"]["start"]), cfg["micro"]["duration_s"] // 3600
    ax.set_xticks([60 * h for h in range(hours + 1)])
    ax.set_xticklabels([f"{start // 3600 + h}:00" for h in range(hours + 1)])
    ax.set_xlabel("time of day", fontsize=8, color=MUTED)


def report(output: Path) -> pd.DataFrame:
    """Summary table and figures from the CSV records of one run folder."""
    cfg = yaml.safe_load((output / "config.yaml").read_text())
    rows = pd.read_csv(output / "evaluation.csv")
    queue = pd.read_csv(output / "queue_trace.csv")
    profile = pd.read_csv(output / "historical_profile.csv")
    controllers = cfg["ablation"]["controllers"]
    requested = rows["requested_ramp_veh"] + rows["requested_mainline_veh"]
    rows["served_pct"] = 100 * rows["exited_veh"] / requested
    rows["time_per_veh_min"] = rows["total_time_veh_s"] / requested / 60
    rows["street_wait_veh_h"] = rows["boundary_ramp_wait_veh_s"] / 3600
    metrics = {
        "served_pct": "demand served in the window (%)",
        "boundary_ramp_max_veh": "peak queue held on Ventura Blvd (veh)",
        "time_per_veh_min": "time in system per vehicle (min)",
    }
    summary = rows.groupby(["variant", "controller"], sort=False)[
        [
            *metrics,
            "congested_min",
            "street_wait_veh_h",
            "ramp_queue_max_veh",
            "nonpositive_gap_events",
        ]
    ].agg(["mean", "min", "max"])
    summary.columns = ["_".join(c) for c in summary.columns]
    summary = summary.reset_index()
    summary.to_csv(output / "summary.csv", index=False)

    # Inputs: observed demand and the imposed downstream boundary.
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    t = profile["start_s"] / 60
    for col, label, color in (
        ("ramp_veh_per_s", "ramp (PeMS 716744)", "#eb6834"),
        ("mainline_veh_per_s", "merge-lane through traffic (derived)", "#2a78d6"),
        ("merge_lane_veh_per_s", "merge lane total = (mainline + ramp) / 5", MUTED),
    ):
        axes[0].step(
            t, profile[col] * 3600, where="post", lw=1.8, color=color, label=label
        )
    axes[0].set_ylabel("flow (veh/h)", fontsize=8, color=MUTED)
    axes[0].legend(fontsize=7, frameon=False)
    axes[1].step(
        t,
        profile["station_speed_mps"],
        where="post",
        lw=1.8,
        color=INK,
        label="observed station speed (PeMS 717816)",
    )
    axes[1].step(
        t,
        profile["exit_speed_mps"],
        where="post",
        lw=1.8,
        color="#1baf7a",
        label="imposed exit speed (flow-matched, congested intervals)",
    )
    axes[1].set_ylabel("speed (m/s)", fontsize=8, color=MUTED)
    axes[1].legend(fontsize=7, frameon=False)
    for ax in axes:
        _clock(ax, cfg)
    _axes(fig, axes, "Inputs: observed weekday demand and downstream boundary (PeMS)")
    fig.savefig(output / "inputs.png", dpi=200)
    plt.close(fig)

    # Historical demand: ramp queue and metering rate over time, first seed.
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), sharex=True)
    base = queue[queue["variant"] == cfg["ablation"]["variants"][0]["id"]]
    for name in controllers:
        label, color, _ = STYLE[name]
        q = base[base["controller"] == name]
        axes[0].plot(
            q["time_s"] / 60, q["ramp_queue_veh"], lw=1.6, color=color, label=label
        )
        if name != "none":
            window = round(300 / cfg["micro"]["snapshot_interval_s"])
            axes[1].plot(
                q["time_s"] / 60,
                (q["rate_veh_per_s"] * 3600).rolling(window, min_periods=1).mean(),
                lw=1.6,
                color=color,
                label=label,
            )
    stop, lanes = (
        cfg["micro"]["meter"]["stop_line_m"],
        cfg["micro"]["ramp"]["sections"][0]["lanes"],
    )
    storage = stop * lanes / 8.84  # 29 ft per stored vehicle (Caltrans design figure)
    axes[0].axhline(storage, color=MUTED, lw=1, ls="--")
    axes[0].annotate(
        f"storage upstream of the meter (~{storage:.0f} veh)",
        (2, storage),
        xytext=(0, 3),
        textcoords="offset points",
        fontsize=7,
        color=MUTED,
    )
    axes[0].set_ylabel("ramp queue incl. Ventura Blvd (veh)", fontsize=8, color=MUTED)
    axes[1].set_ylabel(
        "metering rate, all lanes, 5-min mean (veh/h)", fontsize=8, color=MUTED
    )
    axes[1].legend(fontsize=7, frameon=False)
    axes[0].legend(fontsize=7, frameon=False, loc="upper left", bbox_to_anchor=(0, 0.9))
    for ax in axes:
        _clock(ax, cfg)
    _axes(
        fig, axes, "Historical demand: ramp queue and metering rate (simulated, seed 1)"
    )
    fig.savefig(output / "baseline.png", dpi=200)
    plt.close(fig)

    # Scale sweeps: mean over seeds with the min-max band. Controllers nearly coincide,
    # so one panel per figure shows each one's paired difference from the unmetered run.
    scales = {
        v["id"]: v["factor"]
        for v in cfg["ablation"]["variants"]
        if v["kind"] == "scale" and not v.get("free_exit") and not MIX_KEYS & v.keys()
    }
    rule = cfg["ablation"]["congestion"]
    if scales:  # a mix study has no multiplier to sweep
        order = sorted(scales, key=scales.get)
        x = np.arange(len(order))
        factors = np.array([scales[v] for v in order])

        def sweep(ax, metric: str, floor: float | None = None) -> None:
            for name in controllers:
                text, color, marker = STYLE[name]
                d = (
                    summary[summary["controller"] == name]
                    .set_index("variant")
                    .loc[order]
                )
                lo, hi, mean = (d[f"{metric}_{k}"].clip(lower=floor) for k in STATS)
                ax.fill_between(x, lo, hi, color=color, alpha=0.15, lw=0)
                ax.plot(x, mean, lw=1.6, color=color, marker=marker, ms=5, label=text)

        def difference(ax, metric: str) -> None:
            paired = rows[rows["variant"].isin(scales)].pivot_table(
                index=["variant", "seed"], columns="controller", values=metric
            )
            for name in controllers:
                if name == "none" or "none" not in paired:
                    continue
                text, color, marker = STYLE[name]
                diff = (
                    (paired[name] - paired["none"]).groupby("variant").agg(list(STATS))
                )
                diff = diff.loc[order]
                ax.fill_between(
                    x, diff["min"], diff["max"], color=color, alpha=0.15, lw=0
                )
                ax.plot(
                    x,
                    diff["mean"],
                    lw=1.6,
                    color=color,
                    marker=marker,
                    ms=5,
                    label=text,
                )
            ax.axhline(0, color=MUTED, lw=1)

        def multiplier_axis(axes, labels) -> None:
            for ax, label in zip(axes, labels):
                ax.set_xticks(x)
                ax.set_xticklabels([f"{f:g}" for f in factors])
                ax.set_xlabel(
                    "demand multiplier (1 = observed day)", fontsize=8, color=MUTED
                )
                ax.set_ylabel(label, fontsize=8, color=MUTED)

        fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
        sweep(axes[0], "served_pct")
        # Bottleneck prediction: service is capped at the observed throughput, so the
        # served share of m times the observed demand is 1 / m.
        axes[0].plot(
            x,
            100 / np.maximum(factors, 1),
            lw=1.4,
            ls="--",
            color=INK,
            label="bottleneck prediction, 100 / multiplier",
        )
        sweep(axes[1], "boundary_ramp_max_veh", floor=1)
        axes[1].set_yscale("log")
        difference(axes[2], "time_per_veh_min")
        multiplier_axis(
            axes,
            (
                metrics["served_pct"],
                "peak queue held on Ventura Blvd (veh, log scale)",
                "time in system per vehicle minus no meter (min)",
            ),
        )
        axes[0].legend(fontsize=7, frameon=False)
        axes[2].legend(fontsize=7, frameon=False)
        _axes(fig, axes, "Demand scaling: mean of seeds, band = min to max (simulated)")
        fig.savefig(output / "scale_sweep.png", dpi=200)
        plt.close(fig)

        # Persistent congestion at the mainline station upstream of the gore, by the
        # definition in `ablation.congestion`, with the same count for the PeMS station.
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
        sweep(axes[0], "congested_min")
        if 1.0 in scales.values():
            observed = 5 * int(
                (profile["station_speed_mps"] < rule["speed_below_mps"]).sum()
            )
            at = float(x[factors == 1.0][0])
            axes[0].plot(at, observed, marker="X", ms=8, color=INK, ls="none")
            axes[0].annotate(
                f"PeMS station: {observed} min",
                (at, observed),
                xytext=(-6, 5),
                textcoords="offset points",
                ha="right",
                fontsize=7,
                color=INK,
            )
        difference(axes[1], "congested_min")
        multiplier_axis(
            axes,
            (
                "persistent congestion at the mainline station (min)",
                "persistent congestion minus no meter (min)",
            ),
        )
        axes[0].legend(fontsize=7, frameon=False, loc="lower right")
        _axes(
            fig,
            axes,
            f"Persistent congestion: below {rule['speed_below_mps']:g} m/s or above "
            f"{100 * rule['occupancy_above']:g} % occupancy for at least "
            f"{rule['min_intervals']} intervals of {cfg['micro']['detectors']['interval_s']} s"
            " (simulated)",
        )
        fig.savefig(output / "congestion.png", dpi=200)
        plt.close(fig)

    # Fundamental diagrams per lane: the model's analytic IDM equilibrium, its simulated
    # loops (first variant, first controller, first seed, 5-minute totals) and the PeMS
    # station. PeMS density is flow / reported speed. A simulated loop knows the vehicle
    # length, so its density is occupancy / (vehicle + loop length) and its speed is
    # flow / density, the single-loop estimate.
    sim = cfg["micro"]
    v0 = sim["mainline"]["desired_speed_mps"]
    v_eq = np.linspace(0.05, 0.999 * v0, 800)
    q_eq = micro.equilibrium_flow(
        v_eq, v0, sim["vehicle"]["length_m"], sim["vehicle"]["idm"]
    )
    peak = int(q_eq.argmax())
    station_flow = profile["station_veh_per_s"] / cfg["demand"]["mainline_lanes"]
    series = [
        (
            "PeMS station, mean of 5 lanes (observed)",
            INK,
            "o",
            station_flow,
            profile["station_speed_mps"],
        )
    ]
    obs = pd.read_csv(output / "mainline_observations.csv")
    obs = obs[
        (obs["variant"] == cfg["ablation"]["variants"][0]["id"])
        & (obs["controller"] == controllers[0])
    ]
    for sensor, label, color, marker in (
        ("mainline_upstream", "simulated station upstream of the gore", "#2a78d6", "s"),
        ("mainline_merge", "simulated merge-area detector", "#eb6834", "^"),
    ):
        g = obs[obs["sensor_id"] == sensor]
        seconds = g["interval_end_s"] - g["interval_start_s"]
        five = (
            g.assign(seconds=seconds, occupied=g["occupancy_fraction"] * seconds)
            .groupby(g["interval_start_s"] // 300)[["count", "seconds", "occupied"]]
            .sum()
        )
        five = five[(five["count"] > 0) & (five["occupied"] > 0)]
        flow = five["count"] / five["seconds"]
        density = (
            five["occupied"]
            / five["seconds"]
            / (sim["vehicle"]["length_m"] + sim["detectors"].get("loop_length_m", 0))
        )
        series.append((label, color, marker, flow, flow / density))
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    panels = (
        (lambda q, v: (1000 * q / v, 3600 * q), "density (veh/km)", "flow (veh/h)"),
        (lambda q, v: (1000 * q / v, v), "density (veh/km)", "speed (m/s)"),
        (lambda q, v: (3600 * q, v), "flow (veh/h)", "speed (m/s)"),
    )
    for ax, (xy, xlabel, ylabel) in zip(axes, panels):
        ax.plot(
            *xy(q_eq, v_eq), lw=1.6, color=MUTED, label="IDM equilibrium (analytic)"
        )
        for label, color, marker, flow, speed in series:
            ax.plot(
                *xy(flow, speed),
                ls="none",
                marker=marker,
                ms=4.5,
                color=color,
                markeredgecolor="white",
                markeredgewidth=0.4,
                label=label,
            )
        ax.set_xlabel(f"{xlabel}, per lane", fontsize=8, color=MUTED)
        ax.set_ylabel(
            f"{ylabel}, per lane" if "flow" in ylabel else ylabel,
            fontsize=8,
            color=MUTED,
        )
    axes[0].annotate(
        f"model capacity {3600 * q_eq[peak]:,.0f} veh/h\nat {v_eq[peak]:.1f} m/s",
        (1000 * q_eq[peak] / v_eq[peak], 3600 * q_eq[peak]),
        xytext=(10, -2),
        textcoords="offset points",
        fontsize=7,
        color=MUTED,
    )
    for ax in axes[1:]:
        ax.axhline(rule["speed_below_mps"], color=MUTED, lw=1, ls="--")
    axes[1].annotate(
        f"congested below {rule['speed_below_mps']:g} m/s",
        (axes[1].get_xlim()[1], rule["speed_below_mps"]),
        xytext=(-2, 3),
        textcoords="offset points",
        ha="right",
        fontsize=7,
        color=MUTED,
    )
    axes[1].legend(fontsize=7, frameon=False, loc="upper right")
    _axes(
        fig,
        axes,
        "Fundamental diagrams: model equilibrium, simulated detectors and PeMS "
        "(5-minute intervals, observed-day demand)",
    )
    fig.savefig(output / "fundamental.png", dpi=200)
    plt.close(fig)

    # Time-varying shapes: multiplier and ramp queue, first seed.
    shapes = [v for v in cfg["ablation"]["variants"] if v["kind"] != "scale"]
    if shapes:
        duration = cfg["micro"]["duration_s"]
        fig, axes = plt.subplots(
            2,
            len(shapes),
            figsize=(2.9 * len(shapes), 4.6),
            sharex=True,
            sharey="row",
            squeeze=False,
            gridspec_kw={"height_ratios": [1, 2]},
        )
        grid = np.linspace(0, duration, 600)
        for c, variant in enumerate(shapes):
            axes[0, c].plot(
                grid / 60,
                [multiplier(variant, x, duration) for x in grid],
                lw=1.6,
                color=INK,
            )
            axes[0, c].set_title(variant["id"], fontsize=9, color=INK)
            for name in controllers:
                label, color, _ = STYLE[name]
                q = queue[
                    (queue["variant"] == variant["id"]) & (queue["controller"] == name)
                ]
                axes[1, c].plot(
                    q["time_s"] / 60,
                    q["ramp_queue_veh"],
                    lw=1.4,
                    color=color,
                    label=label,
                )
            _clock(axes[1, c], cfg)
        axes[0, 0].set_ylabel("demand multiplier", fontsize=8, color=MUTED)
        axes[1, 0].set_ylabel(
            "ramp queue incl. Ventura Blvd (veh)", fontsize=8, color=MUTED
        )
        axes[1, 0].legend(fontsize=7, frameon=False, loc="upper left")
        _axes(fig, axes, "Demand shapes: growth and oscillation (simulated, seed 1)")
        fig.savefig(output / "shapes.png", dpi=200)
        plt.close(fig)
    if any(MIX_KEYS & v.keys() for v in cfg["ablation"]["variants"]):
        mix_report(output, cfg, rows)
    return summary


def mix_report(output: Path, cfg: dict, rows: pd.DataFrame) -> None:
    """Ramp/mainline mix study: cell means, metering effects and cell contrasts.

    Differences are paired by seed. One counts when its 95 % t interval excludes zero and
    its mean reaches the size in `ablation.decision`: minutes of congestion, or per cent
    of the unmetered ramp exits of the cell.
    """
    # Imported here because drivers.py imports this module.
    from adaptive_ramp_metering.simulation.drivers import interval

    size, controllers = cfg["ablation"]["decision"], cfg["ablation"]["controllers"]
    rows = rows.assign(
        ramp_exits=rows["exited_ramp_origin_veh"],
        mainline_exits=rows["exited_veh"] - rows["exited_ramp_origin_veh"],
    )
    cell = {
        v["id"]: {
            "exit": "free" if v.get("free_exit") else "limited",
            "ramp": v.get("ramp_factor", 1),
            "mainline": "shoulder lane"
            if v.get("mainline") == "shoulder_lane"
            else v.get("mainline_factor", 1),
        }
        for v in cfg["ablation"]["variants"]
    }
    measures = [
        "congested_min",
        "ramp_exits",
        "mainline_exits",
        "exited_veh",
        "boundary_ramp_veh",
        "boundary_mainline_veh",
        "boundary_ramp_max_veh",
    ]
    means = rows.groupby(["variant", "controller"], sort=False)[measures].mean()
    pd.DataFrame(
        [
            {"variant": v, **cell[v], "controller": c, **values}
            for (v, c), values in means.iterrows()
        ]
    ).to_csv(output / "mix_cells.csv", index=False)
    by = rows.set_index(["variant", "controller", "seed"])[measures].sort_index()

    def paired(a: pd.DataFrame, b: pd.DataFrame, metric: str) -> dict:
        mean, low, high = interval((a[metric] - b[metric]).dropna())
        return {f"{metric}_diff": mean, f"{metric}_low": low, f"{metric}_high": high}

    effects = []
    for variant in cell if "none" in controllers else ():
        base = by.loc[(variant, "none")]
        floors = {
            "congested_min": size["congested_min"],
            "ramp_exits": size["ramp_exits_pct"] / 100 * base["ramp_exits"].mean(),
        }
        for controller in controllers:
            if controller == "none":
                continue
            run = by.loc[(variant, controller)]
            row = {"variant": variant, **cell[variant], "controller": controller}
            for metric in ("congested_min", "ramp_exits", "exited_veh"):
                row |= paired(run, base, metric)
                if metric in floors:
                    low, high = row[f"{metric}_low"], row[f"{metric}_high"]
                    row[f"{metric}_counts"] = bool(
                        (low > 0 or high < 0)
                        and abs(row[f"{metric}_diff"]) >= floors[metric]
                    )
            for metric in ("ramp_exits", "exited_veh"):
                row[f"{metric}_pct"] = 100 * row[f"{metric}_diff"] / base[metric].mean()
            effects.append(row)
    pd.DataFrame(effects).to_csv(output / "mix_effects.csv", index=False)
    contrasts = []
    for a, b in cfg["ablation"].get("contrasts", []):
        for controller in controllers:
            run, base = by.loc[(a, controller)], by.loc[(b, controller)]
            row = {"cell": a, "minus": b, "controller": controller}
            for metric in ("ramp_exits", "mainline_exits", "congested_min"):
                row |= paired(run, base, metric)
            row["ramp_exits_pct"] = (
                100 * row["ramp_exits_diff"] / base["ramp_exits"].mean()
            )
            contrasts.append(row)
    pd.DataFrame(contrasts).to_csv(output / "mix_contrasts.csv", index=False)


def load_config(path: Path) -> dict:
    """A site configuration, or a study file that names one (`site:`) with its own cells."""
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    if "site" not in cfg:
        return cfg
    site = yaml.safe_load(Path(cfg["site"]).read_text(encoding="utf-8"))
    site["site"] = cfg["site"]
    site["micro"]["seeds"] = cfg["seeds"]
    if "shoulder_lane" in cfg:
        site["demand"]["shoulder_lane"] = cfg["shoulder_lane"]
    site["ablation"].update(
        {k: cfg[k] for k in ("variants", "decision", "contrasts") if k in cfg}
    )
    return site


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/i405.yaml"))
    parser.add_argument("--output", type=Path, default=Path("results/demand-ablation"))
    parser.add_argument("--workers", type=int, help="processes; default all cores")
    parser.add_argument(
        "--replot", type=Path, help="redo the table and figures of a run folder"
    )
    parser.add_argument(
        "--analytic", action="store_true", help="print the before-run table and stop"
    )
    args = parser.parse_args(argv)
    try:
        if args.replot:
            output = args.replot
            report(output)
        else:
            cfg = load_config(args.config)
            if args.analytic:
                table = analytic_table(cfg, historical_profile(cfg["demand"]))
                print(table.round(1).to_string(index=False))
                return
            output = run_ablation(cfg, args.config, args.output, args.workers)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    summary = pd.read_csv(output / "summary.csv")
    cols = [
        "variant",
        "controller",
        "served_pct_mean",
        "boundary_ramp_max_veh_mean",
        "time_per_veh_min_mean",
    ]
    print(summary[cols].round(1).to_string(index=False))
    print(f"Demand ablation (simulated, calibrated in part): {output.resolve()}")


if __name__ == "__main__":
    main()
