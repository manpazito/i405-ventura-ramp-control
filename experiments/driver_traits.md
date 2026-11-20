# Which driver trait matters, on the calibrated model

Specification written 2026-11-19 19:24 PST, **before any run of this study**. Results are
added below after the run.
Simulated, with the calibrated site scenario (D023); not a measurement of drivers on
I-405.

## Question

In the one-factor study of the rules ([rule ablation](rule_ablation.md)), drivers whose
IDM values differ add 1.70 min (`drivers_normal`) and 4.23 min (`drivers_field`) to the
time in the system per vehicle without a meter, from 6.86 min. Those cases vary several
traits at once. Two questions follow:

1. Which trait carries the effect: desired speed `v0`, time gap `T`, acceleration `a`,
   comfortable deceleration `b`, standstill gap `s0`, or the merging limit `b_safe`?
2. Does the shape of the distribution matter on the calibrated model? On the model
   before calibration it did not, beyond 0.3 min per vehicle ([D019](driver_populations.md)).

## Design

- Site: `configs/i405.yaml` as calibrated (`T` 1.51 s, `a` 2.5 m/s², `b` 2 m/s², `s0`
  2 m, exponent 20, freeway `v0` 29.1 m/s), the observed day of 2022-10-11, 05:00–10:00,
  no meter.
- Cases (`configs/i405_driver_traits.yaml`): `fixed` (identical drivers); `field` (all
  six traits, the `drivers_field` population); one case per trait at the spread and
  shape it has in `field` (`field_v0` 10 % normal; lognormal `field_T` 20 %, `field_a`
  33 %, `field_b` 33 %, `field_s0` 48 %, `field_b_safe` 25 %); and `uniform`, `normal`,
  `lognormal` with a spread of 25 % on `T`, `a` and `b`.
- Seeds 1–20; 11 cases × 20 seeds = 220 runs. Command: `uv run arm-study --config
  configs/i405_driver_traits.yaml --output results/driver-traits --workers 11`.
- In a given seed every case meets the same arrivals and every driver keeps the same
  percentile of every trait, so cases are compared by paired differences over seeds.

## Measures and rule

The primary measure is the **time in the system per requested vehicle**, because the
driver effects of the rule ablation showed there and persistent congestion is near its
ceiling at this baseline (211 of 300 minutes). A trait **matters** when the 95 % t
interval of its paired difference from `fixed` excludes zero. Secondary: vehicles
served, peak queue held on Ventura Blvd, and persistent congestion with the project's
rule (interval excludes zero and the mean reaches 5 minutes, D016). There are many
intervals; a single interval that barely excludes zero is a candidate, not a result.

## What is known before the run

- One-factor shifts of the mean, no meter, time per vehicle (rule ablation, 10 seeds):
  `T` +20 % +8.40, −20 % −2.11; `a` −20 % +5.84, +20 % −1.68; `s0` 3 m +3.68, 1 m
  −1.72; `b` 3 m/s² +2.12, 1 m/s² −0.88; `v0` ±10 % +0.18 and +0.09 (intervals with
  zero) min.
- Static capacity of a long platoon on one lane, all drivers at one speed and none
  passing (computed from the IDM equilibrium of each population): 1,980 veh/h with
  identical drivers; 1,980 to 1,983 for every case without a `v0` spread; 1,945 with
  the 10 % `v0` spread, because the platoon cannot go faster than its slowest driver
  wants to (22.5 m/s). Mean-preserving spreads of `T` and `s0` leave the static capacity
  unchanged because the equilibrium gap is linear in both.
- Lecture 05B, slide 28: the preferred time gap `T` is "the most relevant influencing
  factor determining the static capacity", and an agile (responsive) driving style
  reduces the capacity drop, bringing the dynamic capacity nearer to the static one.

## Predictions

1. **Acceleration carries the effect.** `field_a` adds the most time per vehicle of the
   six single-trait cases, and its interval excludes zero. Reason: with the static
   capacity unchanged, what remains is the dynamic capacity, which the lecture ties to
   agility; and `a` has a strongly one-sided effect (`a_low` +5.84 against `a_high`
   −1.68), so drivers below the mean cost more than those above it save.
