"""Figures of the mid-report (docs/mid_report/mid_report.tex).

    uv run python scripts/mid_report_figures.py                      # every figure
    uv run python scripts/mid_report_figures.py --only rule_effects  # one of them

Run from the repository root. Sources:

- docs/mid_report/data/: copies of the recorded result tables (the run folder and code
  revision of each are in its run.json) and, in traces/, the series of the simulations
  this script runs itself. Delete a file in traces/ to run its simulation again.
- configs/i405.yaml: the calibrated site scenario.
- data/interim/pems/: PeMS station extracts (git-ignored). The figures that need them
  are skipped, by name, when the folder is missing.

site_geometry.png and design_schematic.png are static drawings and are not built here.
Simulated values are uncertain; PeMS values are observations.
"""

import argparse
import copy
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).parent))
import bottleneck_check
import calibrate_fd

from adaptive_ramp_metering.simulation import ablation, drivers, micro

DATA, FIG = Path("docs/mid_report/data"), Path("docs/mid_report/fig")
SITE, PEMS = Path("configs/i405.yaml"), Path("data/interim/pems")
WIDTH = 6.5  # inches: the text width of the report

# Rule: label, color, marker. Colors are the first three categorical slots of the
# dataviz reference palette (they pass its all-pairs color-vision check); the marker
# repeats the identity for print.
RULES = {
    "none": ("No meter", "#6f6e69", "D"),
    "fixed": ("Fixed rate", "#2a78d6", "s"),
    "caltrans": ("Caltrans plan", "#eb6834", "^"),
    "alinea": ("ALINEA", "#1baf7a", "o"),
}
INK, MUTED, RULE_LINE = "#0b0b0b", "#52514e", "#c3c2b7"
BLUES = LinearSegmentedColormap.from_list("blues", ["#eef4fd", "#86b6ef", "#0d366b"])
SPEED = LinearSegmentedColormap.from_list("speed", ["#0d366b", "#3987e5", "#cde2fb"])
DIVERGING = LinearSegmentedColormap.from_list(
    "diverging", ["#1c5cab", "#f0efec", "#d03b3b"]
)

# The configuration before the calibration of D023 (configs/i405.yaml at commit b1abc30).
BEFORE = {
    "v0": 28.6,
    "idm": {"a_mps2": 2.0, "b_mps2": 2.0, "time_gap_s": 1.0, "s0_m": 2.0, "delta": 4},
}

GROUPS = (
    ("", ("baseline",)),
    (
        "Demand",
        (
            "demand_0.9",
            "demand_1.1",
            "ramp_0.75",
            "ramp_1.25",
            "mainline_0.75",
            "mainline_1.25",
            "shoulder_lane",
            "wave_10min",
            "wave_60min",
            "free_exit",
        ),
    ),
    (
        "Car following",
        (
            "T_low",
            "T_high",
            "a_low",
            "a_high",
            "b_low",
            "b_high",
            "s0_low",
            "s0_high",
            "v0_low",
            "v0_high",
            "delta_4",
        ),
    ),
    ("Drivers", ("drivers_normal", "drivers_field")),
    ("Information", ("detector_fault",)),
)
SYMBOL = {
    "time_gap_s": ("$T$", " s"),
    "a_mps2": ("$a$", " m/s$^2$"),
    "b_mps2": ("$b$", " m/s$^2$"),
    "s0_m": ("$s_0$", " m"),
    "desired_speed_mps": ("$v_0$", " m/s"),
    "delta": (r"$\delta$", ""),
}
METRICS = {
    "congested_min": "persistent congestion (min)",
    "time_per_veh_min": "time in the system (min per vehicle)",
}


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": ["TeX Gyre Termes", "Nimbus Roman", "STIXGeneral"],
            "mathtext.fontset": "stix",
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "axes.titlesize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "legend.frameon": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": "#e4e3df",
            "grid.linewidth": 0.6,
            "axes.edgecolor": MUTED,
            "axes.linewidth": 0.6,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK,
            "ytick.labelcolor": INK,
            "text.color": INK,
            "axes.labelcolor": INK,
            "lines.linewidth": 1.4,
            "savefig.dpi": 200,
        }
    )


def save(fig, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)
    print(f"wrote {FIG / name}.png")


def case_label(case: dict) -> str:
    """Row label of an ablation case, built from its definition so the two cannot differ."""
    if "set" in case:
        ((path, value),) = case["set"].items()
        symbol, unit = SYMBOL[path.rsplit(".", 1)[1]]
        return f"{symbol} = {value:g}{unit}"
    if "spread" in case:
        field = isinstance(case["shape"], dict)
        return "Drivers differ, " + ("field spreads" if field else case["shape"])
    variant = case.get("variant", {})
    if "detector_fault" in variant:
        fault = variant["detector_fault"]
        return (
            f"Merge detector silent, {(fault['until_s'] - fault['from_s']) // 60} min"
        )
    if variant.get("free_exit"):
        return "Free exit"
    if variant.get("mainline") == "shoulder_lane":
        return "Through traffic of the shoulder lane"
    if variant.get("kind") == "sine":
        return f"Demand wave, {variant['period_s'] // 60} min"
    for key, name in (
        ("ramp_factor", "Ramp demand"),
        ("mainline_factor", "Through traffic"),
    ):
        if key in variant:
            return f"{name} × {variant[key]:g}"
    if variant.get("factor", 1) != 1:
        return f"All demand × {variant['factor']:g}"
    return "Baseline (observed day)"


