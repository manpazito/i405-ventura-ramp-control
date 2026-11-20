# Decision log

Use this record to keep research rationale and implementation aligned. Each future
entry needs date, status, decision, evidence, affected documents/code, owner, and
what would justify reconsideration. Update the relevant model/interface/experiment
documents in the same change. A candidate finding is not a validated contribution
and must not automatically modify a working paper.

## Initialization — 2026-11-07

| ID / status | Decision and rationale | Revisit when / evidence |
| --- | --- | --- |
| D001 — accepted | Preserve uv project `adaptive-ramp-metering`, import package `adaptive_ramp_metering`, `src/` layout, authors/version/build backend and greeting CLI. Original Python requirement `>=3.14` and `.python-version` `3.14` remain. Inspection found Python 3.14.10 and uv 0.13.6, no dependencies or lockfile, and no Git commits; existing files were untracked. | A concrete compatibility need arises; do not silently change Python or package behavior. |
| D002 — accepted | Initialization delivers documentation, planning YAML, directory placeholders, required dependencies, and one environment smoke test. Add NumPy, pandas, SciPy, Matplotlib, PyYAML with uv; pytest/Ruff in the dev group; retain `uv.lock`. | New dependencies require a demonstrated task, not anticipated flexibility. |
| D003 — accepted | Use the revised course guide's common simulation/observation/estimation/prediction/TMC foundation and exchange names. Guide identity and requirement map are in [scope](research/scope_and_assumptions.md). | Instructor issues revised requirements or a different scaffold. |
| D004 — provisional | Anticipate `traffic_signal_control`; `pathway_confirmed: false` in [project config](../configs/project.yaml). Retain `cav_control` as the alternative. Signal work uses the supplied isolated intersection; site-interchange substitution is not assumed. | Team confirms pathway and obtains scaffold; reviewed guide asks for confirmation by November 9. |
| D005 — open | Select a justified second model **or** independent calibration/validation evidence, plus a separate focused controller comparison/uncertainty/ablation for CEE 281. No choice or successful evidence yet. | Data suitability and model feasibility are assessed. |
| D006 — provisional | Document IDM, conservation/storage, ALINEA, and a finite-horizon delay formulation as candidates/background. Proposed queue service-before-admission order is explicit. No numerical parameters, model/controller selection, MPC commitment, or calibrated defaults. | Source-backed design and verification justify implementation; record any alternate within-interval order. |
| D007 — accepted | Younggun owns forecasting methods, implementation, experiments and model choice. Only an exchange contract and ownership note are provided; forecasting directory contains only `.gitkeep`. | Explicit instructions authorize a forecast change with ownership respected. |
| D008 — accepted | No data acquisition during preparation. Portals/request procedures are cataloged separately from data availability. Use immutable raw files, provenance/checksums, explicit units/timezones, and separate observed/synthetic and calibration/validation data. | A bounded later acquisition task is authorized and access/coverage are verified. |
| D009 — accepted | Count all requested demand, internal vehicles, exits and external waiting; do not erase arrivals at a full boundary. Withhold truth from control. | Only explicit, conserved diversion/abandonment or measurement mechanisms justify extensions. |
| D010 — accepted | Keep bulk data/results, environments, caches and credentials out of Git by default; version documentation/configuration and lockfile. Do not copy the course PDF or create placeholder simulation outputs. | A small permitted fixture or reviewed result is deliberately selected for versioning. |

## PeMS acquisition pipeline — 2026-11-07

