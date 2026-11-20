# Microscopic ramp-metering demo (IDM, lane changes, meter, ALINEA)

Status: the engine of the I-405 case study (`simulation/micro.py`), described here with its synthetic test scenario (`configs/micro.yaml`). The site scenario and its calibration are in [the study design](study_design.md).

Status: synthetic, exploratory prototype authorized on 2026-11-09 (D013). It is the
first runnable version of the course's shared foundation (vehicle dynamics, arrivals,
bottleneck, virtual detectors, bounded closed-loop metering) for the I-405 southbound
loop ramp at Ventura Boulevard. Every number in `configs/micro.yaml` is an assumption
chosen while PeMS and geometry collection continue. Nothing here is calibrated or
validated against the site; see the limits at the end before quoting any result.

```bash
uv sync --locked
uv run arm-micro            # ≈ 40 s; writes results/ramp-micro/<timestamp>/
```

The run prints a summary table and writes `evaluation.csv` (one row per scenario,
controller and seed), `commands.csv`, `observations.csv`, `vehicle_states.csv`,
`queue_trace.csv`, one figure per scenario, `run.json` (configuration, hashes, git
revision) and a `source/` snapshot. Records use the field names of the course guide
and interfaces.

## Geometry and coordinate system

One longitudinal coordinate `x` in metres runs along the ramp from the Ventura
entrance (`x = 0`) to the freeway merge point, and continues along one modelled
freeway lane. From the aerial image the user confirmed **three entry lanes → two
lanes through the loop → one lane → merge**; lengths, the meter location and all
speeds are assumptions.

| Element | Assumed value | Lane ids |
| --- | --- | --- |
| Entry section, 3 lanes, desired speed 12 m/s | 0–120 m | `ramp_0`, `ramp_1`, `ramp_2` |
| Loop (curve), 2 lanes, desired speed 9 m/s | 120–390 m | `ramp_0`, `ramp_1` |
| Single lane / acceleration lane, desired speed 20 m/s | 390–600 m | `ramp_0` |
| Meter stop line (two lanes at the line) | 380 m | `ramp_0`, `ramp_1` |
| Modelled freeway lane, desired speed 22 m/s | 300–900 m (merge point at 600 m) | `freeway_0` |

Lane `j` ends where the last section with more than `j` lanes ends; `ramp_2` ends at
120 m and must move into `ramp_1`, `ramp_1` ends at 390 m and must move into
`ramp_0`, and `ramp_0` ends at the merge point and must move into `freeway_0`. The
curve is represented only by the lower desired speed on the loop; there is no
curvature model. Only the rightmost freeway lane is modelled; other freeway lanes,
discretionary lane changes and vehicle types are out of scope (the guide lists full
lane changing as optional). Drivers share one set of IDM values unless
`vehicle.spread` is set (see "Driver variation").

## Models and sources

**Car following.** The Intelligent Driver Model of Treiber, Hennecke and Helbing
(2000), in the form and sign convention of
[car_following.md](mathematical_model/car_following.md), integrated with the
constant-acceleration ballistic step that stops exactly when speed would cross
zero (`idm_acceleration`, `ballistic_step`). Step 0.5 s. Parameter values:

| Parameter | Value | Origin |
| --- | --- | --- |
| `s0`, `delta`, vehicle length | 2 m, 4, 5 m | Treiber et al. (2000) |
| `a`, `b`, `T` | 2.0 m/s², 2.0 m/s², 1.0 s | Project choice; see finding below |
| Desired speeds | 12 / 9 / 20 m/s ramp sections, 22 m/s freeway | Assumed |

With the paper's freeway values (`a` = 0.73, `b` = 1.67, `T` = 1.6 s) the modelled
merge discharges only ≈ 0.26 veh/s (≈ 940 veh/h) after breakdown and the ramp's
own lane drops pass ≈ 0.25 veh/s, which made every controller indistinguishable.
The chosen values give a single-lane capacity ≈ 0.6 veh/s and a merge discharge
≈ 0.36 veh/s after breakdown. This sensitivity is a finding about the model, not
about the site; it must be revisited with data (see "Findings").

