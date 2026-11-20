# Ramp and mainline demand mix on the I-405 SB Ventura on-ramp scenario

Specification written 2026-11-19, **before any run of this study** (D021). The design
and the five predictions were agreed with manpazito in a question-and-answer session on
2026-11-18 and 2026-11-19 and signed off on 2026-11-19; they have not been edited since. Results and interpretation are
added underneath after the run. Simulated and uncalibrated, like every simulation result
in this repository; the site characterization below is observed PeMS data.

## Question

The first ablation multiplies ramp demand and mainline demand by one factor, so it
cannot say which of the two matters. manpazito's starting point: congestion at the ramp
seems to come from a congested mainline that does not let ramp traffic in.

1. When the freeway can pass only a fixed flow, who gets it: how do ramp exits change as
   the traffic in the lane next to the ramp rises?
2. Can a metering rule change that split?
3. Where does a meter reduce congestion at all?

## Site characterization (PeMS, observed)

`uv run python scripts/bottleneck_check.py` on the eight October 2022 weekdays on which
mainline station 717816 is fully observed. Lane-level data, observed lanes only; it is
the lane-level redo of the station-level `scripts/downstream_check.py` on the
`mid-report` branch. The
project's congestion line is 20 m/s (44.7 mph). Stations downstream of the merge:
Woodcrest 764754 (0.95 mi) and Royal Ridge 717807 (1.52 mi).

| Day (Oct 2022) | 3 | 10 | 11 | 12 | 14 | 24 | 25 | 28 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Onset, Burbank 1 (0.9 mi upstream) | 06:00 | 06:00 | 06:00 | 06:00 | 06:05 | 06:00 | 06:05 | 06:05 |
| Onset, Ventura | 06:00 | 06:10 | 06:05 | 06:00 | 06:10 | 06:00 | 06:05 | 06:20 |
| Onset, Woodcrest (lanes observed of 6) | 06:00 (3) | 06:05 (1) | 06:10 (2) | 06:05 (4) | 06:10 (3) | 06:10 (2) | 06:20 (3) | 06:30 (4) |
| Onset, Royal Ridge (lanes observed of 5) | 06:05 (3) | 06:05 (3) | 06:10 (3) | 06:10 (4) | 06:25 (4) | 06:15 (3) | 06:20 (4) | 06:15 (3) |
| Intervals of 48 meeting the bottleneck criteria, Ventura to Woodcrest / Royal Ridge | 0 / 0 | 0 / 2 | 0 / 4 | 0 / 1 | 0 / 0 | 3 / 0 | 0 / 4 | 0 / 1 |
| Ventura mainline, 07:00–08:55 (veh/h; mph) | 4,960; 13.3 | 5,112; 14.1 | 5,153; 13.7 | 5,345; 14.7 | 5,839; 17.6 | 5,231; 13.9 | 5,065; 13.1 | 6,137; 20.9 |
| Royal Ridge, 07:00–08:55 (mph) | 24.8 | 27.8 | 28.2 | 29.3 | 28.6 | 27.0 | 29.3 | 30.4 |
| Shoulder lane at Ventura (veh/h) | 873 | 936 | 882 | 915 | 1,046 | 918 | 880 | 1,121 |
| Ramp 716744 (veh/h) | 751 | 682 | 807 | 889 | 728 | 826 | 821 | 689 |
| Ramp per shoulder-lane vehicle | 0.86 | 0.73 | 0.91 | 0.97 | 0.70 | 0.90 | 0.93 | 0.61 |
| North of 101: reported / implied speed (mph) | 50 / 18 | 50 / 18 | 50 / 19 | 50 / 19 | 50 / 21 | 50 / 19 | 50 / 18 | 50 / 22 |
| Shockwave between pre-onset and peak state at Ventura (mph) | −16.2 | −16.1 | −14.7 | −16.0 | −14.0 | −14.9 | −16.5 | −13.6 |

Onset is the first of three consecutive 5-minute intervals below 20 m/s. The bottleneck
test is that of Chen, Skabardonis and Varaiya (2004): upstream speed below 40 mph and at
least 20 mph below the downstream speed, in 5 of 7 consecutive intervals, between
06:00 and 09:55. It is met on none of the eight days. The few intervals that meet the
speed criteria all fall between 06:55 and 09:25, none during onset. The shockwave speed
is the lecture formula (q_A − q_B) / (k_A − k_B) with densities from flow over reported
speed.

