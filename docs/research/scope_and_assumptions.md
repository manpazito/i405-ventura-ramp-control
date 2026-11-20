# Scope, course requirements and assumptions

## Course-guide provenance

*CEE 181 and 281 Design Project Guide*, Fall 2026, eight pages. First read on
2026-11-07 from the copy `CEE181281_Fall2026_Design_Project_Guide_Revised.pdf`; read
again in full on 2026-11-19 from `docs/CEE181281_Fall2026_Design_Project_Guide_Revised-2.pdf`,
which has the same SHA-256:

```text
f8f6d88bc744788a8f10504d3d3182bec8861aac72ac44e0e642c8d9ca4eeb2c
```

No public URL or revision date inside the guide was established. The latest course
instructions take precedence over this map. Page numbers refer to the eight PDF pages.
The mid-report rubric (five sections with weights) was supplied separately by the
author and is followed in `docs/mid_report`.

## Requirement map

Status on 2026-11-19. "Met" means the evidence exists in this repository and can be
shown; it does not mean a grader has accepted it.

### Shared foundation: simulation (guide p. 2)

| Requirement | Evidence here | Status |
| --- | --- | --- |
| Vehicle movement with a justified car-following model; arrivals, exits, a bottleneck, virtual detectors | IDM in `simulation/micro.py`; Poisson arrivals, an exit boundary, a merge, loop detectors; the site scenario `configs/i405.yaml` | Met |
| At least two substantive sources, one of them an original model source; equations, parameter ranges and limits tied to sources | [Source-to-design table](literature_review.md); [car following](../mathematical_model/car_following.md); [ramp metering](../mathematical_model/ramp_metering.md), where ALINEA is checked against its 1991 paper and the lecture | Met |
| Verification: conservation, free motion or equilibrium, gaps, boundary behavior, time-step sensitivity; audit detector counting | `tests/test_micro.py`, `tests/test_ablation.py`; a conservation check in every step; reference runs compared before and after each engine change | Met in simulation. The manual audit of a counted sample is the field count planned for 2026-11-20 |
| A focused claim with a baseline, changed conditions and a prediction made before testing; trajectory and aggregate plots; an independent analytical or literature comparison | The mid-report; the records under `experiments/`, each with predictions written before its runs and the lecture formulas computed first | Met |
| CEE 281: a second model, or independent calibration and validation evidence | [Calibration](../../experiments/calibration.md) (D023): `v0`, `T` and `delta` from the fundamental diagram of three days of PeMS data and checked on five others; `a` from the ramp vehicles served on three days and checked on three others, where FHWA's example criteria are met | Met. The congested branch of the diagram, the comfortable deceleration, the standstill gap and the merge rule are not calibrated, and the record says why |

### Shared foundation: observation, estimation, prediction (guide p. 3)

| Requirement | Evidence here | Status |
| --- | --- | --- |
| An observation pipeline that accepts detector outputs; count crossings or estimate a queue; audit a labeled sample by hand | Loop records with count, speed, occupancy and a quality flag; the ramp queue estimated from entry and passage counts; the PeMS pipeline | Simulation part met. The manual audit is pending (field count) |
| A state estimate and one short-horizon forecast compared with a simple baseline | The queue estimate from the entry and passage loops, and the one-interval forecast of ramp arrivals that the queue rule uses, scored against simulator truth and against a moving average, with a missing-loop case ([record](../../experiments/estimate_and_forecast.md)) | Met in a minimal form: the two that the meter already uses are scored; no estimator or forecast method was developed, because forecasting was dropped with D020 |
| At least one observation defect tested | A merge-detector fault: hold the last command, then fall back to the fixed rate (tests; a case of the rule ablation) | Met |

### Common TMC (guide p. 4)

| Requirement | Evidence here | Status |
| --- | --- | --- |
| Observe, estimate, decide, act, evaluate, with bounds, a storage constraint and a fallback; log observation, estimate, action and response | `control/metering.py`: every command records its reason, bounds, the occupancy and queue estimate it used, and its fallback state | Met |
| One simple baseline against a sophisticated metering algorithm, under identical demand, with residual queues and unmet demand counted | No meter, a fixed rate, the Caltrans local traffic-responsive plan and ALINEA on the same arrivals per seed; vehicles left outside at the end are counted | Met |

