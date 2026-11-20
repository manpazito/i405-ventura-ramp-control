"""Synthetic microscopic ramp-metering prototype; equations and limits in docs/micro_demo.md.

IDM car following with optional per-driver values, mandatory lane changes with the
MOBIL safety criterion, Poisson boundary arrivals, a one-vehicle-per-green meter,
virtual point detectors, bounded feedback control and a D/D/1 vertical-queue reference
for the metered ramp.
"""

import argparse
import bisect
import csv
import hashlib
import json
import math
import platform
import shutil
import subprocess
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from statistics import NormalDist

import matplotlib
import numpy as np
import yaml
from scipy.optimize import brentq

from adaptive_ramp_metering.control.metering import decide


def _fields(value, names: str, context: str) -> None:
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError(f"{context}: expected fields {names}")


def _number(value, name: str, *, zero: bool = False) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (value < 0 if zero else value <= 0)
    ):
        raise ValueError(
            f"{name}: expected a finite {'nonnegative' if zero else 'positive'} number"
        )
    return float(value)


def _multiple(value: float, unit: float, name: str) -> int:
    ratio = value / unit
    if not math.isclose(ratio, round(ratio), abs_tol=1e-9, rel_tol=0):
        raise ValueError(f"{name} must be a multiple of {unit}")
    return round(ratio)


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CONTROLLERS = ("none", "fixed", "alinea")
MAX_DECEL_MPS2 = 8.8  # tyre-road friction, about 0.9 g on dry pavement (D017) [assumed]
LANE_COLORS = {
    "ramp_0": "#2a78d6",
    "ramp_1": "#eb6834",
    "ramp_2": "#1baf7a",
    "freeway_0": "#eda100",
}


# vehicle.spread key -> the Driver field it varies; also the order of the draws.
SPREAD = {
    "v0": "v0_factor",
    "time_gap": "time_gap_s",
    "a": "a_mps2",
    "b": "b_mps2",
    "s0": "s0_m",
    "b_safe": "b_safe_factor",
}
NORMAL = NormalDist()
# Shapes built on a normal are truncated at two standard deviations (TAIL is cut from
# each side), which leaves a standard normal with the standard deviation TRUNC_SD.
TAIL = NORMAL.cdf(-2)
TRUNC_SD = math.sqrt(1 - 4 * NORMAL.pdf(2) / (1 - 2 * TAIL))


def _z(u: float) -> float:
    """Percentile u of a standard normal truncated at two standard deviations."""
    return NORMAL.inv_cdf(TAIL + (1 - 2 * TAIL) * u)


@cache
def _lognormal(cv: float) -> tuple[float, float]:
    """sigma and mean of exp(sigma z), z as in _z, with coefficient of variation cv."""

    def moment(t: float) -> float:  # E[exp(t z)]
        span = NORMAL.cdf(2 - t) - NORMAL.cdf(-2 - t)
        return math.exp(t * t / 2) * span / (1 - 2 * TAIL)

    sigma = brentq(lambda s: moment(2 * s) / moment(s) ** 2 - 1 - cv * cv, 1e-9, 5)
    return sigma, moment(sigma)


# vehicle.shape -> factor on the fixed value at percentile u. Every shape has mean 1 and
# coefficient of variation cv exactly, so shapes differ only in symmetry and tails.
SHAPES = {
    "normal": lambda cv, u: 1 + cv * _z(u) / TRUNC_SD,
    "uniform": lambda cv, u: 1 + cv * math.sqrt(3) * (2 * u - 1),
    "lognormal": lambda cv, u: math.exp(_lognormal(cv)[0] * _z(u)) / _lognormal(cv)[1],
}


@dataclass(frozen=True, slots=True)
class Driver:
    """One driver's own IDM values, kept for the whole trip (docs/micro_demo.md)."""

    a_mps2: float
    b_mps2: float
    time_gap_s: float
    s0_m: float
    delta: float
    v0_factor: float = 1.0  # own desired speed = this x the section's desired speed
    b_safe_factor: float = 1.0  # own merging limit = this x lane_change.b_safe_mps2

    @classmethod
    def sample(
        cls, idm: dict, spread: dict, shape, rng: np.random.Generator
    ) -> "Driver":
        """Draw each value around its fixed one: mean fixed, sd spread x fixed.

        `shape` names one of SHAPES for all parameters or maps parameters to one
        (normal when not listed). A driver has one percentile per parameter, drawn
        whatever the spread and shape: varying one parameter never changes another's
        values, and a driver keeps their rank in the population under every shape.
        """
        typical = cls(**idm)
        if isinstance(shape, str):
            shape = dict.fromkeys(SPREAD, shape)
        percentiles = rng.random(len(SPREAD)).tolist()
        own = {
            field: getattr(typical, field)
            * SHAPES[shape.get(key, "normal")](spread[key], u)
            for (key, field), u in zip(SPREAD.items(), percentiles)
            if spread.get(key)
        }
        return replace(typical, **own)

    def acceleration(self, v, v0, gap, dv):
        """Treiber, Hennecke and Helbing (2000); gap must be positive, dv = v - v_leader.

        `v0` is the driver's desired speed where they are (Simulation.desired_speed).
        """
        s_star = self.s0_m + np.maximum(
            0.0,
            v * self.time_gap_s + v * dv / (2 * np.sqrt(self.a_mps2 * self.b_mps2)),
        )
        return self.a_mps2 * (1 - (v / v0) ** self.delta - (s_star / gap) ** 2)


@dataclass(slots=True)
class Vehicle:
    vid: int
    lane: int
    x: float
    v: float
    length: float
    origin: str
    driver: Driver
    released: bool = False
    acc: float = 0.0
    leader: "Vehicle | None" = None  # effective leader from the last step


