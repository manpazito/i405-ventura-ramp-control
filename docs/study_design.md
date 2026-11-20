# Study design

The direction of the project since decision D024 (2026-11-19). Everything else in the
repository either serves this plan or is marked as an earlier prototype.

## The question

At the I-405 southbound on-ramp from Ventura Boulevard (at Sepulveda Boulevard, Sherman
Oaks), what do the metering rules in actual use and ALINEA do, compared with no meter
and with each other, and how do those effects hold when one condition at a time is
changed?

"In actual use" means the two rules Caltrans District 7 runs: a fixed time-of-day rate,
and local traffic-responsive metering with queue override. ALINEA is the feedback rule
of the course (Lecture 05B, slide 26) and of the literature.

## What is compared

| Rule | What it does | Basis |
| --- | --- | --- |
| No meter | Vehicles enter as they arrive | Reference |
| Fixed rate | One constant rate, 8 vehicles a minute per metered lane | District 7's time-of-day example; the value for this ramp is assumed |
| Caltrans local responsive | A stepwise plan: the rate falls as mainline occupancy upstream of the ramp rises; while the ramp's queue detector is covered the rate steps up (queue override) | Caltrans Traffic Operations Manual and District 7 documents ([sources](i405_ablation.md#sources)); the plan values for this ramp are unpublished and assumed |
| ALINEA | `r(k) = r(k−1) + K_R [ô − o_out(k)]` on the occupancy just past the gore, with a queue rule | Papageorgiou et al. (1991), checked in [ramp_metering.md](mathematical_model/ramp_metering.md); the set value is the critical occupancy of the calibrated model (D022, D023) |

All four run on the same arrivals in a given seed.

## The model and its baseline

One microscopic model: IDM car following on one freeway lane (the lane the ramp merges
into), a ramp with the measured geometry (three lanes at the meter, two, then one, 258 m
in all, about 25 vehicles of storage), mandatory merging, a one-vehicle-per-green meter,
and loop detectors that report counts, speed and occupancy every 30 s.

The baseline is one observed weekday, Tuesday 2022-10-11 from 05:00 to 10:00:

- **Demand** is the PeMS count of the ramp, and for the freeway lane the lane-average
  flow less the ramp's (the lane-balance assumption).
- **The downstream boundary** discharges the observed flow in the intervals PeMS shows
  as congested. PeMS shows that from about 06:30 to 10:00 the merge is inside a queue
  whose head lies downstream
  ([site characterization](../experiments/ramp_mainline_mix.md#site-characterization-pems-observed)).
- **Parameters** carry a label in [configs/i405.yaml](../configs/i405.yaml) saying where
  each comes from. The desired speed, the time gap and the acceleration exponent are
  calibrated on the fundamental diagram of three days of PeMS data, and the
  acceleration on the ramp vehicles served on those days; all are checked on days not
  used ([calibration](../experiments/calibration.md), D023). The comfortable
  deceleration, the standstill gap and the merge rule cannot be calibrated with these
  data; they keep sourced values. All of them are among the factors varied below.

## The ablation: one factor at a time

Each case changes one thing from the baseline and keeps everything else, including the
rules' settings, as calibrated. So the comparison asks how a rule set up for the
baseline holds up when the world, or one of its own settings, is different.
[configs/i405_ablation.yaml](../configs/i405_ablation.yaml) lists the cases;
[experiments/rule_ablation.md](../experiments/rule_ablation.md) holds the predictions
written before the run, and the results.

| Group | Factor | Levels besides the baseline |
| --- | --- | --- |
| Demand | Both origins together | 0.9×, 1.1× |
| | Ramp alone | 0.75×, 1.25× |
| | Mainline alone | 0.75×, 1.25×, and the shoulder lane as observed (an upper bound) |
| | Shape | ±50 % waves with periods of 10 and 60 minutes |
| | Downstream regime | Free exit (the merge is the only bottleneck) |
| Car following | Time gap `T` | −20 %, +20 % |
| | Acceleration `a` | −20 %, +20 % |
| | Comfortable deceleration `b` | 1.0 and 3.0 m/s² |
| | Standstill gap `s0` | 1 m and 3 m |
| | Desired speed `v0` | −10 %, +10 % |
| | Acceleration exponent | 4, the textbook value |
| Drivers | Differences between drivers | A normal spread of 11.5 %; spreads from field studies |
| Information | A fault of ALINEA's detector | Missing for one hour of the peak |
| Rule settings | ALINEA gain | Half, double |
| | ALINEA set value | −20 %, +20 % |
| | ALINEA without its queue rule | The rule as the lecture and the paper state it |
| | Caltrans plan thresholds | Earlier, later |
| | Caltrans plan without queue override | |
| | Fixed rate | 6 and 12 vehicles a minute per lane |

Two supporting studies vary factors jointly and are kept as they are: ramp and mainline
demand on a grid ([D021](../experiments/ramp_mainline_mix.md)) and seven driver
populations ([D019](../experiments/driver_populations.md)). On the calibrated model, one
driver trait at a time and three shapes are compared in
[driver traits](../experiments/driver_traits.md).

## Measures

- **Persistent congestion** at the mainline station upstream of the gore: minutes in
  runs of at least ten 30-second intervals below 20 m/s or above the model's critical
  occupancy (definition D016).
- **Time in the system per vehicle**, counting every vehicle that asked to enter,
  including those still waiting outside at 10:00. This is the total travel time of
  Lecture 05B (slides 24 and 35).
- **Peak queue held on Ventura Boulevard**: vehicles that could not enter the ramp.
- **Demand served**, and where it matters, exits by origin (ramp or mainline).

## Evidence rules

- A study's question, changed factor and predictions are written into its record before
  it runs. A prediction that fails is reported as plainly as one that holds.
- Ten seeds per case and rule. Differences are paired by seed; one counts when its 95 %
  t interval excludes zero and its mean reaches 5 minutes of congestion. With many cases
  a counted difference in one case alone is a candidate, not a result.
- Controllers see only detector records available at decision time. Vehicles are never
  dropped: those left outside at the end are counted.
- Design choices and claims are checked against the lecture slides in `docs/lectures`.
- Simulated results are what-ifs of a model that is calibrated only in part. Only the
  PeMS analyses are observations of the site.

## Course requirements

The [requirement map](research/scope_and_assumptions.md) lists every item of the course
guide with its evidence and status. This study covers the shared foundation, the
calibration evidence and the focused study that CEE 281 adds. **It does not cover the
final pathway**, which the guide requires in addition to ramp metering: the project
takes traffic-signal control on the course's supplied intersection (chosen
2026-11-19), not built yet.

## Open items

1. The final pathway, traffic-signal control: obtain the course's intersection
   scaffold and build the controller comparison on it.
2. The field count at the ramp (planned 2026-11-20): queue per minute, releases per
   minute, how the meter runs, where the mainline loops sit relative to the gore. It is
   the course's manual audit and it settles two assumptions.
3. The observation component is met in a minimal form
   ([record](../experiments/estimate_and_forecast.md)). Ask whether an individual project
   owes more than that.
4. Commit the repository and give it a remote; the reports need a link.
5. The ramp's own metering plan from Caltrans District 7.
