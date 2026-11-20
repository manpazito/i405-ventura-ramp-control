# One-factor ablation of the metering rules

The main study of the project (D024, [study design](../docs/study_design.md)).
Specification written on 2026-11-19, **before any run of this study**; the predictions
are not edited after the run. Results
and interpretation are added underneath. Simulated, on a model that is calibrated only
in part ([calibration](calibration.md)).

## Question

At the I-405 southbound Ventura Boulevard on-ramp, what do a fixed rate, the Caltrans
local traffic-responsive plan and ALINEA change compared with no meter and with each
other, and how do those effects hold when one condition at a time is changed?

## Baseline and changed factor

Baseline: the calibrated site scenario of `configs/i405.yaml`: the observed day
2022-10-11 from 05:00 to 10:00, identical drivers, the downstream boundary limited to
the observed flow, and the four rules with their baseline settings. ALINEA's set value
is the critical occupancy of the calibrated model.

Each case of `configs/i405_ablation.yaml` changes exactly one thing and keeps the rest,
the rules' settings included (a test checks that every case changes one thing and that
the change takes effect). A rule set up for the baseline is therefore tested in a world
that differs from it in one respect.

| Group | Case | What changes |
| --- | --- | --- |
| Demand | `demand_0.9`, `demand_1.1` | Ramp and mainline demand together |
| | `ramp_0.75`, `ramp_1.25` | Ramp demand alone |
| | `mainline_0.75`, `mainline_1.25` | Through traffic in the freeway lane alone |
| | `shoulder_lane` | Through traffic as observed in the lane next to the ramp, an upper bound (D021) |
| | `wave_10min`, `wave_60min` | Demand oscillating by ±50 % |
| | `free_exit` | No downstream restriction: the merge is the only bottleneck |
| Car following | `T_low`, `T_high` | Time gap 1.21 and 1.81 s (±20 %) |
| | `a_low`, `a_high` | Acceleration 2.0 and 3.0 m/s² (±20 %) |
| | `b_low`, `b_high` | Comfortable deceleration 1.0 and 3.0 m/s² |
| | `s0_low`, `s0_high` | Standstill gap 1 and 3 m |
| | `v0_low`, `v0_high` | Desired speed on the freeway lane 26.2 and 32.0 m/s (±10 %) |
| | `delta_4` | The textbook acceleration exponent |
| Drivers | `drivers_normal` | Each driver's `v0`, `T`, `a`, `b` drawn with a spread of 11.55 % (D019) |
| | `drivers_field` | Spreads observed or calibrated at other sites (D019) |
| Information | `detector_fault` | ALINEA's detector reports nothing from 06:30 to 07:30 |
| Rule settings | `alinea_gain_half`, `alinea_gain_double` | `K_R` 0.75 and 3.0 veh/s per unit occupancy |
| | `alinea_target_low`, `alinea_target_high` | Set value 0.126 and 0.190 (±20 %) |
| | `alinea_no_queue_rule` | ALINEA as the lecture and the 1991 paper state it |
| | `caltrans_early`, `caltrans_late` | Plan thresholds at 3 to 12 % and at 8 to 32 % occupancy |
| | `caltrans_no_override` | The plan without queue override |
| | `fixed_6_per_min`, `fixed_12_per_min` | Fixed rate of 6 and 12 vehicles a minute per lane |

A rule-setting case changes one rule; the other rules repeat the baseline in it.

## Design

- 35 cases × 4 rules (no meter, fixed rate, Caltrans plan, ALINEA) × seeds 1 to 10 =
  1,400 runs of five simulated hours.
- Command: `uv run arm-study --config configs/i405_ablation.yaml --output results/rule-ablation`.
- In a given seed every case with the same demand meets the same arrivals, and every
  rule meets the same arrivals in every case.

## Measures and decision rule

Primary: minutes of persistent congestion at the mainline station upstream of the gore
(`congested_min`, definition D016, with the occupancy line recomputed for the calibrated
model). Secondary: time in the system per vehicle that asked to enter (the total travel
time of Lecture 05B, slides 24 and 35), the peak queue held on Ventura Blvd, the share
of demand served. Integrity: steps with overlapping vehicles, vehicle conservation.

