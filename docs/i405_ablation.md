# I-405 SB Ventura on-ramp: site scenario, Caltrans metering, demand ablation

Status: the site scenario and the first ablation, authorized on 2026-11-15 (D015). The
geometry, the demand day, the boundary and the metering logic described here are still
those of the project; the **results in this document are from the model before
calibration** (`T` = 1 s, `delta` = 4, ALINEA's set value 0.34) and are what the
mid-report shows. The configuration has since been calibrated (D022, D023): see
[calibration](../experiments/calibration.md), and [the study design](study_design.md)
for the current plan. Geometry comes from the project's AutoCAD sketch, demand from one
observed PeMS weekday, and the meter logic from Caltrans documents. This ramp's own
metering plan is unpublished. Results are simulated what-ifs, not site findings.

```bash
uv sync --locked
uv run arm-pems scan --dates 2022-10-11   # once; needs a PeMS session (see data/README.md)
uv run arm-ablation                       # ≈ 16 min on 12 cores; writes results/demand-ablation/<timestamp>/
uv run arm-ablation --replot results/demand-ablation/<timestamp>   # table and figures only
```

A run writes `evaluation.csv` (one row per variant, controller and seed),
`summary.csv` (mean, min, max over seeds), `queue_trace.csv` and
`mainline_observations.csv` (first seed), `historical_profile.csv` (the demand and
boundary actually used), six figures, `config.yaml` and `run.json` (hashes of the
configuration, the PeMS extract and the code). Everything is set in
[`configs/i405.yaml`](../configs/i405.yaml); each value there carries a label:
`[sketch]`, `[PeMS]`, `[Caltrans]` or `[assumed]`.

## Geometry (measured from the project's sketch)

`scripts/smooth_ramp_geometry.py` converts the traced polylines to metres and smooths
them. `scripts/measure_ramp_pdf.py` recovers what the JSON export dropped (the loop
arcs and the red meter line) from the vector linework of the PDF plot; the PDF matches
the JSON to 0.04 m. The scale checks out: traced lanes are 3.4–3.8 m wide.

| Element | Value | Basis |
| --- | --- | --- |
| Approach leg, 3 lanes | 95 m | lane lines 95.0 and 95.5 m |
| Meter stop line, across all 3 lanes | 72.5 m from the entrance | red line, 10.6 m wide, confirmed by the user |
| Loop, 3 lanes | 48 m | middle-lane arc; outer 62 m, inner 33 m |
| Return leg, 2 lanes | 30 m | lane line 2EC; the third lane line ends at the loop exit |
| Single lane to the gore, then acceleration lane and taper | 11.5 m + 73.5 m | lane line 338 is 73.3 m, outer edge 75.5 m |
| Freeway upstream of the gore / downstream of the taper | 225 m / 235 m | traced edge lengths |
| Storage upstream of the stop line | ≈ 25 vehicles | 3 × 72.5 m at 29 ft (8.84 m) per vehicle [S6] |

The whole ramp is about 258 m. The earlier synthetic demo assumed 600 m and about
100 vehicles of storage on the same basis. The Caltrans design figure of storage for
7 % of the peak-hour volume [S6] would be about 64 vehicles for the 914 veh/h observed
on 2022-10-12, so the sketch shows roughly 40 % of that.

Still open: the sketch is in a local drawing frame (not georeferenced, despite the
"State Plane" note in the JSON), freeway lane lines west of line 376 are not traced
downstream of the taper, and desired speeds (11, 7, 12 m/s on the ramp) are assumed.

## Demand and downstream boundary (PeMS, Tuesday 2022-10-11)

Source: `data/interim/pems/station_5min_2022_10_11.csv`, a day on which both the
on-ramp station 716744 and the mainline station 717816 pass the screening
([pipeline findings](../data/README.md#findings-2026-11-07)). Window 05:00–10:00.
`historical_profile` refuses a window with missing or PeMS-imputed intervals.

The engine has **one freeway lane**. Two assumptions map the five-lane station onto it:

1. **Lane balance.** Downstream of the merge the modelled lane carries
   `(mainline + ramp) / 5`. Its through traffic is that share minus the ramp flow.
   Using the outer lane's own count plus the ramp instead asks one lane to carry about
   2,000 veh/h at 6 m/s, which neither the model nor a real lane does; in reality
   outer-lane drivers move left.
2. **Flow-matched downstream boundary.** PeMS shows the station congested from
   06:05, when its speed first drops below 20 m/s (it falls from 36 to 5–8 m/s while flow drops by about a quarter); the
   cause is taken to lie downstream of the modelled section. PeMS supports this for the
   peak, from about 06:30: both stations downstream of the merge are congested and no
   active bottleneck lies between the merge and Royal Ridge. It does not show it for the
   onset ([site characterization](../experiments/ramp_mainline_mix.md#site-characterization-pems-observed),
   candidate, D021). In intervals
   with station speed below 20 m/s the exit discharges exactly the observed merge-lane
   flow: the last vehicle out continues as a virtual vehicle at the IDM
   equilibrium speed of that flow (`Simulation._move`, `discharge_speed`). The boundary
   is held at its historical value in every variant.

Consequences to keep in mind: observed flow is a **lower bound on demand** once the
freeway is congested, so the historical case sits at demand ≈ capacity; and the model
reproduces observed throughput, not observed speed (the imposed exit speed is 3–7 m/s
where PeMS shows 5–8 m/s, because one IDM time gap cannot fit both the capacity and
the congested spacing).

## Metering logic simulated

What is normally in place: District 7 runs **local traffic-responsive metering**
("local mainline responsive") on top of a time-of-day table; fixed time-of-day rates
alone are a fallback [S3]. Statewide policy requires local traffic-responsive operation
on URMS [S1]. This ramp is listed as a loop ramp with two metered lanes [S10, S11], was
converted to a 2070 controller running URMS, and uses staggered release [S3].

| Rule in the model (`control/metering.py`, mode `caltrans`) | Value | Basis |
| --- | --- | --- |
| Rate update interval | 30 s | [S4, S20] |
| Mainline station | upstream of the gore | [S6]; exact position assumed |
| Plan table: stepwise rate from mainline occupancy | 15 levels, 900 veh/h/lane at ≤ 5 % down to 240 at ≥ 20 % | form [S2]; values after the published SR-99 Mack Rd plan [S8]; **assumed for this ramp** |
| Rate limits, one vehicle per green | 240–900 veh/h per lane, 2 lanes | [S6] |
| Queue override, highest priority | +120 veh/h/lane per update while the queue loop is covered; back to the plan in one step | [S2, S5, S9] |
| Queue loop position | 3/4 of the way back from the limit line (18 m from the entrance) | [S6] |
| Queue loop trigger | covered ≥ 50 % of a 30 s interval | **assumed**; field values are 2.0–3.2 s of continuous presence [S4, S5] |
| Release | one vehicle per green, lanes alternating, no yellow | [S2, S3] |
| Fixed-rate comparison (`fixed`) | 8 veh/min/lane | District 7 time-of-day example [S4]; assumed for this ramp |

Not modelled: the speed gate that older District 7 software puts on queue override
(normally 35 mph [S3, S5]), the non-metered HOV lane listed in the 2017 plan but not
the 2023 one [S10, S11] (all three lanes at the line share the two-lane rate), and
time-of-day switching (the meter is on for the whole window).

Compared controllers: `none` (no meter), `fixed`, `caltrans`, and `alinea` (ALINEA with
ALINEA/Q queue control from the earlier demo, merge-area detector). ALINEA's set value is
the critical occupancy, 0.26, since D022 (2026-11-19); every ALINEA result in this
document was obtained with 0.34. A test of 30 runs found no counted difference between
the two ([check](mathematical_model/ramp_metering.md#alinea-checked-against-the-lecture-and-the-original-paper-2026-11-19)).

## Ablation design

Every variant multiplies ramp and through demand by `m(t)`; arrivals stay Poisson and
the same seed gives every controller the same vehicles.

| Variant | `m(t)`, `t` = fraction of the window |
| --- | --- |
| `historical` | 1 |
| `x0.5` … `x10` | constant 0.5, 0.75, 0.9, 1.1, 1.25, 1.5, 2, 3, 5, 10 |
| `log_2x` | `1 + ln(1 + 9t) / ln 10`: fast early growth to 2 |
| `exp_2x` | `2^t`: slow early growth to 2 |
| `wave_10min`, `wave_60min` | `1 + 0.5 sin(2π · time / period)` |
| `free_exit_x1`, `free_exit_x1.25` | boundary check: same demand, no downstream restriction |

Metrics: share of demand served within the window, peak number of vehicles held on
Ventura Blvd (the ramp's boundary queue), and total time in system per requested
vehicle, which includes all waiting and counts unserved vehicles up to the end.

**Drivers that differ (D018, D019).** Every result in this document uses identical
drivers. What changes when they differ is studied separately, with seven driver
populations on three of the demand cases: see the
[experiment record](../experiments/driver_populations.md) and
`uv run arm-drivers` (`configs/i405_drivers.yaml`). `configs/i405_spread.yaml` remains as
a way to run this whole ablation with one population (5 % coefficient of variation on
`v0` and 10 % on `T`, `a`, `b` and `s0`, all [assumed]); it has not been run.

**Ramp and mainline demand scaled separately (D021).** Every variant above multiplies
both demands by the same factor, so it cannot say which of the two matters. A second
study gives each its own level under the flow-limited and the free exit, and adds the
observed shoulder lane as an upper bound for the through traffic: see the
[experiment record](../experiments/ramp_mainline_mix.md) and
`uv run arm-ablation --config configs/i405_mix.yaml` (`--analytic` prints its before-run
table without simulating).

## Testable question and congestion definition (D016)

**Question.** How far can morning demand rise at the Ventura Blvd on-ramp before the
freeway beside it stays congested, and does the metering rule change that point?

| Term | Definition (`ablation.congestion` in the configuration) | Basis |
| --- | --- | --- |
| Congested interval | a 30 s detector interval with mean speed below 20 m/s (45 mph) **or** occupancy above 26 % | 20 m/s is the line used to read congestion at PeMS station 717816; 26 % is the IDM equilibrium occupancy at capacity for the configured parameters and a 6 ft loop |
| Persistent congestion | at least 10 consecutive congested intervals (5 minutes, one PeMS interval); shorter events count as disturbances | project choice |
| Station | the simulated mainline loop upstream of the gore (`mainline_upstream`) | the merge-area loop is tripped by slow merging vehicles even at 0.5× demand |
| A rule "makes a difference" | its paired difference from no meter has the same sign in every seed and a mean of at least 5 minutes | project choice; weak with three seeds (see Limits) |

`evaluation.csv` carries `congested_min`, the minutes each run spends in persistent
congestion (`persistent_minutes`); `congestion.png` plots it against the multiplier.

**What the model predicts.** (1) Below capacity a merge disturbance decays and there is
no persistent congestion. (2) Above capacity the queue grows at demand minus capacity;
because the downstream boundary is held at the observed throughput, the share of demand
served is about 1 / multiplier. (3) Metering can help only near capacity and only while
the ramp can store the held vehicles (about 25). These were written down on 2026-11-15
**after** the first ablation run, so (2) is an analytical check, not a blind prediction.
Predictions for tests that do not exist yet are under "Next tests" below.

## Results

Run `20261116T042759_346757Z` (2026-11-15 PST): 17 variants × 4 controllers × 3 seeds = 204
simulations, no non-positive gap events, smallest gap 1.15 m. It repeats run
`20261116T023142_804744Z` and reproduces every earlier column exactly; it adds
`congested_min` and two figures. Each cell is the range
across the four controllers of the three-seed mean; `summary.csv` has every value.

| Variant | Served in the window (%) | Peak queue on Ventura Blvd (veh) | Time in system (min per vehicle) |
| --- | --- | --- | --- |
| `historical` | 96.3–96.5 | 169–185 | 7.0–7.6 |
| `x0.5` | 99.8–99.9 | 0–1 | 0.5 |
| `x0.75` | 99.8 | 1–2 | 0.6 |
| `x0.9` | 99.7–99.8 | 5–10 | 1.0–1.2 |
| `x1.1` | 89.0–89.4 | 666–698 | 16.2–17.1 |
| `x1.25` | 79.0–79.3 | 1,515–1,530 | 31.0–31.7 |
| `x1.5` | 68.9–69.0 | 2,396–2,403 | 44.2–44.3 |
| `x2` | 53.5–53.6 | 4,202–4,208 | 67.0–67.2 |
| `x3` | 36.5 | 7,584 | 94.9 |
| `x5` | 21.8 | 14,463 | 120.0 |
| `x10` | 10.9 | 31,406 | 138.6 |
| `log_2x` | 60.4–60.5 | 3,325–3,333 | 47.3–47.6 |
| `exp_2x` | 68.4–68.8 | 2,425–2,442 | 31.8–32.8 |
| `wave_10min` | 96.4–96.7 | 196–215 | 7.7–8.5 |
| `wave_60min` | 94.5–94.7 | 475–495 | 14.3–14.8 |
| `free_exit_x1` | 99.1–99.7 | 136–153 | 3.4–4.0 |
| `free_exit_x1.25` | 82.9–83.3 | 1,246–1,279 | 24.6–25.5 |

Candidates for discussion (simulated, uncalibrated; not site findings):

- **The observed day sits at the tipping point.** At 0.9× almost nothing queues (10
  vehicles or fewer on Ventura Blvd on average); at 1.1× 11 % of the demand is still waiting at 10:00 and
  about 700 vehicles are held on the street. This follows from the boundary: observed
  flow is taken as both the demand and the downstream capacity.
- **Above about 1.25× the extra demand only queues.** Served share falls roughly as
  1 / multiplier; the 3×, 5× and 10× cases are identical for every controller, because
  the ramp is one standing queue and the meter never binds.
- **The four controllers end close together.** In served share, street queue and time
  in system, differences from the unmetered run are within the spread between seeds
  (largest mean: ALINEA −1.0 min per vehicle at 1.1×, with seeds from −0.1 to −2.2).
  ALINEA is nevertheless lower in every seed at 0.9×, 1.1× and 1.25× (−0.1, −1.0 and
  −0.7 min per vehicle); see the persistent-congestion results below for the one
  comparison that passes the D016 rule.
- **Why the meter does not bind.** The queue forms between the stop line and the
  merge and reaches back through the stop line. In the congested period the ramp
  discharges about 800 veh/h into the merge; the fixed rate (960), ALINEA/Q (about
  1,120) and the Caltrans plan are all above that. After 06:45 the Caltrans plan is at
  its maximum 100 % of the time: the queue loop stays covered and override has priority.
  With about 25 vehicles of storage the queue fills it between 06:21 and 06:34 (seed 1).
- **The model's mainline station is unrealistic in the congested period.** Through
  traffic in the modelled lane is light (about 390 veh/h) and keeps moving, so the
  station upstream of the gore reads about 7 % occupancy and 14 m/s where PeMS shows
  about 48 % and 6 m/s. The plan therefore sees an uncongested freeway. The merge area
  itself crawls at about 1 m/s. A meter's mainline benefit cannot appear in this setup.
- **Timing of growth matters.** Logarithmic growth to 2× (average multiplier 1.68,
  early) serves 60 %; exponential growth to 2× (average 1.44, late) serves 68–69 %.
- **A short oscillation is absorbed, a long one is not.** ±50 % with a 10-minute
  period ends near the observed day (about 200 vehicles on the street); a 60-minute
  period more than doubles it (about 480) and doubles time in system.
- **Boundary check.** With no downstream restriction the observed day is served
  99.1–99.7 % but still holds 136–153 vehicles on the street: the modelled merge passes
  about 1,290 veh/h while the onset demand is about 1,735 veh/h for half an hour.
  Controllers are again within the seed spread (3.4–4.0 min per vehicle).

### Persistent congestion at the mainline station (D016 definition)

Minutes of the 300-minute window, three-seed mean. The PeMS station itself is below
20 m/s for 235 minutes on that morning.

| Variant | No meter | Fixed rate | Caltrans plan | ALINEA |
| --- | --- | --- | --- | --- |
| `x0.5` | 0 | 0 | 0 | 0 |
| `x0.75` | 0 | 0 | 2 | 0 |
| `x0.9` | 57 | 42 | 51 | 26 |
| `historical` | 202 | 201 | 201 | 204 |
| `x1.1` | 224 | 224 | 224 | 218 |
| `x1.25` | 256 | 258 | 258 | 263 |
| `x1.5` | 261 | 261 | 261 | 261 |
| `x2` | 286 | 286 | 286 | 286 |
| `x3`, `x5`, `x10` | 297–298 | 297–298 | 297–298 | 297–298 |
| `log_2x` | 258 | 260 | 260 | 260 |
| `exp_2x` | 246 | 246 | 248 | 247 |
| `wave_10min` | 213 | 212 | 213 | 212 |
| `wave_60min` | 211 | 209 | 206 | 206 |
| `free_exit_x1` | 176 | 138 | 178 | 124 |
| `free_exit_x1.25` | 252 | 254 | 254 | 258 |

- **Congestion becomes persistent just below the observed demand**: none up to 0.75×,
  26–57 minutes at 0.9×, about 200 minutes on the observed day.
- **One of the 33 scale-sweep comparisons passes the decision rule: ALINEA at 0.9×**,
  −31 minutes (seeds −32, −27, −35). The fixed rate (−32, +6, −20) and the Caltrans plan
  (−3, +1, −16.5) do not. This is the region prediction (3) names: near capacity, with
  the held vehicles still inside the ramp's storage.
- **From 1× upward no rule passes.** The imposed downstream boundary sets the
  throughput there. In the boundary check with no downstream restriction at 1×, ALINEA
  (−52 minutes; seeds −68, −66, −23.5) and the fixed rate (−38; −24.5, −72.5, −16) pass
  and the Caltrans plan does not (+14, −12, +2.5): its queue override holds it at the
  maximum rate and its mainline station reads free flow.
- Three seeds are weak evidence: three equal signs arise by chance one time in four.
  Treat the ALINEA result as a lead to confirm with more seeds, not as a finding.

### Bottleneck prediction check

Above 1× the served share stays within 3.6 percentage points of 100 / multiplier
(dashed line in `scale_sweep.png`). The model departs from it at 1× (96 % instead of
100 %), where its merge passes fewer vehicles than the observed onset flow.

### Fundamental diagrams (`fundamental.png`)

Flow–density, speed–density and speed–flow per lane for three sources: the analytic IDM
equilibrium of the configured parameters, the simulated loops (observed-day demand, no
meter, seed 1, 5-minute totals) and PeMS station 717816 (mean of five lanes, 05:00–10:00).
PeMS density is flow / reported speed. A simulated loop's density is occupancy /
(vehicle + loop length) and its speed is flow / density, the single-loop estimate; the
arithmetic mean of crossing speeds would put stop-and-go intervals above jam density.

- The simulated merge-area loop falls on the analytic curve near jam density, so the
  engine reproduces its own equilibrium.
- Model capacity is 2,420 veh/h per lane at 17.6 m/s (headway 1.5 s, critical occupancy
  26 %). PeMS peaks at 1,978 veh/h per lane and then breaks down. Matching that peak
  needs `T` ≈ 1.3 s; the congested PeMS points (about 45 veh/km at 7 m/s) need about
  2.1 s with 7 m per stopped vehicle. One time gap cannot fit both.
- PeMS free-flow speeds (33–37 m/s, mean of five lanes) exceed the model's 28.6 m/s,
  which is the outer lane's median.
- The simulated mainline station lies off the curve (sparse, braking traffic), which is
  the mismatch described above.

### Next tests, with the prediction stated before the test exists (2026-11-15)

| Test | Prediction |
| --- | --- |
| Calibrate `T` and `a` on Oct 10–12, hold out Oct 14 | `T` near 1.3 s reproduces the capacity; a single `T` still misses the congested branch |
| Make the modelled mainline station congest as observed | above 20 % occupancy the Caltrans plan drops to 240 veh/h per lane and the meter binds |
| Control ablation: storage length, queue override, plan thresholds | with more storage or a later override the Caltrans plan matches ALINEA's gain at 0.9× |
| 10 seeds and a second day | ALINEA's gain at 0.9× keeps its sign in at least 9 of 10 seeds |
| Driver populations (D019, added 2026-11-18) | six predictions written before the run in the [experiment record](../experiments/driver_populations.md) |

Figures in the run folder: `inputs.png`, `baseline.png`, `fundamental.png`,
`scale_sweep.png`, `congestion.png`, `shapes.png`.

## Engine problems found and fixed on the way

- **A queued vehicle drove into a leader straddling the stop line.** The meter rule
  compared the stop line with the leader's front bumper, not its rear. Found because
  the gap counter reported events on this geometry.
- **The gap counter skipped overlapping vehicles in the same lane**, so the event
  above had been invisible. Both have a regression test
  (`test_gap_counter_sees_overlaps_and_leaders_straddling_the_stop_line`).
- The first downstream boundary discharged 7–14 % more than intended because the
  virtual vehicle was advanced one step ahead of its followers; it now discharges the
  intended flow to within the test tolerance.
- **Braking at the loop entry (D017, 2026-11-16).** The loop's lower desired speed
  took effect only inside the loop, so IDM's free-road term braked arriving vehicles
  at up to −15.4 m/s² (observed day, no meter, seed 1). Drivers now anticipate a
  slower section: v₀ ahead of it is √(v_next² + 2b·distance). Hardest braking at the
  loop entry: −3.6 m/s². IDM has no braking limit either, and lane-end events reached
  −24.9 m/s²; acceleration is now bounded at −8.8 m/s² (about 0.9 g, assumed).
  Regression test: `test_slower_section_is_anticipated_and_braking_is_bounded`. All
  results above this note's date predate the change; the deck uses the rerun
  `20261116T184142_972776Z`. In that rerun a merging car that cuts in closer than
  8.8 m/s² allows now leaves a brief overlap instead of impossible braking: 15 steps in
  6 of 204 runs (`nonpositive_gap_events`), all after cut-ins the yield rule accepted.
  The headline comparison is unchanged (ALINEA at 0.9×: −31 min).

## Limits

- One freeway lane. Lane balance and the flow-matched boundary are assumptions that
  decide the capacity available to the ramp; neither is validated.
- IDM values (`a` = `b` = 2 m/s², `T` = 1 s) are project choices. The modelled merge
  passes about 1,290 veh/h after breakdown and that figure follows `a` (930 at 1 m/s²,
  1,570 at 3 m/s²), not `T`, the safety limit or the merge-zone length.
- Drivers are identical in every result above. The optional spread (D018) is assumed,
  not measured, and with one freeway lane and no passing a slower driver holds every
  vehicle behind them, which five real lanes would not.
- Demand is observed throughput: a lower bound whenever the freeway is congested, and
  the ramp count was taken under whatever metering was running that day.
- The Ventura plan table, queue trigger and detector positions are assumed.
- One day, three seeds. No calibration, no validation; tuning is not validation.
- The D016 decision rule (same sign in every seed, at least 5 minutes) has a one-in-four
  chance of passing on signs alone with three seeds. The congestion thresholds were
  chosen after the first run.
- PeMS speed at station 717816 is used as reported; whether it is measured or estimated
  from occupancy was not checked, and the fundamental-diagram density inherits it.

## Sources

Collected by web research on 2026-11-15. Quotes were read from the linked documents in
that pass; the author should re-open each before it is cited in the paper.

- [S1] Caltrans, Traffic Operations Policy Directive 21-12, 2021.
  <https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/memos-letters/11012021-topd-21-12-local-traffic-responsive-corridor-adaptive-rm-shs-a11y.pdf>
- [S2] Caltrans, Traffic Operations Manual, Ch. 215 Part 4, Ramp Metering Operations, April 2025.
  <https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/trafficops/202504-ch-215-pt-4-ramp-metering-operations-a11y.pdf>
- [S3] Caltrans District 7, 2014 Ramp Metering Annual Report.
  <https://dot.ca.gov/-/media/dot-media/district-7/documents/f0002720-2014-ramp-metering-annual-report-a11y.pdf>
- [S4] Caltrans District 7, Ramp Metering Procedure Manual, 2002.
  <https://rosap.ntl.bts.gov/view/dot/27601/dot_27601_DS1.pdf>
- [S5] G. Gomes, Optimization and Microsimulation of On-ramp Metering for Congested
  Freeways, PATH UCB-ITS-PRR-2004-44. <https://escholarship.org/uc/item/95k1q411>
- [S6] Caltrans, Ramp Metering Design Manual, October 2022.
  <https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/ramp-metering/202210-rmdm-a11y.pdf>
- [S8] S. Shladover and X.-Y. Lu, Field Test of Coordinated Ramp Metering, CA16-2445, 2017, Table 2-2.
  <https://dot.ca.gov/-/media/dot-media/programs/research-innovation-system-information/documents/ca16-2445-finalreport-a11y.pdf>
- [S9] R. Horowitz, P. Varaiya, R. Sanchez, Field Test Implementation of Queue Control, CA11-2055, 2011.
  <https://dot.ca.gov/-/media/dot-media/programs/research-innovation-system-information/documents/task-2055-tsm-a11y.pdf>
- [S10] Caltrans, 2017 Ramp Metering Development Plan, p. 110 (LA-405 PM 39.09 SB Ventura Bl.).
  <https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/ramp-metering/rampmeteringdevelopmentplan-a11y.pdf>
- [S11] Caltrans, 2023 Ramp Metering Development Plan, Table 10.
  <https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/ramp-metering/2023-rmdp-a11y.pdf>
- [S20] R. Sanchez, G. Gomes, R. Horowitz et al., Ramp Metering Design Tools and Field
  Test Implementation of Queue Control, UCB-ITS-PRR-2010-16. <https://escholarship.org/uc/item/7tq3h0px>
- IDM, ALINEA and ALINEA/Q: see the [literature record](research/literature_review.md).
  IDM values checked on 2026-11-15: Treiber, Hennecke and Helbing (2000), Table I, read
  from the arXiv copy (cond-mat/0002177): `v0` 120 km/h, `T` 1.6 s, `a` 0.73 m/s²,
  `b` 1.67 m/s², `δ` 4, `s0` 2 m, `s1` 0, length 5 m; acceleration is Eq. 6 and the
  desired gap Eq. 7. The author's notes
  (<https://traffic-simulation.de/info/info_IDM.html>) give as realistic `T` 0.8–2 s,
  `a` 0.8–2.5 m/s² and `b` about 2 m/s². The project values (`T` 1.0 s, `a` = `b` =
  2.0 m/s²) lie inside those ranges and are not calibrated.
