# Ramp metering and bounded feedback

Status: established control concepts plus proposed evaluation safeguards. The bounded
rules are implemented in `control/metering.py` (D013, D015); no target, gain, rate bound
or fallback timing is calibrated. The ALINEA rule was checked against the lecture and
the original paper on 2026-11-19: see the last section.

## Baselines and feedback

Fixed-rate metering commands a constant rate or a documented time-of-day schedule;
actual discharge is limited by demand, signal service, and receiving supply.
Traffic-responsive metering changes the command from available measurements.
Neither is a substitute for the final course CAV or signal-control pathway.

The ALINEA integral-feedback formulation is

$$
r_{t+1}^{\rm raw}=r_t+K_R(o^*-o_t).
$$

$r_t$ is the previous meter command in veh/s. $o_t$ is downstream occupancy
from a completed measurement interval, and $o^*$ is its target, both fractions.
$K_R>0$ has units (veh/s)/occupancy fraction per discrete update. Lower measured
occupancy increases the commanded rate. The original reference is
[Papageorgiou, Hadj-Salem, and Blosseville (1991), Eq. 14](https://onlinepubs.trb.org/Onlinepubs/trr/1991/1320/1320-008.pdf).

Choose the target from a supported operating-point assessment. Do not substitute
density for occupancy or import gains without their scaling and update interval.
A gain expressed in (veh/h)/percentage point converts by $100/3600$ to these
units. If using a continuous integral gain, its discrete counterpart includes
$\Delta_c$; do not multiply an already discrete gain by the interval again.

The original formulation discusses saturation and queue overrides. In normal
operation retain the previous commanded rate; under a binding constraint or
override, the recurrence must reflect realized constrained flow instead of the
suspended command. Document the exact state-update rule to avoid windup. Gain,
delay, detector position, and operating conditions affect response; robustness at
this site remains untested.

## Caltrans local traffic-responsive plan (as simulated)

The site scenario's `caltrans` mode implements the stepwise plan lookup used by
Caltrans field controllers, with queue override. With mainline occupancy $o_t$ from the
station upstream of the gore, $L$ plan levels, occupancy thresholds from $o_1$ to
$o_L$ and per-lane rates falling from $\rho_1$ to $\rho_L$, both evenly spaced, and
$n$ metered lanes:

$$
\ell_t=\min\!\left(L-1,\max\!\left(0,\left\lfloor\frac{o_t-o_1}{o_L-o_1}(L-1)\right\rfloor\right)\right),
\qquad
r^{\text{plan}}_t=n\left[\rho_1+\ell_t\,\frac{\rho_L-\rho_1}{L-1}\right].
$$

While the queue detector's occupancy over the last interval is at or above its
threshold, the command steps up from the applied rate,
$r_t=\max(r^{\text{plan}}_t,r_{t-1})+n\,\delta$, and returns to $r^{\text{plan}}_t$ in
one step when the detector clears. The result is bounded to $[r_{\min},r_{\max}]$. The
structure follows the Caltrans documents cited in the
[site design record](../i405_ablation.md#metering-logic-simulated); the threshold and
rate values for the Ventura ramp are unpublished and are assumptions there.

## Proposed project safeguards

These are design candidates, not claims about the original ALINEA law:

1. Bound rates by $r_{\min}\le r_t\le r_{\max}$. If justified, add a slew bound
   $|r_{t+1}-r_t|\le\dot r_{\max}\Delta_c$, where $\dot r_{\max}$ is veh/s².
   Project onto the feasible interval only after resolving the override policy.
2. Use an estimated storage margin and a declared threshold to request a queue
   override. Decide whether it supersedes slew limiting; it cannot supersede
   physical receiving or actuator constraints. Log which bound was active.
3. Separate $h$, $\Delta_o$, and $\Delta_c$; record measurement window,
   availability time, processing delay, decision time, and application time. Hold
   commands between updates and prevent reuse of a measurement as if it were new.
4. Validate measurement age, quality, lane coverage, and occupancy range. Proposed
   fault behavior is a bounded last-valid-command hold with a declared timeout,
   followed by a predeclared fixed-rate fallback. Values and recovery rules must
   be selected and tested before a run; there is no universal safe fallback rate.
5. Log requested command, applied command, realized flow, override reason, and
   boundary queues. A missing observation is not zero occupancy.

For a rate interpreted as average one-vehicle-per-release service, nominal headway
is $1/r$ seconds when $r>0$. The actuator must still enforce actual red/green
and clearance constraints. Zero rate means no release, not division by zero.

[Caltrans Ramp Metering Operations, April 2025](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/trafficops/202504-ch-215-pt-4-ramp-metering-operations-a11y.pdf)
provides operational context for local traffic-responsive plans and queue handling.
It also cautions that measured metered discharge can be lower than arrival demand.
Site settings and installed equipment still need verification. See
queue conservation and experiment design.

## ALINEA checked against the lecture and the original paper (2026-11-19)

Requested by manpazito. Sources: Lecture 05B, slide 26 (`docs/lectures`), and
Papageorgiou, Hadj-Salem and Blosseville (1991), read in full from an archived copy of
the TRB file linked above. The queue rule is ALINEA/Q (Smaragdis and Papageorgiou 2003);
that paper could not be opened, so its formula is **not verified** here. Model numbers
come from the reference run `20261116T184142_972776Z` (seed 1, all variants and rules,
merge-area detector); they are simulated and uncalibrated.

| Item | Lecture and paper | Implementation (`control/metering.py`, `configs/i405.yaml`) | Verdict |
| --- | --- | --- | --- |
| Control law | `r(k) = r(k−1) + K_R [ô − o_out(k)]` (slide 26; paper Eq. 14) | The same. `r(k−1)` = 0.30 veh/s, `o` = 0.40 and `ô` = 0.34 give 0.21 veh/s by hand and in code | Matches |
| Direction | Occupancy below (above) the set value raises (lowers) the rate | The same | Matches |
| Steady state | `o_out = ô`; a constant disturbance is removed | The rate is unchanged at `o = ô` | Matches |
| `r(k−1)` | The calculated value in normal operation; under a limit or an override, the cars that actually entered (paper, pp. 61–62) | The last applied, bounded command, including the queue rule's value | Matches for limits. Under the override it is the command, not a count of entered cars |
| Measurement | Downstream of the merge area, where congestion caused by the ramp is visible; 40 m past the nose in Paris, 400 m in Amsterdam | A loop on the freeway lane 43.5 m past the gore, 30 m before the end of the acceleration lane | Consistent with Paris. It lies inside the merge area: vehicles that merge in the last 30 m are not seen |
| Sample interval | Any `T`, 10 s to 1 min or more; a 40 s cycle in Paris | A decision every 30 s on the last completed 30 s interval | Consistent |
| Gain | `K_R` = 70 veh/h per percentage point; results insensitive over a wide range, very high values oscillate; deadbeat at `K_R = Q'`, the slope of flow against occupancy | 1.5 veh/s per unit occupancy = 54 veh/h per point. The detector's slope below 15 % occupancy is about 92 veh/h per point | Consistent (`K_R / Q'` about 0.6) |
| Set value | `ô` = the critical occupancy, where flow is at capacity; 29 % in Paris | 0.34. The detector's 5-minute flow peaks at 2,400 veh/h at 23 to 25 % occupancy (19.6 m/s) and is about 1,700 veh/h at 32 to 36 % (15 m/s) | **Does not match** |
| Realization | Any: one by one, platoon, cycle. Lecture slide 20: one or a few vehicles per green | One vehicle per green, lanes alternating | Consistent |
| Limits, override | Rates may be limited; an override keeps the ramp queue off the street (paper); discontinue at `n_max` (lecture, slide 22) | Bounds 480 to 1,800 veh/h; queue rule `r' = (w − ŵ)/T + d`, the larger of the two rates applies | Consistent in kind; the formula itself is unverified |

Findings (candidates):

1. **The set value is about ten points above the detector's critical occupancy.** It was
   carried over from the synthetic demo (0.25 at a point detector) and rescaled for the
   loop length, not read from this detector's flow and occupancy, as this document asks
   above. With `ô` = 0.34 the regulator keeps raising the rate while occupancy climbs
   from 0.24 to 0.34, the range in which the merge passes capacity. Every ALINEA result
   so far, including the driver study and the ramp/mainline mix study, uses 0.34.
2. **The loop is almost never near its set value.** Between 06:00 and 09:00 the measured
   occupancy is within 5 points of 0.34 in 1 to 2 % of the intervals: the detector reads
   free flow (0.10 to 0.16) or the standing queue (0.76), and 0.76 with and without the
   meter on the observed day.
3. **The queue rule decides most commands once the merge is congested.** On the observed
   day 456 of 600 decisions are logged as queue control and the rate reverses direction
   about 68 times an hour (120 decisions an hour): the command alternates between
   ALINEA's low rate and the queue rule's high rate. With about 25 vehicles of storage
   and a queue target of 20 the regulator has roughly 90 seconds of ramp demand to hold.
4. **A logging detail.** When both rates are below the lower bound the command is the
   bound but its `reason` is `queue_control`, so `queue_control_count` overstates how
   often the queue rule overrode ALINEA.

### Set-value check: prediction written before the run

Run: the site scenario with `target_occupancy` 0.24 (the detector's critical occupancy)
and everything else unchanged; ALINEA only; variants `x0.9`, `historical` and
`free_exit_x1`; seeds 1 to 10 (30 runs). Compared, paired by seed, with the identical-driver
runs of the driver study (`results/driver-study/20261119T051703_669425Z`, no meter and
ALINEA at 0.34). A difference counts when its 95 % t interval excludes zero and its mean
is at least 5 minutes of persistent congestion.

Prediction: with `ô` = 0.24 ALINEA's congestion is lower than with 0.34 by a counted
amount at `x0.9` and at `free_exit_x1`; on the observed day (`historical`, limited exit)
the two settings do not differ by a counted amount. Contradicted if neither of the first
two differences counts, if either has the opposite sign, or if the observed day shows a
counted difference. The peak queue held on Ventura Blvd is reported with it, because a
lower set value holds more vehicles on a ramp that stores about 25.

### Set-value check: result (2026-11-19)

Run folder `results/alinea-set-value/20261119T181319_754646Z` (generated, not in Git):
30 runs, vehicles conserved in all, the same arrivals per seed as the driver-study runs.
Mean over seeds 1 to 10 of persistent congestion in minutes; paired differences with
their 95 % intervals.

| Variant | No meter | ALINEA, `ô` = 0.34 | ALINEA, `ô` = 0.24 | 0.24 minus 0.34 | 0.24 minus no meter |
| --- | --- | --- | --- | --- | --- |
| `x0.9` | 59.1 | 35.4 | 35.2 | −0.3 (−7.6 to +7.0) | **−23.9 (−37.5 to −10.4)** |
| `historical` | 206.4 | 203.6 | 204.9 | +1.2 (−2.8 to +5.3) | −1.4 (−5.1 to +2.2) |
| `free_exit_x1` | 171.4 | 147.2 | 140.7 | −6.5 (−13.7 to +0.7) | **−30.8 (−52.8 to −8.7)** |

**The prediction is contradicted.** Neither difference between the two settings counts
at `x0.9` or at the free exit; only the part about the observed day holds. The peak
queue on Ventura Blvd does not differ either (+0.9, −1.5 and −5.5 vehicles, every
interval including zero); time in system per vehicle is 0.14 min lower at the free exit
(−0.27 to −0.01) and unchanged elsewhere. The queue rule is logged in 103 to 460 of the
600 decisions with either setting. In this model the set value hardly matters, for the
reasons in findings 2 and 3: the measured occupancy is almost never near it, and once
the merge is congested the queue rule decides. ALINEA's benefit at `x0.9` and at the
free exit is the same with either setting.

### Fix (D022)

On manpazito's request the set value is now the critical occupancy of the configured
equilibrium curve as the loop sees it: 0.26 for the site (0.2605 computed) and 0.22 for
the demo (0.2205). `tests/test_micro.py` recomputes it for each configuration. The table
above describes the state before the fix. The run at 0.24 is kept as a second point: the
detector's flow is within 1 % of capacity from 23 to 26 % occupancy.