### Final submission (guide pp. 4–7)

| Requirement | Evidence here | Status |
| --- | --- | --- |
| Baseline comparisons, a changed-demand test, a failure or degraded-information test | [Rule ablation](../../experiments/rule_ablation.md) (D024): demand cases and a detector-fault case among its one-factor changes | Met: run and scored on 2026-11-19 |
| CEE 281: a focused controller comparison, uncertainty analysis or ablation | D024, with D021 (ramp and mainline demand) and D019 (driver populations) | Met |
| **One final pathway: CAV control, or traffic-signal control on the supplied isolated-intersection scaffold. "The final submission must include the selected CAV or signal implementation, not only this common TMC"; ramp metering is "a foundation exercise"** | Nothing in this repository | **Not met.** Traffic-signal control was chosen on 2026-11-19; the scaffold has not been obtained |
| README with one reproducible run command, dependencies, inputs, expected outputs and known limits | [README](../../README.md) | Met |
| Versioned code and scenario configurations | Git | **Not met in the main checkout:** the branch `main` has no commit and the repository has no remote. The mid-report rubric also asks for a repository link |
| Plots with axes, units and scenario labels | Figures written by `arm-ablation` and `arm-study` | Met |
| Experiment record: prediction, change made, result, interpretation | `experiments/` | Met |
| Source-to-design table; a concise AI-use and verification disclosure | [Literature record](literature_review.md); the "AI use and verification" section of the mid-report | Met; carry the disclosure into the final report |
| Individual contribution record | Individual project (D020): one author for every component | Met by D020; state it in the final report |
| Design record of about six pages for the final report, plus references, plots and code | `docs/mid_report` is the mid-term stage | Pending |

Schedule from the guide: the final submission and an eight-minute presentation for an
individual project follow 2 December 2026.

## What is in place

A PeMS acquisition and screening pipeline run on October 2022; a microscopic engine
with four metering rules; a site scenario with measured ramp geometry and one observed
weekday; a calibration of the parameters the loop data identify; four studies with
written predictions (demand ablation, driver populations, ramp and mainline demand,
rule ablation). The synthetic prototypes (aggregate CTM demo, simplified merge, paper draft)
were removed on 2026-11-19; the engine keeps its synthetic test scenario.

## Assumption register

| Item | Status | What would settle it |
| --- | --- | --- |
| The ramp | I-405 SB on-ramp from Ventura Blvd, LA-405 PM 39.09; PeMS stations 716744 (ramp) and 717816 (mainline), identities checked against the metadata of 2022-07-15 | Settled |
| Geometry, storage, meter line | Measured from the project's AutoCAD sketch; the meter line confirmed by the author; not georeferenced | Dated Caltrans plans |
| The ramp's metering plan | Unpublished. The plan table, queue trigger and detector positions are assumed after other Caltrans documents | The District 7 plan for this ramp; the field count of 2026-11-20 for how the meter runs |
| Where mainline station 717816 sits relative to the gore | Assumed upstream | The field count, or Caltrans as-built drawings |
| What limits flow in the peak | Observed: the merge is inside a queue whose head is at or beyond Royal Ridge from about 06:30 to 10:00; the onset is not shown to come from downstream; the head is not located | Observed data through the Sepulveda Pass |
| Demand | One observed weekday, Tuesday 2022-10-11. Counts are a lower bound on demand once the freeway is congested | Not obtainable from loop data |
| IDM `v0`, `T`, `delta`, `a` | Calibrated on three days and checked on others (D023); `a` is at the upper end of its range | Settled within the limits of that record |
| IDM `s0`, `b`; the merge rule | Sourced values and project rules; not calibrated; varied one at a time in the rule ablation | Vehicle trajectories at a merge |
| One freeway lane and the lane-balance assumption | Structural. The observed shoulder lane is an upper bound for the through traffic (D021) | A multi-lane or macroscopic merge model |
| Detector speed | PeMS derives speed at this station from flow and occupancy with a fixed effective length of 10.2 m | Dual-loop or probe speeds |
| Pedestrians, bicycles, vehicle classes, incidents | Not modeled; no claim is made about them | Out of scope |
| Safety | No crash-reduction claim; overlap counts are a numerical check, not a surrogate safety measure | Out of scope |