2. **A spread in the time gap costs little.** `field_T` adds less than 1 min per vehicle,
   although `T` has the largest one-factor effect of all (+8.40 min at +20 %). Reason:
   with its mean unchanged the static capacity is unchanged (1,982 against 1,980 veh/h).
3. **Desired speed and the merging limit do not matter.** The intervals of `field_v0`
   and `field_b_safe` include zero in time per vehicle, and neither changes persistent
   congestion by a counted amount. Reasons: `v0` did not matter in the one-factor study,
   and the 1.8 % loss of static capacity from the slowest driver binds only in free
   flow, while the lane is congested most of the morning (it could still move the onset
   of congestion); MOBIL's authors find `b_safe` "negligible within a reasonable range".
4. **The traits add up.** The sum of the six single-trait effects lies inside the 95 %
   interval of the `field` effect. Reason: the lane is oversaturated for most of the
   morning, and in a deterministic queue (Lecture 03, D/D/1) the delay grows linearly
   with the capacity lost, so small losses add.
5. **Shape stays second-order.** No shape contrast changes persistent congestion by a
   counted amount, and the three shapes' time-per-vehicle effects against `fixed`
   differ from each other by less than a quarter of their mean. Reason: the follow-up of
   D019 on the model before calibration.

Check, not a prediction: for seeds 1–10, `fixed` and `field` must reproduce the
`baseline` and `drivers_field` runs of the rule ablation exactly (same engine, seeds and
configuration).

## What would contradict them

1. Another trait with a larger mean effect than `field_a`, or `field_a`'s interval
   including zero.
2. `field_T` adding 1 min per vehicle or more.
3. An interval excluding zero for `field_v0` or `field_b_safe` in time per vehicle, or a
   counted congestion difference.
4. The sum of the six effects outside the `field` interval.
5. A counted shape contrast in congestion, or shapes differing by a quarter of their
   mean effect or more.

## Results

Run folder `results/driver-traits/20261120T032135_110584Z` (generated, not in Git): 220
runs, 2026-11-19 19:21 to 19:41 PST on 11 processes. Vehicles are conserved in every run
and no run has an overlap step. Check passed: for seeds 1–10, `fixed` and `field`
reproduce the rule ablation's `baseline` and `drivers_field` runs exactly (vehicles
exited, total and delay times, congested minutes).

Identical drivers (`fixed`, 20 seeds): 6.66 min per vehicle, 97.18 % served, peak queue
on Ventura Blvd 146.7 vehicles, 208.9 congested minutes. Each case minus `fixed`, mean
over 20 seeds and 95 % interval; **bold**: interval excludes zero (for congestion: and
the mean reaches 5 min).

| Case | Time per vehicle (min) | Served (%) | Peak queue on Ventura Blvd (veh) | Congestion (min) |
| --- | --- | --- | --- | --- |
| `field` (all six) | **+3.71 (+3.13 to +4.29)** | **−1.88 (−2.16 to −1.59)** | **+119.1 (+102.7 to +135.4)** | **+13.7 (+6.1 to +21.3)** |
| `field_v0` | **−0.26 (−0.49 to −0.03)** | **+0.11 (+0.01 to +0.20)** | **−7.0 (−13.4 to −0.6)** | +3.0 (+1.3 to +4.8) |
| `field_T` | **+1.45 (+0.87 to +2.03)** | **−0.68 (−0.96 to −0.41)** | **+41.8 (+25.9 to +57.7)** | +5.5 (−0.5 to +11.4) |
| `field_a` | **+3.22 (+2.57 to +3.88)** | **−1.63 (−1.94 to −1.32)** | **+102.4 (+83.4 to +121.4)** | **+8.4 (+0.7 to +16.2)** |
| `field_b` | **+0.55 (+0.17 to +0.93)** | **−0.25 (−0.42 to −0.08)** | **+16.9 (+7.8 to +25.9)** | +2.4 (+0.3 to +4.6) |
| `field_s0` | **+0.48 (+0.24 to +0.72)** | **−0.23 (−0.33 to −0.12)** | **+15.1 (+7.7 to +22.5)** | +4.0 (+0.5 to +7.6) |
| `field_b_safe` | −0.20 (−0.48 to +0.09) | +0.07 (−0.05 to +0.19) | −4.9 (−12.8 to +3.1) | +2.5 (+0.1 to +4.9) |
| `uniform` (25 % on `T`, `a`, `b`) | **+3.18 (+2.53 to +3.84)** | **−1.56 (−1.88 to −1.24)** | **+101.7 (+82.8 to +120.7)** | +6.3 (−2.1 to +14.7) |
| `normal` | **+3.03 (+2.29 to +3.76)** | **−1.50 (−1.85 to −1.14)** | **+96.3 (+75.1 to +117.4)** | +7.6 (−1.2 to +16.5) |
| `lognormal` | **+3.30 (+2.75 to +3.86)** | **−1.60 (−1.89 to −1.32)** | **+103.3 (+87.4 to +119.2)** | +8.5 (−0.1 to +17.0) |

