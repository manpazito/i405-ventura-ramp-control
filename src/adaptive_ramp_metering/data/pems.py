"""Caltrans PeMS District Station 5-Minute acquisition and quality screening.

Authentication and resumable HTTP transfer come from the MIT-licensed `pems_data`
package (wcc961129/pems-data-downloader). This module adds the staged availability
scan, corridor extraction, per-station-day screening, period ranking, and the SI
export with a provenance manifest. Run `uv run arm-pems --help`.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pandas as pd
import yaml
from pems_data.browser import BASE_URL
from pems_data.http import ResumableDownloader, SessionExpiredError
from pems_data.metadata import read_station_records
from pems_data.planner import daily_filename, parse_remote_file

PACIFIC = ZoneInfo("America/Los_Angeles")
INTERVAL_S = 300
# First twelve columns of a Station 5-Minute text row; lane columns follow.
RAW_COLUMNS = [
    "timestamp",
    "station",
    "district",
    "freeway",
    "direction",
    "lane_type",
    "station_length",
    "samples",
    "percent_observed",
    "total_flow",
    "average_occupancy",
    "average_speed",
]
SCAN_LOG_COLUMNS = [
    "date",
    "file_name",
    "status",
    "url",
    "bytes",
    "sha256",
    "retrieved_at_utc",
    "error",
]


# --------------------------------------------------------------------------- config


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["_root"] = Path(cfg.get("data_root", "data"))
    return cfg


def stage_days(cfg: dict, stage: int) -> list[date]:
    """Weekdays inside every inclusive range of the stage, ordered and unique."""
    days: set[date] = set()
    for start, end in cfg["stages"][stage]:
        day = start
        while day <= end:
            if day.weekday() < 5:
                days.add(day)
            day += timedelta(days=1)
    return sorted(days)


def _dirs(cfg: dict) -> dict[str, Path]:
    root = cfg["_root"]
    dirs = {
        "raw": root / "raw" / "pems",
        "catalog": root / "raw" / "pems" / "catalog",
        "meta": root / "raw" / "pems" / "meta",
        "interim": root / "interim" / "pems",
        "processed": root / "processed" / "pems",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


# -------------------------------------------------------------------------- catalog


def parse_catalog(payload: dict) -> dict[str, str]:
    """Map file name -> absolute URL from a Clearinghouse JSON `data` object.

    Station archives arrive as {month: [{file_name, url}, ...]}; metadata arrives as
    {key: {format: {text: {file_name, url}}}}. Both shapes are handled.
    """
    files: dict[str, str] = {}
    for entries in payload.values():
        if isinstance(entries, dict):
            entries = [entries.get("format", {}).get("text", {})]
        if not isinstance(entries, list):
            continue
        for item in entries:
            name = item.get("file_name", "")
            if parse_remote_file(name, item.get("url", "")):
                files[name] = urljoin(BASE_URL, item["url"])
    return files


def fetch_catalog(
    downloader: ResumableDownloader,
    cfg: dict,
    year: int,
    dataset: str,
    refresh: bool = False,
) -> dict[str, str]:
    """Authenticated catalog listing for one district/year/dataset, cached on disk."""
    cache = _dirs(cfg)["catalog"] / f"d{cfg['district']:02d}_{dataset}_{year}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))["files"]
    response = downloader.session.get(
        BASE_URL,
        params={
            "srq": "clearinghouse",
            "district_id": str(cfg["district"]),
            "geotag": "",
            "yy": str(year),
            "type": dataset,
            "returnformat": "text",
        },
        timeout=cfg["download"]["timeout_s"],
    )
    response.raise_for_status()
    try:  # PeMS labels the JSON catalog text/html; a login page fails to parse
        payload = response.json()
    except ValueError:
        raise SessionExpiredError("PeMS returned a page, not the catalog") from None
    # a year with no files answers with a bare list instead of {"data": {...}}
    data = payload.get("data") if isinstance(payload, dict) else None
    files = parse_catalog(data) if isinstance(data, dict) else {}
    cache.write_text(
        json.dumps(
            {"retrieved_at_utc": _now(), "url": response.url, "files": files}, indent=1
        ),
        encoding="utf-8",
    )
    return files


def metadata_file(downloader: ResumableDownloader, cfg: dict, day: date) -> Path:
    """Latest district metadata snapshot dated on or before `day`, downloaded."""
    for year in range(day.year, day.year - 24, -1):
        listed = fetch_catalog(downloader, cfg, year, "meta")
        remotes = [parse_remote_file(name, url) for name, url in listed.items()]
        before = [r for r in remotes if r and r.file_date <= day]
        if before:
            best = max(before, key=lambda r: r.file_date)
            return downloader.download(best.url, _dirs(cfg)["meta"] / best.name)
    raise FileNotFoundError(
        f"No District {cfg['district']} metadata on or before {day}"
    )


# ------------------------------------------------------------------- scan / extract


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_log(path: Path, row: dict) -> None:
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCAN_LOG_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in SCAN_LOG_COLUMNS})


def read_scan_log(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=SCAN_LOG_COLUMNS)
    return pd.read_csv(path, dtype=str).fillna("")


def download_day(
    downloader: ResumableDownloader, cfg: dict, day: date, catalog: dict[str, str]
) -> Path | None:
    """Fetch one daily archive with retry/backoff; log outcome; None if not listed."""
    dirs = _dirs(cfg)
    log = dirs["interim"] / "scan_log.csv"
    name = daily_filename(cfg["district"], day)
    target = dirs["raw"] / name
    if name not in catalog:
        _append_log(log, {"date": day, "file_name": name, "status": "not_listed"})
        return None
    url = catalog[name]
    cached = target.exists()
    retries = cfg["download"]["retries"]
    for attempt in range(1, retries + 1):
        try:
            downloader.download(url, target)
            break
        except SessionExpiredError:
            raise
        except Exception as exc:  # network/HTTP error; retried with backoff
            if attempt == retries:
                _append_log(
                    log,
                    {
                        "date": day,
                        "file_name": name,
                        "status": "failed",
                        "url": url,
                        "error": str(exc)[:200],
                    },
                )
                return None
            time.sleep(cfg["download"]["backoff_s"] * 2 ** (attempt - 1))
    _append_log(
        log,
        {
            "date": day,
            "file_name": name,
            "status": "cached" if cached else "downloaded",
            "url": url,
            "bytes": target.stat().st_size,
            "sha256": _sha256(target),
            "retrieved_at_utc": _now(),
        },
    )
    return target


def extract_day(raw_gz: Path, station_ids: set[int], destination: Path) -> int:
    """Stream a district archive and keep rows of the given stations. Returns rows."""
    rows = 0
    # Written under another name first: scan treats an existing day file as complete.
    part = destination.with_suffix(".part")
    with (
        gzip.open(raw_gz, "rt", encoding="utf-8", newline="") as source,
        part.open("w", encoding="utf-8", newline="") as target,
    ):
        writer = csv.writer(target)
        writer.writerow([*RAW_COLUMNS, "lane_values"])
        for row in csv.reader(source):
            if len(row) >= 12 and row[1].isdigit() and int(row[1]) in station_ids:
                writer.writerow([*row[:12], "|".join(row[12:])])
                rows += 1
    part.replace(destination)
    return rows


def corridor_inventory(meta_path: Path, cfg: dict) -> pd.DataFrame:
    """Stations inside the corridor filter plus the configured IDs, with roles."""
    records = pd.DataFrame(list(read_station_records(meta_path)))
    records["station_id"] = records["station_id"].astype(int)
    for col in ("freeway", "absolute_postmile"):
        records[col] = pd.to_numeric(records[col], errors="coerce")
    cor = cfg["corridor"]
    in_corridor = (
        (records["freeway"] == cor["freeway"])
        & (records["direction"].str.upper() == cor["direction"])
        & records["absolute_postmile"].between(cor["abs_pm_min"], cor["abs_pm_max"])
    )
    configured = records["station_id"].isin([int(s) for s in cfg["stations"]])
    out = records[in_corridor | configured].copy()
    out["in_corridor_filter"] = in_corridor[out.index]
    out["role"] = (
        out["station_id"]
        .map({int(k): v["role"] for k, v in cfg["stations"].items()})
        .fillna("")
    )
    out["metadata_file"] = meta_path.name
    return out.sort_values("absolute_postmile").reset_index(drop=True)


# -------------------------------------------------------------------------- screen


def expected_intervals(day: date) -> int:
    start = datetime.combine(day, datetime.min.time(), PACIFIC)
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), PACIFIC)
    return int((end - start).total_seconds() // INTERVAL_S)


def screen_day(frame: pd.DataFrame, day: date, thresholds: dict) -> pd.DataFrame:
    """Per-station quality metrics for one day of extracted rows (source units)."""
    expected = expected_intervals(day)
    numeric = ["percent_observed", "total_flow", "average_occupancy", "average_speed"]
    frame = frame.copy()
    for col in numeric:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    out = []
    for station, g in frame.groupby("station", sort=True):
        g = g.sort_values("timestamp")
        obs = g["percent_observed"].fillna(0)
        flow = g["total_flow"]
        run = (flow != flow.shift()).cumsum()
        stuck = flow[flow > 0].groupby(run).size().max() if (flow > 0).any() else 0
        metrics = {
            "station": int(station),
            "date": day,
            "lane_type": g["lane_type"].iloc[0],
            "expected_intervals": expected,
            "available_records": len(g),
            "duplicate_timestamps": int(g["timestamp"].duplicated().sum()),
            "missing_pct": round(100 * max(expected - len(g), 0) / expected, 2),
            "mean_observed_pct": round(obs.mean(), 2) if len(g) else None,
            "pct_intervals_ge90": round(100 * (obs >= 90).sum() / expected, 2),
            "flow_reported": int(flow.notna().sum()),
            "speed_reported": int(g["average_speed"].notna().sum()),
            "occupancy_reported": int(g["average_occupancy"].notna().sum()),
            "flow_observed": int((flow.notna() & (obs > 0)).sum()),
            "zero_flow_unobserved": int(((flow == 0) & (obs == 0)).sum()),
            "negative_values": int((g[numeric] < 0).any(axis=1).sum()),
            "occupancy_out_of_range": int(
                (
                    ~g["average_occupancy"].between(0, 1)
                    & g["average_occupancy"].notna()
                ).sum()
            ),
            "speed_above_max": int(
                (g["average_speed"] > thresholds["max_speed_mph"]).sum()
            ),
            "longest_stuck_flow_run": int(stuck),
        }
        metrics["suspicious"] = bool(
            metrics["negative_values"]
            or metrics["occupancy_out_of_range"]
            or metrics["speed_above_max"]
            or metrics["duplicate_timestamps"]
            or metrics["longest_stuck_flow_run"] >= thresholds["stuck_run_intervals"]
        )
        metrics["meets_thresholds"] = bool(
            len(g)
            and metrics["mean_observed_pct"] >= thresholds["min_mean_observed_pct"]
            and metrics["pct_intervals_ge90"] >= thresholds["min_pct_intervals_ge90"]
            and metrics["missing_pct"] <= thresholds["max_missing_pct"]
        )
        out.append(metrics)
    return pd.DataFrame(out)


def empty_day(day: date, cfg: dict) -> pd.DataFrame:
    """Screening rows for a day whose archive has no rows for the configured stations."""
    return pd.DataFrame(
        [
            {
                "station": s,
                "date": day,
                "lane_type": "",
                "available_records": 0,
                "mean_observed_pct": None,
                "pct_intervals_ge90": 0.0,
                "suspicious": False,
                "meets_thresholds": False,
            }
            for s in sorted(int(x) for x in cfg["stations"])
        ]
    )


def _upsert(path: Path, new: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if path.exists():
        old = pd.read_csv(path)
        old["date"] = pd.to_datetime(old["date"]).dt.date
        new = pd.concat([old, new]).drop_duplicates(keys, keep="last")
    new = new.sort_values(keys).reset_index(drop=True)
    new.to_csv(path, index=False)
    return new


# ---------------------------------------------------------------------------- rank


def rank_periods(
    screening: pd.DataFrame, cfg: dict
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(periods, days): periods are runs of consecutive weekdays with equal status."""
    roles = {int(k): v["role"] for k, v in cfg["stations"].items()}
    required = set(cfg["thresholds"]["required_roles"])
    incidents = set(cfg.get("incident_dates") or [])
    s = screening.copy()
    s["date"] = pd.to_datetime(s["date"]).dt.date
    s["role"] = s["station"].map(roles).fillna("")
    s["lane_type"] = s["lane_type"].fillna("")  # empty-day rows read back from CSV
    days = []
    for day, g in s.groupby("date", sort=True):
        req = g[g["role"].isin(required)]
        present = set(req["role"])
        ok = present == required and bool(req["meets_thresholds"].all())
        days.append(
            {
                "date": day,
                "weekday": day.strftime("%a"),
                "qualifies": ok,
                "station_ids": ",".join(str(x) for x in sorted(g["station"])),
                "station_types": ",".join(g.sort_values("station")["lane_type"]),
                "min_mean_observed_pct": req["mean_observed_pct"].min(),
                "min_pct_intervals_ge90": req["pct_intervals_ge90"].min(),
                # ramps report no speed; require it from mainline stations only
                "flow_speed_occ_available": bool(
                    (req[["flow_reported", "occupancy_reported"]] > 0).all(axis=None)
                    and (req.loc[req["lane_type"] == "ML", "speed_reported"] > 0).all()
                ),
                "missing_required_roles": ",".join(sorted(required - present)),
                "suspicious_stations": ",".join(
                    str(x) for x in g.loc[g["suspicious"], "station"]
                ),
                "incident_reported": day in incidents,
            }
        )
    periods = []
    for d in days:
        prev = periods[-1] if periods else None
        gap = (d["date"] - prev["end_date"]).days if prev else 0
        # consecutive weekday: next day, or Friday -> Monday
        consecutive = gap == 1 or (gap == 3 and d["date"].weekday() == 0)
        if (
            prev
            and consecutive
            and prev["qualifies"] == d["qualifies"]
            and prev["station_ids"] == d["station_ids"]
        ):
            prev["end_date"] = d["date"]
            prev["n_days"] += 1
            prev["min_mean_observed_pct"] = min(
                prev["min_mean_observed_pct"], d["min_mean_observed_pct"]
            )
            prev["min_pct_intervals_ge90"] = min(
                prev["min_pct_intervals_ge90"], d["min_pct_intervals_ge90"]
            )
            prev["incident_days"] += int(d["incident_reported"])
            prev["flow_speed_occ_available"] &= d["flow_speed_occ_available"]
        else:
            periods.append(
                {
                    "start_date": d["date"],
                    "end_date": d["date"],
                    "n_days": 1,
                    "qualifies": d["qualifies"],
                    "station_ids": d["station_ids"],
                    "station_types": d["station_types"],
                    "min_mean_observed_pct": d["min_mean_observed_pct"],
                    "min_pct_intervals_ge90": d["min_pct_intervals_ge90"],
                    "flow_speed_occ_available": d["flow_speed_occ_available"],
                    "incident_days": int(d["incident_reported"]),
                    "missing_required_roles": d["missing_required_roles"],
                }
            )
    out = pd.DataFrame(periods)
    out = out.sort_values(
        ["qualifies", "n_days", "min_mean_observed_pct"], ascending=[False] * 3
    ).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out, pd.DataFrame(days)