A difference **counts** when the 95 % t interval of the differences paired over the ten
seeds excludes zero **and** its mean reaches 5 minutes of congestion. For the secondary
measures the interval alone is reported. Three kinds of difference are reported: each
case minus the baseline under the same rule (`differences.csv`), each rule minus no
meter in the same case (`controller_effect.csv`), and one rule minus another in the same
case (`rule_differences.csv`). There are many of them, so a counted difference in one
case alone is a candidate, not a result.

## Before the run: what the course formulas give

From the calibrated configuration, with the equilibrium curve of each case, 5-minute
steps and no simulation (`ablation.analytic_table`, as in D021). Capacity is the static
capacity of Lecture 05B (slide 28); the deterministic queue is that of Lecture 03; the
last column is how long the capping strategy of Lecture 05B (slides 22 and 23) can hold
vehicles before the 24.6 vehicles of storage are full.

| Case | Static capacity (veh/h) | Speed at capacity (m/s) | Peak demand (veh/h) | 5-min intervals above capacity | D/D/1 unserved at 10:00 (veh) | Minutes the cap can hold |
| --- | --- | --- | --- | --- | --- | --- |
| `baseline` | 1,980 | 23.8 | 2,009 | 1 | 0 | 7 |
| `demand_0.9` | 1,980 | 23.8 | 1,808 | 0 | 0 | 0 |
| `demand_1.1` | 1,980 | 23.8 | 2,210 | 3 | 537 | 10 |
| `ramp_0.75` | 1,980 | 23.8 | 1,970 | 0 | 0 | 0 |
| `ramp_1.25` | 1,980 | 23.8 | 2,048 | 1 | 800 | 25 |
| `mainline_0.75` | 1,980 | 23.8 | 1,546 | 0 | 0 | 0 |
| `mainline_1.25` | 1,980 | 23.8 | 2,472 | 10 | 615 | 14 |
| `shoulder_lane` | 1,980 | 23.8 | 2,292 | 15 | 2,051 | 4 |
| `wave_10min` | 1,980 | 23.8 | 3,013 | 18 | 26 | 26 |
| `wave_60min` | 1,980 | 23.8 | 2,712 | 8 | 73 | 8 |
| `free_exit` | 1,980 | 23.8 | 2,009 | 1 | 0 | 7 |
| `T_low` | 2,375 | 24.0 | 2,009 | 0 | 0 | 0 |
| `T_high` | 1,697 | 23.6 | 2,009 | 8 | 81 | 8 |
| `s0_low`, `s0_high` | 2,027; 1,935 | 23.7; 23.9 | 2,009 | 0; 1 | 0 | 0; 12 |
| `v0_low`, `v0_high` | 1,945; 2,009 | 21.5; 26.1 | 2,009 | 1; 0 | 0 | 11; 0 |
| `delta_4` | 1,777 | 16.7 | 2,009 | 4 | 32 | 34 |

`a` and `b` do not enter these formulas. At the baseline the observed demand touches
the calibrated capacity for one interval, at 05:40, because the capacity is the largest
flow observed on that day. The formulas leave no queue at 10:00 at the baseline; what
the simulation leaves there is the cost of the merge.

Known from the calibration (step 2, the Caltrans rule, five seeds): at the baseline the
model passes 6,648 of the 6,829 vehicles observed and 3,190 of the 3,380 ramp vehicles,
and its station is congested for 214 minutes against 235 observed.

## Predictions

Written before any run of the study. What was known: the probe of the calibrated
baseline (two seeds), the records of the model before calibration (D015, D019, D021,
D022), the lecture material and the cited papers.

1. **At the baseline no rule makes a counted difference.** No rule's congestion differs
   from no meter's, and no rule's from another's. Reason: in the probe the three runs
   with and without a meter were within 4 minutes of each other; the merge is inside a
   queue for most of the morning, and Lecture 05B (slide 25) notes that metering is
   generally deactivated in oversaturated situations.
2. **A meter helps where the merge is not saturated, and only there.** ALINEA's
   reduction of congestion against no meter counts in at least one of `demand_0.9`,
   `ramp_0.75` and `free_exit`, and in none of `demand_1.1`, `ramp_1.25`,
   `mainline_1.25` and `shoulder_lane`. Reason: metering works by preventing a breakdown
   (Lecture 05B, slide 19); before calibration ALINEA's effect counted at 0.9× demand
   and at the free exit and nowhere above the observed demand.
