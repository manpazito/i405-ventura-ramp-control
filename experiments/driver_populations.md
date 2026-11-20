# Driver populations on the I-405 SB Ventura on-ramp scenario

Specification written 2026-11-18 21:16 PST, **before any run of this study**. The
predictions below have not been edited since; results and interpretation are added underneath after the run. Simulated and
uncalibrated, like every result in this repository.

Note added 2026-11-19 (D022): the ALINEA runs below used the set value 0.34. It is now
the critical occupancy, 0.26; a test of 30 runs found no counted difference between the
two settings, and this study was not rerun.

Note added 2026-11-19 (D023): every number below comes from the model **before
calibration** (`a` = `b` = 2 m/s², `T` = 1 s, exponent 4; the resolved settings are stored in each
run folder's `config.yaml`).
Running `uv run arm-drivers` now uses the calibrated site and does not reproduce them.
On the calibrated model, two of these populations are cases of the
[rule ablation](rule_ablation.md) (`drivers_normal`, `drivers_field`), and which trait
carries their effect, and whether shape matters there, is tested in
[driver traits](driver_traits.md).

## Question

Every result so far gives all drivers the same IDM values. Does that matter?

1. Does it change the results that drivers differ at all?
2. Does it matter which **shape** their differences follow (uniform, normal, skewed),
   when mean and spread are the same?
3. Does it matter **how much** they differ, and in which parameters (car following
   versus the lane-changing preference)?
4. Does any of this change what ramp metering does in the model?

## Baseline and changed factor

Baseline: the site scenario of `configs/i405.yaml` with identical drivers (case `fixed`).
Changed factor: the driver population only (`vehicle.spread`, `vehicle.shape`), set per
case in `configs/i405_drivers.yaml`. Geometry, demand, downstream boundary, detectors and
controllers are those of the site scenario. In a given seed every case meets the same
arrivals, and the k-th driver of an origin sits at the same percentile of every
parameter, so cases are compared by paired differences over seeds.

## Cases

Spreads are coefficients of variation around the site's fixed values (`a` = `b` =
2 m/s², `T` = 1 s, `s0` = 2 m, `b_safe` = 4 m/s², desired speed per section). Sources and
checks: [driver heterogeneity review](../docs/research/driver_heterogeneity.md).

| Case | What varies | Shape | Basis |
| --- | --- | --- | --- |
| `fixed` | nothing | – | every earlier result |
| `speed_only` | `v0` 0.10 | normal | SUMO's default: only the desired-speed factor is drawn per vehicle |
| `uniform` | `v0`, `T`, `a`, `b` 0.1155 | uniform | Kesting, Treiber and Helbing (2010): uniform and independent, 80–120 % of the mean |
| `normal` | same four, 0.1155 | normal, truncated at 2 sd | the same mean and spread in the shape most simulators use |
| `lognormal` | same four, 0.1155 | lognormal | the same mean and spread, skewed to the right |
| `merge_only` | `b_safe` 0.25 | lognormal | the lane-changing preference alone; spread assumed |
| `empirical` | `v0` 0.10, `T` 0.20, `a` 0.33, `b` 0.33, `s0` 0.48, `b_safe` 0.25 | normal for `v0`, lognormal for the rest | spreads observed or calibrated at other sites |

## Design

- Demand variants: `x0.9` (where metering made a difference before), `historical` (the
  observed day) and `free_exit_x1` (the observed day without the downstream restriction,
  so the merge is the only bottleneck).
- Controllers: no meter and ALINEA with queue control. The fixed-rate and Caltrans rules
  are left out to limit the run; they can be added in the configuration.
- Seeds 1–20. Runs: 7 cases × 3 variants × 2 controllers × 20 seeds = 840, five simulated
  hours each (05:00–10:00).
- Command: `uv run arm-drivers --workers 10`.

## Metrics and decision rule

Primary: minutes of persistent congestion at the mainline station upstream of the gore
(`congested_min`, definition D016). Secondary: demand served, time in system per
requested vehicle, peak queue held on Ventura Blvd. Integrity: steps with overlapping
vehicles, vehicle conservation.