def rows(skip: tuple = ()) -> tuple[list, list]:
    """(y, case id) per row and (y, title) per group header, from the top down."""
    y, cases, heads = 0.0, [], []
    for title, members in GROUPS:
        members = [m for m in members if m not in skip]
        if title and members:
            y -= 0.9
            heads.append((y, title))
        for member in members:
            y -= 1
            cases.append((y, member))
    return cases, heads


def mark(ax, y, mean, low, high, color, marker, counts, limits) -> None:
    """A difference: its 95 % interval as a line and its mean as a marker, filled when it
    counts. A mean outside `limits` is drawn at the limit as an arrowhead with its value."""
    lo, hi = limits
    face = color if counts else "white"
    if lo <= mean <= hi:
        ax.plot([max(low, lo), min(high, hi)], [y, y], color=color, lw=1.1, zorder=2)
        ax.plot(mean, y, marker, color=color, mfc=face, ms=4.6, mew=1.0, zorder=3)
        for end, edge, arrow in ((low, lo, "<"), (high, hi, ">")):
            if not lo <= end <= hi:  # the interval runs past the axis
                ax.plot(edge, y, arrow, color=color, ms=3.5, clip_on=False, zorder=3)
        return
    left = mean < lo
    ax.plot(
        lo if left else hi,
        y,
        "<" if left else ">",
        color=color,
        mfc=face,
        ms=5.5,
        mew=1.0,
        clip_on=False,
        zorder=3,
    )
    ax.annotate(
        f"{mean:.0f} [{low:.0f}, {high:.0f}]".replace("-", "\N{MINUS SIGN}"),
        (lo if left else hi, y),
        xytext=(5 if left else -5, 0),
        textcoords="offset points",
        ha="left" if left else "right",
        va="center",
        fontsize=8,
    )


def forest_axes(axes, cases, heads, labels) -> None:
    """Shared rows of the two forest plots: case labels, group headers, separators."""
    for ax in axes:
        ax.set_ylim(cases[-1][0] - 0.7, cases[0][0] + 0.7)
        ax.set_yticks([y for y, _ in cases], [labels[c] for _, c in cases])
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="y", visible=False)
        ax.axvline(0, color=MUTED, lw=0.8, zorder=1)
        for y, _ in heads:
            ax.axhline(y + 0.45, color=RULE_LINE, lw=0.6)
    for ax in axes[1:]:
        ax.tick_params(axis="y", labelleft=False)
    for y, title in heads:
        axes[0].text(
            -0.03,
            y - 0.05,
            title,
            transform=axes[0].get_yaxis_transform(),
            ha="right",
            va="center",
            fontweight="bold",
        )


def fill_legend(color: str = MUTED) -> list:
    return [
        Line2D(
            [], [], marker="o", ls="", color=color, mfc=color, ms=4.6, label="counts"
        ),
        Line2D(
            [],
            [],
            marker="o",
            ls="",
            color=color,
            mfc="white",
            ms=4.6,
            label="does not",
        ),
    ]


def study() -> tuple[dict, dict]:
    """The rule ablation's recorded configuration and its row labels by case id."""
    cfg = yaml.safe_load((DATA / "rule_ablation/config.yaml").read_text())
    world = {member for _, members in GROUPS for member in members}
    cases = [c for c in cfg["study"]["cases"] if c["id"] in world]
    return cfg, {c["id"]: case_label(c) for c in cases}


def counted(metric: str, mean: float, low: float, high: float, at_least: float) -> bool:
    """The record's decision rule: the interval excludes zero, and for the primary
    measure the mean also reaches the smallest difference of interest."""
    return (low > 0 or high < 0) and (
        metric != "congested_min" or abs(mean) >= at_least
    )


def rule_effects() -> None:
    """Each rule minus no meter in the same case, paired by seed (controller_effect.csv)."""
    cfg, labels = study()
    at_least = cfg["study"]["decision"]["at_least"]
    effect = pd.read_csv(DATA / "rule_ablation/controller_effect.csv")
    cases, heads = rows()
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 6.9), layout="constrained")
    forest_axes(axes, cases, heads, labels)
    for ax, (metric, name), limits in zip(
        axes, METRICS.items(), ((-45.0, 20.0), (-1.75, 1.95))
    ):
        table = effect[effect["metric"] == metric].set_index(["case", "controller"])
        for y, case in cases:
            for (rule, (_, color, marker)), dy in zip(
                list(RULES.items())[1:], (0.27, 0.0, -0.27)
            ):
                r = table.loc[(case, rule)]
                mark(
                    ax,
                    y + dy,
                    r["effect"],
                    r["low"],
                    r["high"],
                    color,
                    marker,
                    counted(metric, r["effect"], r["low"], r["high"], at_least),
                    limits,
                )
        ax.set_xlim(*limits)
        ax.set_xlabel(f"Rule minus no meter:\n{name}")
    for edge in (-at_least, at_least):
        axes[0].axvline(edge, color=MUTED, lw=0.7, ls=":", zorder=1)
    handles = [
        Line2D([], [], marker=m, color=c, lw=1.1, ms=4.6, label=label)
        for label, c, m in list(RULES.values())[1:]
    ]
    fig.legend(
        handles=handles + fill_legend(),
        loc="outside upper center",
        ncols=5,
        columnspacing=1.4,
    )
    save(fig, "rule_effects")