3. **Where ALINEA and the Caltrans plan differ by a counted amount, ALINEA has less
   congestion.** In no case does the plan beat ALINEA by a counted amount. Reason: the
   plan reads the station upstream of the merge, which the queue reaches late, and its
   queue override hands the ramp back; ALINEA reads the merge itself.
4. **How people drive moves the outcome more than any rule does.** Going from `T_low` to
   `T_high` changes unmetered congestion by more than 20 minutes. Going from `a_low` to
   `a_high` changes unmetered time in the system per vehicle by more than 1 minute, with
   an interval that excludes zero. Each is more than the largest effect of any rule at
   the baseline in the same measure. Reason: `T` sets the static capacity and `a` what
   the merge passes after breakdown (Lecture 05B, slide 28). This prediction was revised
   on 2026-11-19 after the system-level step of the calibration and before any run of
   this study: that step showed that `a` moves the vehicles served and hardly the
   congested minutes, so the first wording (more than 20 congested minutes for `a` too)
   was already known to be wrong.
5. **ALINEA is insensitive to its gain and its set value.** In none of
   `alinea_gain_half`, `alinea_gain_double`, `alinea_target_low` and
   `alinea_target_high` does ALINEA's congestion differ from the baseline's ALINEA by a
   counted amount. Reason: the 1991 paper reports results "insensitive for a wide range
   of K_R values", and the set-value test of D022 found no counted difference.
6. **The queue rule and the override are what take the meter out of play.** Without
   them (`alinea_no_queue_rule`, `caltrans_no_override`) the rule's congestion is lower
   than with them by a counted amount, and its peak queue on Ventura Blvd is higher by
   more than 100 vehicles. Reason: the ramp stores about 25 vehicles; the capping
   strategy of the lecture must be discontinued within minutes at this ramp (D021),
   and the lecture shows the spillover that follows when it is not (slide 21).
7. **With its detector missing, ALINEA behaves as the fixed rate.** In `detector_fault`
   every ALINEA run records fallback decisions, and ALINEA's congestion differs from the
   fixed rule's in that case by no counted amount.
8. **Drivers that differ do not reorder the rules.** In `drivers_normal` and
   `drivers_field` no rule contrast counts with the opposite sign to the baseline's, and
   time in the system per vehicle is higher than at the baseline for `drivers_field`
   without a meter. Reason: the driver study (D019).

## What would contradict them

1. Any counted difference among the six baseline comparisons (three rules against no
   meter, three rule contrasts).
2. No counted ALINEA reduction in any of the three unsaturated cases, or a counted one
   in any of the four saturated cases.
3. A counted difference in favor of the Caltrans plan in any case.
4. A change of 20 congested minutes or less from `T_low` to `T_high`; a change of 1
   minute or less in time per vehicle from `a_low` to `a_high`, or an interval including
   zero; or a larger rule effect at the baseline in the same measure.
5. A counted difference from the baseline's ALINEA in any of the four cases.
6. No counted reduction of congestion without the queue rule or without the override,
   or a rise of the street queue of 100 vehicles or fewer.
7. An ALINEA run without fallback decisions in `detector_fault`, or a counted difference
   from the fixed rule there.
8. A rule contrast that counts with the opposite sign in a driver case, or no rise in
   time per vehicle for `drivers_field` (interval including zero).

## Results (2026-11-19)

Run `results/rule-ablation/20261119T200447_267513Z`, code at commit `12f6a67`; the
tables are copied to `docs/mid_report/data/rule_ablation/`. 1,400 runs, every one
conserves vehicles, and no step has overlapping vehicles. The run was started before
this section existed and the predictions above were not edited. Two notes on
provenance: the machine slept twice during the run, so its 6 h 20 min of wall time is
about 2 h of computing on 11 processes; and `run.json` and the console call the model
"uncalibrated", which was stale text in `drivers.py` (corrected after the run). The
configuration that ran is the calibrated one (`config.yaml` in the run folder).

Simulated, on a model calibrated in part, for one observed day. Differences are means
of the ten seeds, paired, with 95 % t intervals; "counts" is the decision rule above.

### Cell means