def validate_config(cfg: dict) -> None:
    _fields(
        cfg,
        "schema_version duration_s step_s snapshot_interval_s seeds vehicle lane_change "
        "ramp mainline meter detectors control scenarios",
        "config",
    )
    if cfg["schema_version"] != "ramp-micro-v1":
        raise ValueError("schema_version must be ramp-micro-v1")
    h = _number(cfg["step_s"], "step_s")
    if h > 1:
        raise ValueError("step_s must not exceed 1 s for the ballistic IDM step")
    for key in ("duration_s", "snapshot_interval_s"):
        _multiple(_number(cfg[key], key), h, key)
    seeds = cfg["seeds"]
    if (
        not isinstance(seeds, list)
        or not seeds
        or any(type(s) is not int for s in seeds)
    ):
        raise ValueError("seeds must be a nonempty list of integers")
    optional = [k for k in ("spread", "shape") if k in cfg["vehicle"]]
    _fields(cfg["vehicle"], " ".join(["length_m idm", *optional]), "vehicle")
    cvs, shape = cfg["vehicle"].get("spread", {}), cfg["vehicle"].get("shape", {})
    if isinstance(shape, str):
        shape = dict.fromkeys(SPREAD, shape)
    if not isinstance(cvs, dict) or not set(cvs) <= set(SPREAD):
        raise ValueError(f"vehicle.spread: expected fields among {' '.join(SPREAD)}")
    if (
        not isinstance(shape, dict)
        or not set(shape) <= set(SPREAD)
        or any(not isinstance(s, str) or s not in SHAPES for s in shape.values())
    ):
        raise ValueError(
            f"vehicle.shape: expected {', '.join(SHAPES)} for fields among "
            + " ".join(SPREAD)
        )
    for key, value in cvs.items():
        cv = _number(value, f"spread.{key}", zero=True)
        if cv >= 1 or cv and SHAPES[shape.get(key, "normal")](cv, 0.0) <= 0:
            raise ValueError(
                f"vehicle.spread.{key}: too wide, a driver's value must stay positive"
            )
    _number(cfg["vehicle"]["length_m"], "length_m")
    _fields(cfg["vehicle"]["idm"], "a_mps2 b_mps2 time_gap_s s0_m delta", "idm")
    for key, value in cfg["vehicle"]["idm"].items():
        _number(value, key)
    _fields(cfg["lane_change"], "zone_m b_safe_mps2", "lane_change")
    for key, value in cfg["lane_change"].items():
        _number(value, key)
    _fields(cfg["ramp"], "sections", "ramp")
    sections = cfg["ramp"]["sections"]
    if not isinstance(sections, list) or not sections:
        raise ValueError("ramp.sections must be a nonempty list")
    lanes = []
    for section in sections:
        _fields(section, "id lanes length_m desired_speed_mps", "ramp section")
        if type(section["lanes"]) is not int or not 1 <= section["lanes"] <= 3:
            raise ValueError("ramp lanes must be integers from 1 to 3")
        lanes.append(section["lanes"])
        _number(section["length_m"], "length_m")
        _number(section["desired_speed_mps"], "desired_speed_mps")
    if lanes != sorted(lanes, reverse=True) or lanes[-1] != 1:
        raise ValueError("ramp lane counts must be nonincreasing and end with one lane")
    ramp_length = sum(s["length_m"] for s in sections)
    _fields(
        cfg["mainline"],
        "upstream_length_m downstream_length_m desired_speed_mps",
        "mainline",
    )
    for key, value in cfg["mainline"].items():
        _number(value, key)
    _fields(cfg["meter"], "stop_line_m release_window_m", "meter")
    stop = _number(cfg["meter"]["stop_line_m"], "stop_line_m")
    _number(cfg["meter"]["release_window_m"], "release_window_m")
    if stop >= ramp_length:
        raise ValueError("meter.stop_line_m must lie on the ramp")
    det = cfg["detectors"]
    optional = [k for k in ("mainline_upstream_m", "loop_length_m") if k in det]
    _fields(
        det,
        " ".join(["interval_s ramp_entry_m meter_passage_m merge_area_m", *optional]),
        "detectors",
    )
    if "loop_length_m" in det:
        _number(det["loop_length_m"], "loop_length_m", zero=True)
    _multiple(_number(det["interval_s"], "interval_s"), h, "interval_s")
    for key in ("ramp_entry_m", "meter_passage_m"):
        if not 0 < _number(det[key], key) < ramp_length:
            raise ValueError(f"{key} must lie on the ramp")
    for key in ("merge_area_m", "mainline_upstream_m"):
        point = det.get(key, 0)
        if (
            isinstance(point, bool)
            or not isinstance(point, (int, float))
            or not (
                -cfg["mainline"]["upstream_length_m"]
                < point
                < cfg["mainline"]["downstream_length_m"]
            )
        ):
            raise ValueError(
                f"{key} must lie on the modeled freeway lane, relative to the merge point"
            )
    ctrl = cfg["control"]
    _fields(
        ctrl,
        "interval_s min_rate_veh_per_s max_rate_veh_per_s fixed_rate_veh_per_s alinea "
        "queue_target_veh fault_hold_s" + (" caltrans" if "caltrans" in ctrl else ""),
        "control",
    )
    if "caltrans" in ctrl:
        plan = ctrl["caltrans"]
        _fields(
            plan,
            "metered_lanes levels occupancy rate_veh_per_h_per_lane queue_occupancy "
            "queue_step_veh_per_h_per_lane",
            "caltrans",
        )
        pairs = [plan["occupancy"], plan["rate_veh_per_h_per_lane"]]
        if any(not isinstance(pair, list) or len(pair) != 2 for pair in pairs):
            raise ValueError("caltrans occupancy and rate must be [first, last] pairs")
        for value in (*pairs[0], *pairs[1], plan["queue_occupancy"]):
            _number(value, "caltrans plan value")
        _number(plan["queue_step_veh_per_h_per_lane"], "queue_step", zero=True)
        if (
            type(plan["metered_lanes"]) is not int
            or plan["metered_lanes"] < 1
            or type(plan["levels"]) is not int
            or plan["levels"] < 2
            or not pairs[0][0] < pairs[0][1] <= 1
            or not pairs[1][0] > pairs[1][1]
            or "mainline_upstream_m" not in det
        ):
            raise ValueError(
                "caltrans plan needs >= 2 levels, rising occupancy, falling rates and "
                "detectors.mainline_upstream_m"
            )
    _multiple(
        _number(ctrl["interval_s"], "interval_s"),
        det["interval_s"],
        "control interval_s",
    )
    for key in (
        "min_rate_veh_per_s",
        "max_rate_veh_per_s",
        "fixed_rate_veh_per_s",
        "queue_target_veh",
        "fault_hold_s",
    ):
        _number(ctrl[key], key)
    if (
        not ctrl["min_rate_veh_per_s"]
        <= ctrl["fixed_rate_veh_per_s"]
        <= ctrl["max_rate_veh_per_s"]
    ):
        raise ValueError("fixed rate must lie within the rate bounds")
    _fields(ctrl["alinea"], "gain_veh_per_s_per_occupancy target_occupancy", "alinea")
    _number(ctrl["alinea"]["gain_veh_per_s_per_occupancy"], "gain")
    if not 0 < _number(ctrl["alinea"]["target_occupancy"], "target_occupancy") < 1:
        raise ValueError("target_occupancy must be a fraction strictly between 0 and 1")
    scenarios = cfg["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("scenarios must be a nonempty list")
    ids = set()
    for scenario in scenarios:
        keys = "id name description periods" + (
            " detector_fault" if "detector_fault" in scenario else ""
        )
        _fields(scenario, keys, "scenario")
        if not isinstance(scenario["id"], str) or scenario["id"] in ids:
            raise ValueError("scenario IDs must be unique strings")
        ids.add(scenario["id"])
        start = 0
        for period in scenario["periods"]:
            keys = "until_s ramp_veh_per_s mainline_veh_per_s" + (
                " exit_speed_mps" if "exit_speed_mps" in period else ""
            )
            _fields(period, keys, "period")
            if "exit_speed_mps" in period:
                _number(period["exit_speed_mps"], "exit_speed_mps")
            end = _number(period["until_s"], "until_s")
            if not start < end <= cfg["duration_s"]:
                raise ValueError("period ends must increase and not exceed duration_s")
            _number(period["ramp_veh_per_s"], "ramp_veh_per_s", zero=True)
            _number(period["mainline_veh_per_s"], "mainline_veh_per_s", zero=True)
            start = end
        if start != cfg["duration_s"]:
            raise ValueError("each demand schedule must cover duration_s exactly")
        fault = scenario.get("detector_fault")
        if fault is not None:
            _fields(fault, "sensor_id from_s until_s", "detector_fault")
            if fault["sensor_id"] not in (
                "ramp_entry",
                "meter_passage",
                "mainline_merge",
            ):
                raise ValueError("detector_fault.sensor_id is unknown")
            if (
                not 0
                <= _number(fault["from_s"], "from_s", zero=True)
                < _number(fault["until_s"], "until_s")
            ):
                raise ValueError("detector_fault window must be increasing")


def build_lanes(cfg: dict) -> tuple[list[dict], list[float]]:
    """Lane j of the ramp ends where the last section with more than j lanes ends."""
    sections = cfg["ramp"]["sections"]
    ends, position = [], 0.0
    for section in sections:
        position += section["length_m"]
        ends.append(position)
    n_ramp = sections[0]["lanes"]
    lanes = []
    for j in range(n_ramp):
        last = max(i for i, s in enumerate(sections) if s["lanes"] > j)
        lanes.append(
            {
                "id": f"ramp_{j}",
                "start": 0.0,
                "end": ends[last],
                "target": j - 1 if j else n_ramp,
                "exit": False,
            }
        )
    main = cfg["mainline"]
    lanes.append(
        {
            "id": "freeway_0",
            "start": position - main["upstream_length_m"],
            "end": position + main["downstream_length_m"],
            "target": None,
            "exit": True,
        }
    )
    return lanes, ends


def idm_acceleration(v, v0, gap, dv, p: dict):
    """Driver.acceleration for the `vehicle.idm` values in `p`; arrays are allowed."""
    return Driver(**p).acceleration(v, v0, gap, dv)


def equilibrium_flow(v, v0, length, p: dict):
    """IDM steady-state flow (veh/s) of identical vehicles at speed v < v0."""
    gap = (p["s0_m"] + v * p["time_gap_s"]) / np.sqrt(1 - (v / v0) ** p["delta"])
    return v / (length + gap)


def ballistic_step(x, v, acc, h):
    """Constant-acceleration step that stops exactly when speed would cross zero."""
    stopping = (acc < 0) & (v + acc * h < 0)
    dt = np.where(stopping, -v / np.where(stopping, acc, -1.0), h)
    return x + v * dt + 0.5 * acc * dt**2, np.where(stopping, 0.0, v + acc * h)


class Simulation:
    def __init__(
        self, cfg: dict, scenario: dict, controller: str, seed: int, trace: bool = False
    ):
        self.cfg, self.scenario, self.controller, self.seed = (
            cfg,
            scenario,
            controller,
            seed,
        )
        self.h = cfg["step_s"]
        self.lanes, self.ends = build_lanes(cfg)
        self.F = len(self.lanes) - 1
        self.idm = cfg["vehicle"]["idm"]
        self.length = cfg["vehicle"]["length_m"]
        self.stop = cfg["meter"]["stop_line_m"]
        self.metered = controller != "none"
        self.rng = np.random.default_rng(seed)
        self.spread = cfg["vehicle"].get("spread", {})
        self.shape = cfg["vehicle"].get("shape", {})
        self.typical = Driver(**self.idm)  # the fixed values, without spread
        # One stream per origin, apart from arrivals: the k-th ramp (or through) driver
        # is the same under every rule, and a zero spread changes nothing.
        self.driver_rng = [np.random.default_rng([seed, b]) for b in (0, 1)]
        self.next_driver = [self._driver(b) for b in (0, 1)]
        self.vehicles: list[Vehicle] = []
        self.next_id = 0
        self.index = 0
        self.waiting = np.zeros(2, dtype=int)  # ramp, mainline boundary buffers
        self.requested = np.zeros(2, dtype=int)
        self.entered = np.zeros(2, dtype=int)
        self.exited = self.exited_ramp_origin = 0
        self.rate: float | None = None
        self.pending = None
        self.next_release = 0.0
        self.rr = 0
        self.releases = 0
        self.last_valid_obs_t = None
        self.exit_speed: float | None = None  # imposed downstream speed, if any
        self.ghost_rear = math.inf  # rear of the virtual vehicle beyond the exit
        zone = cfg["lane_change"]["zone_m"]
        # Target lanes yield to vehicles ahead in the lane that ends (zipper courtesy).
        self.yield_to: dict[int, list[tuple[int, float, float]]] = {
            k: [] for k in range(len(self.lanes))
        }
        for k, lane in enumerate(self.lanes):
            if lane["target"] is not None:
                self.yield_to[lane["target"]].append(
                    (k, lane["end"] - zone, lane["end"])
                )
        self.meter_lanes = [
            i
            for i, ln in enumerate(self.lanes[: self.F])
            if ln["start"] <= self.stop < ln["end"]
        ]
        det = cfg["detectors"]
        positions = {
            "ramp_entry": det["ramp_entry_m"],
            "meter_passage": det["meter_passage_m"],
            "mainline_merge": self.ends[-1] + det["merge_area_m"],
        }
        if "mainline_upstream_m" in det:
            positions["mainline_upstream"] = self.ends[-1] + det["mainline_upstream_m"]
        self.loop = det.get("loop_length_m", 0.0)  # detection-zone length
        self.detectors = {
            k: (
                p,
                [
                    i
                    for i, ln in enumerate(self.lanes)
                    if ln["start"] <= p < ln["end"]
                    and (i == self.F) == k.startswith("mainline")
                ],
            )
            for k, p in positions.items()
        }
        self.acc = {
            k: {"count": 0, "speed_sum": 0.0, "occupied": 0.0, "steps": 0.0}
            for k in positions
        }
        self.cum_counts = {"ramp_entry": 0, "meter_passage": 0}
        self.observations: list[dict] = []
        self.commands: list[dict] = []
        self.ddl_arrivals = 0
        self.ddl_departures = 0.0
        self.ddl_abs_error = 0.0
        self.delay = self.boundary_wait = self.time_spent = 0.0
        self.boundary_ramp_wait = 0.0
        self.max_boundary_ramp = 0
        self.min_gap = math.inf
        self.nonpositive_gaps = 0
        self.max_queue = 0
        self.trace = {"states": [], "queue": []} if trace else None

    # -- helpers -----------------------------------------------------------
    @property
    def time(self) -> float:
        return self.index * self.h

    def _driver(self, b: int) -> Driver:
        """The next driver of origin b (0 ramp, 1 mainline)."""
        return Driver.sample(self.idm, self.spread, self.shape, self.driver_rng[b])

    def desired_speed(self, lane: int, x: float, driver: Driver | None = None) -> float:
        """The driver's desired speed at x (the typical driver's when none is given)."""
        driver = driver or self.typical
        f = driver.v0_factor
        if lane == self.F:
            return f * self.cfg["mainline"]["desired_speed_mps"]
        sections = self.cfg["ramp"]["sections"]
        v0 = f * next(
            (s["desired_speed_mps"] for e, s in zip(self.ends, sections) if x < e),
            sections[-1]["desired_speed_mps"],
        )
        # A slower section ahead (the loop) lowers the desired speed early enough to
        # reach it braking at the driver's comfortable rate b (D017), not once inside it.
        for start, s in zip([0.0, *self.ends], sections):
            if start > x:
                reach = (f * s["desired_speed_mps"]) ** 2 + 2 * driver.b_mps2 * (
                    start - x
                )
                v0 = min(v0, math.sqrt(reach))
        return v0

    def ramp_queue(self) -> int:
        """Boundary waiting plus ramp vehicles upstream of the configured stop line."""
        return int(self.waiting[0]) + sum(
            1 for v in self.vehicles if v.lane < self.F and v.x < self.stop
        )

    def queue_estimate(self) -> int:
        return self.cum_counts["ramp_entry"] - self.cum_counts["meter_passage"]

    # -- one integration step ------------------------------------------------
    def step(self) -> None:
        t, h, cfg = self.time, self.h, self.cfg
        obs_interval = cfg["detectors"]["interval_s"]
        if self.index and self.index % round(obs_interval / h) == 0:
            self._emit_observations(t - obs_interval, t)
        if self.metered and self.index % round(cfg["control"]["interval_s"] / h) == 0:
            self._decide(t)
        if self.pending is not None and t >= self.pending["apply_time_s"] - 1e-9:
            self.rate = self.pending["value"]
            self.pending = None
        period = next(p for p in self.scenario["periods"] if t < p["until_s"])
        self.exit_speed = period.get("exit_speed_mps")
        arrivals = self.rng.poisson(
            [period["ramp_veh_per_s"] * h, period["mainline_veh_per_s"] * h]
        )
        self.requested += arrivals
        self.waiting += arrivals
        self._entries()
        self._lane_changes()
        if self.metered and self.rate:
            self._release(t)
        self._move()
        self.ddl_arrivals += int(arrivals[0])
        queue = self.ramp_queue()
        self.max_queue = max(self.max_queue, queue)
        ddl_queue = math.nan
        if self.metered and self.rate is not None:
            self.ddl_departures = min(
                self.ddl_arrivals, self.ddl_departures + self.rate * h
            )
            ddl_queue = self.ddl_arrivals - self.ddl_departures
            self.ddl_abs_error += abs(ddl_queue - queue) * h
        self.time_spent += h * (len(self.vehicles) + int(self.waiting.sum()))
        self.boundary_wait += h * int(self.waiting.sum())
        self.boundary_ramp_wait += h * int(self.waiting[0])
        self.max_boundary_ramp = max(self.max_boundary_ramp, int(self.waiting[0]))
        if (
            self.requested.sum()
            != self.exited + len(self.vehicles) + self.waiting.sum()
        ):
            raise RuntimeError(f"vehicle conservation violated at {t}s")
        self.index += 1
        if (
            self.trace is not None
            and self.index % round(cfg["snapshot_interval_s"] / h) == 0
        ):
            now = self.time
            self.trace["queue"].append(
                (now, queue, self.queue_estimate(), ddl_queue, self.rate)
            )
            self.trace["states"].extend(
                (now, v.vid, self.lanes[v.lane]["id"], v.x, v.v, v.acc)
                for v in self.vehicles
            )

    def _entries(self) -> None:
        for b, lane_ids in enumerate((list(range(self.F)), [self.F])):
            origin = "ramp" if b == 0 else "mainline"
            used = set()
            while self.waiting[b] > 0:
                driver = self.next_driver[b]
                best = None
                for k in lane_ids:
                    if k in used:
                        continue
                    x0 = self.lanes[k]["start"]
                    v0 = self.desired_speed(k, x0, driver)
                    last = min(
                        (v for v in self.vehicles if v.lane == k),
                        key=lambda v: v.x,
                        default=None,
                    )
                    if last is None:
                        gap, speed = math.inf, v0
                    else:
                        gap, speed = last.x - last.length - x0, min(v0, last.v)
                        if gap < driver.s0_m + speed * driver.time_gap_s:
                            continue
                    if best is None or gap > best[0]:
                        best = (gap, k, x0, speed)
                if best is None:
                    break
                _, k, x0, speed = best
                used.add(k)
                self.vehicles.append(
                    Vehicle(self.next_id, k, x0, speed, self.length, origin, driver)
                )
                self.next_driver[b] = self._driver(b)
                self.next_id += 1
                self.waiting[b] -= 1
                self.entered[b] += 1

    def _lane_changes(self) -> None:
        zone, b_safe = (
            self.cfg["lane_change"]["zone_m"],
            self.cfg["lane_change"]["b_safe_mps2"],
        )
        candidates = [
            v
            for v in self.vehicles
            if v.lane < self.F and v.x >= self.lanes[v.lane]["end"] - zone
        ]
        for veh in sorted(candidates, key=lambda v: -v.x):
            tgt = self.lanes[veh.lane]["target"]
            target = self.lanes[tgt]
            if not target["start"] <= veh.x < target["end"]:
                continue
            others = [o for o in self.vehicles if o.lane == tgt]
            lead = min(
                (o for o in others if o.x > veh.x), key=lambda o: o.x, default=None
            )
            foll = max(
                (o for o in others if o.x <= veh.x), key=lambda o: o.x, default=None
            )
            if lead is None:
                gap_l = math.inf if target["exit"] else target["end"] - veh.x
                dv_l = 0.0 if target["exit"] else veh.v
            else:
                gap_l, dv_l = lead.x - lead.length - veh.x, veh.v - lead.v
            # The merging driver judges the gap: their own limit holds for the braking
            # they accept and for the braking they impose on the new follower.
            limit = b_safe * veh.driver.b_safe_factor
            if (
                gap_l <= 0
                or veh.driver.acceleration(
                    veh.v, self.desired_speed(tgt, veh.x, veh.driver), gap_l, dv_l
                )
                < -limit
            ):
                continue
            if foll is not None:
                gap_f = veh.x - veh.length - foll.x
                # A follower already yielding to this vehicle is unaffected by the change.
                if (
                    gap_f <= 0
                    or foll.leader is not veh
                    and foll.driver.acceleration(
                        foll.v,
                        self.desired_speed(tgt, foll.x, foll.driver),
                        gap_f,
                        foll.v - veh.v,
                    )
                    < -limit
                ):
                    continue
            veh.lane = tgt

    def _release(self, t: float) -> None:
        if t < self.next_release - 1e-9:
            return
        window = self.cfg["meter"]["release_window_m"]
        n = len(self.meter_lanes)
        for i in range(n):
            idx = (self.rr + 1 + i) % n
            k = self.meter_lanes[idx]
            front = max(
                (
                    v
                    for v in self.vehicles
                    if v.lane == k and not v.released and v.x < self.stop
                ),
                key=lambda v: v.x,
                default=None,
            )
            if front is not None and self.stop - front.x <= window:
                front.released = True
                self.releases += 1
                self.rr = idx
                self.next_release = t + 1 / self.rate
                return

    def _move(self) -> None:
        h, vehs = self.h, self.vehicles
        b_safe = self.cfg["lane_change"]["b_safe_mps2"]
        for acc in self.acc.values():
            acc["steps"] += h
        # Downstream boundary: traffic beyond the exit moves at the imposed speed. The
        # last vehicle out lives on as a ghost at that speed, held no farther than the
        # IDM equilibrium gap past the exit, so a queue discharges the equilibrium flow
        # of that speed and a lone vehicle still leaves at that speed. The ghost moves
        # after the vehicles do, so both are read at the same time level.
        vb, v_main = self.exit_speed, self.cfg["mainline"]["desired_speed_mps"]
        limit = math.inf
        if vb is not None and vb < v_main:
            p = self.idm
            limit = self.lanes[self.F]["end"] + (
                p["s0_m"] + vb * p["time_gap_s"]
            ) / math.sqrt(1 - (vb / v_main) ** p["delta"])
        self.ghost_rear = min(self.ghost_rear, limit) if limit < math.inf else limit
        if not vehs:
            self.ghost_rear = min(limit, self.ghost_rear + (vb or 0.0) * h)
            return
        n = len(vehs)
        gap, dv, v, v0 = np.empty(n), np.empty(n), np.empty(n), np.empty(n)
        by_lane: dict[int, list[Vehicle]] = {k: [] for k in range(len(self.lanes))}
        for veh in sorted(vehs, key=lambda o: o.x):
            by_lane[veh.lane].append(veh)
        pos = {k: [o.x for o in group] for k, group in by_lane.items()}

        def ahead(k: int, x: float, limit: float, clear: float = 0.0) -> Vehicle | None:
            """Nearest vehicle in lane k beyond x (by more than `clear`) and not beyond limit."""
            j = bisect.bisect_right(pos[k], x)
            while j < len(pos[k]) and pos[k][j] - by_lane[k][j].length - x <= clear:
                j += 1
            return by_lane[k][j] if j < len(pos[k]) and pos[k][j] <= limit else None

        for i, veh in enumerate(vehs):
            k, lane = veh.lane, self.lanes[veh.lane]
            v[i], v0[i] = veh.v, self.desired_speed(k, veh.x, veh.driver)
            # Own lane: nothing is skipped, so an overlap reaches the gap counter below.
            lead = ahead(k, veh.x, math.inf, -math.inf)
            veh.leader = lead
            xl, vl, ll = (lead.x, lead.v, lead.length) if lead else (math.inf, 0.0, 0.0)
            if lead is None and lane["exit"] and self.ghost_rear < math.inf:
                xl, vl = self.ghost_rear, vb
            # A lane end is braked for only once it lies within the stopping distance at
            # b_safe (late-braking merge behaviour); beyond that the driver seeks a gap.
            if (
                not lane["exit"]
                and lane["end"] < xl
                and lane["end"] - veh.x
                <= (
                    veh.v**2 / (2 * b_safe * veh.driver.b_safe_factor)
                    + self.idm["s0_m"]
                    + 2 * veh.v * h
                )
            ):
                xl, vl, ll = lane["end"], 0.0, 0.0
            if (
                self.metered
                and k < self.F
                and not veh.released
                and veh.x
                < self.stop
                < xl - ll  # a leader straddling the line stays the leader
            ):
                xl, vl, ll = self.stop, 0.0, 0.0
            g = xl - ll - veh.x
            if g <= 0:
                self.nonpositive_gaps += 1
                g = 0.1  # recorded, not concealed: see nonpositive_gap_events
            if g < self.min_gap:
                self.min_gap = g
            # Merge interaction: inside a lane-end zone, a target-lane vehicle yields to the
            # nearest ending-lane vehicle ahead of it (not alongside) when following it is
            # comfortable (IDM deceleration within b_safe) or when it can still stop behind
            # it at b_safe; otherwise it passes and the merging vehicle waits.
            for partner, lo, hi in self.yield_to[k]:
                if lo <= veh.x <= hi:
                    other = ahead(partner, veh.x, hi, self.idm["s0_m"])
                    if other and (go := other.x - other.length - veh.x) < g:
                        if (
                            go >= veh.v**2 / (2 * b_safe)
                            or veh.driver.acceleration(
                                veh.v, v0[i], go, veh.v - other.v
                            )
                            >= -b_safe
                        ):
                            g, vl, veh.leader = go, other.v, other
            gap[i], dv[i] = g, veh.v - vl
        # Every vehicle's own values as arrays, so IDM is evaluated once for all of them.
        own = {
            field: np.array([getattr(o.driver, field) for o in vehs])
            for field in SPREAD.values()
            if field in self.idm
        }
        # IDM has no braking limit; a car cannot brake harder than its tyres allow.
        acc = np.maximum(
            idm_acceleration(v, v0, gap, dv, {**self.idm, **own}), -MAX_DECEL_MPS2
        )
        x_old = np.array([veh.x for veh in vehs])
        x_new, v_new = ballistic_step(x_old, v, acc, h)
        self.delay += float(h * np.sum(1 - v / v0))
        lane_of = np.array([veh.lane for veh in vehs])
        # A vehicle is over a detector while its front is within length + loop of it.
        lengths = np.array([veh.length for veh in vehs]) + self.loop
        dx = x_new - x_old
        for k, (point, lanes) in self.detectors.items():
            mask = np.isin(lane_of, lanes)
            crossed = mask & (x_old < point) & (point <= x_new)
            a = self.acc[k]
            a["count"] += int(crossed.sum())
            a["speed_sum"] += float(v_new[crossed].sum())
            # Occupied time: the front bumper lies in [point, point + length] while moving
            # at the step's mean speed, or the whole step when standing over the point.
            covered = np.clip(
                np.minimum(x_new, point + lengths) - np.maximum(x_old, point), 0, None
            )
            standing = (dx <= 1e-9) & (x_new - lengths < point) & (point <= x_new)
            occupied = np.where(
                dx > 1e-9,
                covered / np.where(dx > 1e-9, dx, 1.0) * h,
                np.where(standing, h, 0.0),
            )
            a["occupied"] += min(h, float(occupied[mask].sum()))
        self.ghost_rear = min(limit, self.ghost_rear + (vb or 0.0) * h)
        remaining = []
        for i, veh in enumerate(vehs):
            veh.x, veh.v, veh.acc = float(x_new[i]), float(v_new[i]), float(acc[i])
            if self.lanes[veh.lane]["exit"] and veh.x >= self.lanes[veh.lane]["end"]:
                self.exited += 1
                if self.ghost_rear < math.inf:
                    self.ghost_rear = veh.x - veh.length
                self.exited_ramp_origin += veh.origin == "ramp"
            else:
                remaining.append(veh)
        self.vehicles = remaining

    def _emit_observations(self, start: float, end: float) -> None:
        fault = self.scenario.get("detector_fault")
        for k, a in self.acc.items():
            missing = (
                bool(fault)
                and fault["sensor_id"] == k
                and start < fault["until_s"]
                and end > fault["from_s"]
            )
            self.observations.append(
                {
                    "sensor_id": k,
                    "interval_start_s": start,
                    "interval_end_s": end,
                    "available_time_s": end,
                    "count": None if missing else a["count"],
                    "mean_speed_mps": None
                    if missing or a["count"] == 0
                    else a["speed_sum"] / a["count"],
                    "occupancy_fraction": None
                    if missing
                    else a["occupied"] / a["steps"],
                    "quality_flag": "missing" if missing else "valid",
                }
            )
            if not missing and k in self.cum_counts:
                self.cum_counts[k] += a["count"]
            a.update(count=0, speed_sum=0.0, occupied=0.0, steps=0.0)

    def _decide(self, t: float) -> None:
        # Caltrans meters on the mainline station upstream of the gore; ALINEA on the
        # merge-area station.
        sensor = (
            "mainline_upstream" if self.controller == "caltrans" else "mainline_merge"
        )
        obs = next(
            (
                o
                for o in reversed(self.observations)
                if o["sensor_id"] == sensor and o["available_time_s"] <= t
            ),
            None,
        )
        if obs is not None and obs["occupancy_fraction"] is not None:
            self.last_valid_obs_t = t
        entry = next(
            (
                o
                for o in reversed(self.observations)
                if o["sensor_id"] == "ramp_entry" and o["quality_flag"] == "valid"
            ),
            None,
        )
        demand = (
            None
            if entry is None
            else entry["count"] / (entry["interval_end_s"] - entry["interval_start_s"])
        )
        command = decide(
            self.cfg["control"],
            self.controller,
            t,
            self.rate,
            obs,
            self.queue_estimate(),
            demand,
            self.last_valid_obs_t,
            self.h,
            None if entry is None else entry["occupancy_fraction"],
        )
        self.commands.append(command)
        self.pending = command

    # -- run -----------------------------------------------------------------
    def run(self) -> dict:
        steps = round(self.cfg["duration_s"] / self.h)
        for _ in range(steps):
            self.step()
        down = [
            o
            for o in self.observations
            if o["sensor_id"] == "mainline_merge" and o["quality_flag"] == "valid"
        ]
        speeds = [o["mean_speed_mps"] for o in down if o["mean_speed_mps"] is not None]
        reasons = [c["reason"] for c in self.commands]
        metrics = {
            "requested_ramp_veh": int(self.requested[0]),
            "requested_mainline_veh": int(self.requested[1]),
            "entered_ramp_veh": int(self.entered[0]),
            "entered_mainline_veh": int(self.entered[1]),
            "exited_veh": self.exited,
            "exited_ramp_origin_veh": int(self.exited_ramp_origin),
            "boundary_ramp_veh": int(self.waiting[0]),
            "boundary_mainline_veh": int(self.waiting[1]),
            "internal_veh": len(self.vehicles),
            "ramp_queue_end_veh": self.ramp_queue(),
            "ramp_queue_max_veh": self.max_queue,
            "meter_releases": self.releases,
            "delay_veh_s": self.delay,
            "boundary_wait_veh_s": self.boundary_wait,
            "boundary_ramp_wait_veh_s": self.boundary_ramp_wait,
            "boundary_ramp_max_veh": self.max_boundary_ramp,
            "total_time_veh_s": self.time_spent,
            "min_gap_m": self.min_gap,
            "nonpositive_gap_events": self.nonpositive_gaps,
            "queue_control_count": reasons.count("queue_control"),
            "queue_override_count": reasons.count("queue_override"),
            "hold_count": reasons.count("hold_last_valid_command"),
            "fallback_count": reasons.count("fixed_rate_fallback"),
            "ddl_queue_mae_veh": self.ddl_abs_error / self.cfg["duration_s"]
            if self.metered
            else math.nan,
            "mean_merge_occupancy": float(
                np.mean([o["occupancy_fraction"] for o in down])
            )
            if down
            else math.nan,
            "mean_merge_speed_mps": float(np.mean(speeds)) if speeds else math.nan,
        }
        return {
            "scenario_id": self.scenario["id"],
            "controller": self.controller,
            "seed": self.seed,
            "metrics": metrics,
            "observations": self.observations,
            "commands": self.commands,
            "trace": self.trace,
        }


def simulate(
    cfg: dict, scenario_id: str, controller: str, seed: int, trace: bool = False
) -> dict:
    validate_config(cfg)
    scenario = next((s for s in cfg["scenarios"] if s["id"] == scenario_id), None)
    if (
        scenario is None
        or controller not in (*CONTROLLERS, "caltrans")
        or (controller == "caltrans" and "caltrans" not in cfg["control"])
    ):
        raise ValueError(f"unknown scenario or controller: {scenario_id}, {controller}")
    return Simulation(cfg, scenario, controller, seed, trace).run()


def plot_scenario(cfg: dict, scenario: dict, runs: dict[str, dict], path: Path) -> None:
    """Trajectories, ramp queue versus estimate and D/D/1, applied rate, downstream occupancy."""
    ctrl = cfg["control"]
    fig, axes = plt.subplots(
        4,
        len(CONTROLLERS),
        figsize=(5 * len(CONTROLLERS), 13),
        sharex=True,
        sharey="row",
    )
    for c, name in enumerate(CONTROLLERS):
        run = runs[name]
        states = run["trace"]["states"]
        t = np.array([s[0] for s in states]) / 60
        lane = np.array([s[2] for s in states])
        x = np.array([s[3] for s in states])
        ax = axes[0, c]
        for lane_id, color in LANE_COLORS.items():
            m = lane == lane_id
            if m.any():
                ax.scatter(
                    t[m], x[m], s=0.6, color=color, label=lane_id, rasterized=True
                )
        ax.axhline(cfg["meter"]["stop_line_m"], color="#777", lw=1, ls="--")
        ax.axhline(
            sum(s["length_m"] for s in cfg["ramp"]["sections"]),
            color="#777",
            lw=1,
            ls=":",
        )
        ax.set_title(f"{name} controller")
        q = np.array(run["trace"]["queue"], dtype=float)
        tq = q[:, 0] / 60
        ax = axes[1, c]
        ax.plot(
            tq, q[:, 1], color=LANE_COLORS["ramp_0"], lw=2, label="simulated ramp queue"
        )
        ax.plot(
            tq,
            q[:, 2],
            color=LANE_COLORS["ramp_1"],
            lw=2,
            label="detector-count estimate",
        )
        if name != "none":
            ax.plot(
                tq,
                q[:, 3],
                color=LANE_COLORS["ramp_2"],
                lw=2,
                label="D/D/1 vertical queue",
            )
        ax.axhline(
            ctrl["queue_target_veh"], color="#777", lw=1, ls="--", label="queue target"
        )
        ax = axes[2, c]
        if name != "none":
            ax.step(
                tq,
                q[:, 4],
                where="post",
                color=LANE_COLORS["ramp_0"],
                lw=2,
                label="applied rate",
            )
            for key in ("min_rate_veh_per_s", "max_rate_veh_per_s"):
                ax.axhline(ctrl[key], color="#777", lw=1, ls="--")
        ax = axes[3, c]
        obs = [o for o in run["observations"] if o["sensor_id"] == "mainline_merge"]
        occ = [
            math.nan if o["occupancy_fraction"] is None else o["occupancy_fraction"]
            for o in obs
        ]
        ax.step(
            [o["interval_end_s"] / 60 for o in obs],
            occ,
            where="pre",
            color=LANE_COLORS["ramp_0"],
            lw=2,
            label="merge-area occupancy",
        )
        ax.axhline(
            ctrl["alinea"]["target_occupancy"],
            color="#777",
            lw=1,
            ls="--",
            label="ALINEA target",
        )
        ax.set_xlabel("time (min)")
    labels = (
        "position (m)",
        "ramp queue (veh)",
        "release rate (veh/s)",
        "occupancy (fraction)",
    )
    for row, label in enumerate(labels):
        axes[row, 0].set_ylabel(label)
        axes[row, -1].legend(fontsize=8, loc="upper left", markerscale=6)
    seed = runs["none"]["seed"]
    fig.suptitle(
        f"{scenario['name']} (synthetic, seed {seed}): {scenario['description']}",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def export_runs(cfg: dict, config_path: Path, output_root: Path) -> Path:
    validate_config(cfg)
    now = datetime.now(UTC)
    output = output_root / now.strftime("%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True, exist_ok=False)
    rows, commands, observations, states, queues = [], [], [], [], []
    for scenario in cfg["scenarios"]:
        traced = {}
        for controller in CONTROLLERS:
            for seed in cfg["seeds"]:
                trace = seed == cfg["seeds"][0]
                run = simulate(cfg, scenario["id"], controller, seed, trace)
                key = {
                    "scenario_id": scenario["id"],
                    "controller": controller,
                    "seed": seed,
                }
                rows.append({**key, **run["metrics"]})
                commands.extend({**key, **c} for c in run["commands"])
                observations.extend({**key, **o} for o in run["observations"])
                if trace:
                    traced[controller] = run
                    states.extend(
                        (scenario["id"], controller, seed, *s)
                        for s in run["trace"]["states"]
                    )
                    queues.extend(
                        (scenario["id"], controller, seed, *q)
                        for q in run["trace"]["queue"]
                    )
        plot_scenario(cfg, scenario, traced, output / f"{scenario['id']}.png")
    _write_csv(output / "evaluation.csv", rows)
    _write_csv(output / "commands.csv", commands)
    _write_csv(output / "observations.csv", observations)
    _write_csv(
        output / "vehicle_states.csv",
        states,
        [
            "scenario_id",
            "controller",
            "seed",
            "time_s",
            "vehicle_id",
            "lane_id",
            "position_m",
            "speed_mps",
            "acceleration_mps2",
        ],
    )
    _write_csv(
        output / "queue_trace.csv",
        queues,
        [
            "scenario_id",
            "controller",
            "seed",
            "time_s",
            "ramp_queue_veh",
            "queue_estimate_veh",
            "ddl_queue_veh",
            "rate_veh_per_s",
        ],
    )
    source_dir = output / "source"
    source_dir.mkdir()
    sources = {
        "micro.py": Path(__file__),
        "metering.py": Path(__file__).parents[1] / "control" / "metering.py",
        "micro.yaml": config_path,
        "pyproject.toml": Path("pyproject.toml"),
        "uv.lock": Path("uv.lock"),
    }
    hashes = {}
    for name, path in sources.items():
        shutil.copyfile(path, source_dir / name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    revision = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], capture_output=True, text=True
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    )
    metadata = {
        "schema_version": "ramp-micro-v1",
        "origin": "synthetic",
        "created_utc": now.isoformat(),
        "initial_state": "empty",
        "epoch_utc": None,
        "config": cfg,
        "controllers": list(CONTROLLERS),
        "source_sha256": hashes,
        "git_revision": revision.stdout.strip() if revision.returncode == 0 else None,
        "git_dirty": bool(status.stdout) if status.returncode == 0 else None,
        "python_version": platform.python_version(),
    }
    (output / "run.json").write_text(
        json.dumps(metadata, indent=1) + "\n", encoding="utf-8"
    )
    return output


def _write_csv(path: Path, rows: list, header: list[str] | None = None) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        if header is None:
            writer = csv.DictWriter(stream, list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        else:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)


def summarize(path: Path) -> str:
    with (path / "evaluation.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    keys = (
        "exited_veh",
        "ramp_queue_max_veh",
        "boundary_ramp_veh",
        "delay_veh_s",
        "boundary_wait_veh_s",
        "total_time_veh_s",
    )
    lines = [
        f"{'scenario':<10}{'controller':<11}"
        + "".join(f"{k:>24}" for k in keys)
        + "   mean over seeds (min-max)"
    ]
    for scenario in dict.fromkeys(r["scenario_id"] for r in rows):
        for controller in CONTROLLERS:
            group = [
                r
                for r in rows
                if r["scenario_id"] == scenario and r["controller"] == controller
            ]
            cells = []
            for k in keys:
                values = [float(r[k]) for r in group]
                cells.append(
                    f"{np.mean(values):.0f} ({min(values):.0f}-{max(values):.0f})".rjust(
                        24
                    )
                )
            lines.append(f"{scenario:<10}{controller:<11}" + "".join(cells))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/micro.yaml"))
    parser.add_argument("--output", type=Path, default=Path("results/ramp-micro"))
    args = parser.parse_args(argv)
    try:
        cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        output = export_runs(cfg, args.config, args.output)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    print(summarize(output))
    print(
        f"Synthetic microscopic runs, figures, traces and source snapshot: {output.resolve()}"
    )


if __name__ == "__main__":
    main()