def case_effects() -> None:
    """Each case minus the baseline without a meter, paired by seed (differences.csv)."""
    cfg, labels = study()
    at_least = cfg["study"]["decision"]["at_least"]
    diff = pd.read_csv(DATA / "rule_ablation/differences.csv")
    diff = diff[diff["controller"] == "none"]
    cases, heads = rows(skip=("baseline", "detector_fault"))
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 5.5), layout="constrained")
    forest_axes(axes, cases, heads, labels)
    color = RULES["none"][1]
    for ax, (metric, name) in zip(axes, METRICS.items()):
        table = diff[diff["metric"] == metric].set_index("case")
        span = table.loc[[c for _, c in cases]]
        pad = 0.06 * (span["high"].max() - span["low"].min())
        limits = (span["low"].min() - pad, span["high"].max() + pad)
        for y, case in cases:
            r = table.loc[case]
            hit = counted(metric, r["difference"], r["low"], r["high"], at_least)
            mark(ax, y, r["difference"], r["low"], r["high"], color, "D", hit, limits)
        ax.set_xlim(*limits)
        ax.set_xlabel(f"Case minus baseline, no meter:\n{name}")
    fig.legend(handles=fill_legend(color), loc="outside upper center", ncols=2)
    save(fig, "case_effects")


def tradeoff() -> None:
    """Freeway congestion against what is held on the street, by rule setting."""
    cfg, _ = study()
    control = cfg["site"]["micro"]["control"]
    lanes = control["caltrans"]["metered_lanes"]
    per_lane = {
        c["id"]: 60 * c["set"]["micro.control.fixed_rate_veh_per_s"] / lanes
        for c in cfg["study"]["cases"]
        if "micro.control.fixed_rate_veh_per_s" in c.get("set", {})
    }
    base = 60 * control["fixed_rate_veh_per_s"] / lanes
    ev = pd.read_csv(DATA / "rule_ablation/evaluation.csv")
    # case, rule, direct label (None: in the baseline cluster) and where it goes, in
    # points from the mark, in each of the two panels
    slow = f"Fixed rate, {per_lane['fixed_6_per_min']:g} veh/min per lane"
    points = [
        ("baseline", "none", None, None),
        ("baseline", "fixed", None, None),
        ("baseline", "caltrans", None, None),
        ("baseline", "alinea", None, None),
        ("fixed_12_per_min", "fixed", None, None),
        ("caltrans_no_override", "caltrans", None, None),
        (
            "alinea_no_queue_rule",
            "alinea",
            "ALINEA without\nits queue rule",
            ((9, 0), (9, 0)),
        ),
        ("fixed_6_per_min", "fixed", slow, ((9, 0), (9, 9))),
        ("s0_high", "alinea", "ALINEA, $s_0$ = 3 m", ((9, 0), (9, -9))),
        ("s0_high", "none", "No meter, $s_0$ = 3 m", ((-9, 11), (-9, 11))),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.1), layout="constrained")
    measures = (
        ("boundary_ramp_max_veh", "Peak queue held on Ventura Blvd (veh)"),
        ("time_per_veh_min", "Time in the system (min per vehicle)"),
    )
    for panel, (ax, (measure, name)) in enumerate(zip(axes, measures)):
        cluster = []
        for case, rule, label, offsets in points:
            runs = ev[(ev["case"] == case) & (ev["controller"] == rule)]
            x, x0, x1 = drivers.interval(runs["congested_min"])
            y, y0, y1 = drivers.interval(runs[measure])
            _, color, marker = RULES[rule]
            changed = case != "baseline"  # hollow: one setting or condition changed
            ax.errorbar(
                x,
                y,
                xerr=[[x - x0], [x1 - x]],
                yerr=[[y - y0], [y1 - y]],
                fmt=marker,
                color=color,
                mfc="white" if changed else color,
                ms=5,
                mew=1.0,
                elinewidth=0.8,
                zorder=3,
            )
            if label is None:
                cluster.append((x, y))
                continue
            ax.annotate(
                label,
                (x, y),
                xytext=offsets[panel],
                textcoords="offset points",
                ha="left" if offsets[panel][0] > 0 else "right",
                va="center",
                fontsize=8,
            )
        cx, cy = np.mean(cluster, axis=0)
        text = (
            "Baseline: no meter and the\nthree rules; fixed rate at "
            f"{per_lane['fixed_12_per_min']:g};\nplan without override"
        )
        ax.annotate(
            text,
            (cx, cy),
            xytext=(-20, -22),
            textcoords="offset points",
            ha="right",
            va="center",
            fontsize=8,
            arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.6, "shrinkB": 6},
        )
        ax.set_xlabel("Persistent congestion at the mainline station (min)")
        ax.set_ylabel(name)
        ax.set_xlim(0, 250)
        ax.set_ylim(0, None)
    handles = [
        Line2D([], [], marker=m, ls="", color=c, ms=5, label=label)
        for label, c, m in RULES.values()
    ]
    handles[1].set_label(f"Fixed rate ({base:g} veh/min per lane at the baseline)")
    handles.append(
        Line2D(
            [],
            [],
            marker="o",
            ls="",
            color=MUTED,
            mfc="white",
            ms=5,
            label="one thing changed",
        )
    )
    fig.legend(handles=handles, loc="outside upper center", ncols=5, columnspacing=1.2)
    save(fig, "tradeoff")