| Case | Congested minutes (none / fixed / Caltrans / ALINEA) | Time per vehicle, min | Peak queue on Ventura Blvd, veh | Served, % |
| --- | --- | --- | --- | --- |
| `baseline` | 210.7 / 204.4 / 214.0 / 213.2 | 6.86 / 6.86 / 6.98 / 6.81 | 148 / 162 / 152 / 148 | 97.1 each |
| `demand_0.9` | 47.4 / 42.8 / 44.0 / 34.2 | 0.97 / 1.10 / 1.00 / 1.05 | 7 / 9 / 9 / 11 | 99.7 to 99.8 |
| `demand_1.1` | 212.4 / 212.0 / 211.8 / 210.6 | 17.66 / 17.54 / 17.54 / 17.56 | 689 / 685 / 685 / 686 | 89.2 to 89.3 |
| `ramp_0.75` | 43.4 / 42.1 / 40.8 / 37.0 | 1.02 / 1.06 / 1.04 / 1.03 | 2 / 3 / 4 / 3 | |
| `ramp_1.25` | 219.0 / 213.0 / 221.2 / 221.2 | 20.42 / 20.64 / 20.54 / 20.47 | 945 / 955 / 950 / 947 | 86.2 to 86.3 |
| `mainline_0.75` | 26.4 / 25.6 / 26.4 / 10.8 | 0.87 / 1.52 / 0.88 / 1.00 | 3 / 42 / 3 / 8 | |
| `mainline_1.25` | 219.2 in every rule | 18.56 / 18.55 / 18.55 / 18.55 | 658 each | 89.4 each |
| `shoulder_lane` | 235.4 / 235.7 / 236.3 / 236.6 | 32.26 / 32.35 / 32.40 / 32.23 | 776 / 761 / 772 / 777 | 73.7 to 73.8 |
| `free_exit` | 95.3 / 65.3 / 90.0 / 85.0 | 2.63 / 3.41 / 2.52 / 2.54 | 113 / 137 / 112 / 106 | 99.7 to 99.8 |
| `T_low`, `T_high` (no meter) | 195.8, 186.0 | 4.75, 15.26 | 90, 399 | 97.9, 93.5 |
| `a_low`, `a_high` (no meter) | 219.2, 210.7 | 12.70, 5.18 | 359, 98 | 93.4, 97.9 |
| `alinea_no_queue_rule` (ALINEA) | 39.0 | 8.58 | 275 | 95.6 |
| `fixed_6_per_min` (fixed) | 75.1 | 11.55 | 484 | 92.3 |
| `s0_high` (none / ALINEA) | 213.4 / 79.0 | 10.53 / 10.87 | 284 / 355 | 95.0 / 94.4 |

### The predictions

| # | Outcome | Evidence (congested minutes unless stated) |
| --- | --- | --- |
| 1 | **Contradicted** | Against no meter no rule counts: fixed −6.3 [−14.3, +1.6], Caltrans plan +3.2 [−0.5, +7.0], ALINEA +2.5 [−0.7, +5.8]; ALINEA does not differ from the plan (−0.7 [−2.5, +1.1]). But the fixed rate has less congestion than ALINEA by 8.9 [1.0, 16.8] and than the plan by 9.6 [2.3, 16.9]: two of the six comparisons count. |
| 2 | **Supported** | ALINEA minus no meter counts in all three unsaturated cases: `demand_0.9` −13.2 [−19.1, −7.2], `ramp_0.75` −6.5 [−9.2, −3.8], `free_exit` −10.2 [−18.7, −1.8]; and in none of the saturated ones: `demand_1.1` −1.9 [−4.0, +0.3], `ramp_1.25` +2.1 [−2.3, +6.6], `mainline_1.25` −0.1 [−0.2, +0.1], `shoulder_lane` +1.2 [−1.1, +3.5]. |
| 3 | **Supported** | ALINEA minus the plan counts in five cases, all with less congestion for ALINEA: `demand_0.9` −9.8 [−16.1, −3.4], `mainline_0.75` −15.7 [−24.8, −6.6], `free_exit` −5.0 [−9.3, −0.7] (at the 5-minute line), `s0_high` −135.9 [−145.0, −126.9], `alinea_no_queue_rule` −175.0 [−180.9, −169.1]. Nearest to a contradiction: `caltrans_no_override` +4.2 [+1.5, +6.8], below the line. |
| 4 | **Contradicted in part** | `T_low` to `T_high` without a meter: −9.9 [−21.8, +2.0], less than 20 minutes, the interval includes zero and the sign is the opposite of the expected one. `a_low` to `a_high` without a meter: time per vehicle −7.52 [−8.74, −6.29] min, as predicted. The largest rule effects at the baseline are 6.3 congested minutes (fixed rate, not counted) and 0.12 min per vehicle. |
| 5 | **Supported** | ALINEA in each case minus ALINEA at the baseline: gain halved +0.0 [−3.0, +3.0], gain doubled +1.2 [−0.8, +3.3], set value −20 % +1.1 [−1.3, +3.5], +20 % +1.0 [−0.3, +2.3]. |
| 6 | **Supported for ALINEA's queue rule, contradicted for the plan's override** | ALINEA without the queue rule: −174.3 [−179.9, −168.7] and +127.7 [+108.9, +146.5] vehicles at the peak on Ventura Blvd. The plan without the override: −4.8 [−8.2, −1.5], below the line, and +1.9 [−18.7, +22.5] vehicles. |
| 7 | **Supported** | Each of the ten ALINEA runs records 118 fallback decisions in the 120 intervals of the fault (the other two hold the last rate). ALINEA minus the fixed rate in that case: +5.2 [−2.5, +13.0]. |
| 8 | **Supported** | `drivers_normal`: ALINEA minus fixed +8.6 [+1.0, +16.2] and plan minus fixed +10.5 [+5.1, +15.9], the baseline's signs. `drivers_field`: no contrast counts. Time per vehicle without a meter at `drivers_field`: +4.23 [+3.38, +5.07] min. |