def rank_weeks(screening: pd.DataFrame, cfg: dict, length: int = 7) -> pd.DataFrame:
    """Rolling calendar windows with every day screened, scored on the on-ramp first."""
    roles = {int(k): v["role"] for k, v in cfg["stations"].items()}
    incidents = set(cfg.get("incident_dates") or [])
    s = screening.copy()
    s["date"] = pd.to_datetime(s["date"]).dt.date
    s["role"] = s["station"].map(roles)
    ramp = s[s["role"] == "on_ramp"].set_index("date")
    main = s[s["role"] == "mainline"].set_index("date")
    rows = []
    for start in sorted(ramp.index):
        window = [start + timedelta(days=i) for i in range(length)]
        if any(d not in ramp.index for d in window):
            continue
        r, m = ramp.loc[window], main.reindex(window)
        rows.append(
            {
                "start_date": start,
                "end_date": window[-1],
                "ramp_days_passing": int(r["meets_thresholds"].sum()),
                "ramp_min_observed_pct": r["mean_observed_pct"].min(),
                "ramp_mean_observed_pct": round(r["mean_observed_pct"].mean(), 2),
                "ramp_min_pct_intervals_ge90": r["pct_intervals_ge90"].min(),
                "ramp_suspicious_days": int(r["suspicious"].sum()),
                "mainline_days_passing": int(m["meets_thresholds"].fillna(False).sum()),
                "mainline_mean_observed_pct": round(m["mean_observed_pct"].mean(), 2),
                "incident_days": sum(d in incidents for d in window),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.sort_values(
        [
            "ramp_days_passing",
            "ramp_min_observed_pct",
            "ramp_mean_observed_pct",
            "mainline_days_passing",
        ],
        ascending=False,
    ).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out


# -------------------------------------------------------------------------- export


def to_si(frame: pd.DataFrame) -> pd.DataFrame:
    """Source-unit rows -> SI exchange rows. PeMS timestamps label interval starts."""
    out = pd.DataFrame()
    start = pd.to_datetime(frame["timestamp"], format="%m/%d/%Y %H:%M:%S")
    start = start.dt.tz_localize(PACIFIC, ambiguous="NaT", nonexistent="NaT")
    out["interval_start_utc"] = start.dt.tz_convert("UTC")
    out["interval_end_utc"] = out["interval_start_utc"] + pd.Timedelta(
        seconds=INTERVAL_S
    )
    out["source_timestamp_local"] = frame["timestamp"].values
    out["sensor_id"] = frame["station"].astype(int).values
    out["lane_type"] = frame["lane_type"].values
    count = pd.to_numeric(frame["total_flow"], errors="coerce")
    out["count"] = count.values
    out["flow_veh_per_s"] = (count / INTERVAL_S).values
    speed_mph = pd.to_numeric(frame["average_speed"], errors="coerce")
    out["mean_speed_mps"] = (speed_mph * 0.44704).values
    out["occupancy_fraction"] = pd.to_numeric(
        frame["average_occupancy"], errors="coerce"
    ).values
    obs = pd.to_numeric(frame["percent_observed"], errors="coerce").fillna(0)
    out["observed_fraction"] = (obs / 100).values
    out["quality_flag"] = (
        pd.Series(
            [
                "observed" if o == 100 else "partially_observed" if o > 0 else "imputed"
                for o in obs
            ],
        )
        .where(count.notna().values, "missing")
        .values
    )
    out["samples"] = frame["samples"].values
    return out


def export_dataset(cfg: dict, start: date, end: date, revision: int) -> Path:
    dirs = _dirs(cfg)
    ids = sorted(int(s) for s in cfg["stations"])
    frames, sources = [], []
    log = read_scan_log(dirs["interim"] / "scan_log.csv")
    day = start
    while day <= end:
        interim = dirs["interim"] / f"station_5min_{day:%Y_%m_%d}.csv"
        if interim.exists():
            df = pd.read_csv(interim, dtype=str)
            frames.append(df[df["station"].astype(int).isin(ids)])
            name = daily_filename(cfg["district"], day)
            rows = log[
                (log["file_name"] == name)
                & log["status"].isin(["downloaded", "cached"])
            ]
            if not rows.empty:
                sources.append(rows.iloc[-1].to_dict())
        day += timedelta(days=1)
    if not frames:
        raise FileNotFoundError("No extracted days in range; run `scan` first")
    dataset_id = f"observed_pems_ventura_{start:%Y%m%d}_{end:%Y%m%d}_5min_v{revision}"
    out_path = dirs["processed"] / f"{dataset_id}.csv"
    si = to_si(pd.concat(frames)).sort_values(["sensor_id", "interval_start_utc"])
    si.to_csv(out_path, index=False)
    try:
        code_version = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        code_version = "unknown"
    manifest = {
        "dataset_id": dataset_id,
        "source_id": "pems_mainline+pems_ramp",
        "agency": "Caltrans PeMS Data Clearinghouse, District 7 Station 5-Minute",
        "data_origin": "observed (PeMS-imputed values retained and flagged)",
        "coverage_local_dates": [str(start), str(end)],
        "station_ids": ids,
        "station_roles": {str(k): v for k, v in cfg["stations"].items()},
        "source_timezone": "America/Los_Angeles; source timestamp labels interval start",
        "interval": "[start, end) 300 s",
        "units": {
            "count": "veh per 5 min (source Total Flow)",
            "flow_veh_per_s": "count / 300",
            "mean_speed_mps": "source Avg Speed mph * 0.44704; PeMS flow-weighted",
            "occupancy_fraction": "source Avg Occupancy (fraction) unchanged",
            "observed_fraction": "source % Observed / 100",
        },
        "quality_flag": "observed=100% observed; partially_observed; imputed=0% "
        "observed but value reported; missing=no value",
        "output_file": str(out_path),
        "output_sha256": _sha256(out_path),
        "output_rows": int(len(si)),
        "source_files": sources,
        "config_snapshot": {k: v for k, v in cfg.items() if not k.startswith("_")},
        "code_version": code_version,
        "created_at_utc": _now(),
        "license_note": "Caltrans data terms apply; session cookies never stored here",
        "split_assignment": "unassigned",
    }
    manifest_dir = Path("data/manifests")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / f"{dataset_id}.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    return out_path


# ----------------------------------------------------------------------------- CLI


def cmd_inventory(cfg: dict, args) -> None:
    dl = ResumableDownloader(Path(cfg["session_file"]))
    meta = metadata_file(dl, cfg, args.date)
    inventory = corridor_inventory(meta, cfg)
    out = _dirs(cfg)["processed"] / "detector_inventory.csv"
    inventory.to_csv(out, index=False)
    print(inventory.to_string(index=False))
    missing = set(int(s) for s in cfg["stations"]) - set(inventory["station_id"])
    print(f"\nWrote {out} ({len(inventory)} stations, metadata {meta.name})")
    if missing:
        print(f"WARNING configured stations absent from metadata: {sorted(missing)}")


def cmd_scan(cfg: dict, args) -> None:
    dirs = _dirs(cfg)
    dl = ResumableDownloader(
        Path(cfg["session_file"]), timeout=cfg["download"]["timeout_s"]
    )
    days = stage_days(cfg, args.stage) if args.stage else args.dates
    log = read_scan_log(dirs["interim"] / "scan_log.csv")
    skip = (
        set(log.loc[log["status"] == "not_listed", "date"])
        if not args.retry_missing
        else set()
    )
    for day in days:
        interim = dirs["interim"] / f"station_5min_{day:%Y_%m_%d}.csv"
        if str(day) in skip:
            print(f"{day}: previously not listed, skipping (use --retry-missing)")
            continue
        if not interim.exists():
            catalog = fetch_catalog(
                dl, cfg, day.year, "station_5min", args.refresh_catalog
            )
            raw = download_day(dl, cfg, day, catalog)
            if raw is None:
                print(f"{day}: archive not available (see scan_log.csv)")
                continue
            meta = metadata_file(dl, cfg, day)
            ids = set(corridor_inventory(meta, cfg)["station_id"])
            rows = extract_day(raw, ids, interim)
            print(f"{day}: extracted {rows} corridor rows from {raw.name}")
        frame = pd.read_csv(interim, dtype=str)
        screened = screen_day(frame, day, cfg["thresholds"])
        if screened.empty:
            screened = empty_day(day, cfg)
        _upsert(
            dirs["processed"] / "quality_screening.csv", screened, ["station", "date"]
        )
        print(
            screened[
                [
                    "station",
                    "lane_type",
                    "available_records",
                    "mean_observed_pct",
                    "pct_intervals_ge90",
                    "meets_thresholds",
                ]
            ].to_string(index=False)
        )


def cmd_rank(cfg: dict, args) -> None:
    dirs = _dirs(cfg)
    screening = pd.read_csv(dirs["processed"] / "quality_screening.csv")
    periods, days = rank_periods(screening, cfg)
    periods.to_csv(dirs["processed"] / "candidate_periods.csv", index=False)
    days.to_csv(dirs["processed"] / "candidate_days.csv", index=False)
    weeks = rank_weeks(screening, cfg)
    weeks.to_csv(dirs["processed"] / "candidate_weeks.csv", index=False)
    print(periods.to_string(index=False))
    print("\nBest 7-day windows (on-ramp first):")
    print(weeks.head(10).to_string(index=False))


def cmd_export(cfg: dict, args) -> None:
    out = export_dataset(cfg, args.start, args.end, args.revision)
    print(f"Wrote {out}; manifest in data/manifests/")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="arm-pems", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/pems.yaml"))
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory", help="corridor detector inventory from metadata")
    inv.add_argument("--date", type=date.fromisoformat, default=date(2022, 10, 17))
    scan = sub.add_parser("scan", help="download, extract and screen configured days")
    scan.add_argument("--stage", type=int)
    scan.add_argument("--dates", type=date.fromisoformat, nargs="*", default=[])
    scan.add_argument("--retry-missing", action="store_true")
    scan.add_argument("--refresh-catalog", action="store_true")
    sub.add_parser("rank", help="rank candidate periods from quality_screening.csv")
    exp = sub.add_parser(
        "export", help="write SI dataset and manifest for a date range"
    )
    exp.add_argument("--start", type=date.fromisoformat, required=True)
    exp.add_argument("--end", type=date.fromisoformat, required=True)
    exp.add_argument("--revision", type=int, default=1)
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    if args.command in ("inventory", "scan") and not Path(cfg["session_file"]).exists():
        sys.exit(
            f"No PeMS session at {cfg['session_file']}. Once: `uv run playwright "
            "install chromium`; then `uv run pems-data auth` and log in."
        )
    try:
        {
            "inventory": cmd_inventory,
            "scan": cmd_scan,
            "rank": cmd_rank,
            "export": cmd_export,
        }[args.command](cfg, args)
    except SessionExpiredError as exc:
        sys.exit(f"{exc}\nRun `uv run pems-data auth` to refresh the PeMS session.")
    except FileNotFoundError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