A difference **counts** when the 95 % t interval of the paired differences over the 20
seeds excludes zero **and** the mean difference is at least 5 minutes of congestion (the
size D016 uses). For secondary metrics the interval alone is reported. With 7 cases, 3
variants and 2 controllers there are many intervals, so about one in twenty will exclude
zero by chance; a difference that appears in one cell only is treated as a candidate,
not a result.

## Predictions

1. **Shape does not matter.** No contrast between `uniform`, `normal` and `lognormal`
   counts in any variant or controller. Reason: with the same mean time gap the
   steady-state capacity of a mixed platoon is the same (computed from the IDM
   equilibrium for these populations: 2,403 to 2,404 veh/h against 2,420 for identical
   drivers), and Kesting et al. (2007) saw no qualitative difference with Gaussian
   parameters on a single-lane on-ramp road.
2. **Differences between drivers add congestion where the merge is the bottleneck.** In
   `free_exit_x1` the cases `uniform`, `normal`, `lognormal` and `empirical` give more
   congested minutes and more time per vehicle than `fixed`. Reason: outflow from
   congested traffic is lower with distributed parameters while free-flow capacity is
   not (Kesting et al. 2007), and the merge discharge of this model follows `a`
   concavely.
3. **Desired speed alone costs time, not congestion.** `speed_only` raises the time in
   system per vehicle (on one lane a slower driver holds the platoon behind them) but
   its congestion difference from `fixed` does not count, because the slowest desired
   speed (22.1 m/s) stays above the 20 m/s congestion line and capacity is unchanged
   (2,400 veh/h).
4. **The lane-changing preference alone changes nothing that counts.** `merge_only` does
   not differ from `fixed`. Reason: the MOBIL authors report a negligible influence of
   `b_safe` within a reasonable range.
5. **More spread, more effect.** `empirical` differs from `fixed` by more than `uniform`
   does, in the same direction, in congested minutes and in time per vehicle.
6. **Metering keeps its sign.** ALINEA at `x0.9` reduces congested minutes under every
   population, and the change of that effect relative to `fixed` drivers does not count.

## What would contradict them

1. Any shape contrast that counts in two or more cells.
2. A counted reduction of congestion, or no counted difference at all, for those four
   cases in `free_exit_x1`.
3. A counted congestion difference for `speed_only`, or no increase in time per vehicle.
4. A counted difference for `merge_only`.
5. `empirical` closer to `fixed` than `uniform` is, or of opposite sign.
6. ALINEA's effect at `x0.9` positive under some population, or a counted change of the
   effect.

## Limits known before the run

- Spreads and shapes come from other sites and other models; none is estimated for
  I-405. Calibrated spreads mix differences between drivers with variation within a
  driver and with optimizer bounds, so `empirical` is an upper estimate.
- Parameters are drawn independently. Studies that calibrate whole drivers find the
  parameters correlated and report that ignoring this changes simulation outputs; no
  across-driver correlation matrix for IDM could be found to put in.
- One freeway lane without passing: a spread in desired speed costs more here than on
  five real lanes, where faster drivers move left.
- The merge-yield weakness recorded on 2026-11-18 (a yielding vehicle ignores its
  own-lane leader) is more exposed when drivers differ. Overlap steps are reported per
  case, not hidden.
- The congestion line (20 m/s, 26 % occupancy) was derived for identical drivers.

## Results of the first run

Run folder `results/driver-study/20261119T051703_669425Z` (generated, not in Git): 840 runs, command as
specified, started 2026-11-18 21:17 PST and finished 22:52 (95 minutes on 10 processes).
Python 3.14.10; source hashes in the folder's `run.json`. Vehicles are
conserved in all 840 runs. The report code was changed after this run only to handle a
study without a metering rule; these tables are unaffected. Every table below is copied
from the folder's `differences.csv`, `controller_effect.csv` and `evaluation.csv`:
mean over 20 seeds of the paired difference, 95 % interval in brackets, **bold** when
the difference counts by the rule above (for secondary metrics: when the interval
excludes zero).

### Persistent congestion (min), each population minus `fixed`