### What the run shows

1. **At the observed demand no rule changes the outcome.** Against no meter the three
   rules differ by at most 0.12 min per vehicle (intervals of about ±0.5), each serves
   97.1 % of the demand, and none makes a counted difference in congestion. The decision
   counts give the reason: ALINEA's queue rule set the rate in 464 of the 600 intervals
   and the plan's override in 441. The ramp stores about 25 vehicles, so for three
   quarters of the morning the rate is set by the queue on the ramp and not by the
   freeway.
2. **A meter helps the freeway below saturation, and the gain is paid on the ramp.**
   ALINEA's four counted reductions among the conditions that do not change the model
   are `demand_0.9`, `ramp_0.75`, `mainline_0.75` (−15.7 [−26.2, −5.1]) and
   `free_exit`. In none of them is time per vehicle lower with ALINEA: +0.08
   [+0.03, +0.12], +0.01 [−0.01, +0.03], +0.13 [+0.09, +0.18] and −0.09 [−0.26, +0.09]
   min. The meter moves the wait from the freeway lane to the ramp.
3. **The fixed rate has less freeway congestion because nothing makes it give way.**
   It makes a counted difference from no meter in seven of the 25 conditions
   (`wave_60min` −16.8, `free_exit` −30.0, `T_low` −9.2, `a_high` −21.1, `v0_low` −10.4,
   `v0_high` −15.2, `drivers_normal` −11.1), ALINEA in five and the plan in none. The
   fixed rate has no queue rule: its street queue is longer (`free_exit` +23.9
   [+13.3, +34.5] vehicles, `wave_60min` +35.3 [+12.8, +57.8], `mainline_0.75` +39.3
   [+27.1, +51.5]) and its time per vehicle is never lower and is higher in five cases
   (`mainline_0.75` +0.65, `wave_60min` +0.90, `free_exit` +0.78, `demand_0.9` +0.13,
   `ramp_0.75` +0.04 min). This is the trade the mix study found (D021), not a gain.
4. **A meter allowed to hold removes most of the congestion at the station and costs
   more than it saves.** Fixed at 6 vehicles a minute per lane: −135.6
   [−146.4, −124.8] congested minutes, +336 vehicles on Ventura Blvd, +4.70
   [+3.98, +5.41] min per vehicle, 92.3 % served. ALINEA without its queue rule: −171.8
   [−178.8, −164.7] against no meter, +127 vehicles, +1.73 [+1.25, +2.21] min per
   vehicle, 95.6 % served. The downstream boundary passes a fixed flow in congested
   intervals, so a vehicle held at the meter leaves part of that flow unused; this
   result depends on that boundary.