def curve(v0: float, idm: dict, length: float) -> tuple:
    """Density (veh/km) and flow (veh/h) of an equilibrium curve, and its capacity point."""
    _, density, flow = calibrate_fd.equilibrium(v0, idm, length)
    peak = int(flow.argmax())
    return 1000 * density, 3600 * flow, (1000 * density[peak], 3600 * flow[peak])


def fd_calibration() -> None:
    """PeMS station points against the equilibrium curve before and after calibration."""
    cfg = yaml.safe_load(SITE.read_text())
    sim, demand = cfg["micro"], cfg["demand"]
    length, idm = sim["vehicle"]["length_m"], sim["vehicle"]["idm"]
    after = curve(sim["mainline"]["desired_speed_mps"], idm, length)
    before = curve(BEFORE["v0"], BEFORE["idm"], length)
    station, lanes = demand["mainline_station"], demand["mainline_lanes"]
    fig, axes = plt.subplots(
        1, 2, figsize=(WIDTH, 2.9), layout="constrained", sharex=True, sharey=True
    )
    panels = (
        ("Calibration days", calibrate_fd.CALIBRATION, (before, after)),
        ("Held-out days", calibrate_fd.VALIDATION, (after,)),
    )
    for ax, (title, days, curves) in zip(axes, panels):
        points = calibrate_fd.station_points(PEMS, station, lanes, days)
        ax.plot(
            1000 * points["density"],
            3600 * points["flow"],
            ".",
            color=MUTED,
            ms=2.6,
            alpha=0.45,
            rasterized=True,
            label=f"PeMS, 5 min ({len(points):,} intervals)",
        )
        for k, q, (kc, qc) in curves:
            calibrated = k is after[0]
            color = INK if calibrated else "#8a8984"
            ax.plot(
                k,
                q,
                color=color,
                ls="-" if calibrated else "--",
                label="IDM, calibrated" if calibrated else "IDM, before calibration",
            )
            ax.plot(kc, qc, "o", color=color, ms=4, zorder=3)
            ax.annotate(
                f"{qc:,.0f} veh/h",
                (kc, qc),
                xytext=(6, 3),
                textcoords="offset points",
                fontsize=8,
            )
        ax.set_title(title, loc="left")
        ax.set_xlabel("Density (veh/km per lane)")
        ax.legend(loc="upper right", handlelength=1.6)
    axes[0].set_ylabel("Flow (veh/h per lane)")
    axes[0].set_xlim(0, 150)
    axes[0].set_ylim(0, 2750)
    save(fig, "fd_calibration")


def clock(ax, start: str, t0: float, t1: float, step: int = 3600) -> None:
    """Clock-time ticks on an axis in seconds after `start` ("HH:MM")."""
    origin = 3600 * int(start[:2]) + 60 * int(start[3:])
    ticks = np.arange(np.ceil(t0 / step) * step, t1 + 1, step)
    ax.set_xticks(
        ticks,
        [
            f"{int(origin + t) // 3600:02d}:{int(origin + t) % 3600 // 60:02d}"
            for t in ticks
        ],
    )
    ax.set_xlim(t0, t1)


def pems_station(demand: dict, station: int) -> pd.DataFrame:
    """A station's 5-minute rows in the study window, as `bottleneck_check` reads lanes."""
    frame = pd.read_csv(demand["pems_file"], dtype=str)
    frame = frame[frame["station"] == str(station)]
    stamp = pd.to_datetime(frame["timestamp"], format="%m/%d/%Y %H:%M:%S")
    lane = frame["lane_values"].str.split("|", expand=True)
    lane.columns = [12 + j for j in lane.columns]  # positions in the raw archive
    out = bottleneck_check.observed_lanes(lane)
    out["veh_h"] = 12 * pd.to_numeric(frame["total_flow"])
    out["start_s"] = (
        stamp.dt.hour * 3600 + stamp.dt.minute * 60 - ablation._seconds(demand["start"])
    )
    span = ablation._seconds(demand["end"]) - ablation._seconds(demand["start"])
    return out[(out["start_s"] >= 0) & (out["start_s"] < span)].sort_values("start_s")


