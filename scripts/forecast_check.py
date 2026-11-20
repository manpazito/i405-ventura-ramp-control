"""Score the queue estimate and a short-horizon forecast against simulator truth.

The course asks for a state estimate and one short-horizon forecast compared with a
simple baseline, and for one observation defect. The meter already uses both: its queue
rule estimates the ramp queue from the entry and passage loops, and takes the last
interval's ramp arrivals as the next interval's demand. This script runs the site's
observed day once (ALINEA, one seed) and reports, from 06:00 on:

- the queue estimate against the true queue (vehicles upstream of the stop line plus
  those waiting on the street), in vehicles;
- the forecast of the next interval's ramp arrivals at the entry loop: the last value
  (what the controller uses) against a moving average of the last ten intervals (the
  simple baseline), in vehicles per interval;
- the same forecasts when the entry loop reports nothing for one hour.

Truth is used only to score. No forecast informs a decision beyond the queue rule's own.

    uv run python scripts/forecast_check.py
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from adaptive_ramp_metering.simulation import ablation, micro

WINDOW = 10  # intervals in the moving average: five minutes of 30 s loop records


def forecasts(counts: np.ndarray) -> pd.DataFrame:
    """Forecasts of each interval's count made from the intervals before it.

    A missing count (NaN) is not available to forecast from: the last valid value is
    carried forward, and the moving average uses the valid values in its window.
    """
    seen = pd.Series(counts, dtype=float)
    known = seen.shift(1)  # what was available when the forecast was issued
    return pd.DataFrame(
        {
            "actual": seen,
            "last_value": known.ffill(),
            "moving_average": known.rolling(WINDOW, min_periods=1).mean().ffill(),
        }
    )


def mean_absolute_error(table: pd.DataFrame, column: str, rows) -> float:
    """Mean absolute error over `rows`, scored where the true count is known."""
    part = table[rows].dropna(subset=["actual", column])
    return float((part[column] - part["actual"]).abs().mean())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path, default=Path("configs/i405.yaml"))
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)
    cfg = ablation.load_config(args.config)
    cfg["ablation"]["variants"] = cfg["ablation"]["variants"][:1]  # the observed day
    variant = cfg["ablation"]["variants"][0]["id"]
    sim_cfg = ablation.build_config(cfg, ablation.historical_profile(cfg["demand"]))
    run = micro.simulate(sim_cfg, variant, "alinea", args.seed, True)
    interval = sim_cfg["detectors"]["interval_s"]
    scored_from = 3600  # 06:00: the first hour only fills the moving average

    entry = [o for o in run["observations"] if o["sensor_id"] == "ramp_entry"]
    counts = np.array([o["count"] for o in entry], dtype=float)
    start = np.array([o["interval_start_s"] for o in entry])
    table = forecasts(counts)
    late = start >= scored_from
    print(f"Ramp arrivals per {interval:g} s interval at the entry loop, from 06:00:")
    print(f"  mean count {counts[late].mean():.2f} vehicles")
    for name in ("last_value", "moving_average"):
        print(f"  {name:15s} error {mean_absolute_error(table, name, late):.2f} veh")

    # Observation defect: the entry loop reports nothing from 06:30 to 07:30.
    hidden = (start >= 5400) & (start < 9000)
    defect = forecasts(np.where(hidden, np.nan, counts))
    defect["actual"] = counts  # scored against what really arrived
    print("With the entry loop missing from 06:30 to 07:30, error in that hour:")
    for name in ("last_value", "moving_average"):
        print(f"  {name:15s} error {mean_absolute_error(defect, name, hidden):.2f} veh")

    queue = pd.DataFrame(
        run["trace"]["queue"], columns=["time_s", "true", "estimate", "ddl", "rate"]
    )
    queue = queue[queue["time_s"] >= scored_from]
    error = queue["estimate"] - queue["true"]
    ramp = cfg["micro"]["ramp"]["sections"][0]
    storage = cfg["micro"]["meter"]["stop_line_m"] * ramp["lanes"] / 8.84  # 29 ft each
    inside = queue["true"] <= storage
    print("Ramp queue estimated from the entry and passage loops, from 06:00:")
    print(
        f"  true queue: mean {queue['true'].mean():.1f}, largest {queue['true'].max()}"
    )
    print(
        f"  error, all samples: {error.abs().mean():.1f} veh (bias {error.mean():+.1f})"
    )
    print(
        f"  error while the queue fits upstream of the stop line "
        f"({100 * inside.mean():.0f} % of samples): {error[inside].abs().mean():.1f} veh"
    )
    print("Simulated, one seed; truth is used only to score.")


if __name__ == "__main__":
    main()
