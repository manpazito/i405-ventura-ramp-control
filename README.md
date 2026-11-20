# Ramp metering at the I-405 southbound Ventura Boulevard on-ramp

A simulation case study of one real on-ramp: I-405 southbound from Ventura Boulevard at
Sepulveda Boulevard, Sherman Oaks, Los Angeles. It compares the metering rules in actual
use (a fixed time-of-day rate, and Caltrans' local traffic-responsive plan with queue
override) and ALINEA with no meter and with each other, on a calibrated microscopic
model, and checks how the effects hold when one condition at a time is changed.

UCLA CEE 281, Fall 2026, individual project (manpazito). Plan:
[study design](docs/study_design.md). Course requirements and their status:
[requirement map](docs/research/scope_and_assumptions.md).

## Quick start

```bash
uv sync --locked          # Python 3.14 and pinned packages; use uv only
uv run pytest             # 103 tests
uv run arm-study --config configs/i405_ablation.yaml --output results/rule-ablation  # main study, ~2 h on 12 cores
```

The PeMS data the code reads are in the repository (see [data/README.md](data/README.md)),
so no PeMS login is needed. Every parameter in [configs/i405.yaml](configs/i405.yaml) is
labeled with its source (`[sketch]`, `[PeMS]`, `[Caltrans]`, `[calibrated]`, `[model]`,
`[assumed]`). Each run folder holds one row per run, paired differences with 95 %
intervals, figures, the configuration and file hashes.

## Contents

| Part | Record | Command |
| --- | --- | --- |
| Data: PeMS station data, screened for observed intervals | [data/README.md](data/README.md) | `uv run arm-pems` (needs a PeMS login) |
| Site: what limits flow at the ramp | [ramp_mainline_mix.md](experiments/ramp_mainline_mix.md#site-characterization-pems-observed) | `uv run python scripts/bottleneck_check.py` |
| Model: IDM, merging, meter, loop detectors, four rules | [site record](docs/i405_ablation.md), [engine](docs/micro_demo.md), [equations](docs/mathematical_model/) | `uv run arm-micro` (engine test scenario) |
| Calibration, checked on held-out days | [calibration.md](experiments/calibration.md) | `uv run python scripts/calibrate_fd.py` |
| Main study: four rules, one-factor changes | [rule_ablation.md](experiments/rule_ablation.md) | see Quick start |
| Ramp and mainline demand scaled separately | [ramp_mainline_mix.md](experiments/ramp_mainline_mix.md) | `uv run arm-ablation --config configs/i405_mix.yaml` |
| Which driver trait matters | [driver_traits.md](experiments/driver_traits.md) | `uv run arm-study --config configs/i405_driver_traits.yaml` |
| Driver populations (before calibration) | [driver_populations.md](experiments/driver_populations.md) | `uv run arm-drivers` |
| Queue estimate and forecast | [estimate_and_forecast.md](experiments/estimate_and_forecast.md) | `uv run python scripts/forecast_check.py` |
| Decisions, dated | [decisions.md](docs/decisions.md) | |

Code: `src/adaptive_ramp_metering/` (`simulation/micro.py` engine, `control/metering.py`
rules, `simulation/ablation.py` site scenario, `simulation/drivers.py` case studies,
`data/pems.py` acquisition), `scripts/`, `tests/`. Every experiment record states its
predictions before its runs.

## Reproduce the mid-report

```bash
uv run python scripts/mid_report_figures.py      # figures, from the tables in docs/mid_report/data/
cd docs/mid_report && latexmk -pdf mid_report.tex
```

The tables come from the commands above: the bottleneck check (Table 5), calibration
step 1 (Table 6), `arm-study --config configs/i405_validation.yaml` then
`scripts/validation_table.py` (Figure 5), `arm-study --config configs/i405_ablation.yaml
--analytic` (Table 7), the main study (Table 8, Figures 7–9; run
`20261119T200447_267513Z`), the mix study (Figure 11, run on the model before
calibration) and the forecast check (Section 3.8). Team number and repository link:
`docs/mid_report/submission.tex`.

## Status and limits

- **Final pathway:** traffic-signal control on the course's intersection (chosen
  2026-11-19), not built yet.
- **Model:** one modeled freeway lane; a downstream boundary taken from observed flow;
  demand is a lower bound once the freeway is congested; this ramp's metering plan is
  unpublished and assumed; the merge rule, `b` and `s0` are not calibrated. Only
  October 2022 has both stations observed.
- Results are simulated what-ifs, not site findings. Passing tests shows the code does
  what its design says, not that the traffic model is valid.