def pems_day() -> None:
    """The observed day at the site: speed here and downstream, mainline and ramp flow."""
    cfg = yaml.safe_load(SITE.read_text())
    demand, sim = cfg["demand"], cfg["micro"]
    woodcrest, lanes_down, miles = bottleneck_check.STATIONS["woodcrest"]
    here = pems_station(demand, demand["mainline_station"])
    down = pems_station(demand, woodcrest)
    ramp = pems_station(demand, demand["ramp_station"])
    seen = down["lanes_observed"]
    print(
        f"pems_day: station {woodcrest} has {seen.min()} to {seen.max()} of {lanes_down} "
        f"lanes observed (mean {seen.mean():.2f}; imputed share "
        f"{100 * (1 - seen.mean() / lanes_down):.0f} %); station "
        f"{demand['mainline_station']} has {here['lanes_observed'].min()} to "
        f"{here['lanes_observed'].max()} of {demand['mainline_lanes']}"
    )
    fig, axes = plt.subplots(
        2, 1, figsize=(WIDTH, 3.9), layout="constrained", sharex=True
    )
    t = here["start_s"] + 150  # middle of each 5-minute interval
    mps = bottleneck_check.MPH
    axes[0].plot(
        t,
        here["mph"] * mps,
        color=INK,
        label=f"Ventura Blvd mainline station ({demand['mainline_station']})",
    )
    axes[0].plot(
        t,
        down["mph"] * mps,
        color=MUTED,
        ls="--",
        label=f"Woodcrest ({woodcrest}), {1.609344 * miles:.1f} km downstream, observed lanes only",
    )
    line = cfg["ablation"]["congestion"]["speed_below_mps"]
    axes[0].axhline(line, color=MUTED, lw=0.7, ls=":")
    axes[0].annotate(
        f"{line:g} m/s: congested below",
        (sim["duration_s"], line),
        xytext=(-4, 3),
        textcoords="offset points",
        ha="right",
        fontsize=8,
    )
    axes[0].set_ylabel("Speed (m/s)")
    axes[0].set_ylim(0, 40)
    axes[0].legend(loc="upper right", handlelength=2.2)
    axes[1].plot(t, here["veh_h_lane"], color=INK, label="Mainline, per lane")
    axes[1].plot(
        t, ramp["veh_h"], color=MUTED, ls="-.", label="On-ramp (station 716744)"
    )
    axes[1].set_ylabel("Flow (veh/h)")
    axes[1].set_ylim(0, None)
    axes[1].legend(loc="lower right", ncols=2, handlelength=2.2)
    clock(axes[1], demand["start"], 0, sim["duration_s"])
    axes[1].set_xlabel("Time of day, Tuesday 11 October 2022")
    save(fig, "pems_day")


def scenario(
    variant: dict, snapshot_s: float | None = None
) -> tuple[dict, dict, pd.DataFrame]:
    """Site configuration, the micro configuration of one variant, the observed profile."""
    cfg = copy.deepcopy(ablation.load_config(SITE))
    cfg["ablation"]["variants"] = [variant]
    if snapshot_s:
        cfg["micro"]["snapshot_interval_s"] = snapshot_s
    profile = ablation.historical_profile(cfg["demand"])
    return cfg, ablation.build_config(cfg, profile), profile


def traced(name: str, build) -> pd.DataFrame:
    """A table of simulated series, kept in data/traces/ so a rerun need not simulate."""
    path = DATA / "traces" / name
    if path.exists():
        print(f"using {path} (delete it to simulate again)")
        return pd.read_csv(path)
    table = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)
    return table


def inputs() -> None:
    """Demand of the observed day on the modeled lane, and the exit boundary."""
    cfg, sim, profile = scenario({"id": "historical", "kind": "scale", "factor": 1.0})
    length, idm = sim["vehicle"]["length_m"], sim["vehicle"]["idm"]
    capacity = curve(sim["mainline"]["desired_speed_mps"], idm, length)[2][1]
    t = profile["start_s"] + 150
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.7), layout="constrained")
    series = (
        ("merge_lane_veh_per_s", "Merge lane, total", INK, "-"),
        ("mainline_veh_per_s", "Through traffic", MUTED, "--"),
        ("ramp_veh_per_s", "On-ramp", MUTED, "-."),
    )
    for column, label, color, ls in series:
        axes[0].plot(t, 3600 * profile[column], color=color, ls=ls, label=label)
    axes[0].axhline(capacity, color=MUTED, lw=0.7, ls=":")
    axes[0].annotate(
        f"static capacity, {capacity:,.0f} veh/h",
        (0, capacity),
        xytext=(4, 3),
        textcoords="offset points",
        fontsize=8,
    )
    axes[0].set_ylabel("Flow (veh/h)")
    axes[0].set_ylim(0, 3000)
    axes[0].legend(loc="upper right", handlelength=2.2)
    axes[1].plot(
        t, profile["station_speed_mps"], color=INK, label="Station speed (PeMS)"
    )
    axes[1].plot(
        t,
        profile["exit_speed_mps"].astype(float),
        "o",
        color=RULES["none"][1],
        mfc="white",
        ms=3.2,
        label="Exit speed imposed",
    )
    line = cfg["demand"]["congested_below_mps"]
    axes[1].axhline(line, color=MUTED, lw=0.7, ls=":")
    axes[1].set_ylabel("Speed (m/s)")
    axes[1].set_ylim(0, 40)
    axes[1].legend(loc="upper right", handlelength=2.2)
    for ax in axes:
        clock(ax, cfg["demand"]["start"], 0, sim["duration_s"])
        ax.set_xlabel("Time of day")
    save(fig, "inputs")