| ID / status | Decision and rationale | Revisit when / evidence |
| --- | --- | --- |
| D011 — accepted | Authorized bounded acquisition task (supersedes D008's "no acquisition"): implement a reproducible PeMS District 7 Station 5-Minute scan/screen/export pipeline in `adaptive_ramp_metering.data.pems` (`uv run arm-pems`). Reuse the MIT-licensed `pems-data` package (wcc961129/pems-data-downloader, pinned to commit `a66cdf3`) for browser login and resumable authenticated downloads instead of re-implementing PeMS authentication; it adds Playwright/Chromium and `requests`. Catalog listing, staged scanning, screening, ranking and SI export live in this repo because the package aborts on any missing day, deletes raw archives, and has no screening. Method and outputs: [PeMS pipeline](../data/README.md). Station IDs 716744/717816/765197 and incident dates are team-reported inputs in `configs/pems.yaml`, verified only once `inventory`/`scan` run. | Downloader upstream changes break the catalog JSON; team prefers a stdlib-only client; a screened dataset is selected (record its manifest and split here). |

The runtime/development requirements were added using `uv add` / `uv add --dev`.
Tooling uses Ruff's Python 3.14 target and a minimal pytest import test. Environment
checks are separate from the prospective traffic validation gates.

## Synthetic two-merge demo — 2026-11-08

| ID / status | Decision and rationale | Revisit when / evidence |
| --- | --- | --- |
| D012 — accepted for prototype only | The user's explicit simulator-demo request authorizes this bounded exception to initialization-only scope. The user confirmed three ramp lanes narrowing to two, then one, before a separate freeway merge. Implement a deterministic aggregate CTM and offline replay in `simulation/demo.py`, configured separately by `configs/demo.yaml`; preserve the greeting, PeMS work, and Younggun's forecasting boundary. The design record specifies equations, synchronous update order, fixed merge priority, synthetic parameters, storage/conservation, timestamps, metrics, and source evidence. Retain boundary waiting and terminal inventories. No data download or controller is part of this task. Requested by manpazito; ongoing research component ownership is still unassigned, and this standalone prototype performs no team component exchange. | Confirm geometry and data, assign research owners, then select the course microscopic model and independent evidence route. Do not treat the demo as calibration, a controller comparison, or completion of either CEE 281 evidence obligation. |

## Microscopic metering demo — 2026-11-09

| ID / status | Decision and rationale | Revisit when / evidence |
| --- | --- | --- |
| D013 — accepted for prototype only | The user's request for a runnable on-ramp metering demo while data collection continues authorizes a second bounded exception. Implement a microscopic prototype in `simulation/micro.py` with `control/metering.py` and `configs/micro.yaml`: IDM car following (Treiber et al. 2000 form, project parameter values), mandatory lane changes with the MOBIL safety criterion, a project merge-yielding rule, Poisson boundary arrivals, a one-vehicle-per-green meter at an assumed stop line, virtual point detectors, bounded ALINEA with ALINEA/Q queue control and hold-then-fixed fallback, fixed-rate and unmetered baselines, a D/D/1 vertical-queue reference, seeds 1–3, and course-format records. The [design record](micro_demo.md) states equations, rules, parameters and limits. The CTM demo (D012) is retained unchanged. Requested by manpazito; component owners are still unassigned and Younggun's forecasting boundary is untouched (no forecast is used). | Verify geometry, meter location and detector positions; choose IDM parameters from observed flows (capacity changes ≈ 2× across published value sets); settle the merge rule against observations or a second model; tune `o*`, `K_R`, startup rate; decide whether the demo's D/D/1 comparison or an independent calibration route serves the CEE 281 model-evidence obligation. Not a calibration, not a controller recommendation. |

## Simplified merge and paper draft — 2026-11-10

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D014 — accepted for synthetic prototype and draft only | The user requests one ramp lane with an acceleration section merging into one mainline lane, a Plotly visualization, and a TRR-oriented case-study paper at `docs/paper/main.tex`. Reuse `micro.Simulation` unmetered through `simulation/simple_merge.py` and a separate configuration; use assumed geometry now, not an unverified OSM reconstruction. Add independent per-step accounting/gap audits, two synthetic demand cases, three seeds, traceable output tables, and source hashes. The design record defines coordinates, equations, assumptions, metrics, and the remaining evidence obligations. This authorizes the named implementation and manuscript drafting; no forecasting changes, traffic downloads, operational recommendations, or submission. Ongoing nonforecasting ownership remains unassigned. | User supplies lane details; verify dated geometry and boundaries, calibrate on one data split and validate independently, test merge-rule and geometry sensitivity, and complete the focused controller/uncertainty/ablation study. A polished manuscript does not establish novelty or empirical validity. |

## Site scenario and demand ablation — 2026-11-15

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D015 — accepted for a first site scenario and ablation only | The user asks for a fully runnable simulation with assumptions taken from PeMS and Caltrans, the metering method normally in place, and a first ablation on demand (historical, scaled, logarithmic and exponential growth, oscillation). Reuse `micro.Simulation` through `simulation/ablation.py` (`uv run arm-ablation`) and `configs/i405.yaml`. Geometry: the team's AutoCAD sketch, with the loop arcs and the user-confirmed red meter line measured from the PDF plot (`scripts/`). Demand: Tuesday 2022-10-11, 05:00–10:00, stations 716744 and 717816. The one-lane engine gets two explicit assumptions: lane balance for the merge lane's through traffic and a flow-matched downstream boundary held fixed across variants. Control: a `caltrans` mode (stepwise local traffic-responsive plan, queue override, two metered lanes, alternating release) next to `none`, `fixed` and `alinea`; the plan values for this ramp are unpublished and assumed. Engine changes: optional exit boundary, upstream mainline detector, detector loop length, two spillback metrics, and two gap/stop-line fixes with tests. The [design record](i405_ablation.md) lists sources, assumptions, results and limits. Requested by manpazito; forecasting is untouched. | Calibrate IDM acceleration against onset throughput and validate on a held-out day; replace the lane-balance and boundary assumptions with a multi-lane model or upstream-station demand; obtain the ramp's actual plan, detector positions and HOV treatment from Caltrans District 7; re-open the cited sources before using them in the paper. Not a calibration, not a validation, not a controller recommendation. |

## Testable question, congestion definition and fundamental diagrams — 2026-11-15

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D016 — accepted for the mid-report question and the 2026-11-16 update | The user asks for a testable question with numbers, fundamental-diagram plots, and a presentation that follows the mid-report sections. **Congestion definition** (`ablation.congestion` in `configs/i405.yaml`): a 30 s interval at the simulated mainline station upstream of the gore is congested when its mean speed is below 20 m/s (the line already used to read congestion at PeMS station 717816) or its occupancy is above 26 % (the IDM equilibrium occupancy at capacity for the configured parameters and a 6 ft loop); congestion is persistent when at least 10 consecutive intervals are congested, which is one 5-minute PeMS interval. `arm-ablation` reports the minutes of persistent congestion of every run (`congested_min`). The merge-area loop is not used for the definition: slow merging vehicles trip it at half the observed demand. **Decision rule** for controller comparisons: a rule differs from no meter when the paired difference has the same sign in every seed and a mean of at least 5 minutes. **Bottleneck prediction** drawn on the scale sweep: served share ≈ 1 / multiplier above 1×. Added `fundamental.png` (analytic IDM equilibrium, simulated loops, PeMS station) and `congestion.png`. These definitions were written after the first ablation run and are held fixed for later tests; predictions for the next tests are listed, before those tests exist, in the deck's timeline and in the [design record](i405_ablation.md). The mid-report itself is drafted at `docs/mid_report/mid_report.tex` at the user's request; it reports this run and awaits the author's review. Requested by manpazito; forecasting is untouched. | The thresholds and the three-seed sign rule are choices. Revisit after calibration (the critical occupancy moves with `T`), and replace the sign rule with an interval once at least 10 seeds are run. |

## Curve anticipation, braking limit and dynamics figures — 2026-11-16

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D017 — accepted for the engine and the 2026-11-16 update | The user asks for a more realistic simulation that accounts for the ramp's curves, plus flow-density, shockwave, trajectory, gap/speed/acceleration and lane-change stability figures and a fact sheet. IDM has no curvature term; the loop entered the model only as a lower section desired speed (7 m/s, assumed from a radius of about 15 m, i.e. about 3.3 m/s² lateral). Because the step took effect only inside the loop, IDM's free-road term braked vehicles at up to −15.4 m/s² at the loop entry (observed day, no meter, seed 1, previous engine). **Change 1:** `Simulation.desired_speed` lowers v₀ ahead of a slower section to √(v_next² + 2b·distance), so drivers reach the curve speed braking at the comfortable b; the hardest braking at the loop entry became −3.6 m/s². **Change 2:** acceleration is bounded below by `MAX_DECEL_MPS2` = 8.8 m/s² (about 0.9 g, tyre-road friction on dry pavement, assumed), because IDM itself has no braking limit and lane-end events reached −24.9 m/s²; it binds rarely. Where a merging car cuts in closer than 8.8 m/s² allows, the follower now overlaps briefly instead of braking impossibly hard; the existing `nonpositive_gap_events` counter records it (rerun `20261116T184142_972776Z`: 15 steps in 6 of 204 runs, all after merge cut-ins accepted by the project yield rule). Both apply to every configuration (`micro.yaml`, `i405.yaml`, the live demo). The deck's results were regenerated from a new `arm-ablation` run. Dynamics figures (built by `docs/presentations/build_update_nov16.py` from single-seed re-runs with 1 s samples) are descriptive: the shockwave comparison uses Edie cells and Rankine–Hugoniot, and the stability panel uses a linear string-stability criterion derived in the script and checked against a platoon simulation (stable and unstable parameter sets). Requested by manpazito; forecasting is untouched. | The curve speed and the friction limit are assumptions: replace them with the loop's measured radius and a design-speed or field-speed source; tighten the merge-yield acceptance or test a model with a constant-acceleration braking heuristic for tight cut-ins (Kesting, Treiber and Helbing 2010; verify before citing); consider per-driver heterogeneity only once calibration data exist. |

## Per-driver IDM values — 2026-11-18

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D018 — accepted for the engine as an optional sensitivity check with assumed spreads | The user asks for randomness in the IDM parameters: each driver's value drawn from a normal distribution around the fixed value with a small variance, applied to several parameters, with drivers as objects. `simulation/micro.py` gets a `Driver` class that holds one driver's own `a`, `b`, `T`, `s0`, `δ` and a desired-speed factor and computes that driver's IDM acceleration; every `Vehicle` carries one. `Driver.sample` draws θᵢ = θ̄(1 + c·ε), ε standard normal clipped at ±2, independently per parameter; `vehicle.spread` gives c for any of `v0`, `time_gap`, `a`, `b`, `s0` (each below 0.5, so every value stays positive), and without it every driver has the fixed values. A driver's own values enter their IDM acceleration (car following, the lane-change safety test for the merging driver and the new follower, the decision to yield), the gap they need to enter the network and their approach to a slower section; the merge rule's thresholds (`b_safe`, the zone, `s0` as the "alongside" and lane-end margin), the downstream boundary and the analytic equilibrium curves keep the fixed values. Drivers come from one random stream per origin, separate from arrivals, with all five draws always taken, so the k-th driver of an origin depends only on the seed. This replaces an unrecorded earlier version (three multipliers on `v0`, `T`, `a` stored on the vehicle, already labeled D018 in `configs/i405_spread.yaml`, with no documented result; its run folder `results/spread-check/20261116T214616_277183Z` is empty). `configs/i405_spread.yaml` now also varies `b` and `s0` at 10 %. **Evidence:** ten fixed-value reference runs (`micro.yaml` peak and heavy × three controllers, seed 1; `simple_merge.yaml` loaded, seed 2; `i405.yaml` 1.1× with no meter, Caltrans and ALINEA, seed 1) give identical metrics, traces, observations and commands before and after the change (compared by SHA-256, first 64 bits); new tests in `tests/test_micro.py` cover the distribution, the pairing, the configuration check and a driver's own values in car following, the approach to a slower section, the entry gap, lane-change safety and yielding, and all 18 deliberate breaks of the lines they guard made a test fail. Spread results differ from the earlier version: five draws per driver instead of three, and a driver now approaches a slower section at their own speed and braking. Equations: [car_following.md](mathematical_model/car_following.md); engine notes: [micro_demo.md](micro_demo.md). This sets aside D017's note to wait for calibration data: the spread is an assumption for sensitivity checks, off by default. The sampling rule was replaced the same day: see D019. Requested by manpazito; forecasting is untouched. | The normal form, the independence between parameters and every spread value are assumptions: replace them with distributions estimated from individual headways or trajectories. State the prediction in [i405_ablation.md](i405_ablation.md) before running the spread check. Decide on the merge-yield finding of 2026-11-18 below before reading controller differences from spread runs. `δ` and vehicle length are not varied; drivers' values are not written to the trace. |

## Driver populations: shapes, merging limit and comparison tool — 2026-11-18

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D019 — accepted for the engine and the comparison tool; study run on 2026-11-18, results are candidates | The user asks which parameters and distributions commercial simulators and papers use for differences between drivers (car following and lane changing), whether uniform, normal or skewed shapes are preferred, and for an implementation from which differences and conclusions can be extracted. **Sampling (replaces the clipped normal of D018):** each driver draws one percentile per parameter. `vehicle.shape` turns it into a `normal` (truncated at two standard deviations), `uniform` or `lognormal` factor on the fixed value. Every shape has exactly mean 1 and the coefficient of variation given in `vehicle.spread`, so `spread` is now the realized coefficient of variation and two shapes differ only in symmetry and tails; a configuration whose shape could reach zero is rejected. A driver keeps their percentiles under every shape and spread, so cases are paired driver by driver. **Lane-changing preference:** the spread key `b_safe` gives a driver an own safety limit for their own mandatory lane change (the braking they accept and impose) and for braking at a lane end; the yield rule keeps the fixed limit. **Comparison tool:** `simulation/drivers.py` (`uv run arm-drivers`) runs driver cases × demand variants × controllers × seeds on the site scenario, with the same arrivals and driver percentiles per seed, and writes paired differences with 95 % t intervals, the effect of each metering rule under each population, the realized populations and three figures. **Cases** (`configs/i405_drivers.yaml`): identical drivers; desired speed only at 10 % (SUMO's default); `v0`, `T`, `a`, `b` at 11.55 % as a uniform (the 80–120 % rule of Kesting, Treiber and Helbing 2010), a normal and a lognormal; the merging limit alone at 25 %; and an `empirical` case with spreads observed or calibrated at other sites (`T` 20 %, `a` and `b` 33 %, `s0` 48 %, lognormal). **Evidence:** implementation checks, and one study of 840 runs with six predictions written before it ran. The ten fixed-value reference runs of D018 are still identical (SHA-256, first 64 bits); tests cover the mean, spread, range, symmetry and pairing of each shape, the configuration check, the merging limit and the difference statistics, and all 14 deliberate breaks of the lines they guard made a test fail. The study's outcome is recorded below under findings awaiting validation. Sources and the chosen cases: [driver heterogeneity review](research/driver_heterogeneity.md); question, predictions and results: [experiment record](../experiments/driver_populations.md); equations: [car_following.md](mathematical_model/car_following.md). Requested by manpazito; forecasting is untouched. | Spreads and shapes come from other sites and other models, not from this site: replace them when individual headways or trajectories for I-405 exist. Parameters are drawn independently; the review discusses what that leaves out. Probe of 2026-11-18: with spreads wide enough to give time gaps near 0.1 s the 0.5 s step produces more than 100 overlap steps per run, so the smallest time gap a case can draw should stay near or above the step. The merge-yield finding of 2026-11-18 still applies to every case with a spread. |

## Team and scope — 2026-11-18

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D020 — accepted | manpazito states on 2026-11-18 that Younggun is no longer on the team and that the project has shifted from predictive control to the I-405 case study. The project is an individual one and manpazito owns every component. Forecasting and predictive control are out of scope; `src/adaptive_ramp_metering/forecasting/` stays empty and the prediction exchange contract in interfaces is kept for reference only. Supersedes D007. The mid-report names one author and has no forecast task in its timeline. This entry was drafted on the `mid-report` branch (`patches/decisions.patch`) and entered here on 2026-11-19, when the documents it names were brought into line with it (D024). | How the change affects the course's final pathway (signal control or CAV) is not stated and stays unconfirmed. |

## Ramp/mainline mix study and site characterization — 2026-11-19

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D021 — accepted as a focused CEE 281 study of D005, chosen before its results; run on 2026-11-19, results are candidates | manpazito asks whether congestion at the ramp comes from a congested mainline that does not let ramp traffic in, and whether the project focus should shift to that. The answers were settled in a question-and-answer session on 2026-11-18 and 2026-11-19, and the predictions were signed off before any run. **Decision:** the project keeps ramp metering at the Ventura on-ramp as its subject. A study that scales ramp demand and merge-lane through demand separately, under the flow-limited exit and the free exit, is the one focused CEE 281 study. It replaces the control ablation (storage, queue override, plan thresholds) that the mid-report timeline planned for 2026-11-23, and its shoulder-lane level is the test planned for 2026-11-20 (make the modeled mainline congest as observed). The driver-population study (D019) stays supporting evidence. D016 (question and congestion definition) is unchanged. **Design:** three ramp levels × four mainline levels (0.75, 1 and 1.25 times the lane-balance profile, and the observed shoulder lane, PeMS lane 5 of station 717816, as an upper bound) × two exits, four metering rules, seeds 1 to 10, 960 runs. `configs/i405_mix.yaml` is a study file that names the site configuration (`site:`) and is read by `arm-ablation` (`ablation.load_config`); a variant may carry `ramp_factor`, `mainline_factor` and `mainline: shoulder_lane`; `--analytic` prints the before-run table (static capacity, deterministic queue, and the capping strategy of Lecture 05B) without simulating; the report adds `mix_cells.csv`, `mix_effects.csv` and `mix_contrasts.csv`. No engine change. **Decision rule:** a paired difference over the 10 seeds counts when its 95 % t interval excludes zero and its mean reaches 5 minutes of congestion or 2 % of the unmetered ramp exits; this is the interval rule of D019 in place of the three-seed sign rule, as D016's revisit clause asks. **Scope accepted by manpazito:** under the limited exit "total served is fixed" is an input of the boundary, not a result; a negative headline is acceptable; the detector gap through the Sepulveda Pass is accepted; no new engine work while the final pathway is pending; the course's video/manual audit becomes a count of the ramp queue on 2026-11-20. **Course material:** design choices and claims were checked against the lecture slides in `docs/lectures` (02, 03, 05A, 05B); the record lists every check. **Evidence so far:** implementation checks only. Equal ramp and mainline factors give exactly the demand of the plain scale variant; four new tests in `tests/test_ablation.py` and four in `tests/test_bottleneck_check.py`; all 19 deliberate breaks of the new lines made a test fail. Question, site characterization, before-run numbers, predictions and results: [experiment record](../experiments/ramp_mainline_mix.md). Requested by manpazito. | Calibration of `T` and `a`: the static capacity, the 26 % threshold and the merge's discharge move with them, so the study is repeated and its levels re-centered. The site count of 2026-11-20: how the meter runs, the ramp queue, and where station 717816 sits relative to the gore. A multi-lane or macroscopic merge model that places reality between the two mainline bounds. Observed data through the Sepulveda Pass that locate the head of the queue. A constant-demand experiment for the per-vehicle comparison of ramp and mainline demand, which this design cannot make. |

## ALINEA set value — 2026-11-19

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D022 — accepted | manpazito asks for ALINEA to be verified against the lecture material and then for its target to be the critical occupancy. **Check:** the control law, its direction, the anti-windup rule, the detector distance (43.5 m against 40 m in Paris), the sample interval and the gain (54 against 70 veh/h per percentage point) agree with Lecture 05B (slide 26) and with Papageorgiou, Hadj-Salem and Blosseville (1991), read in full; the set value did not. The paper puts it at the critical occupancy (29 % in Paris, "which corresponds to capacity flow"); the site configuration had 0.34, carried over from the demo and rescaled for the loop length, where the merge-area detector's flow peaks at 23 to 25 % and the equilibrium curve at 26.05 %. **Decision:** `control.alinea.target_occupancy` is the critical occupancy of the configured IDM equilibrium curve as the configured loop sees it: 0.26 in `configs/i405.yaml` and `configs/i405_spread.yaml` (was 0.34), 0.22 in `configs/micro.yaml` and `configs/simple_merge.yaml` (was 0.25; unused in the latter, which has no meter). A test recomputes that occupancy for each of the four files and fails when the target, or D016's occupancy line, is more than 0.005 away; it fails with 0.34 and with 0.25. Gain, interval, bounds, detector position and the queue rule are unchanged. **Evidence:** implementation checks, and one test of 30 runs written up before it ran (ALINEA at 0.24 against 0.34, seeds 1 to 10, paired with the identical-driver runs of D019). Its prediction of a counted improvement at 0.9× and at the free exit was **contradicted**: −0.3 min (−7.6 to +7.0) and −6.5 min (−13.7 to +0.7); on the observed day +1.2 min (−2.8 to +5.3), as predicted. The set value hardly matters in this model because the measured occupancy is almost never near it and the queue rule decides most commands (103 to 460 of 600 decisions). ALINEA results obtained with 0.34 (D015, D016, D019) are therefore not expected to change materially, but they were not rerun. The ramp/mainline mix study (D021) is run with 0.26; its first run, at 0.34, was stopped unread. Record: [ramp_metering.md](mathematical_model/ramp_metering.md#alinea-checked-against-the-lecture-and-the-original-paper-2026-11-19). Requested by manpazito. | Calibration of `T`: the critical occupancy moves with it (22.3 % at 1.3 s) and the test then fails until both values are recomputed. A measured flow and occupancy relation at the real merge. The source of the queue rule (Smaragdis and Papageorgiou 2003) could not be opened and its formula is unverified. The queue target (20 of about 25 stored vehicles) and the alternation between the two rules. A detector downstream of the lane end, which is where the paper puts it. |

## Calibration — 2026-11-19

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D023 — accepted | manpazito reports that the professor asks for parameters to be calibrated and asks how that is done and what the standard is. **Standard followed:** there is none for a self-written microsimulation; the nearest is FHWA's Traffic Analysis Toolbox Volume III (2004, rewritten 2019), with Dervisoglu et al. (2009) for the fundamental diagram from PeMS data and Treiber and Kesting (2013) for what a data set can identify. **Step 1, no simulation** (`scripts/calibrate_fd.py`): on three days (10 to 12 October 2022) the free-flow speed gives `v0` = 29.1 m/s; the largest 5-minute flow, 1,978 veh/h per lane, gives `T` = 1.51 s by matching the equilibrium capacity (FHWA's capacity calibration by the mean headway); the shape of the free-flow branch gives `delta` = 20 (the smallest value within 5 % of the best flow error). On five other days the flow error at the observed densities is 271 veh/h against 558 before, and the free-flow branch is within 15 % in 87 % of intervals; the congested branch is not reproduced (11 %). **Step 2, simulated** (`configs/i405_validation.yaml`, `scripts/validation_table.py`): by a rule written before the run, `a` = 2.5 m/s² among 1.5, 2.0 and 2.5, the value with the smallest error in ramp vehicles served on the three calibration days (3.2 %). On three held-out days (3, 14 and 25 October) vehicles through the merge lane are within 3 %, ramp vehicles within 5 % and congested minutes within 10 %, with GEH at most 1.3: FHWA's example criteria are met. **Consequences:** `configs/i405.yaml` and `configs/i405_spread.yaml` carry the calibrated values with a `[calibrated]` label; ALINEA's set value and D016's occupancy line move to 0.158, the critical occupancy of the calibrated curve, and the test of D022 enforces both; "a calibrated ALINEA" means that set value, not a tuned gain. **Not calibrated, and why:** `s0` and the vehicle length (no standstill in the data), `b` and the merge rule (no trajectories), the ramp's metering plan (unpublished), demand under congestion (counts are what was served); capacity in FHWA's sense (queue discharge) cannot be measured because the station sits inside a queue. PeMS derives speed at this station from flow and occupancy with a fixed effective length of 10.2 m, so the speed scale is PeMS's. `a` = 2.5 is at the upper end of the range its authors call realistic. This is the CEE 281 calibration and validation evidence. Every result recorded before this entry (D015, D016, D019, D021, D022 and the mid-report) used `T` = 1 s, `delta` = 4, `a` = 2 m/s² and stands as a record of that model. Record: [calibration](../experiments/calibration.md). Requested by manpazito. | Vehicle trajectories at a merge (for `a`, `b` and the merge rule); a detector with measured speed; observed data downstream that show an active bottleneck; the field count of 2026-11-20; a model with a capacity drop in its equilibrium relation, if the congested branch has to be reproduced. |

## Direction and the one-factor ablation of the rules — 2026-11-19

| Decision | Basis and boundary | Revisit when |
| --- | --- | --- |
| D024 — accepted; implemented; study run and scored on 2026-11-19 | manpazito asks for the project to be cleaned up around one direction: the effects of ramp metering at the real I-405 southbound on-ramp at Sepulveda and Ventura, comparing the rules in actual use with ALINEA, by ablations that fix every parameter but one and test a calibrated ALINEA against changed IDM parameters, changed demand and the like, following the course rubric. **Direction:** stated in [the study design](study_design.md) and the README. The rules compared are no meter, a fixed time-of-day rate, the Caltrans local traffic-responsive plan with queue override, and ALINEA with its set value from the calibrated model. **Baseline:** the calibrated site scenario (D023) on the observed day. **Study:** `configs/i405_ablation.yaml`, 35 cases that each change one thing (demand level, ramp or mainline demand alone, the observed shoulder lane, demand waves, a free exit; `T`, `a`, `b`, `s0`, `v0`, `delta`; two driver populations; a fault of ALINEA's detector; ALINEA's gain, set value and queue rule; the Caltrans plan's thresholds and override; the fixed rate), four rules, seeds 1 to 10, 1,400 runs; a test checks that every case changes exactly one thing and that the change takes effect. Eight predictions were written before the run in [the record](../experiments/rule_ablation.md). **Tooling:** `simulation/drivers.py` became a general case runner (`uv run arm-study`; `arm-drivers` is kept): a case may set any existing configuration value by its dotted path, replace the demand, or carry a detector fault, and rules are compared with each other in `rule_differences.csv`. **Clean-up:** one front door (README with one run command), AGENTS.md and the requirement map rewritten for the current project, the research questions reduced to those being answered, the documents that described a two-person team and an unimplemented project brought into line with D020, the three synthetic prototypes marked as such, `configs/simulation.yaml` (empty placeholders) removed. **Course rubric:** the [requirement map](research/scope_and_assumptions.md) lists every item of the guide with its evidence. Not met: the final pathway (a CAV or traffic-signal controller on the supplied scaffold) and versioned code (`main` has no commit and no remote). The observation component is met in a minimal form ([record](../experiments/estimate_and_forecast.md)). The earlier studies (D015, D019, D021) stay as supporting records of the uncalibrated model. **Result (run `20261119T200447_267513Z`, 1,400 runs, all conserving, no overlap):** of the eight predictions five are supported (2, 3, 5, 7, 8), one is contradicted (1: the fixed rate has 9 fewer congested minutes than ALINEA and than the plan at the baseline) and two are contradicted in part (4 for the time gap, 6 for the plan's override). At the observed demand no rule differs from no meter; the summary is under findings below and the full record in `experiments/rule_ablation.md`. Requested by manpazito. | The instructor's answer on the final pathway for an individual project; the field count; a change of baseline day; results of the study that contradict its design. |

## Open decisions

- Confirm the final pathway for an individual project (CAV or traffic-signal control)
  and obtain its supplied scaffold. The course guide requires it in addition to the
  ramp-metering foundation.
- Commit the repository and give it a remote; `main` has no commit.
- The field count at the ramp (planned 2026-11-20): how the meter runs, the ramp queue,
  and where mainline station 717816 sits relative to the gore.
- Obtain the ramp's own metering plan, detector positions and HOV treatment from Caltrans
  District 7.
- Decide whether to revise the merge rule: a yielding vehicle ignores its own-lane
  leader (finding of 2026-11-18), and the calibrated acceleration sits at the upper end
  of its range (D023). Added 2026-11-19 (rule ablation record): with both
  approaches queued the merge passes 1,440 veh/h, 27 % below the static capacity, and
  it shuts the ramp out while the freeway lane flows near capacity, where PeMS shows
  ramp vehicles entering.
- Whether the driver-population study (D019) should be repeated on the calibrated model;
  the rule ablation (D024) carries two of its populations.
- Tie the queue rule's target to what its loops can count. The target of 20 vehicles
  was set from the whole storage (24.6 vehicles); between the entry loop and the stop
  line 23.4 vehicles fit at the model's 7 m and 18.5 at the 8.84 m of the Caltrans
  manual, and with 8 m the rule stops working (rule ablation, case `s0_high`).
- Replace or complement minutes of congestion as the primary measure: it saturates at
  the observed demand and falls when the time gap rises (rule ablation, prediction 4).

## Findings awaiting validation

The demos illustrate synthetic queue accumulation, blocked boundary admissions,
merge breakdown and the metering trade-off. These are expected mechanisms under
assumed inputs, not empirical site findings, calibration outcomes, or research
contributions. The microscopic demo's [findings](micro_demo.md#findings-awaiting-discussion-synthetic-seeds-13-run-of-2026-11-09)
(2026-11-09) include a factor-two capacity sensitivity to IDM `a`, `b`, `T` and a
detector-placement result; both need observed data before use.

- 2026-11-19, which driver trait matters (candidate; calibrated model, observed day, no
  meter, 220 runs, seeds 1–20, five predictions written before the run;
  [record](../experiments/driver_traits.md)). With the spreads of `drivers_field` varied
  one at a time, the spread of acceleration `a` (33 %, lognormal) adds 3.22 min per
  vehicle to 6.66, 87 % of the 3.71 min of all six together, and about 100 vehicles to
  the street queue; the time gap's spread adds 1.45 min although it leaves the static
  capacity of a platoon unchanged; `b`, `s0`, `v0` and the merging limit add at most
  0.55 min. The six effects sum to 5.25 min, more than together (interaction −1.54,
  −2.49 to −0.59). Uniform, normal and lognormal at 25 % on `T`, `a`, `b` differ by at
  most 0.28 min per vehicle and in no measure by a counted amount. Two of five
  predictions supported, two contradicted, one in part. Limits: spreads from other
  sites, independent traits, no meter, one day.
- 2026-11-19, one-factor ablation of the metering rules (D024; simulated, calibrated in
  part, one observed day, ten seeds; [record](../experiments/rule_ablation.md)). At the
  observed demand no rule differs from no meter by a counted amount in congestion, and
  the rules are within 0.12 min per vehicle of it; ALINEA's queue rule sets the rate in
  464 of 600 intervals and the plan's override in 441. ALINEA reduces congestion by a
  counted amount at 0.9 times the demand (13 min), with 25 % less ramp demand (7 min),
  with 25 % less through traffic (16 min) and with a free exit (10 min), never above the
  observed demand, and in none of these is time per vehicle lower. The fixed rate has 9
  fewer congested minutes than ALINEA and than the plan at the baseline and holds a
  longer street queue. A fixed rate of 6 vehicles a minute per lane, or ALINEA without
  its queue rule, removes 136 and 172 congested minutes and adds 4.7 and 1.7 min per
  vehicle. Time per vehicle without a meter moves by +8.4 min for a 20 % longer time
  gap and +5.8 min for 20 % less acceleration, against at most 0.12 min for any rule.
  ALINEA is insensitive to its gain and set value; with its detector missing it behaves
  as the fixed rate. Candidates, not findings about the site.
- 2026-11-07, PeMS coverage screening of October 2022 (see
  [pipeline findings](../data/README.md#findings-2026-11-07)): on-ramp 716744 fully
  observed on all 21 weekdays; mainline 717816 passes 9 of 21 days with lane-level
  imputation on the rest; off-ramp 765197 never observed; best 7-day on-ramp sample
  Mon Oct 10 – Sun Oct 16, 2022 (ramp 99.9 % observed, no incident days; exported as
  `observed_pems_ventura_20221010_20221016_5min_v1`, split unassigned); the ramp and mainline stations are 0 % observed in sampled
  October weeks of 2023, 2024 and 2025; upstream 777066 is a strong boundary station, downstream mainline
  coverage is poor. Calibration/validation dates are **not** chosen yet. Coverage flags
  are not measurement validation.
- 2026-11-18, merge-yield rule under driver variation (candidate; synthetic
  `configs/micro.yaml`, scenario `peak`, seeds 1–3, no meter and ALINEA). With a spread
  of 5 % on `v0` and 10 % on `T`, `a`, `b`, `s0`, one of the six runs records 3
  nonpositive-gap steps; with fixed values none of the six does. In the traced event (no
  meter, seed 1, 404–408 s) a freeway-lane vehicle yields to a faster ramp vehicle that
  is nearer than its own-lane leader. The yield rule replaces the own-lane leader instead
  of taking the more restrictive of the two, so the vehicle does not react while its
  own-lane leader stops; when the ramp vehicle has passed that leader, the vehicle is
  7.0 m behind it at 12.1 m/s, brakes at the 8.8 m/s² limit and overlaps it by 0.8 m. The
  rule itself is the same with fixed values. Not checked: how often this happens on the
  site configuration with a spread, whether the 15 nonpositive-gap steps D017 attributed
  to cut-ins share the mechanism, and whether taking the lower of the two IDM
  accelerations removes it without side effects. That change would alter fixed-value
  results and needs its own decision.
- 2026-11-18, driver populations (candidates; site scenario, 840 simulated runs: seven
  populations × three demand cases × no meter and ALINEA × seeds 1–20; six predictions
  written before the run; [record](../experiments/driver_populations.md)). (1) At equal
  mean and spread (11.5 %), uniform, normal and lognormal drivers give the same
  congestion within what 20 seeds resolve (about ±5 to ±7 min); one of 18 shape contrasts
  crosses the counting rule. A follow-up of 160 runs at a spread of 25 % on `T`, `a`,
  `b` again shows no shape difference in congestion (all within ±1.4 min) and none at
  all between uniform and normal; the lognormal population has 0.3 min less time per
  vehicle than the symmetric ones when the downstream restriction is removed. (2) The
  amount of spread matters: with the downstream
  restriction removed, 11.5 % on `v0`, `T`, `a`, `b` adds 19 to 22 min of persistent
  congestion without a meter, and spreads taken from field and calibration studies add
  43; on the observed day those add 0.5 to 0.6 and 3.0 min of time per vehicle to 7.4.
  (3) Desired speed alone at 10 % (SUMO's default) and the merging limit alone at 25 %
  stay within about 8 min of identical drivers; each crosses the rule in one cell of
  six. (4) ALINEA's reduction of congestion at 0.9× demand (−20.7 min with identical
  drivers) holds under every population (−23.7 to −30.6); with the restriction removed
  and the field-study spreads it disappears (−2.7, interval −10.1 to +4.7). Limits: no
  population is calibrated for this site and the field-study one is an upper estimate;
  parameters are independent; one lane without passing; the single-cell differences
  need new seeds before they are called results.

- 2026-11-19, the Ventura merge in the morning peak (candidate; observed PeMS data at
  lane level, observed lanes only, eight weekdays of October 2022: 3, 10, 11, 12, 14, 24,
  25, 28; `uv run python scripts/bottleneck_check.py`;
  [record](../experiments/ramp_mainline_mix.md#site-characterization-pems-observed)).
  (1) From about 06:30 to 10:00 the merge is inside a queue: Woodcrest (0.95 mi
  downstream) and Royal Ridge (1.52 mi) are below 20 m/s on every day, and the bottleneck
  test of Chen, Skabardonis and Varaiya (2004) is met on none; at most 4 of 48 intervals
  meet its speed criteria, all between 06:55 and 09:25. (2) The onset does not show a
  queue arriving from downstream: the lecture's shockwave speed is −14 to −16 mph, about
  6 minutes from Royal Ridge, but Royal Ridge crosses the line after Ventura on 6 days
  (by 5 to 15 minutes) and before it on 2, and Burbank 1 upstream is first or tied on
  every day. Breakdown at or upstream of the merge at onset is not excluded. (3) From
  07:00 to 08:55 the Ventura mainline carries 4,960–6,140 veh/h at 13–21 mph, and the
  ramp passes 680–890 veh/h, 61–97 % of the shoulder lane's 870–1,120 veh/h. (4) Station
  777066 reports about 50 mph where its flow and occupancy imply 18–22 mph. Limits: the
  downstream stations are partly imputed (1 to 4 of 6 and 3 to 4 of 5 lanes observed);
  reported speeds are station estimates, so an order read at a fixed speed line depends
  on them; the shoulder-lane comparison assumes that lane 5 is the shoulder side and
  that station 717816 is upstream of the gore; the ramp was metered at unknown rates;
  the head of the queue is not located (no observed mainline station from Abs PM 60.3
  to 52.9). This is the lane-level redo of the station-level check drafted on the
  `mid-report` branch.

- 2026-11-19, ramp and mainline demand scaled separately (candidates; D021, the model
  before calibration, 960 simulated runs, five predictions written before the run;
  [record](../experiments/ramp_mainline_mix.md#results-of-the-run)). (1) Under the
  limited exit, raising the freeway lane's demand by 25 % lowers ramp exits by 536 (505
  to 567), about one for one with the through vehicles added: supported. (2) With the
  shoulder lane as observed both approaches are queued and the ramp keeps 2,561 exits,
  about 42 % of all, while 1,461 mainline vehicles are left: supported; neither side has
  priority. (3) At that level 25 % more ramp demand still raises ramp exits by 2.5 %
  (58 to 71 vehicles), against a line of 2 %: the fixed-ratio prediction is contradicted,
  narrowly. (4) No rule changes ramp exits by 2 % or more in any of 36 comparisons:
  supported. (5) ALINEA's reduction of congestion counts in 6 of the 8 cells with 30 to
  200 unmetered minutes and in none above 240: supported. Also: a fixed rate below the
  ramp demand lowers freeway congestion by 66 to 103 minutes and raises the peak queue
  on Ventura Blvd by 91 to 283 vehicles and time per vehicle by 0.8 to 3.5 minutes.
  Limits: uncalibrated model; the shoulder-lane level is a bound; whole-window counts.
- 2026-11-19, calibration (candidates; D023; [record](../experiments/calibration.md)).
  Observed: at station 717816 the largest 5-minute flow is 1,978 veh/h per lane at 27 to
  31 m/s, and the congested points extrapolate to about 1,600 to 1,700 veh/h at the same
  density, so one equilibrium curve cannot fit both; PeMS speed there is flow times a
  fixed 10.2 m over occupancy. Simulated: with `v0` 29.1 m/s, `T` 1.51 s, `delta` 20 and
  `a` 2.5 m/s² the model reproduces, on three days it was not fitted to, the vehicles
  through the merge lane within 3 %, the ramp vehicles within 5 % and the congested
  minutes within 10 %. It still passes slightly fewer vehicles than observed, and `a` is
  at the upper end of its range: the merge rule, not the drivers' acceleration, is the
  likelier cause.
- 2026-11-19, the meter's queue estimate and forecast (candidate; one seed;
  [record](../experiments/estimate_and_forecast.md)). The last-value forecast of ramp
  arrivals per 30 s has an error of 1.20 vehicles against 1.30 for a ten-interval mean.
  The queue estimate from the entry and passage loops is within 1.8 vehicles while the
  queue fits on the ramp and short by 63 on average over the morning, because the queue
  is beyond the entry loop 89 % of the time: the modeled controller does not know the
  queue on Ventura Blvd.

Initialization contained no experiments, calibration outcomes, or empirical
traffic findings. Later entries must identify the evidence and its limits before
being discussed as potential research contributions.