5. **How people drive moves the outcome far more than the rule.** Time per vehicle
   without a meter, each case minus the baseline: `T_high` +8.40, `a_low` +5.84,
   `drivers_field` +4.23, `s0_high` +3.68, `b_high` +2.12, `drivers_normal` +1.70,
   `delta_4` +0.57, `b_low` −0.88, `a_high` −1.68, `s0_low` −1.72, `T_low` −2.11 min, all
   with intervals that exclude zero; the desired speed does not matter (`v0_low` +0.18
   [−0.12, +0.48], `v0_high` +0.09 [−0.21, +0.39]). The acceleration `a`, which loop
   data cannot identify (D023), moves time per vehicle from 5.2 to 12.7 min.
6. **Demand.** 10 % less demand removes 163 congested minutes and 5.9 min per vehicle;
   10 % more adds 10.8 min per vehicle and 541 vehicles on the street. 25 % more ramp
   demand adds 13.6 min per vehicle and 797 vehicles on the street, 25 % more through
   traffic 11.7 min and 510 vehicles, and the shoulder-lane bound 25.4 min. A 60-minute
   wave adds 3.0 min per vehicle; a 10-minute wave is absorbed (+0.8 [−0.5, +2.0]).

### Two things the run exposed

- **The queue rule fails when fewer vehicles fit between its loops.** With a 3 m
  standstill gap ALINEA cuts congestion by 134 minutes and holds 71 [49, 93] more
  vehicles on the street, as if it had no queue rule. Checked after the run on seed 1:
  the queue estimate is the count between the entry loop (18 m from the entrance) and
  the stop line, which holds 54.5 m × 3 lanes / 8 m = 20.4 vehicles at that gap. The
  estimate never passes 22 and is above the rule's target of 20 in 3 % of the samples
  after 06:00 (84 % at the baseline, where 23.4 vehicles fit), while 238 vehicles wait
  on average. The target was set as 80 % of the 24.6 vehicles of the whole storage
  (assumed); at the 8.84 m per vehicle of the Caltrans manual only 18.5 fit between the
  loops. The target has to be tied to what the loops can count. Not corrected in this
  run.
- **Minutes of congestion saturate and can mislead above capacity.** `T_high` has
  fewer congested minutes than the baseline (186 against 211) while its time per
  vehicle more than doubles (15.3 against 6.9 min) and 399 vehicles wait on the street.
  The measure counts intervals at one station against thresholds fixed at the baseline
  values, and vehicles that cannot enter the modeled lane wait outside it. Above
  saturation, time per vehicle and the street queue have to be read with it. This is
  why prediction 4 failed for `T`.

- **For the first 40 minutes of congestion the modeled merge is the limit, not the
  exit.** Checked after the run on the baseline, seed 1, by stepping the simulation and
  counting exits by origin every five minutes. From 06:05 to 06:45 the exit's
  allowance (1,517 to 1,829 veh/h) is above what leaves: with both approaches queued the
  merge passes 120 vehicles per five minutes, 1,440 veh/h, 60 from the ramp and 60
  through, under ALINEA from 06:25 to 06:45 and in total under no meter too. That is
  27 % below the static capacity of 1,980 veh/h. With identical drivers the pattern
  repeats exactly, which is the flat 2.0 m/s that ALINEA's station speed shows from
  06:24 to 06:48 in the report's figure. From 06:45 the exits equal the allowance
  (112 and 118 per five minutes at exit speeds of 6.1 and 6.8 m/s) and the exit is the
  limit. In the same seed without a meter no ramp vehicle leaves between 06:10 and
  06:20, while the freeway lane flows at about 1,800 veh/h, where PeMS shows 480 and
  708 veh/h entering from the ramp in those two intervals: the merge rule shuts the
  ramp out when the freeway lane flows near capacity. Both observations point at the
  merge rule (open decision in `docs/decisions.md`).

### Limits

One observed day; ten seeds; a one-lane freeway with a flow-limited exit; identical
drivers except in two cases; `a` chosen among three values. 105 rule-against-no-meter
comparisons were made for each measure, so a counted difference in one case alone
(`T_low`, `a_high`, the two `v0` cases) is a candidate. The plan's thresholds and the
ALINEA/Q rule are assumed or unverified (D015, D022).