def baseline_runs() -> pd.DataFrame:
    """30 s series of the calibrated baseline, seed 1, one run per rule."""
    _, sim, _ = scenario({"id": "historical", "kind": "scale", "factor": 1.0})
    frames = []
    for rule in RULES:
        run = micro.simulate(sim, "historical", rule, 1, True)
        queue = pd.DataFrame(
            run["trace"]["queue"],
            columns=["time_s", "queue", "estimate", "ddl", "rate"],
        )
        station = pd.DataFrame(
            [o for o in run["observations"] if o["sensor_id"] == "mainline_upstream"]
        )
        frames.append(
            pd.DataFrame(
                {
                    "rule": rule,
                    "time_s": queue["time_s"],
                    "queue_veh": queue["queue"],
                    "rate_veh_per_s": queue["rate"],
                }
            ).merge(
                station.rename(columns={"interval_end_s": "time_s"})[
                    ["time_s", "count", "mean_speed_mps"]
                ],
                on="time_s",
                how="left",
            )
        )
    return pd.concat(frames)


def baseline_day() -> None:
    """The observed day under the four rules: ramp queue, metering rate, station speed."""
    cfg, sim, profile = scenario({"id": "historical", "kind": "scale", "factor": 1.0})
    runs = traced("baseline_day.csv", baseline_runs)
    ramp = sim["ramp"]["sections"][0]
    storage = sim["meter"]["stop_line_m"] * ramp["lanes"] / 8.84  # 29 ft per vehicle
    fig, axes = plt.subplots(
        3, 1, figsize=(WIDTH, 5.6), layout="constrained", sharex=True
    )
    for rule, (label, color, _) in RULES.items():
        run = runs[runs["rule"] == rule]
        axes[0].plot(run["time_s"], run["queue_veh"], color=color, lw=1.1, label=label)
        five = run.assign(bin=(run["time_s"] - 1e-9) // 300)
        if rule != "none":
            rate = 3600 * five.groupby("bin")["rate_veh_per_s"].mean()
            axes[1].step(
                300 * np.append(rate.index, rate.index[-1] + 1),
                np.append(rate.to_numpy(), rate.iloc[-1]),
                where="post",
                color=color,
                lw=1.2,
            )
        seen = five.dropna(subset=["mean_speed_mps"])
        speed = (seen["mean_speed_mps"] * seen["count"]).groupby(seen["bin"]).sum()
        speed = speed / seen.groupby("bin")["count"].sum()
        axes[2].plot(300 * speed.index + 150, speed, color=color, lw=1.1)
    axes[0].axhline(storage, color=MUTED, lw=0.7, ls=":")
    axes[0].annotate(
        f"storage upstream of the stop line, {storage:.1f} veh",
        (0, storage),
        xytext=(4, 3),
        textcoords="offset points",
        fontsize=8,
    )
    axes[0].set_ylabel("Ramp queue, street\nincluded (veh)")
    axes[1].set_ylabel("Metering rate\n(veh/h, 5 min mean)")
    axes[1].set_ylim(0, 1900)
    axes[2].plot(
        profile["start_s"] + 150,
        profile["station_speed_mps"],
        color=INK,
        ls="--",
        lw=1.2,
        label="PeMS station 717816",
    )
    line = cfg["ablation"]["congestion"]["speed_below_mps"]
    axes[2].axhline(line, color=MUTED, lw=0.7, ls=":")
    axes[2].set_ylabel("Speed at the mainline\nstation (m/s, 5 min mean)")
    axes[2].set_ylim(0, 40)
    axes[2].legend(loc="upper right", handlelength=2.2)
    clock(axes[2], cfg["demand"]["start"], 0, sim["duration_s"])
    axes[2].set_xlabel("Time of day (simulated: seed 1)")
    for ax, tag in zip(axes, "abc"):
        ax.set_title(f"({tag})", loc="left", pad=2)
    fig.legend(
        handles=axes[0].get_legend_handles_labels()[0],
        loc="outside upper center",
        ncols=4,
    )
    save(fig, "baseline_day")


def validation() -> None:
    """Simulated against observed, day by day, for the acceleration that was chosen."""
    chosen = yaml.safe_load(SITE.read_text())["micro"]["vehicle"]["idm"]["a_mps2"]
    table = pd.read_csv(DATA / "validation/validation.csv")
    table = table[table["a_mps2"] == chosen].sort_values(["split", "day"])
    x = np.arange(len(table))
    days = [f"{pd.Timestamp(d):%-d %b}" for d in table["day"]]
    held = int((table["split"] == "calibration").sum())  # first held-out position
    color = RULES["caltrans"][1]  # these runs are under the Caltrans plan
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.8), layout="constrained")
    axes[0].axhspan(0.85, 1.15, color="#f0efec", zorder=0)
    axes[0].axhline(1, color=MUTED, lw=0.8)
    series = (
        ("exited_veh", "All vehicles past the merge", color),
        ("ramp_veh", "Ramp vehicles", "white"),
    )
    for key, label, face in series:
        ratio = table[f"{key}_model"] / table[f"{key}_observed"]
        axes[0].plot(x, ratio, "o", color=color, mfc=face, ms=5, mew=1.0, label=label)
    axes[0].text(
        0.985,
        1.145,
        "±15 %",
        transform=axes[0].get_yaxis_transform(),
        ha="right",
        va="top",
    )
    axes[0].set_ylabel("Simulated over observed")
    axes[0].set_ylim(0.8, 1.2)
    axes[0].legend(loc="lower left", handletextpad=0.3)
    width = 0.36
    axes[1].bar(
        x - width / 2 - 0.02,
        table["congested_min_observed"],
        width,
        color=MUTED,
        label="PeMS",
    )
    axes[1].bar(
        x + width / 2 + 0.02,
        table["congested_min_model"],
        width,
        color=color,
        label="Simulated",
    )
    axes[1].set_ylabel("Congested at the mainline\nstation (min)")
    axes[1].set_ylim(0, 300)
    axes[1].legend(loc="upper right", ncols=2)
    axes[1].grid(axis="x", visible=False)
    for ax in axes:
        ax.set_xticks(x, days)
        ax.axvline(held - 0.5, color=RULE_LINE, lw=0.6)
        ax.set_xlabel("Calibration days" + " " * 22 + "Held-out days")
    save(fig, "validation")
    print(
        table[
            [
                "day",
                "split",
                "exited_veh_error_pct",
                "ramp_veh_error_pct",
                "congested_min_observed",
                "congested_min_model",
            ]
        ]
        .round(1)
        .to_string(index=False)
    )