**Driver variation (optional, D018 and D019).** Every vehicle carries a `Driver`
object with its own IDM values. Without `vehicle.spread` each driver has the values in
the table. `vehicle.spread` gives a coefficient of variation for any of `v0`, `time_gap`,
`a`, `b`, `s0` and `b_safe`, for example `{v0: 0.10, time_gap: 0.20, a: 0.20}`, and
`vehicle.shape` chooses `normal` (the default, truncated at two standard deviations),
`uniform` or `lognormal`, for all parameters or per parameter. Every shape gives exactly
the stated mean and coefficient of variation, so shapes can be compared like for like
([formulation](mathematical_model/car_following.md#driver-heterogeneity-optional));
`v0` is a factor `f` on the desired speed of every section. A driver's own values enter
their IDM acceleration (car following, the lane-change safety test for the merging
driver and for the new follower, and the decision to yield), the gap they need to enter
the network, and their approach to a slower section,
min(f·v₀, √((f·v_next)² + 2b·distance)). `b_safe` is the lane-changing preference: the
merging driver's own limit replaces the fixed `b_safe` in the safety test of their own
lane change and in the distance at which they brake for a lane end. The yield rule, the
zone, `s0` as the "alongside" and lane-end margin, the downstream boundary and the
analytic equilibrium curves keep the fixed values. Drivers come from one random stream
per origin, separate from arrivals; each driver draws one percentile per parameter
whatever the spread and shape, so the k-th ramp driver sits at the same percentiles
under every controller, demand level, spread and shape. No scenario in
`configs/micro.yaml` sets a spread. Which spreads and shapes are used, and where they
come from, is recorded in the [driver heterogeneity review](research/driver_heterogeneity.md).

**Mandatory lane changes.** A vehicle whose lane ends within `zone_m` (100 m)
changes to the target lane when the MOBIL safety criterion of Kesting, Treiber and
Helbing (2007) holds: the IDM acceleration of the new follower and of the vehicle
itself in the target lane must be at least `−b_safe` (4 m/s²), and both physical gaps
must be positive. The incentive criterion is not used (no discretionary changes).

**Merge interaction (project rule, not from a source).** Inside a lane-end zone a
target-lane vehicle treats the nearest ending-lane vehicle ahead of it (not
alongside, i.e. gap > `s0`) as its leader when following it needs at most `b_safe`
or when it can still stop behind it at `b_safe`; otherwise it passes. A follower that
is already yielding this way does not veto the lane change. A vehicle brakes for its
lane end only once the end lies within its `b_safe` stopping distance; before that it
drives on looking for a gap. Without these rules the ramp queue stalled at the merge
regardless of demand. Deadlocks are prevented by the positive-gap and "not alongside"
conditions; a vehicle that reaches its lane end without a gap stops and waits.

**Arrivals.** Poisson counts per step at the ramp entrance and the freeway boundary
(`numpy.random.default_rng(seed)`, one draw per boundary per step). Vehicles wait in
an unbounded external buffer until the entry lane with the largest gap offers at
least `s0 + v T` behind its last vehicle; waiting demand is counted, never dropped.
Because the generator is consumed in the same order for every controller, a seed
gives identical realized demand across controllers (paired comparison).

**Meter.** One vehicle per green: a release event grants the first unreleased
vehicle within `release_window_m` of the stop line in the next lane of a round robin;
unreleased vehicles see the stop line as a standing obstacle. Releases are at least
`1/r` seconds apart (`r` in veh/s) and only occur when a vehicle is waiting, so the
commanded rate is a service ceiling. Zero rate means no release.

**Virtual detectors.** Point detectors at 15 m (`ramp_entry`), 400 m
(`meter_passage`) and 30 m before the merge point on the freeway lane
(`mainline_merge`). Each 30 s interval reports crossings, mean crossing speed (null
when none) and occupancy = occupied time ÷ interval, where occupied time is the time
the front bumper lies within one vehicle length past the point at the step's mean
speed. A faulted detector reports nulls with `quality_flag = missing`.

**Controllers.** All consume detector records only; vehicle states are withheld.

- `none`: meter off.
- `fixed`: 0.15 veh/s (540 veh/h) every interval; also the startup and fallback rate.
- `alinea`: `r_{k+1} = r_k + K_R (o* − o_k)` from
  [ramp_metering.md](mathematical_model/ramp_metering.md) with `K_R` = 1.5
  (veh/s)/occupancy fraction and `o*` = 0.22 at the merge-area detector (the critical
  occupancy of the equilibrium curve since D022; 0.25 in the runs recorded below), bounded to
  [0.1, 0.5] veh/s, integrating from the applied bounded rate (anti-windup). Queue
  control follows ALINEA/Q (Smaragdis and Papageorgiou, 2003): the rate
  `(ŵ − w*)/Δc + d̂` that returns the detector-count queue estimate `ŵ` to its target
  `w*` = 40 veh within one interval, given the entrance-detector demand `d̂`, applies
  when larger. A missing occupancy holds the last valid command for 60 s, then uses
  the fixed rate. Each command records issue and application time, bounds, fallback
  state, reason and the observation it used.

**Analytical reference.** For the metered ramp a vertical D/D/1 queue is integrated
from the realized Poisson arrivals and the applied rate: `D_{t+1} = min(A_{t+1},
D_t + r h)`, `Q = A − D`. `ddl_queue_mae_veh` is its mean absolute difference from
the simulated ramp queue (boundary waiting plus vehicles upstream of the stop line).
Agreement within the ramp travel time is a consistency check of the meter mechanics;
divergence shows where merge blocking, not the meter, limits the ramp.

## Scenarios and outputs

Three demand profiles share off-peak demand (0.08 veh/s ramp, 0.35 veh/s freeway)
for 5 min and 25 min: `peak` (0.20 ramp, 0.40 freeway for 20 min), `heavy` (0.30
ramp), `fault` (peak demand with the merge-area detector missing from 10 to 16 min).
Each runs with every controller and seeds 1, 2, 3 for 30 min from an empty network.
Residual queues are reported, not cleared. Metrics (`evaluation.csv`):

- requested, entered and exited vehicles by origin; boundary waiting at the horizon;
- `ramp_queue_max_veh`, `ramp_queue_end_veh`, `meter_releases`;
- `delay_veh_s` = Σ h (1 − v/v0) over vehicle-steps inside the network;
  `boundary_wait_veh_s`; `total_time_veh_s` includes both and internal travel;
- `min_gap_m` and `nonpositive_gap_events` (a nonzero count flags a numerical overlap;
  all shipped runs report zero); controller reason counts; `ddl_queue_mae_veh`;
  mean merge-area occupancy and speed.

## Findings awaiting discussion (synthetic, seeds 1–3, run of 2026-11-09)

| Scenario | Controller | Exited veh | Max ramp queue | Total time veh·s |
| --- | --- | --- | --- | --- |
| peak | none | 673 | 20 | 272 000 |
| peak | fixed | 747 | 82 | 224 000 |
| peak | alinea | 721 | 48 | 222 000 |
| heavy | none | 668 | 137 | 392 000 |
| heavy | fixed | 754 | 205 (ramp full, 67 waiting outside) | 336 000 |
| heavy | alinea | 670 | 140 | 391 000 |
| fault | alinea | 716 | 52 | 228 000 |

- Under assumed peak demand the unmetered merge breaks down after ≈ 6 min and does
  not recover; the freeway queue reaches its boundary. Fixed metering postpones the
  breakdown and moves waiting onto the ramp; ALINEA reaches a similar total time with
  about half the ramp queue, but in these runs it also fails to prevent breakdown
  because the startup rate and the low initial occupancy drive it to the maximum rate
  first. Tuning `o*`, `K_R` and the startup rate is open work.
- In `heavy`, ALINEA/Q queue control lifts the rate to protect the 40-vehicle queue
  target and the merge breaks down as without control: the storage/mainline
  trade-off is visible, not resolved.
- The merge-area detector discriminates regimes (≈ 0.1 free, ≈ 0.35 near capacity,
  ≈ 0.5 after breakdown); a detector 100 m downstream of the merge did not.
- The detector-count queue estimate saturates once the queue reaches the entrance
  detector (`heavy`: it stays near 112 veh while the true queue, including vehicles
  waiting outside the ramp, exceeds 200); an estimator needs a boundary measurement.
- D/D/1 and the simulated queue agree within ≈ 7–9 veh when the meter binds and
  diverge (≈ 50–60 veh) when the merge blocks released vehicles (`heavy`, `alinea`).
- The IDM parameter sensitivity described above changes capacity by about a factor
  of two; this must be settled with observed flows before any comparison is trusted.

These are mechanisms under assumed inputs, not site results. Halving the step
changes exits by less than 15 % in the shipped test; a finer convergence study is
pending.

## Checks and limits

`tests/test_micro.py` covers the IDM equilibrium gap and free-road limits, the
ballistic stop, lane topology, zero demand, conservation and positive gaps for all
controllers, paired demand across controllers, the meter as a service ceiling and
D/D/1 agreement, causal command traces, hold-then-fallback under a detector fault,
controller bounds and queue control, a half-step comparison, configuration
rejection and the export, and per-driver values: their distribution, their pairing
across runs, and their use in following, entering, merging, yielding and approaching a
slower section. These are implementation checks, not validation.

Not modelled or unverified: other freeway lanes and discretionary changes, measured
driver heterogeneity (the optional spread is assumed, and it exposes a weakness of the
merge rule: see the 2026-11-18 finding in the [decision log](decisions.md)),
reaction time, curvature, actual signal timing (green/red durations,
two-lane alternation details), the real meter location and storage, calibration of
any parameter, forecasting (out of scope since 2026-11-18, D020; no forecast is used, by
declaration), and the supplied signal-control scaffold. The capacity drop produced by
the merge rules is large (≈ 40 %) and untested against observations. Vehicles that
reach a lane end without a gap stop and can block their lane; this is reported in the
trajectories rather than suppressed.