What this supports, and what it does not:

- **Peak, from about 06:30 to 10:00: the merge is inside a queue.** Both stations
  downstream are below the congestion line on all eight days and no active bottleneck
  is found between the merge and Royal Ridge. The head of the queue is at or beyond
  Royal Ridge.
- **Onset, 06:00 to 06:25: the data do not show the congestion arriving from
  downstream.** A queue growing back at 14 to 16 mph would reach Royal Ridge about six
  minutes, one interval, before Ventura. Royal Ridge crosses the line before Ventura on
  2 days and after it on 6 (by 5 to 15 minutes); Burbank 1, upstream, is first or tied
  on every day. Speeds fall together over the section and a gap of about 5 mph decides
  the order. Breakdown at or upstream of the merge at onset is not excluded.
- **The ramp is not shut out during the peak.** It passes 680 to 890 veh/h, 61 to 97 %
  of what the shoulder lane carries, on every day.
- **Not located:** the head of the queue. Every mainline station from Skirball/Mulholland
  to National (Abs PM 60.3 to 52.9) is 0 % observed in October 2022, a gap of about
  14 km where Lecture 05B (slide 4) asks for detectors no more than 3 km apart.

Limits: Woodcrest and Royal Ridge are partly imputed by PeMS (lanes observed are in the
table); reported speeds are station estimates, so an order read at a fixed speed line
depends on them; the shoulder-lane comparison assumes that PeMS lane 5 is the shoulder
side (lane 1 is the fastest in free flow, 76.5 mph, lane 5 the slowest, 64.8 mph) and
that station 717816 sits upstream of the gore; the ramp was metered at unknown rates;
the reported speed of station 777066 (North of 101) contradicts its own flow and
occupancy and is not used. A count of the ramp queue on site is planned for 2026-11-20.

## Baseline and changed factor

Baseline: the site scenario of `configs/i405.yaml` (observed day 2022-10-11, identical
drivers, four metering rules). Changed factors, set per cell in `configs/i405_mix.yaml`:

- **Ramp demand:** 0.75, 1 and 1.25 times the observed ramp flow.
- **Mainline level,** the through traffic in the one modeled freeway lane: 0.75, 1 and
  1.25 times the site's lane-balance profile, and the shoulder lane as observed (PeMS
  lane 5 of station 717816). Lane balance assumes that shoulder-lane drivers move left
  as needed (about 500 veh/h of through traffic while the exit is limited); the observed
  shoulder lane is the upper bound in which none does (about 1,020 veh/h). Reality lies
  between the two and a one-lane model cannot say where.