| | `x0.9`, no meter | `x0.9`, ALINEA | `historical`, no meter | `historical`, ALINEA | `free_exit_x1`, no meter | `free_exit_x1`, ALINEA |
| --- | --- | --- | --- | --- | --- | --- |
| `fixed` (level) | 54.8 | 34.0 | 203.4 | 197.6 | 167.3 | 140.6 |
| `speed_only` | +5.3 (-1.8 to +12.4) | +0.3 (-5.2 to +5.8) | +2.1 (-0.6 to +4.9) | +5.2 (-6.9 to +17.2) | **+7.4 (+1.4 to +13.4)** | -1.9 (-6.9 to +3.1) |
| `uniform` | **+10.0 (+4.2 to +15.9)** | **+7.0 (+1.1 to +12.9)** | +3.0 (-0.4 to +6.3) | +5.8 (-7.2 to +18.8) | **+22.2 (+12.0 to +32.4)** | **+28.5 (+14.8 to +42.1)** |
| `normal` | **+9.9 (+2.7 to +17.0)** | +2.4 (-1.7 to +6.5) | +0.9 (-4.3 to +6.0) | +5.0 (-8.7 to +18.7) | **+19.2 (+10.9 to +27.6)** | **+25.4 (+11.7 to +39.0)** |
| `lognormal` | **+9.8 (+4.6 to +15.0)** | +0.1 (-5.1 to +5.4) | +2.3 (-1.8 to +6.4) | +5.8 (-5.7 to +17.4) | **+21.4 (+13.2 to +29.5)** | **+23.8 (+10.8 to +36.8)** |
| `merge_only` | +3.7 (-1.8 to +9.2) | -0.3 (-2.7 to +2.1) | +1.6 (-1.0 to +4.1) | +3.2 (-8.7 to +15.1) | **+6.3 (+0.4 to +12.3)** | +7.5 (-5.4 to +20.4) |
| `empirical` | **+43.4 (+30.6 to +56.1)** | **+33.4 (+23.9 to +42.9)** | **+13.6 (+8.8 to +18.4)** | **+18.2 (+5.9 to +30.5)** | **+43.4 (+25.7 to +61.1)** | **+67.4 (+47.2 to +87.6)** |

### Shapes at equal mean and spread: congestion (min)

| | `x0.9`, no meter | `x0.9`, ALINEA | `historical`, no meter | `historical`, ALINEA | `free_exit_x1`, no meter | `free_exit_x1`, ALINEA |
| --- | --- | --- | --- | --- | --- | --- |
| `normal` − `uniform` | -0.1 (-6.2 to +5.9) | -4.6 (-9.4 to +0.2) | -2.1 (-4.9 to +0.8) | -0.8 (-4.1 to +2.5) | -3.0 (-8.2 to +2.2) | -3.1 (-7.5 to +1.3) |
| `lognormal` − `uniform` | -0.2 (-5.7 to +5.2) | **-6.9 (-13.7 to -0.0)** | -0.7 (-3.2 to +1.8) | +0.1 (-2.9 to +3.1) | -0.8 (-6.1 to +4.4) | -4.7 (-11.0 to +1.7) |
| `lognormal` − `normal` | -0.1 (-4.3 to +4.1) | -2.3 (-6.0 to +1.4) | +1.4 (-2.2 to +5.0) | +0.9 (-2.8 to +4.6) | +2.1 (-3.7 to +8.0) | -1.6 (-8.8 to +5.7) |

### Time in system per requested vehicle (min), each population minus `fixed`