WINDOW_S = 1800  # width of the time-space window, 30 minutes
TIMESPACE_CASE = "demand_0.9"  # a case in which ALINEA's effect counts


def gore_m(sim: dict) -> float:
    """Position of the gore: 11.5 m into the last ramp section (configs/i405.yaml)."""
    return sum(s["length_m"] for s in sim["ramp"]["sections"][:-1]) + 11.5


def typical_seed(case: str) -> int:
    """Seed whose ALINEA-minus-no-meter congestion is closest to the mean over the seeds."""
    ev = pd.read_csv(DATA / "rule_ablation/evaluation.csv")
    cell = ev[ev["case"] == case].pivot(
        index="seed", columns="controller", values="congested_min"
    )
    gain = cell["alinea"] - cell["none"]
    return int((gain - gain.mean()).abs().idxmin())


def timespace_variant() -> dict:
    cases = study()[0]["study"]["cases"]
    return {
        **next(c for c in cases if c["id"] == TIMESPACE_CASE)["variant"],
        "id": "case",
    }


def freeway_runs() -> pd.DataFrame:
    """1 s samples of the freeway lane with and without ALINEA, for the typical seed, in
    the 30 minutes (starting on a 5-minute mark) in which the speed upstream of the gore
    differs most between the two runs."""
    seed = typical_seed(TIMESPACE_CASE)
    _, sim, _ = scenario(timespace_variant(), 1)
    frames = {}
    for rule in ("none", "alinea"):
        run = micro.simulate(sim, "case", rule, seed, True)
        states = pd.DataFrame(
            run["trace"]["states"],
            columns=["time_s", "vid", "lane", "x_m", "v_mps", "acc"],
        )
        frames[rule] = states.loc[
            states["lane"] == "freeway_0", ["time_s", "vid", "x_m", "v_mps"]
        ]
    minute = {}
    for rule, f in frames.items():
        upstream = f[f["x_m"] < gore_m(sim)]
        minute[rule] = upstream.groupby(upstream["time_s"] // 60)["v_mps"].mean()
    gain = (minute["alinea"] - minute["none"]).dropna()
    starts = np.arange(0, sim["duration_s"] - WINDOW_S + 1, 300)
    total = [
        gain[(gain.index >= s / 60) & (gain.index < (s + WINDOW_S) / 60)].sum()
        for s in starts
    ]
    start = starts[int(np.argmax(total))]
    return pd.concat(
        f[(f["time_s"] >= start) & (f["time_s"] <= start + WINDOW_S)]
        .assign(rule=r, seed=seed)
        .round(2)
        for r, f in frames.items()
    )


def timespace() -> None:
    """Freeway-lane trajectories with and without ALINEA where the rule helps."""
    variant = timespace_variant()
    cfg, sim, _ = scenario(variant)
    runs = traced("timespace.csv.gz", freeway_runs)
    taper, gore = sum(s["length_m"] for s in sim["ramp"]["sections"]), gore_m(sim)
    det = sim["detectors"]
    places = (
        (taper + det["mainline_upstream_m"] - gore, "mainline station"),
        (0.0, "gore"),
        (taper - gore, "end of the taper"),
    )
    norm = Normalize(0, 30)
    fig, axes = plt.subplots(
        2, 1, figsize=(WIDTH, 4.6), layout="constrained", sharex=True
    )
    t0 = runs["time_s"].min()
    for ax, rule in zip(axes, ("none", "alinea")):
        run = runs[runs["rule"] == rule].sort_values(["vid", "time_s"])
        t, x = run["time_s"].to_numpy(), run["x_m"].to_numpy() - gore
        v, vid = run["v_mps"].to_numpy(), run["vid"].to_numpy()
        joined = (vid[1:] == vid[:-1]) & (np.diff(t) <= 1.01)
        segments = np.stack(
            [np.column_stack([t[:-1], x[:-1]]), np.column_stack([t[1:], x[1:]])], axis=1
        )[joined]
        lines = LineCollection(
            segments, cmap=SPEED, norm=norm, linewidths=0.45, rasterized=True
        )
        lines.set_array(((v[:-1] + v[1:]) / 2)[joined])
        ax.add_collection(lines)
        for y, name in places:
            ax.axhline(y, color=INK, lw=0.6, ls=":")
            ax.annotate(
                name,
                (t0 + WINDOW_S, y),
                xytext=(-3, 3),
                textcoords="offset points",
                ha="right",
                fontsize=8,
                bbox={
                    "facecolor": "white",
                    "edgecolor": "none",
                    "pad": 1,
                    "alpha": 0.85,
                },
            )
        ax.set_ylim(x.min(), x.max())
        ax.set_ylabel("Distance from the gore (m)")
        ax.set_title(RULES[rule][0], loc="left", pad=2)
        ax.grid(visible=False)
    clock(axes[1], cfg["demand"]["start"], t0, t0 + WINDOW_S, 300)
    axes[1].set_xlabel(
        f"Time of day ({variant['factor']:g} times the observed demand, "
        f"seed {runs['seed'].iloc[0]})"
    )
    fig.colorbar(lines, ax=axes, label="Speed (m/s)", pad=0.015, aspect=35)
    save(fig, "timespace")
    print(
        f"timespace: seed {runs['seed'].iloc[0]}, window {t0:.0f} to {t0 + WINDOW_S:.0f} s "
        f"after {cfg['demand']['start']}"
    )


def mix_study() -> None:
    """Ramp and mainline demand scaled apart (D021), flow-limited exit."""
    cells = pd.read_csv(DATA / "mix_study/mix_cells.csv")
    effects = pd.read_csv(DATA / "mix_study/mix_effects.csv")
    cells = cells[(cells["exit"] == "limited") & (cells["controller"] == "none")]
    effects = effects[
        (effects["exit"] == "limited") & (effects["controller"] == "alinea")
    ]
    columns = list(dict.fromkeys(cells["mainline"]))
    columns.sort(
        key=lambda m: (not m.replace(".", "").isdigit(), m)
    )  # factors, then the lane
    level = cells.pivot(index="ramp", columns="mainline", values="congested_min")[
        columns
    ]
    change = effects.pivot(
        index="ramp", columns="mainline", values="congested_min_diff"
    )
    counts = effects.pivot(
        index="ramp", columns="mainline", values="congested_min_counts"
    )
    change, counts = change[columns], counts[columns]
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.5), layout="constrained")
    limit = float(np.abs(change.to_numpy()).max())
    panels = (
        (level, BLUES, Normalize(0, 300), "No meter: persistent congestion (min)"),
        (
            change,
            DIVERGING,
            TwoSlopeNorm(0, -limit, limit),
            "ALINEA minus no meter (min)",
        ),
    )
    for ax, (table, cmap, norm, title) in zip(axes, panels):
        image = ax.imshow(
            table.to_numpy(), cmap=cmap, norm=norm, aspect="auto", origin="lower"
        )
        for (i, j), value in np.ndenumerate(table.to_numpy()):
            dark = sum(cmap(norm(value))[:3]) < 1.5
            star = "*" if table is change and counts.to_numpy()[i, j] else ""
            ax.text(
                j,
                i,
                f"{round(value)}{star}".replace("-", "\N{MINUS SIGN}"),
                ha="center",
                va="center",
                color="white" if dark else INK,
            )
        ax.set_xticks(
            range(len(columns)),
            [f"× {float(c):g}" if c[0].isdigit() else c for c in columns],
        )
        ax.set_yticks(range(len(table.index)), [f"× {r:g}" for r in table.index])
        ax.set_xlabel("Through traffic")
        ax.set_title(title, loc="left")
        ax.grid(visible=False)
        ax.tick_params(length=0)
        fig.colorbar(image, ax=ax, pad=0.02, aspect=18)
    axes[0].set_ylabel("Ramp demand")
    save(fig, "mix_study")


FIGURES = {
    f.__name__: f
    for f in (
        rule_effects,
        tradeoff,
        case_effects,
        fd_calibration,
        pems_day,
        baseline_day,
        inputs,
        validation,
        timespace,
        mix_study,
    )
}
NEEDS_PEMS = ("fd_calibration", "pems_day", "baseline_day", "inputs", "timespace")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", choices=FIGURES, help="build one figure")
    args = parser.parse_args(argv)
    style()
    for name, build in FIGURES.items():
        if args.only not in (None, name):
            continue
        if name in NEEDS_PEMS and not PEMS.is_dir():
            print(f"skipped {name}: no PeMS extracts in {PEMS}")
            continue
        build()


if __name__ == "__main__":
    main()