Shape contrasts: `normal` − `uniform` −0.16 (−0.59 to +0.28) min per vehicle and +1.3
(−2.0 to +4.6) congested min; `lognormal` − `uniform` +0.12 (−0.27 to +0.50) and +2.2
(−2.3 to +6.6); `lognormal` − `normal` +0.28 (−0.26 to +0.82) and +0.8 (−4.1 to +5.7).
None excludes zero in any measure.

### Predictions against the results

| Prediction | Verdict | Evidence |
| --- | --- | --- |
| 1. Acceleration carries the effect | **Supported** | `field_a` +3.22 min per vehicle, the largest of the six and 87 % of `field`'s +3.71; it also accounts for most of the street queue (+102 of +119 vehicles) |
| 2. A spread in the time gap costs little | **Contradicted** | `field_T` +1.45 (+0.87 to +2.03) min, above the 1-minute line, although the static capacity of a long platoon is unchanged |
| 3. Desired speed and the merging limit do not matter | **Half** | `b_safe`: no interval excludes zero and congestion does not count. `v0`: congestion does not count, but time per vehicle falls slightly, −0.26 (−0.49 to −0.03) min; a candidate |
| 4. The traits add up | **Contradicted** | The six single effects sum to +5.25 min, outside `field`'s interval; per seed, `field` minus the sum is −1.54 (−2.49 to −0.59) min. The traits overlap |
| 5. Shape stays second-order | **Supported** | The three shapes add +3.03 to +3.30 min; they differ by at most 0.28 min, a tenth of their mean, and no shape contrast excludes zero |

### What this shows, and what it does not

1. **On the calibrated model, the drivers' differences in acceleration are what costs
   time.** A spread of `a` alone produces 87 % of the effect of all six spreads, and with
   it a street queue about 100 vehicles longer. That fits Lecture 05B (slide 28): agility
   sets how close the dynamic capacity comes to the static one, and the slow
   accelerators set the pace of a queue discharging onto one lane without passing.
2. **The time gap's spread matters more than the static capacity suggests** (+1.45 min
   against an unchanged platoon capacity), so the static argument of prediction 2 was
   wrong. One possible reason, not tested: on one lane without passing, drivers with
   long gaps leave space at the merge and at queue discharge that drivers with short
   gaps behind them cannot use.
3. **`b`, `s0`, `v0` and the merging limit matter little** (at most 0.55 min each).
4. **Effects overlap instead of adding**: all six together cost 1.5 min less than the
   sum of their parts. Why was not tested; one reading is that once slow accelerators
   pace the queue, further differences in other traits cost less.
5. **Shape does not matter on the calibrated model either**, at a spread of 25 %, in any
   measure. The conclusion of D019 carries over.
6. Not shown: that real I-405 drivers differ by these amounts (the spreads come from
   other sites); correlated traits; any effect under a meter (`none` only); a second
   day.