| | `x0.9`, no meter | `x0.9`, ALINEA | `historical`, no meter | `historical`, ALINEA | `free_exit_x1`, no meter | `free_exit_x1`, ALINEA |
| --- | --- | --- | --- | --- | --- | --- |
| `fixed` (level) | 1.30 | 1.16 | 7.40 | 6.88 | 3.89 | 3.55 |
| `speed_only` | **+0.07 (+0.01 to +0.13)** | +0.02 (-0.05 to +0.08) | -0.04 (-0.21 to +0.14) | -0.01 (-0.19 to +0.17) | +0.09 (-0.06 to +0.24) | -0.01 (-0.09 to +0.06) |
| `uniform` | **+0.19 (+0.10 to +0.28)** | **+0.12 (+0.03 to +0.21)** | **+0.62 (+0.36 to +0.89)** | **+0.69 (+0.36 to +1.02)** | **+0.88 (+0.62 to +1.14)** | **+0.91 (+0.59 to +1.22)** |
| `normal` | **+0.21 (+0.10 to +0.31)** | **+0.09 (+0.02 to +0.16)** | **+0.46 (+0.24 to +0.67)** | **+0.52 (+0.31 to +0.74)** | **+0.94 (+0.62 to +1.26)** | **+0.78 (+0.52 to +1.04)** |
| `lognormal` | **+0.20 (+0.11 to +0.30)** | **+0.06 (+0.01 to +0.11)** | **+0.52 (+0.34 to +0.70)** | **+0.51 (+0.32 to +0.69)** | **+1.07 (+0.71 to +1.42)** | **+0.91 (+0.56 to +1.25)** |
| `merge_only` | **+0.05 (+0.00 to +0.09)** | +0.03 (-0.01 to +0.06) | +0.00 (-0.12 to +0.13) | -0.07 (-0.26 to +0.11) | +0.01 (-0.11 to +0.14) | +0.09 (-0.10 to +0.27) |
| `empirical` | **+0.93 (+0.67 to +1.18)** | **+0.71 (+0.49 to +0.93)** | **+2.97 (+2.64 to +3.31)** | **+3.09 (+2.70 to +3.49)** | **+3.84 (+3.41 to +4.27)** | **+3.86 (+3.38 to +4.35)** |

### Peak queue held on Ventura Blvd (veh), each population minus `fixed`

| | `x0.9`, no meter | `x0.9`, ALINEA | `historical`, no meter | `historical`, ALINEA | `free_exit_x1`, no meter | `free_exit_x1`, ALINEA |
| --- | --- | --- | --- | --- | --- | --- |
| `fixed` (level) | 18.7 | 13.2 | 180.3 | 165.8 | 137.4 | 126.3 |
| `speed_only` | +1.6 (-0.4 to +3.7) | +1.6 (-1.2 to +4.3) | -1.1 (-5.4 to +3.2) | -1.2 (-5.2 to +2.7) | +0.6 (-4.2 to +5.3) | +0.1 (-2.6 to +2.9) |
| `uniform` | **+7.5 (+4.2 to +10.7)** | +4.6 (-0.6 to +9.8) | **+23.1 (+15.0 to +31.1)** | **+23.8 (+15.1 to +32.4)** | **+18.4 (+11.5 to +25.3)** | **+22.1 (+14.3 to +29.9)** |
| `normal` | **+8.1 (+4.3 to +11.8)** | +3.0 (-0.6 to +6.7) | **+18.4 (+11.5 to +25.3)** | **+19.1 (+13.7 to +24.4)** | **+20.7 (+12.0 to +29.4)** | **+18.4 (+12.1 to +24.6)** |
| `lognormal` | **+7.5 (+4.0 to +11.0)** | **+1.9 (+0.1 to +3.7)** | **+19.5 (+13.9 to +25.1)** | **+17.9 (+12.4 to +23.3)** | **+24.1 (+14.4 to +33.7)** | **+22.6 (+14.5 to +30.6)** |
| `merge_only` | **+1.1 (+0.1 to +2.2)** | +1.4 (-0.2 to +3.1) | +0.0 (-3.1 to +3.1) | -2.8 (-7.1 to +1.5) | -1.6 (-5.4 to +2.3) | +1.3 (-4.0 to +6.6) |
| `empirical` | **+32.0 (+21.9 to +42.1)** | **+26.4 (+16.8 to +35.9)** | **+122.8 (+105.6 to +140.1)** | **+119.2 (+104.9 to +133.6)** | **+77.2 (+66.2 to +88.2)** | **+84.5 (+73.4 to +95.5)** |

### What ALINEA changes: congestion (min), ALINEA minus no meter

