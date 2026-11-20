"""Case studies on the site scenario: one change per case, compared with the first case.

A case changes the site scenario (`simulation/ablation.py`) in one respect: the drivers'
spread and shape per IDM parameter (`micro.Driver`), any configuration value named by
its dotted path (`set`), or the demand of the study's variants (`variant`). Every case
runs under every metering rule and seed; cases are compared with the first case, and
rules with each other, by paired differences over seeds. With identical demand a seed
gives every case the same arrivals and the same driver percentiles.

Studies: driver populations (experiments/driver_populations.md, `uv run arm-drivers`)
and the one-factor ablation of the metering rules (experiments/rule_ablation.md,
`uv run arm-study --config configs/i405_ablation.yaml`).
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
from scipy import stats

from adaptive_ramp_metering.simulation import ablation, micro
from adaptive_ramp_metering.simulation.ablation import GRID, INK, MUTED, STYLE
from adaptive_ramp_metering.simulation.micro import plt

METRICS = {
    "congested_min": "Persistent congestion at the mainline station (min)",
    "served_pct": "Demand served in the window (%)",
    "time_per_veh_min": "Time in system per vehicle (min)",
    "boundary_ramp_max_veh": "Peak queue held on Ventura Blvd (veh)",
    "nonpositive_gap_events": "Steps with overlapping vehicles",
}


def interval(values) -> tuple[float, float, float]:
    """Mean of paired differences over seeds and its 95 % t interval."""
    d = np.asarray(values, dtype=float)
    if len(d) < 2:
        return float(d.mean()), math.nan, math.nan
    half = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / math.sqrt(len(d))
    return float(d.mean()), float(d.mean() - half), float(d.mean() + half)


def population(vehicle: dict, n: int = 20000) -> pd.DataFrame:
    """n drivers of a case, each value as a multiple of its fixed value."""
    rng, typical = np.random.default_rng(0), micro.Driver(**vehicle["idm"])
    spread, shape = vehicle.get("spread", {}), vehicle.get("shape", {})
    drawn = (micro.Driver.sample(vehicle["idm"], spread, shape, rng) for _ in range(n))
    return pd.DataFrame(
        {k: getattr(d, f) / getattr(typical, f) for k, f in micro.SPREAD.items()}
        for d in drawn
    )


def _vehicle(site: dict, case: dict) -> dict:
    """The site's vehicle settings with the case's spread and shape."""
    extra = {k: case[k] for k in ("spread", "shape") if k in case}
    return {**site["micro"]["vehicle"], **extra}


def _case_config(site: dict, case: dict) -> dict:
    """The site configuration with one case's changes applied.

    `set` assigns existing configuration values by dotted path, so a mistyped path
    fails instead of leaving the case equal to the baseline. `variant` replaces the
    demand of every variant of the study, keeping its id.
    """
    cfg = copy.deepcopy(site)
    # The copy's own vehicle settings, so that `set` stays within this case.
    cfg["micro"]["vehicle"] = _vehicle(cfg, case)
    for path, value in case.get("set", {}).items():
        *parents, key = path.split(".")
        node = cfg
        for name in parents:
            node = node[name] if isinstance(node, dict) and name in node else None
        if not isinstance(node, dict) or key not in node:
            raise ValueError(f"case {case['id']}: no configuration value at {path}")
        node[key] = value
    if "variant" in case:
        cfg["ablation"]["variants"] = [
            {**case["variant"], "id": v["id"]} for v in cfg["ablation"]["variants"]
        ]
    return cfg


def _site(study: dict) -> dict:
    site = yaml.safe_load(Path(study["site"]).read_text(encoding="utf-8"))
    if "shoulder_lane" in study:  # lets a case take its through traffic from that lane
        site["demand"]["shoulder_lane"] = study["shoulder_lane"]
    return site


def analytic(study: dict) -> pd.DataFrame:
    """The course formulas for every case of a study, without simulation.

    One row per case and variant: `ablation.analytic_table` on the case's configuration.
    """
    site = _site(study)
    site["ablation"]["variants"] = [
        v for v in site["ablation"]["variants"] if v["id"] in study["variants"]
    ]
    tables = []
    for case in study["cases"]:
        cfg = _case_config(site, case)
        table = ablation.analytic_table(cfg, ablation.historical_profile(cfg["demand"]))
        tables.append(table.assign(case=case["id"]))
    return pd.concat(tables, ignore_index=True)


def run_study(
    study: dict, config_path: Path, output_root: Path, workers: int | None = None
) -> Path:
    site = _site(study)
    ids = [case["id"] for case in study["cases"]]
    if (
        len(set(ids)) != len(ids)
        or not set(study["variants"]) <= {v["id"] for v in site["ablation"]["variants"]}
        or any(not set(pair) <= set(ids) for pair in study.get("contrasts", []))
        or any(
            not set(pair) <= set(study["controllers"])
            for pair in study.get("rule_contrasts", [])
        )
        or study["decision"]["metric"] not in METRICS
    ):
        raise ValueError(
            "study: repeated case, unknown variant, unknown case or rule in a "
            "contrast or unknown decision metric"
        )
    site["micro"]["seeds"] = study["seeds"]
    site["ablation"]["variants"] = [
        v for v in site["ablation"]["variants"] if v["id"] in study["variants"]
    ]
    rule = site["ablation"]["congestion"]
    tasks = []
    for case in study["cases"]:
        cfg = _case_config(site, case)
        sim_cfg = ablation.build_config(cfg, ablation.historical_profile(cfg["demand"]))
        tasks += [
            (case["id"], (sim_cfg, variant, controller, seed, False, rule))
            for variant in study["variants"]
            for controller in study["controllers"]
            for seed in study["seeds"]
        ]
    now = datetime.now(UTC)
    output = output_root / now.strftime("%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True, exist_ok=False)
    runs = [task for _, task in tasks]
    if workers == 1:
        results = [ablation._run(run) for run in runs]
    else:
        with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
            results = list(pool.map(ablation._run, runs))
    rows = pd.DataFrame(
        {"case": case, **result["row"]} for (case, _), result in zip(tasks, results)
    )
    requested = rows["requested_ramp_veh"] + rows["requested_mainline_veh"]
    rows["served_pct"] = 100 * rows["exited_veh"] / requested
    rows["time_per_veh_min"] = rows["total_time_veh_s"] / requested / 60
    rows.to_csv(output / "evaluation.csv", index=False)
    (output / "config.yaml").write_text(
        yaml.safe_dump({"study": study, "site": site}, sort_keys=False)
    )
    report(output)
    sources = {
        "config": config_path,
        "site": Path(study["site"]),
        "pems_extract": Path(site["demand"]["pems_file"]),
        "drivers.py": Path(__file__),
        "ablation.py": Path(ablation.__file__),
        "micro.py": Path(micro.__file__),
        "metering.py": Path(micro.__file__).parents[1] / "control" / "metering.py",
    }
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    (output / "run.json").write_text(
        json.dumps(
            {
                "schema_version": "i405-driver-study-v1",
                "origin": "simulated from observed PeMS demand; model calibrated in part",
                "created_utc": now.isoformat(),
                "source_sha256": {
                    k: hashlib.sha256(p.read_bytes()).hexdigest()
                    for k, p in sources.items()
                    if p.exists()
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


def _forest(table: pd.DataFrame, columns: tuple, study: dict, text: tuple) -> None:
    """One row per case, one panel per demand variant: mean and 95 % interval."""
    value, low, high = columns
    xlabel, title, path = text
    cases = [c for c in table["case"].unique()]
    variants, controllers = study["variants"], table["controller"].unique()
    height = 0.55 * len(cases) + 2.3
    fig, axes = plt.subplots(
        1,
        len(variants),
        figsize=(max(7.5, 3.3 * len(variants) + 1.4), height),
        sharey=True,
        squeeze=False,
    )
    for ax, variant in zip(axes[0], variants):
        ax.axvspan(
            -study["decision"]["at_least"],
            study["decision"]["at_least"],
            color=GRID,
            alpha=0.6,
            lw=0,
        )
        ax.axvline(0, color=MUTED, lw=1)
        for j, name in enumerate(controllers):
            label, color, marker = STYLE[name]
            d = table[(table["variant"] == variant) & (table["controller"] == name)]
            d = d.set_index("case").reindex(cases)
            y = np.arange(len(cases)) + (j - (len(controllers) - 1) / 2) * 0.24
            ax.hlines(y, d[low], d[high], color=color, lw=2)
            ax.plot(
                d[value],
                y,
                marker,
                ms=8,
                color=color,
                mec="white",
                mew=1.5,
                ls="",
                label=label,
            )
        ax.set_title(variant, fontsize=9, color=INK)
        ax.set_xlabel(xlabel, fontsize=8, color=MUTED)
    axes[0][0].set_yticks(range(len(cases)), cases, fontsize=8, color=INK)
    axes[0][0].invert_yaxis()
    ablation._axes(fig, axes, title)
    # The legend sits under the panels so it never covers an interval.
    fig.legend(
        *axes[0][0].get_legend_handles_labels(),
        loc="lower center",
        ncol=len(controllers),
        fontsize=7,
        frameon=False,
    )
    fig.subplots_adjust(bottom=0.95 / height)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def report(output: Path) -> pd.DataFrame:
    """Difference tables and figures from the records of one run folder."""
    cfg = yaml.safe_load((output / "config.yaml").read_text())
    study, site = cfg["study"], cfg["site"]
    rows = pd.read_csv(output / "evaluation.csv")
    cases = [case["id"] for case in study["cases"]]
    decision = study["decision"]
    cell = rows.set_index(["case", "variant", "controller", "seed"]).sort_index()

    def over_seeds(case: str, variant: str, controller: str, metric: str) -> pd.Series:
        return cell.loc[(case, variant, controller), metric]

    # Every case against the first one, and the named contrasts, paired by seed.
    pairs = [(c, cases[0]) for c in cases[1:]] + [
        tuple(pair) for pair in study.get("contrasts", [])
    ]
    differences, effects = [], []
    for variant in study["variants"]:
        for controller in study["controllers"]:
            for metric in METRICS:
                for case, against in pairs:
                    a = over_seeds(case, variant, controller, metric)
                    b = over_seeds(against, variant, controller, metric)
                    mean, low, high = interval(a - b)
                    floor = decision["at_least"] if metric == decision["metric"] else 0
                    differences.append(
                        {
                            "case": case,
                            "against": against,
                            "variant": variant,
                            "controller": controller,
                            "metric": metric,
                            "value": a.mean(),
                            "reference": b.mean(),
                            "difference": mean,
                            "low": low,
                            "high": high,
                            "seeds": len(a),
                            "differs": bool(
                                (low > 0 or high < 0) and abs(mean) >= floor
                            ),
                        }
                    )
                if controller == "none" or "none" not in study["controllers"]:
                    continue
                # What the meter changes, and whether the driver population alters that.
                reference = over_seeds(cases[0], variant, controller, metric)
                reference = reference - over_seeds(cases[0], variant, "none", metric)
                for case in cases:
                    e = over_seeds(case, variant, controller, metric)
                    e = e - over_seeds(case, variant, "none", metric)
                    effect, change = interval(e), interval(e - reference)
                    effects.append(
                        {
                            "case": case,
                            "variant": variant,
                            "controller": controller,
                            "metric": metric,
                            "effect": effect[0],
                            "low": effect[1],
                            "high": effect[2],
                            "change": change[0],
                            "change_low": change[1],
                            "change_high": change[2],
                            "seeds": len(e),
                        }
                    )
    differences = pd.DataFrame(differences)
    differences.to_csv(output / "differences.csv", index=False)
    effects = pd.DataFrame(effects)
    effects.to_csv(output / "controller_effect.csv", index=False)
    # One metering rule against another in the same case and seed.
    rules = []
    for case in cases:
        for variant in study["variants"]:
            for metric in METRICS:
                floor = decision["at_least"] if metric == decision["metric"] else 0
                for a_rule, b_rule in study.get("rule_contrasts", []):
                    a = over_seeds(case, variant, a_rule, metric)
                    b = over_seeds(case, variant, b_rule, metric)
                    mean, low, high = interval(a - b)
                    rules.append(
                        {
                            "case": case,
                            "variant": variant,
                            "rule": a_rule,
                            "against": b_rule,
                            "metric": metric,
                            "value": a.mean(),
                            "reference": b.mean(),
                            "difference": mean,
                            "low": low,
                            "high": high,
                            "differs": bool(
                                (low > 0 or high < 0) and abs(mean) >= floor
                            ),
                        }
                    )
    pd.DataFrame(rules).to_csv(output / "rule_differences.csv", index=False)

    # Populations: the drivers each case draws, as multiples of the fixed values.
    people = {case["id"]: population(_vehicle(site, case)) for case in study["cases"]}
    z = {k: (p - p.mean()) / p.std().replace(0, 1) for k, p in people.items()}
    pd.DataFrame(
        {
            "case": case,
            "parameter": key,
            "mean": p[key].mean(),
            "cv": p[key].std() / p[key].mean(),
            "min": p[key].min(),
            "max": p[key].max(),
            "skewness": (z[case][key] ** 3).mean(),
        }
        for case, p in people.items()
        for key in micro.SPREAD
    ).to_csv(output / "populations.csv", index=False)
    varied = [k for k in micro.SPREAD if any(p[k].std() > 0 for p in people.values())]
    shown = [c for c, p in people.items() if p.std().max() > 0]
    if varied:
        fig, axes = plt.subplots(
            len(varied),
            len(shown),
            figsize=(max(7.5, 1.9 * len(shown) + 0.8), 1.15 * len(varied) + 0.9),
            sharex="row",
            sharey="row",
            squeeze=False,
        )
        for r, key in enumerate(varied):
            span = (
                min(people[c][key].min() for c in shown),
                max(people[c][key].max() for c in shown),
            )
            for c, case in enumerate(shown):
                ax, values = axes[r, c], people[case][key]
                ax.axvline(1, color=MUTED, lw=1)
                if values.std() > 0:
                    share = np.full(len(values), 100 / len(values))
                    bins = {"bins": 40, "range": span, "weights": share}
                    ax.hist(values, **bins, color=MUTED, alpha=0.25)
                    ax.hist(values, **bins, histtype="step", color=INK, lw=1.2)
                if r == 0:
                    ax.set_title(case, fontsize=8, color=INK)
            axes[r, 0].set_ylabel(f"{key}\n% of drivers", fontsize=7, color=MUTED)
        for ax in axes[-1]:
            ax.set_xlabel("multiple of the fixed value", fontsize=7, color=MUTED)
        ablation._axes(
            fig,
            axes,
            "Driver populations: each driver's value as a multiple of the fixed value",
        )
        fig.savefig(output / "populations.png", dpi=200)
        plt.close(fig)

    label = METRICS[decision["metric"]]
    chosen = differences[differences["metric"] == decision["metric"]]
    _forest(
        chosen[chosen["against"] == cases[0]],
        ("difference", "low", "high"),
        study,
        (
            f"difference from {cases[0]} drivers",
            f"{label}: each driver population minus {cases[0]} drivers\nMean over "
            f"{len(study['seeds'])} seeds and 95 % interval; shaded: under "
            f"{decision['at_least']:g}, too small to count",
            output / "differences.png",
        ),
    )
    if len(effects):  # empty when the study has no metering rule to compare
        chosen = effects[effects["metric"] == decision["metric"]]
        _forest(
            chosen,
            ("effect", "low", "high"),
            study,
            (
                "difference from no meter",
                f"{label}: each metering rule minus no meter\nPer driver "
                f"population; mean over {len(study['seeds'])} seeds and 95 % interval",
                output / "controller_effect.png",
            ),
        )
    return differences


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/i405_drivers.yaml")
    )
    parser.add_argument("--output", type=Path, default=Path("results/driver-study"))
    parser.add_argument("--workers", type=int, help="processes; default all cores")
    parser.add_argument(
        "--replot", type=Path, help="redo the tables and figures of a run folder"
    )
    parser.add_argument(
        "--analytic",
        action="store_true",
        help="print the course formulas for every case and stop (no simulation)",
    )
    args = parser.parse_args(argv)
    try:
        if args.analytic:
            study = yaml.safe_load(args.config.read_text(encoding="utf-8"))
            print(analytic(study).round(1).to_string(index=False))
            return
        if args.replot:
            output = args.replot
            report(output)
        else:
            study = yaml.safe_load(args.config.read_text(encoding="utf-8"))
            output = run_study(study, args.config, args.output, args.workers)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    table = pd.read_csv(output / "differences.csv")
    study = yaml.safe_load((output / "config.yaml").read_text())["study"]
    table = table[table["metric"] == study["decision"]["metric"]]
    cols = "case against variant controller reference value difference low high differs"
    print(table[cols.split()].round(1).to_string(index=False))
    print(f"Case study (simulated, calibrated in part): {output.resolve()}")


if __name__ == "__main__":
    main()