- **Exit:** limited to the observed flow in the intervals PeMS shows as congested (the
  site's boundary), or free.

Geometry, detectors, controllers, the congestion definition (D016) and the exit
boundary are those of the site scenario and are not rescaled. Cells with equal ramp and
mainline factors repeat existing variants and must reproduce them for seeds 1 to 3:
`lim_r0.75_m0.75` = `x0.75`, `lim_r1_m1` = `historical`, `lim_r1.25_m1.25` = `x1.25`,
`free_r1_m1` = `free_exit_x1`, `free_r1.25_m1.25` = `free_exit_x1.25`.

## Design

- Cells: 3 ramp levels × 4 mainline levels × 2 exits = 24.
- Controllers: no meter, fixed rate, Caltrans local responsive plan, ALINEA with queue
  control.
- Seeds 1 to 10. Runs: 24 × 4 × 10 = 960, five simulated hours each (05:00–10:00).
- Commands: `uv run arm-ablation --config configs/i405_mix.yaml --analytic` (the
  before-run table, no simulation) and
  `uv run arm-ablation --config configs/i405_mix.yaml --output results/mix-study`.
- Parameters are the current ones (`T` = 1 s, `a` = `b` = 2 m/s², not calibrated). A
  repeat after calibration is a separate run with the occupancy threshold recomputed.

## Metrics and decision rule

- **Ramp exits** and **mainline exits:** vehicles of each origin that left the section
  in the window (`exited_ramp_origin_veh`, and the rest of `exited_veh`).
- **Unserved at 10:00** by origin (`boundary_ramp_veh`, `boundary_mainline_veh`) and the
  peak queue held on Ventura Blvd (`boundary_ramp_max_veh`).
- **Persistent congestion** at the mainline station upstream of the gore
  (`congested_min`, definition D016, unchanged).

All comparisons use means over the 10 seeds and differences paired by seed. A
difference **counts** when the 95 % t interval of the paired differences excludes zero
**and** its mean reaches 5 minutes of congestion or 2 % of the unmetered ramp exits of
the cell. Arrivals of both origins are drawn from one random stream, so cells with
different mainline levels do not share their ramp arrivals; cell contrasts are paired
by seed, not by vehicle. With 24 cells and three rules there are many intervals; a
counted difference in one cell only is a candidate, not a result.

Outputs: `mix_cells.csv` (means per cell and rule), `mix_effects.csv` (each rule minus
no meter), `mix_contrasts.csv` (cell minus cell), `analytic.csv`.

## Before any run: what the course formulas give

**Capacity.** The peak of the IDM equilibrium flow for the configured parameters is
2,420 veh/h per lane at 17.6 m/s (headway 1.49 s), the static capacity of Lecture 05B
(slide 28). The same curve gives the 26.0 % critical occupancy of D016 for the 1.83 m
loop, and `discharge_speed` uses its peak to decide whether the exit restricts. `a` and
`b` do not enter it; `T` does: with `T` = 1.3 s it would be 1,990 veh/h and 22.3 %, and
the 1× mainline level, which peaks at 2,009 veh/h, would already be at capacity.

**Exit.** The exit is limited in 47 of the 60 intervals, from 06:05 on, to 948 to
1,829 veh/h (5,167 vehicles in all). It never reaches 2,420 veh/h, so the boundary
always restricts in those intervals. The modeled merge passes about 1,290 veh/h after
breakdown (the figure of the ablation record, set by `a`, not re-measured here). In the
first hour the exit allows more than that, so there the merge is the limit, not the
exit.

**Per cell,** from `--analytic` (5-minute steps). Peak demand is ramp plus through
traffic. The deterministic queue of Lecture 03 uses the exit allowance as its service
rate where the exit is limited and the static capacity elsewhere. The capping strategy
of Lecture 05B (slides 22 and 23) admits `max(0, Q_c − Q_in)` from the ramp and is
discontinued when its queue reaches `n_max`, here the 24.6 vehicles of storage upstream
of the stop line.

| Limited-exit cell (ramp, mainline) | Peak demand (veh/h) | 5-min intervals above 2,420 | D/D/1 unserved at 10:00 (veh) | Minutes the cap holds vehicles before the storage is full | Storage full at |
| --- | --- | --- | --- | --- | --- |
| 0.75, 0.75 | 1,507 | 0 | 0 | 0 | never |
| 0.75, 1 | 1,970 | 0 | 0 | 0 | never |
| 0.75, 1.25 | 2,433 | 1 | 4 | 12.1 | 06:11 |
| 0.75, shoulder lane | 2,088 | 0 | 1,257 | 5.7 | 06:15 |
| 1, 0.75 | 1,546 | 0 | 0 | 0 | never |
| 1, 1 (observed day) | 2,009 | 0 | 0 | 0 | never |
| 1, 1.25 | 2,472 | 1 | 492 | 12.9 | 06:09 |
| 1, shoulder lane | 2,292 | 0 | 2,051 | 3.9 | 06:13 |
| 1.25, 0.75 | 1,748 | 0 | 356 | 23.9 | 06:43 |
| 1.25, 1 | 2,048 | 0 | 800 | 12.8 | 06:17 |
| 1.25, 1.25 | 2,511 | 1 | 1,292 | 15.3 | 06:08 |
| 1.25, shoulder lane | 2,547 | 6 | 2,844 | 3.0 | 06:12 |

- The 1.25× mainline level exceeds the static capacity in one interval, at 05:40 before
  onset (2,433 to 2,511 veh/h). It is kept because it repeats the existing `x1.25`
  variant. The shoulder-lane level with 1.25× ramp demand exceeds it in six intervals
  from 06:25.
- With a free exit the deterministic queue is empty at 10:00 in all 12 cells: the static
  capacity is never exceeded for long. Any queue the simulation leaves there comes from
  the lower dynamic capacity of the merge, the capacity drop of Lecture 05B (slide 19).
- By the course's own strategy the cap could hold vehicles for 3 to 24 minutes before it
  must be discontinued, in each of the eight limited-exit cells whose demand exceeds the
  allowance, out of 235 minutes of limited exit. Lecture 05B (slide 25) adds that ramp
  metering is generally deactivated in oversaturated situations.

**Known from existing runs of the repeated cells** (reference run
`20261116T184142_972776Z`, seeds 1 to 3, no meter, limited exit): ramp exits 3,163 of
3,391 requested on the observed day, 2,926 of 3,694 at 1.1× and 2,609 of 4,205 at 1.25×;
mainline exits 3,434 of 3,466, 3,783 of 3,841 and 4,161 of 4,361. No rule changes ramp
exits by more than 1.1 % or total exits by more than 0.5 % on average in those cells.
With 20 seeds (driver study, identical drivers) ALINEA reduces congestion by 20.7 min
(±6.3) at 0.9×, by 26.7 min (±12.0) at the free exit and by 5.9 min (±11.6, includes
zero) on the observed day, and adds 17 vehicles (±6, 0.25 %) to total exits there.

## Predictions

1. **Displacement.** Limited exit, ramp 1×, no meter: raising the mainline from 1× to
   1.25× adds 492 through vehicles while the exit is limited, and ramp exits fall by
   350 to 650. Reason: in the existing cells the mainline is served almost in full and
   the ramp gives way; one for one would be 492.
2. **Sharing at the bound.** At the shoulder-lane level (ramp 1×, limited exit, no
   meter) ramp exits are between 2,300 and 3,000 and the mainline ends with more than
   1,000 unserved. Reason: once both approaches are queued, queued merges share at a
   near-fixed ratio close to the lane ratio, here 1:1 (Cassidy and Ahn 2005; Bar-Gera
   and Ahn 2010); in the existing `x1.25` cell the two origins split the limited-period
   output about 51:49 (estimated from whole-window counts). A 1:1 split of that output
   plus the 182 ramp vehicles served before onset is about 2,530 to 2,770.
3. **Fixed ratio.** At that level, raising ramp demand from 1× to 1.25× does not raise
   ramp exits by 2 % or more: the extra vehicles wait on Ventura Blvd.
4. **The meter and the split.** In no limited-exit cell does a rule change ramp exits by
   2 % or more. That includes the shoulder-lane level, where the Caltrans plan sees a
   congested mainline and asks for its minimum rate, and queue override hands it back.
5. **Where a meter cuts congestion.** ALINEA's reduction counts in more than half the
   cells where the unmetered run is congested for 30 to 200 minutes, and no rule's
   reduction counts in a cell above 240 minutes.

Check, not a prediction: total exits stay within 2 % across the rules in every
limited-exit cell. Under that exit the output is set by the boundary and by the merge,
so this is an input of the model, backed by Gomes et al. (2008), not a finding.

## What would contradict them

1. A mean paired difference in ramp exits between `lim_r1_m1.25` and `lim_r1_m1`
   outside −650 to −350. Less than 350 means the ramp holds its place.
2. Mean ramp exits of `lim_r1_mlane5` outside 2,300 to 3,000, or 1,000 or fewer mainline
   vehicles unserved. Below 2,000 means the mainline has priority, as the course's
   gap-acceptance model has it for a flowing stream; above 3,000 means the ramp has.
3. A counted increase of 2 % or more in ramp exits from `lim_r1_mlane5` to
   `lim_r1.25_mlane5`.
4. A counted change of 2 % or more in ramp exits for any rule in any of the 12
   limited-exit cells (36 comparisons; a single one is a candidate to confirm with new
   seeds).
5. ALINEA's reduction counted in half or fewer of the cells with 30 to 200 unmetered
   minutes, or any rule's reduction counted in a cell above 240 minutes. If no cell
   falls between 30 and 200 minutes the first half cannot be tested.

## Amendment of 2026-11-19, before any result was read

manpazito asked for ALINEA to be checked against the lecture material and then for its
set value to be the critical occupancy (D022). `target_occupancy` in the site
configuration changed from 0.34 to 0.26. The first run of this study had been going for
23 minutes with 0.34; it was stopped, nothing of it was read and its folder was empty.
The study is run with 0.26. The predictions above are unchanged. The numbers quoted
above from earlier ALINEA runs were obtained with 0.34; a test of 30 runs (seeds 1 to 10,
0.24 against 0.34) found no counted difference in congestion in any of three cells, so
they are kept as the reference for predictions 4 and 5.

## Checked against the course lectures

Lecture slides in `docs/lectures` (CEE 181/281, J. Ma), read on 2026-11-19.

| Course statement | Where | Bearing on this study |
| --- | --- | --- |
| A jam needs high load, a bottleneck and a perturbation; bottlenecks include on-ramps and uphill gradients | 05B, slides 3–5 and 10 | The Sepulveda Pass grade south of the ramp is a bottleneck type of its own; the merge is another |
| Detectors no more than 3 km apart, upstream and downstream of bottlenecks | 05B, slide 4 | Met between Ventura, Woodcrest and Royal Ridge; not met beyond Royal Ridge, so the head of the queue is not located |
| Shockwave speed = change of flow over change of density | 03 | −14 to −16 mph at Ventura: about 6 minutes from Royal Ridge, below what 5-minute data resolve; the onset order does not show a queue arriving from downstream |
| Capacity is the maximum flow, at the critical density; demand is what wants to pass | 03 | 2,420 veh/h at 17.6 m/s; observed flow is a lower bound on demand once the freeway is congested |
| Static capacity is set by the time headway `T`; the dynamic capacity after breakdown is lower (capacity drop) | 05B, slides 19 and 28 | The modeled merge passes about 1,290 veh/h after breakdown, 47 % below its static capacity; field studies report 5 to 15 %. A limit of the model, tied to `a` |
| Ramp metering works by preventing a breakdown and its capacity drop | 05B, slides 12 and 19 | Inside a queue from downstream there is no breakdown at this merge to prevent; the question becomes the split |
| Capping strategy `Q_rmp = max(0, Q_c − Q_in)`, discontinued when the ramp queue reaches `n_max` | 05B, slides 22–23 | Computed per cell above. The Caltrans plan with queue override is its nearest implemented relative; the capping strategy itself is not implemented |
| Metering is generally deactivated in oversaturated situations | 05B, slide 25 | Consistent with queue override and with prediction 4 |
| One or a few vehicles per green, to avoid artificial flow peaks | 05B, slide 20 | The model releases one vehicle per green, lanes alternating |
| ALINEA: `r(k) = r(k−1) + K_R [ô − o_out(k)]` | 05B, slide 26 | Same form as implemented, and the same as Eq. 14 of Papageorgiou et al. (1991). The paper sets `ô` at the critical occupancy; the configured 0.34 was about ten points above it and is 0.26 since D022 (row corrected 2026-11-19; it first said the target had been set from the detector's readings) |
| Total travel time = vehicles in the network integrated over time | 05B, slides 24 and 35 | `total_time_veh_s`, which includes vehicles waiting outside |
| A ramp vehicle merges into a gap at least as long as its critical gap; at 1,800 veh/h and 3.5 s about 312 such gaps an hour | 03, slides 62–71 | Backs the starting intuition for a flowing mainline: more through traffic, fewer gaps. By the same formula 306 gaps an hour at the 05:40 through flow (1,853 veh/h) and 377 at 06:00–06:30 (1,117 veh/h), against ramp demands of 156 and 618 veh/h. Direction only: long gaps admit several vehicles and the model has no fixed critical gap |
| Poisson arrivals are realistic in light traffic only | 03 | The model draws Poisson arrivals up to capacity and holds vehicles at the boundary until a gap exists. A known limit, unchanged here |
| Deterministic D/D/1 queue: arrivals minus departures | 03 | The unserved column above, and the 1 / multiplier check of the first ablation |
| Space-mean speed is the relevant one and never exceeds the time-mean speed | 02, slides 28–31 | D016 tests the arithmetic mean of crossing speeds. At the mainline station the flow/occupancy speed is within 0.2 to 0.4 % of it and changes congested minutes by 0 to 8.5 in the reference run. Not material; D016 is left as it is |
| Ramp metering issues: mainline versus ramp performance; Minnesota study, 9 % more throughput | 05A, slides 38–39 | The split by origin is this study's metric. The Minnesota gain comes from preventing breakdowns across a network, not from a single ramp inside a queue |

## Limits known before the run

- One freeway lane. The two mainline anchors are bounds; where reality sits between them
  is not known. At the shoulder-lane level demand exceeds the exit allowance by
  construction, because the allowance is the lane-average flow.
- Station 717816 is assumed to sit upstream of the gore. If it is downstream, the
  shoulder-lane flow already contains ramp vehicles and the upper bound is too high.
- Counts are for the whole window, not for the limited-exit hours alone.
- The merge's dynamic capacity (about 1,290 veh/h) follows the uncalibrated `a` and is
  far below the static capacity. In the first hour it, not the exit, limits the output.
- The static capacity and the 26 % threshold follow the uncalibrated `T`.
- Identical drivers; the driver populations of D019 are not crossed with these cells.
- One observed day and 10 seeds.
- Not done: a per-vehicle comparison of ramp and mainline demand under the free exit.
  The two demand profiles peak at different times (through traffic at 05:40, the ramp
  from 06:30 to 09:00), so no constant factor removes like for like, and a 25 % cut is
  likely to reach the floor. It needs constant synthetic demand.
- No figure is produced for the cells yet; the tables are the record.

## Sources

- Lecture slides 02, 03, 05A and 05B of CEE 181/281 (`docs/lectures`), read 2026-11-19.
- Chen, Skabardonis and Varaiya (2004), Systematic identification of freeway
  bottlenecks, Transportation Research Record 1867. <https://doi.org/10.3141/1867-06>
- Cassidy and Ahn (2005), Driver turn-taking behavior in congested freeway merges,
  Transportation Research Record 1934. <https://doi.org/10.3141/1934-15>
- Bar-Gera and Ahn (2010), Empirical macroscopic evaluation of freeway merge-ratios,
  Transportation Research Part C 18(4). <https://doi.org/10.1016/j.trc.2009.09.002>
- Gomes, Horowitz, Kurzhanskiy, Varaiya and Kwon (2008), Behavior of the cell
  transmission model and effectiveness of ramp metering, Transportation Research
  Part C 16(4). <https://doi.org/10.1016/j.trc.2007.10.005>

Gomes et al. was read in full during the web research of 2026-11-18; the other three
were checked from abstracts or index records only. Re-open each before it is cited in
the paper.

## Results of the run

Run folder `results/mix-study/20261119T182607_517036Z` (generated, not in Git): 960 runs,
command as specified, on the model before calibration (`T` = 1 s, `delta` = 4) with
ALINEA's set value at 0.26 (amendment above); 10:26 to 11:51 PST on 11 processes. The
code that ran is commit `53ead2b` of the development history, which is not in this
repository (`git_revision` in `run.json`); the file hashes in
`run.json` were taken at the end of the run, after later edits to the working tree, and
do not match that commit. Every table below comes from the CSV files of the folder.

**Integrity.** Vehicles are conserved in all 960 runs. Overlap steps occur in 55 runs
(95 steps in all, at most 5 in a run), under every rule including no meter; they are the
cut-ins already recorded for the engine (D017). The three unchanged rules reproduce the
reference run exactly in the five repeated cells for seeds 1 to 3 (45 of 45 rows, all
27 columns); ALINEA's rows differ because its set value changed (D022).

### Who gets through (no meter, limited exit, means over 10 seeds)

| Ramp | Mainline | Ramp exits | Mainline exits | Ramp unserved at 10:00 | Mainline unserved | Peak queue on Ventura Blvd | Congested (min) | D/D/1 unserved (before the run) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.75 | 3,369 | 2,579 | 0 | 0 | 19 | 52 | 0 |
| 1 | 1 (observed day) | 3,150 | 3,425 | 148 | 2 | 189 | 206 | 0 |
| 1 | 1.25 | 2,614 | 4,223 | 681 | 70 | 697 | 254 | 492 |
| 1 | shoulder lane | 2,561 | 3,503 | 739 | 1,461 | 753 | 234 | 2,051 |
| 0.75 | 1 | 2,517 | 3,452 | 0 | 0 | 2 | 32 | 0 |
| 0.75 | shoulder lane | 2,477 | 3,578 | 1 | 1,403 | 36 | 229 | 1,257 |
| 1.25 | 1 | 3,130 | 3,423 | 1,004 | 4 | 1,008 | 218 | 800 |
| 1.25 | shoulder lane | 2,626 | 3,438 | 1,535 | 1,524 | 1,539 | 240 | 2,844 |

With a free exit the deterministic queue predicted nothing left at 10:00 in any cell;
the simulation leaves from 0 to 2,837 vehicles, 8 on the observed day. That difference
is what the merge's lower dynamic capacity costs.

### The predictions

| Prediction | Verdict | Result |
| --- | --- | --- |
| 1. Displacement | **Supported** | Raising the mainline from 1× to 1.25× lowers ramp exits by 536 (505 to 567), inside 350 to 650 and close to the 492 through vehicles added while the exit is limited. Mainline exits rise by 798; 70 mainline vehicles are left at 10:00 |
| 2. Sharing at the bound | **Supported** | At the shoulder-lane level the ramp gets 2,561 exits (2,533 to 2,592 over the seeds), inside 2,300 to 3,000, and 1,461 mainline vehicles are left. Neither side has priority |
| 3. Fixed ratio | **Contradicted, narrowly** | Raising ramp demand from 1× to 1.25× at that level raises ramp exits by 64 (58 to 71), 2.5 % against a line of 2 %. The mainline loses 65. The other 780 extra ramp vehicles wait on Ventura Blvd (739 to 1,535 unserved). More demand buys the ramp a little, so the ratio is not quite fixed |
| 4. The meter and the split | **Supported** | No rule changes ramp exits by 2 % or more in any of the 36 comparisons; the largest change is −1.35 % (the fixed rate with 1.25× ramp and 0.75× mainline demand). The Caltrans plan's queue override acts in 434 to 451 of 600 decisions in the congested cells |
| 5. Where a meter cuts congestion | **Supported** | ALINEA's reduction counts in 6 of the 8 cells with 30 to 200 unmetered minutes (6 to 31 minutes less) and no rule's reduction counts in the 5 cells above 240 minutes |
| Check: total exits | Holds | Within 0.8 % across the rules in every limited-exit cell |

### What the run adds

- **The starting intuition holds in the model below the half share.** While the freeway
  lane's demand is under about half of what the merge passes, each added mainline
  vehicle takes one ramp vehicle's place. This is the gap-acceptance picture of
  Lecture 03.
- **At the upper bound the two sides share.** With the shoulder lane as observed, both
  approaches are queued and the ramp keeps about 42 % of all exits in the window. The
  course lists the zipper merging rule among local regulations (Lecture 05B, slide 33);
  the model produces something close to it without being told to.
- **A fixed rate with no override moves the queue to the street.** Where ramp demand
  exceeds the fixed rate (1.25× ramp), it lowers freeway congestion by 66 minutes
  (limited exit, 0.75× mainline) and by 103 minutes (free exit), but raises the peak
  queue on Ventura Blvd by 91 and 283 vehicles and time in the system per vehicle by 0.8
  and 3.5 minutes. The Caltrans plan and ALINEA, which both give way to the ramp queue,
  do neither. This is the spillover of Lecture 05B (slide 21).
- **On the observed day** ALINEA lowers the peak street queue by 14 vehicles (7 to 21)
  and time per vehicle by 0.5 minute (0.3 to 0.7); congestion does not change.

Limits specific to this run: the model was not calibrated (the calibrated repeat of the
ramp and mainline factors is part of the [rule ablation](rule_ablation.md)); the
shoulder-lane level is a bound, not an estimate; counts are for the whole window.