| | `x0.9`: effect | `historical`: effect | `free_exit_x1`: effect | `x0.9`: change from `fixed` | `historical`: change from `fixed` | `free_exit_x1`: change from `fixed` |
| --- | --- | --- | --- | --- | --- | --- |
| `fixed` | -20.7 (-27.0 to -14.4) | -5.9 (-17.5 to +5.7) | -26.7 (-38.7 to -14.7) | – | – | – |
| `speed_only` | -25.7 (-33.9 to -17.6) | -2.9 (-6.5 to +0.8) | -36.0 (-47.7 to -24.4) | -5.0 (-10.2 to +0.2) | +3.0 (-9.8 to +15.8) | **-9.3 (-14.8 to -3.9)** |
| `uniform` | -23.7 (-29.2 to -18.3) | -3.0 (-5.3 to -0.8) | -20.4 (-33.3 to -7.6) | -3.0 (-9.7 to +3.6) | +2.8 (-9.9 to +15.6) | +6.3 (-7.3 to +19.9) |
| `normal` | -28.1 (-36.8 to -19.5) | -1.8 (-5.9 to +2.3) | -20.6 (-33.4 to -7.8) | -7.5 (-15.6 to +0.7) | +4.1 (-9.6 to +17.8) | +6.2 (-7.1 to +19.4) |
| `lognormal` | -30.4 (-39.6 to -21.2) | -2.3 (-5.8 to +1.2) | -24.3 (-37.3 to -11.3) | **-9.7 (-17.7 to -1.7)** | +3.6 (-8.1 to +15.2) | +2.5 (-11.3 to +16.2) |
| `merge_only` | -24.7 (-31.7 to -17.7) | -4.3 (-7.1 to -1.4) | -25.6 (-43.0 to -8.2) | -4.0 (-9.8 to +1.7) | +1.6 (-10.4 to +13.6) | +1.1 (-13.5 to +15.8) |
| `empirical` | -30.6 (-40.4 to -20.9) | -1.2 (-4.1 to +1.6) | -2.7 (-10.1 to +4.7) | **-9.9 (-19.6 to -0.3)** | +4.6 (-7.3 to +16.6) | **+24.0 (+8.3 to +39.8)** |

### Integrity

| Case | Runs with an overlap step | Mean overlap steps per run | Most in one run |
| --- | --- | --- | --- |
| `fixed` | 14 of 120 | 0.20 | 5 |
| `speed_only` | 11 of 120 | 0.17 | 5 |
| `uniform` | 17 of 120 | 0.62 | 13 |
| `normal` | 13 of 120 | 0.40 | 11 |
| `lognormal` | 13 of 120 | 0.61 | 24 |
| `merge_only` | 10 of 120 | 0.18 | 7 |
| `empirical` | 20 of 120 | 0.72 | 11 |

A run has 36,000 steps. Overlap steps come from the merge-yield weakness recorded on
2026-11-18; they occur with identical drivers too and stay below one step per run on
average in every case.

### Predictions against the results

| Prediction | Verdict | Evidence |
| --- | --- | --- |
| 1. Shape does not matter | **Not contradicted** | One of 18 shape contrasts counts (`lognormal` − `uniform` at `x0.9` with ALINEA, −6.9 min, interval −13.7 to −0.0); about one in twenty would by chance. In time per vehicle every shape contrast is within ±0.2 min with an interval that includes zero. The test is weak for skewness: see the follow-up |
| 2. Differences add congestion where the merge is the bottleneck | **Supported** | In `free_exit_x1` the three shapes add 19 to 22 min without a meter and 24 to 29 min with ALINEA, `empirical` 43 and 67 min; all count. Time per vehicle rises by 0.8 to 1.1 min (from 3.89 and 3.55), and by 3.8 to 3.9 min for `empirical` |
| 3. Desired speed alone costs time, not congestion | **Half wrong** | The predicted time cost did not appear: at most +0.09 min, and only one interval excludes zero. Congestion counts in one cell of six (`free_exit_x1`, no meter: +7.4 min, +1.4 to +13.4), a candidate by the rule above |
| 4. The lane-changing preference alone changes nothing that counts | **Mostly supported** | Five cells of six do not count. One does: `free_exit_x1`, no meter, +6.3 min (+0.4 to +12.3), the same cell as for `speed_only`. A candidate |
| 5. More spread, more effect | **Supported** | `empirical` exceeds `uniform` in all six cells: +13.6 to +67.4 min of congestion against +3.0 to +28.5, and +0.7 to +3.9 min per vehicle against +0.1 to +0.9 |
| 6. Metering keeps its sign, and its effect does not change | **Sign supported, "no change" contradicted** | At `x0.9` ALINEA reduces congestion under every population (−20.7 min with `fixed`, −23.7 to −30.6 with the others; every interval below zero). But the effect changes by a counted amount in 4 of 18 cells: larger at `x0.9` for `lognormal` (−9.7) and `empirical` (−9.9) and at the free exit for `speed_only` (−9.3), and gone at the free exit for `empirical` (−2.7, interval −10.1 to +4.7, against −26.7 with `fixed`) |

