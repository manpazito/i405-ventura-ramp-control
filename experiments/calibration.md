# Calibration of the site scenario

Decision D023, 2026-11-19. The course guide asks for "independent calibration/validation
evidence" and adds that "calibration requires suitable data; parameter tuning alone is
not validation". This record states which parameters the available data can identify,
how they were set, how the result was checked on days that were not used, and what
stays assumed. The numbers in step 1 are observed PeMS data and an analytic curve; step
2 is simulated.

## The standard followed

There is no single standard for calibrating a traffic microsimulation. The nearest is
FHWA's Traffic Analysis Toolbox, Volume III (2004, rewritten in 2019); Caltrans' 2002
guide follows the 2004 edition. The car-following literature covers calibration from
vehicle trajectories, which this project does not have.

| Step | What the sources ask for | Here |
| --- | --- | --- |
| 1 | Check the model for errors first (FHWA 2004, ch. 4–5) | Conservation, gap, equilibrium and boundary tests; reference runs compared before and after each engine change |
| 2 | Keep the set of adjusted parameters as small as possible (FHWA 2004, §5.2). A parameter whose regime is missing from the data is unobservable and must not be calibrated (Treiber and Kesting 2013) | Three parameters adjusted: `v0`, `T`, `delta`. `s0`, `a`, `b` and the merge rule are not |
| 3 | Field capacity is the flow where a queue discharges, measured while the queue is present (FHWA 2004, §5.3.1) | Not available: the station sits inside a queue from downstream in the peak, with no free flow below it ([site characterization](ramp_mainline_mix.md#site-characterization-pems-observed)). The largest observed 5-minute flow is used instead, as Dervisoglu et al. (2009) do |
| 4 | Fundamental diagram from PeMS 5-minute data (Dervisoglu et al. 2009): free-flow speed by least squares on the points above 55 mph; capacity as the largest flow | As stated |
| 5 | Capacity calibration: adjust the mean following headway until the model's capacity matches the field's (FHWA 2004, §5.3) | `T` is the value at which the IDM equilibrium capacity equals the observed capacity |
| 6 | Then compare system performance (queues, travel times) and adjust sparingly (FHWA 2004, §5.5) | Step 2 below |
| 7 | Acceptance, as an example (FHWA 2004, Table 4, from Wisconsin DOT): flows within 15 % in more than 85 % of cases; GEH below 5 in more than 85 % of cases; speed-flow relationship "to analyst's satisfaction" | Reported below, per branch of the diagram |
| 8 | Validate on field data not used in the calibration (FHWA 2004) | Three calibration days, five held-out days |

## Data

Mainline station 717816, mean of its five lanes, 5-minute intervals in which every lane
is observed. Calibration days: Mon 10, Tue 11 and Wed 12 October 2022 (861 intervals).
Held-out days: 3, 14, 24, 25 and 28 October 2022 (1,429 intervals). Density is flow
divided by the speed PeMS reports.

Two properties of the data limit what can be claimed:

- **PeMS does not measure speed here.** Occupancy divided by density is 10.2 m in every
  speed band, so the reported speed is flow times a fixed effective length over
  occupancy. The free-flow speed below inherits that scale.
- **The peak pre-breakdown flow lies above the congested branch.** The largest 5-minute
  flow is 1,978 veh/h per lane at 27 to 31 m/s; the congested points extrapolate to
  about 1,600 to 1,700 veh/h at the same density. One equilibrium curve cannot pass
  through both.

## Step 1: what the fundamental diagram identifies

`uv run python scripts/calibrate_fd.py` (no simulation).

| Parameter | Can loop data identify it? | Value before | Calibrated |
| --- | --- | --- | --- |
| Desired speed `v0` | Yes: the free-flow branch | 28.6 m/s (shoulder-lane median) | **29.1 m/s** |
| Time gap `T` | Yes: capacity | 1.0 s (assumed) | **1.51 s** |
| Acceleration exponent `delta` | Yes: it shapes the free-flow branch | 4 (textbook value) | **20** |
| Standstill gap `s0`, vehicle length | No: the data hold no standstill (densities stop at 56 veh/km) | 2 m, 5 m | unchanged |
| Accelerations `a`, `b` | No: they do not enter the equilibrium curve (Treiber, Hennecke and Helbing 2000) | 2 m/s² each | unchanged |

How `delta` was chosen: for each value on a grid from 4 to 60, `T` is set so that the
curve's capacity equals the observed 1,978 veh/h; the smallest `delta` whose
root-mean-square flow error on the calibration days is within 5 % of the best is taken.

| `delta` | `T` (s) | Speed at capacity (m/s) | Flow error, all (veh/h) | free | congested |
| --- | --- | --- | --- | --- | --- |
| 4 | 1.32 | 17.1 | 335 | 128 | 658 |
| 8 | 1.43 | 20.1 | 291 | 102 | 576 |
| 12 | 1.47 | 21.9 | 271 | 93 | 539 |
| 16 | 1.50 | 23.0 | 261 | 89 | 520 |
| **20** | **1.51** | **23.8** | **255** | **88** | **508** |
| 30 | 1.53 | 25.1 | 249 | 93 | 492 |
| 40 | 1.54 | 25.8 | 248 | 102 | 483 |

The observed speed at the twenty highest flows is 27.0 m/s. With the textbook exponent
the model reaches capacity at 17 m/s, below the project's 20 m/s congestion line; with
20 it does so at 23.8 m/s.

### Check on the days that were not used

Flow given by the equilibrium curve at each observed density, against the observed flow.

| Parameters | Capacity (veh/h) | Calibration days: error, all / free / congested | Within 15 %: free / congested | Held-out days: error, all / free / congested | Within 15 %: free / congested |
| --- | --- | --- | --- | --- | --- |
| Before (`v0` 28.6, `T` 1.0, `delta` 4) | 2,420 | 530 / 111 / 1,086 | 91 % / 6 % | 558 / 122 / 1,004 | 82 % / 6 % |
| Calibrated (`v0` 29.1, `T` 1.51, `delta` 20) | 1,980 | 256 / 88 / 509 | 90 % / 9 % | 271 / 97 / 472 | 87 % / 11 % |

- The error halves on the held-out days as it does on the calibration days.
- **The free-flow branch meets the 15 % criterion** (87 % of held-out intervals, against
  82 % before).
- **The congested branch does not** (11 %). The model still gives about 470 veh/h too
  much flow at a given congested density. Bringing it down would need a standstill gap
  near 5.6 m, which the data cannot support and which would be wrong for cars queued at
  the meter (Caltrans' design figure is 29 ft per stored vehicle).
- The largest 5-minute flow on each held-out day is 1,783 to 1,920 veh/h, 3 to 10 %
  below the calibrated capacity, which comes from the largest of the calibration days
  (11 October, the day that is simulated).

## Step 2: the whole model against six days

`uv run arm-study --config configs/i405_validation.yaml --output results/validation`,
then `uv run python scripts/validation_table.py results/validation/<timestamp>`.

The simulation is driven by each day's observed flows, so it cannot be scored on what
goes in. It is scored on three things it has to produce: the vehicles that get through
the merge lane between 05:00 and 10:00, the ramp vehicles among them, and the minutes
the mainline station spends below 20 m/s. The rule in the field is of the Caltrans
local traffic-responsive kind, so that rule runs (its plan values are assumed).

Six weekdays have both stations fully observed in that window: 10, 11 and 12 October
(used in step 1) and 3, 14 and 25 October (held out). On 24 and 28 October the mainline
station has imputed intervals in the window.

**Rule, written before the run.** One parameter is adjusted at this step: the
acceleration `a`, which the fundamental diagram cannot identify and which sets what the
modeled merge passes once it has broken down. Among 1.5, 2.0 and 2.5 m/s², all inside
the 0.8 to 2.5 m/s² that the IDM's authors call realistic, take the value with the
smallest mean absolute error in ramp vehicles served over the three calibration days
(seeds 1 to 5). Then score that value on the three held-out days against FHWA's example
criteria: each of the three quantities within 15 %, and GEH below 5 for the two flows.
The comfortable deceleration `b` and the merge rule are left as they are.

A probe of two seeds on 11 October preceded this step. With `a` = 2.0 the model passes
6,395 of the 6,829 vehicles observed (−6 %) and 2,976 of the 3,380 ramp vehicles
(−12 %), and its station is congested for 220 of the 235 minutes observed. With 2.5 the
figures are 6,667, 3,243 and 210.

### Result

Run folder `results/validation/20261119T195328_824380Z` (generated, not in Git): 90
runs. Simulated mean of five seeds against the observed value, in per cent; GEH is on
hourly flows.

| Day | Split | `a` = 1.5: vehicles / ramp / congested min | `a` = 2.0 | `a` = 2.5 |
| --- | --- | --- | --- | --- |
| 10 Oct | calibration | −12.4 / −10.9 / +18.8 | −3.7 / −0.7 / +11.6 | +0.5 / 0.0 / −4.1 |
| 11 Oct | calibration | −14.3 / −28.2 / −4.6 | −6.6 / −13.4 / −7.1 | −2.7 / −5.6 / −9.1 |
| 12 Oct | calibration | −14.8 / −28.3 / +1.8 | −5.8 / −10.6 / −4.2 | −2.2 / −3.8 / −9.6 |
| 3 Oct | held out | −13.7 / −24.3 / +3.6 | −6.8 / −12.9 / −2.4 | −2.9 / −4.6 / −10.3 |
| 14 Oct | held out | −17.6 / −18.3 / +7.3 | −8.4 / −6.2 / +3.0 | −1.6 / −1.0 / −3.2 |
| 25 Oct | held out | −12.7 / −24.9 / −2.0 | −5.9 / −11.4 / −9.2 | −2.7 / −5.1 / −10.2 |
| Mean absolute error, calibration days | | 13.9 / 22.5 / 8.4 | 5.4 / 8.2 / 7.6 | 1.8 / **3.2** / 7.6 |
| Mean absolute error, held-out days | | 14.6 / 22.5 / 4.3 | 7.0 / 10.2 / 4.9 | 2.4 / 3.6 / 7.9 |

- **`a` = 2.5 m/s² is taken**: the smallest error in ramp vehicles served on the
  calibration days (3.2 %, against 8.2 % and 22.5 %).
- **On the three held-out days it meets every criterion.** Vehicles through the merge
  lane are within 3 % (GEH 0.6 to 1.1), ramp vehicles within 5 % (GEH 0.2 to 1.3), and
  congested minutes within 10 %. With 2.0 the criteria are also met, less closely; with
  1.5 the ramp flow misses them on all three days (GEH 4.5 to 6.8).
- **2.5 is the upper end of the range allowed.** The model still passes slightly fewer
  vehicles than were observed on five of six days and is congested for fewer minutes.
  The remaining shortfall points at the merge rule, where ramp vehicles drive to the end
  of the lane and force their way in, more than at how hard drivers accelerate.
- The first value tried, 2.0, was the one in the configuration before; the probe above
  was seen before the rule was written, on a calibration day.

## The calibrated baseline

| Parameter | Value | How it was set |
| --- | --- | --- |
| Desired speed `v0` | 29.1 m/s | Free-flow branch of the fundamental diagram, three days |
| Time gap `T` | 1.51 s | Equilibrium capacity equal to the observed 1,978 veh/h per lane |
| Acceleration exponent `delta` | 20 | Shape of the free-flow branch |
| Acceleration `a` | 2.5 m/s² | Ramp vehicles served on the three days, among three sourced values |
| Comfortable deceleration `b`, standstill gap `s0`, vehicle length | 2 m/s², 2 m, 5 m | Sourced values, not calibrated |
| ALINEA set value | 0.158 | The critical occupancy of the calibrated curve at the 1.83 m loop (D022); a test recomputes it |
| ALINEA gain | 54 veh/h per percentage point | Kept. The 1991 paper found 70 adequate and results insensitive to it; the ablation varies it |
| D016 occupancy line | 0.158 | The same critical occupancy |

"A calibrated ALINEA" in this project means ALINEA with its set value taken from the
calibrated model's fundamental diagram, as its authors prescribe. Its gain, its queue
rule and the Caltrans plan's table are not calibrated: there is no observation of the
ramp's queue or of the meter's rates to calibrate them against.

## What cannot be calibrated with these data

- `a` and `b`: they need acceleration episodes from trajectories. `a` sets what the
  modeled merge passes after breakdown, so it is varied in the ablation, not fitted.
- `s0`: no standstill is observed.
- The merge rule (zone length, the braking a merging driver accepts): no observation of
  individual merges.
- Capacity in the FHWA sense, and the capacity drop: there is no active bottleneck with
  free flow downstream in the data.
- The ramp's own metering plan: unpublished; the plan table is assumed.
- Demand once the freeway is congested: the counts are what was served.
- FHWA's 2019 edition calibrates against a representative day chosen from clusters of
  about a year of data; eight days do not support that.

## Sources

Read on 2026-11-19 during the web research for this decision; the read status is that
of the research pass, and each should be re-opened before it is cited in the paper.

- FHWA, Traffic Analysis Toolbox Volume III: Guidelines for Applying Traffic
  Microsimulation Modeling Software, FHWA-HRT-04-040, 2004, chapter 5 and Appendix B
  (read in full). <https://ops.fhwa.dot.gov/trafficanalysistools/tat_vol3/sect5.htm>
- FHWA, the same, 2019 update, FHWA-HOP-18-036, chapter 5 (read in full).
  <https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm>
- Dervisoglu, Gomes, Kwon, Horowitz and Varaiya (2009), Automatic calibration of the
  fundamental diagram and empirical observations on capacity, TRB 88th Annual Meeting
  (read in full).
  <https://horowitz.me.berkeley.edu/Publications_files/All_papers_numbered/174C_Dervisoglu_TRB09.pdf>
- Treiber and Kesting (2013), Microscopic calibration and validation of car-following
  models: a systematic approach, Procedia Social and Behavioral Sciences 80 (preprint
  read in full). <https://arxiv.org/abs/1403.4990>
- Treiber, Hennecke and Helbing (2000), Congested traffic states in empirical
  observations and microscopic simulations, Physical Review E 62 (read in part).
  <https://arxiv.org/abs/cond-mat/0002177>
- Caltrans (2002), Guidelines for Applying Traffic Microsimulation Modeling Software
  (read in part).
