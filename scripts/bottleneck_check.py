"""Is the Ventura merge an active bottleneck, or inside a queue from downstream?

Lane-level redo of the mid-report's station-level check (an earlier script, not kept) for the ramp/mainline mix study
(experiments/ramp_mainline_mix.md). It reads PeMS Station 5-Minute archives, because Royal Ridge lies outside the
corridor extract, and uses observed lanes only. By default it reads the copies in
`data/interim/pems/bottleneck/` (the eight archives cut to the six stations used,
rows unchanged; see data/README.md); the full archives give the same table.

    uv run python scripts/bottleneck_check.py
    uv run python scripts/bottleneck_check.py --raw data/raw/pems --dates 2022-10-11

Bottleneck test of Chen, Skabardonis and Varaiya (2004): a bottleneck is active between
two stations at most 2 mi apart when the upstream speed is below 40 mph and at least
20 mph below the downstream speed, in 5 of 7 consecutive 5-minute intervals.
Shockwave speed (Lecture 03): the boundary between two states moves at
(q_A - q_B) / (k_A - k_B). Station identities, lanes and postmiles come from the PeMS
metadata snapshot of 2022-07-15; reported speeds enter the densities as published.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DAYS = [f"2022-10-{d}" for d in ("03", "10", "11", "12", "14", "24", "25", "28")]
# I-405 S mainline, upstream to downstream: (station, lanes, miles downstream of Ventura).
STATIONS = {
    "burbank1": (765171, 4, -0.91),
    "north_of_101": (777066, 3, -0.41),
    "ventura": (717816, 5, 0.0),
    "woodcrest": (764754, 6, 0.95),
    "royal_ridge": (717807, 5, 1.52),
}
RAMP, SHOULDER_LANE = 716744, 5
MPH = 0.44704  # m/s per mph
CONGESTED_MPH = 20.0 / MPH  # the project's 20 m/s line (D016)
EFFECTIVE_LENGTH_M = 5.0 + 1.83  # vehicle + loop, as in configs/i405.yaml [assumed]


def observed_lanes(rows: pd.DataFrame) -> pd.DataFrame:
    """Speed (mph), flow (veh/h per lane) and occupancy over the observed lanes only.

    `rows` holds raw archive columns by position: five per lane from column 12 on
    (samples, flow, occupancy, speed, observed).
    """

    def field(k: int) -> np.ndarray:
        lanes = [pd.to_numeric(rows[12 + 5 * i + k], errors="coerce") for i in range(8)]
        return np.stack(lanes, axis=1)

    flow, occupancy, speed = field(1), field(2), field(3)
    seen = (field(4) == 1) & ~np.isnan(speed)
    weight = np.where(seen, np.nan_to_num(flow), 0.0)
    count = seen.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return pd.DataFrame(
            {
                "lanes_observed": count,
                "mph": (np.nan_to_num(speed) * weight).sum(axis=1) / weight.sum(axis=1),
                "veh_h_lane": 12 * weight.sum(axis=1) / count,
                "occupancy": np.where(seen, occupancy, 0.0).sum(axis=1) / count,
                "shoulder_veh_h": 12 * flow[:, SHOULDER_LANE - 1],
            },
            index=rows.index,
        )


def onset(mph: pd.Series) -> pd.Timestamp | None:
    """Start of the first three consecutive intervals below the congestion line."""
    slow = (mph < CONGESTED_MPH).rolling(3).sum() == 3
    return (
        slow.index[slow.to_numpy()][0] - pd.Timedelta(minutes=10)
        if slow.any()
        else None
    )


def chen_active(upstream: pd.Series, downstream: pd.Series) -> tuple[pd.Series, bool]:
    """Intervals meeting the speed criteria, and whether 5 of 7 consecutive ones do."""
    hit = (upstream < 40) & (downstream - upstream > 20)
    return hit, bool((hit.rolling(7).sum() >= 5).any())


def shockwave(q_a: float, k_a: float, q_b: float, k_b: float) -> float:
    """Speed of the boundary between states A and B: change of flow over change of density."""
    return (q_a - q_b) / (k_a - k_b)


def check_day(raw: Path, date: str) -> dict:
    archive = raw / f"d07_text_station_5min_{date.replace('-', '_')}.txt.gz"
    wanted = [s for s, _, _ in STATIONS.values()] + [RAMP]
    parts = [
        chunk[chunk[1].isin(wanted)]
        for chunk in pd.read_csv(
            archive, header=None, names=range(52), chunksize=300_000, low_memory=False
        )
    ]
    day = pd.concat(parts)
    day.index = pd.to_datetime(day[0], format="%m/%d/%Y %H:%M:%S")
    lanes = {
        name: observed_lanes(day[day[1] == station]).sort_index()
        for name, (station, _, _) in STATIONS.items()
    }
    ramp = 12 * pd.to_numeric(day[day[1] == RAMP][9]).sort_index()
    if len(ramp) != 288 or any(len(frame) != 288 for frame in lanes.values()):
        raise ValueError(f"{date}: a station is missing 5-minute intervals")
    row = {"date": date}
    morning = {k: v.between_time("04:30", "10:55") for k, v in lanes.items()}
    for name in ("burbank1", "ventura", "woodcrest", "royal_ridge"):
        start = onset(morning[name]["mph"])
        row[f"onset_{name}"] = "" if start is None else f"{start:%H:%M}"
        row[f"lanes_{name}"] = int(lanes[name]["lanes_observed"].median())
    test = {k: v.between_time("06:00", "09:55")["mph"] for k, v in lanes.items()}
    for name in ("woodcrest", "royal_ridge"):
        hit, sustained = chen_active(test["ventura"], test[name])
        row[f"chen_intervals_{name}"] = int(hit.sum())
        last = hit.index[hit.to_numpy()]
        row[f"chen_last_{name}"] = f"{last[-1]:%H:%M}" if len(last) else ""
        row[f"chen_active_{name}"] = sustained
    peak = {k: v.between_time("07:00", "08:55") for k, v in lanes.items()}
    ventura = peak["ventura"]
    row["ventura_veh_h"] = STATIONS["ventura"][1] * ventura["veh_h_lane"].mean()
    row["ventura_mph"] = ventura["mph"].mean()
    row["royal_ridge_mph"] = peak["royal_ridge"]["mph"].mean()
    row["shoulder_veh_h"] = ventura["shoulder_veh_h"].mean()
    row["ramp_veh_h"] = ramp.between_time("07:00", "08:55").mean()
    row["ramp_per_shoulder"] = row["ramp_veh_h"] / row["shoulder_veh_h"]
    upstream = day[day[1] == STATIONS["north_of_101"][0]].between_time("07:00", "08:55")
    row["n101_reported_mph"] = pd.to_numeric(upstream[11]).mean()
    row["n101_implied_mph"] = (
        peak["north_of_101"]["veh_h_lane"].mean()
        / 3600
        * EFFECTIVE_LENGTH_M
        / peak["north_of_101"]["occupancy"].mean()
        / MPH
    )
    # Shockwave between the 15 minutes before Ventura's onset and the peak (per lane).
    start = onset(morning["ventura"]["mph"])
    if start is not None:
        before = lanes["ventura"][start - pd.Timedelta(minutes=15) : start].iloc[:3]
        q_a, q_b = before["veh_h_lane"].mean(), ventura["veh_h_lane"].mean()
        wave = shockwave(  # densities from q = u k
            q_a, q_a / before["mph"].mean(), q_b, q_b / ventura["mph"].mean()
        )
        row["shockwave_mph"] = wave
        row["wave_min_from_royal_ridge"] = 60 * STATIONS["royal_ridge"][2] / abs(wave)
    return row


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--raw", type=Path, default=Path("data/interim/pems/bottleneck")
    )
    parser.add_argument("--dates", nargs="+", default=DAYS)
    parser.add_argument(
        "--out", type=Path, default=Path("data/processed/pems/bottleneck_check.csv")
    )
    args = parser.parse_args(argv)
    table = pd.DataFrame([check_day(args.raw, date) for date in args.dates])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.out, index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(table.round(2).T.to_string(header=False))
    print(f"PeMS observations, not simulation: {args.out}")


if __name__ == "__main__":
    main()