### What this run shows, and what it does not

Shown, for this model and these demand cases:

1. **How much drivers differ matters far more than the shape of the difference.** At
   the free exit, going from identical drivers to a spread of 11.5 % adds about 20
   minutes of congestion and the spreads found in field studies add 43 to 67; changing
   the shape at a fixed spread moves the result by less than the run can resolve
   (intervals of about ±5 to ±7 minutes).
2. **The car-following parameters carry the effect.** Varying only the desired speed
   (what SUMO does by default) or only the merging limit `b_safe` leaves congestion
   within about 8 minutes of identical drivers and time per vehicle within 0.1 min.
   Which of `T`, `a`, `b` and `s0` matters most was not separated.
3. **Identical drivers understate delay.** On the observed day time in system per vehicle
   is 6 to 8 % higher with an 11.5 % spread (+0.46 to +0.62 min on 7.40) and 40 % higher
   with the `empirical` spreads (+2.97 min); the peak queue held on Ventura Blvd grows
   from 180 vehicles by 18 to 23 and by 123.
4. **ALINEA's benefit at 0.9× demand does not depend on identical drivers.** It is at
   least as large under every population. With a free exit and the `empirical`
   population the congestion benefit disappears, while time per vehicle still improves
   by 0.3 min.

Not shown:

- That any of these populations describes I-405. Nothing is calibrated; `empirical` is an
  upper estimate of how much drivers differ, and a 99 % increase in time per vehicle at
  the free exit says how sensitive the model is, not what happens on the road.
- That shape never matters. At a spread of 11.5 % a normal and a lognormal are nearly
  the same curve, and effects below about 5 minutes are invisible with 20 seeds. The
  follow-up below repeats the comparison at 25 %.
- What correlated parameters would do; they are drawn independently here.
- Anything about the other four freeway lanes: the model has one lane without passing.
- The three single-cell differences above (predictions 1, 3 and 4) are candidates for a
  rerun with new seeds, not results.

## Follow-up: the three shapes at a wider spread

Specified 2026-11-18 22:55 PST, **after** the first run and before this one. It is a
follow-up, not part of the plan above: the first run showed no difference between shapes
at a spread of 11.5 %, but at that spread a normal and a lognormal are almost the same
curve (skewness 0.23), so the test said little about skewed shapes.

- Cases (`configs/i405_drivers_shapes.yaml`): `fixed`, and `uniform`, `normal`,
  `lognormal` with a spread of 0.25 [assumed] on `T`, `a` and `b`. Desired speed stays
  fixed, so the comparison is about car following and not about how slow the slowest
  driver on a lane without passing is. At 0.25 the three shapes reach down to 0.57, 0.43
  and 0.55 times the fixed value, and the lognormal has a skewness of about 0.5.
- Demand cases `x0.9` and `free_exit_x1`, no meter, seeds 1–20: 160 runs.
- Command: `uv run arm-drivers --config configs/i405_drivers_shapes.yaml --output
  results/driver-study-shapes --workers 10`.

**Prediction 7.** No contrast between the three shapes counts in either demand case, and
each shape gives more congestion than identical drivers in `free_exit_x1`, by more than
the 19 to 22 minutes found at a spread of 11.5 %. Less certain than prediction 1: the
normal shape now includes time gaps of 0.43 s, below the 0.5 s simulation step.

**Contradicted by** a shape contrast that counts in either demand case.

### Results of the follow-up

Run folder `results/driver-study-shapes/20261119T065610_267862Z` (generated, not in Git): 160 runs,
2026-11-18 22:56 to 23:14 PST, vehicles conserved in every run. Realized populations: a
coefficient of variation of 0.25 for each shape, skewness 0.52 for the lognormal and
0.00 for the other two. Same conventions as the tables above.

| | `x0.9`: congestion (min) | `free_exit_x1`: congestion (min) | `x0.9`: time per vehicle (min) | `free_exit_x1`: time per vehicle (min) | `x0.9`: peak queue on Ventura Blvd (veh) | `free_exit_x1`: peak queue on Ventura Blvd (veh) |
| --- | --- | --- | --- | --- | --- | --- |
| `fixed` (level) | 54.8 | 167.3 | 1.30 | 3.89 | 18.7 | 137.4 |
| `uniform` | **+27.9 (+18.2 to +37.5)** | **+36.1 (+20.6 to +51.7)** | **+0.65 (+0.45 to +0.84)** | **+3.12 (+2.68 to +3.55)** | **+24.4 (+15.4 to +33.5)** | **+68.3 (+56.8 to +79.8)** |
| `normal` | **+28.7 (+18.4 to +39.0)** | **+36.4 (+19.5 to +53.2)** | **+0.72 (+0.49 to +0.94)** | **+3.06 (+2.67 to +3.45)** | **+26.4 (+16.4 to +36.3)** | **+66.5 (+55.8 to +77.2)** |
| `lognormal` | **+27.4 (+16.8 to +37.9)** | **+35.3 (+19.0 to +51.6)** | **+0.64 (+0.44 to +0.84)** | **+2.77 (+2.42 to +3.13)** | **+25.3 (+16.7 to +33.9)** | **+59.9 (+50.6 to +69.2)** |
| `normal` − `uniform` | +0.8 (-3.8 to +5.5) | +0.2 (-2.2 to +2.6) | +0.07 (-0.03 to +0.17) | -0.05 (-0.17 to +0.07) | +1.9 (-1.7 to +5.5) | -1.8 (-5.4 to +1.8) |
| `lognormal` − `uniform` | -0.5 (-5.8 to +4.8) | -0.8 (-3.8 to +2.2) | -0.01 (-0.10 to +0.09) | **-0.34 (-0.53 to -0.16)** | +0.8 (-3.4 to +5.1) | **-8.4 (-14.1 to -2.7)** |
| `lognormal` − `normal` | -1.4 (-6.4 to +3.7) | -1.0 (-4.5 to +2.5) | -0.08 (-0.18 to +0.03) | **-0.29 (-0.43 to -0.15)** | -1.1 (-5.2 to +3.1) | **-6.6 (-10.6 to -2.6)** |

Overlap steps: `fixed` 4 of 40 runs, 0.23 steps per run; `uniform` 13 of 40 runs, 1.57 steps per run; `normal` 12 of 40 runs, 0.95 steps per run; `lognormal` 8 of 40 runs, 0.75 steps per run.

**Prediction 7: holds for congestion, with a shape effect in the secondary metrics.**

- No shape contrast counts in congested minutes: all six are within ±1.4 min, with
  intervals inside −6.4 to +5.5. Each shape adds 35 to 36 min at the free exit, more
  than the 19 to 22 min found at 11.5 %, and 27 to 29 min at `x0.9`.
- Uniform and normal are indistinguishable in every metric.
- The lognormal population is slightly better off than the two symmetric ones at the
  free exit: 0.29 to 0.34 min less time per vehicle (of about 3 min added), 0.2
  percentage points more demand served and 7 to 8 fewer vehicles held on Ventura Blvd,
  all with intervals that exclude zero. At `x0.9` there is no such difference. A
  possible reason, not tested: at the same mean and spread a lognormal has fewer drivers
  with low acceleration (10.6 % below 0.7 of the fixed value, against 12.8 % for the
  normal and 15.2 % for the uniform), and the queue discharge of this model follows `a`.
  This is a candidate until it is repeated with new seeds.

### Conclusion on shape after both runs

For congested minutes the shape of the distribution made no countable difference at a
spread of 11.5 % or of 25 %. Uniform and normal populations with the same mean and
spread gave the same results in every metric. A skewed (lognormal) population cost
about a tenth less of the added delay than a symmetric one when the spread was 25 % and
the merge was the only bottleneck. For this model the choice of shape is therefore
second-order next to the choice of spread: with the downstream restriction removed,
going from 11.5 % (on `v0`, `T`, `a`, `b`) to 25 % (on `T`, `a`, `b`) raises the added
congestion from about 20 to about 36 minutes and the added time per vehicle from about
0.9 to about 3 minutes, while the largest shape effect seen is 0.3 minutes of time per
vehicle.
