# Ramp metering at the I-405 southbound Ventura Boulevard on-ramp

A simulation case study of one real on-ramp: I-405 southbound from Ventura Boulevard at
Sepulveda Boulevard, Sherman Oaks, Los Angeles. It asks what the metering rules in
actual use (a fixed time-of-day rate, and Caltrans' local traffic-responsive plan with
queue override) and ALINEA do at this ramp, compared with no meter and with each other,
and how those effects hold when one condition at a time is changed.

UCLA CEE 281, Traffic Engineering Systems: Operations and Control, Fall 2026. An
individual project (manpazito). The project began as predictive control with a
forecasting component; that component was dropped on 2026-11-18.

**Read first:** [the study design](docs/study_design.md). **Course requirements and
what is still missing:** [the requirement map](docs/research/scope_and_assumptions.md).

## Run the main study

```bash
uv sync --locked
uv run arm-pems scan --dates 2022-10-11          # once; needs a PeMS session
uv run arm-study --config configs/i405_ablation.yaml --output results/rule-ablation
```

- **Dependencies:** Python 3.14 and the packages of `pyproject.toml`, pinned in
  `uv.lock` (NumPy, pandas, SciPy, Matplotlib, PyYAML, Plotly, pems-data, and Eclipse
  SUMO, which no result here uses; pytest and Ruff for development). Use `uv` only.
- **Inputs:** one observed weekday of PeMS 5-minute data for the ramp (station 716744)
  and the mainline (station 717816), Tuesday 2022-10-11, 05:00 to 10:00; the ramp
  geometry measured from the project's sketch; the parameters of
  [configs/i405.yaml](configs/i405.yaml), each labeled with where it comes from
  (`[sketch]`, `[PeMS]`, `[Caltrans]`, `[calibrated]`, `[model]`, `[assumed]`).
- **What it does:** runs the calibrated baseline and every one-factor change of
  [configs/i405_ablation.yaml](configs/i405_ablation.yaml) under four metering rules
  and ten seeds.
- **Outputs** in `results/rule-ablation/<timestamp>/`: `evaluation.csv` (one row per
  run), `differences.csv` (each case minus the baseline), `controller_effect.csv` (each
  rule minus no meter), `rule_differences.csv` (one rule minus another), three figures,
  the configuration and `run.json` with file hashes. Differences are paired by seed and
  carry 95 % intervals.
- **Record:** [experiments/rule_ablation.md](experiments/rule_ablation.md), with the
  predictions written before the run.
- **Known limits:** one modeled freeway lane; a downstream boundary taken from the
  observed flow; demand that is a lower bound once the freeway is congested; an assumed
  metering plan, because this ramp's own plan is unpublished; the merge rule, the
  comfortable deceleration and the standstill gap not calibrated. Results are simulated
  what-ifs, not site findings.

## What the project consists of

| Step | What | Where | Command |
| --- | --- | --- | --- |
| Data | PeMS District 7 station data, screened for observed (not imputed) intervals | [data/README.md](data/README.md) | `uv run arm-pems` |
| Site | What limits flow at the ramp in the morning peak | [experiments/ramp_mainline_mix.md](experiments/ramp_mainline_mix.md#site-characterization-pems-observed) | `uv run python scripts/bottleneck_check.py` |
| Model | IDM car following, mandatory merging, a one-vehicle-per-green meter, loop detectors, four metering rules | [docs/i405_ablation.md](docs/i405_ablation.md), [docs/mathematical_model/](docs/mathematical_model/) | |
| Calibration | The parameters loop data can identify, checked on days not used | [experiments/calibration.md](experiments/calibration.md) | `uv run python scripts/calibrate_fd.py` |
| Main study | The four rules at the calibrated baseline and under one-factor changes | [experiments/rule_ablation.md](experiments/rule_ablation.md) | `uv run arm-study --config configs/i405_ablation.yaml` |
| Supporting studies | Ramp and mainline demand scaled separately | [experiments/ramp_mainline_mix.md](experiments/ramp_mainline_mix.md) | `uv run arm-ablation --config configs/i405_mix.yaml` |
| | Driver populations (model before calibration) | [experiments/driver_populations.md](experiments/driver_populations.md) | `uv run arm-drivers` |
| | Which driver trait matters (calibrated) | [experiments/driver_traits.md](experiments/driver_traits.md) | `uv run arm-study --config configs/i405_driver_traits.yaml` |
| | The first demand ablation, on the uncalibrated model (mid-report) | [docs/i405_ablation.md](docs/i405_ablation.md) | `uv run arm-ablation` |
| Decisions | Every research decision, dated, with what would reopen it | [docs/decisions.md](docs/decisions.md) | |

Code: `src/adaptive_ramp_metering/simulation/micro.py` (engine),
`control/metering.py` (rules), `simulation/ablation.py` (site scenario and demand
variants), `simulation/drivers.py` (case studies), `data/pems.py` (acquisition).
Tests: `tests/`.

### The engine's own test scenario

`uv run arm-micro` runs the engine on a synthetic ramp (`configs/micro.yaml`); the
engine's equations, rules and checks are in [docs/micro_demo.md](docs/micro_demo.md).

## Course requirements

The course guide asks for a shared foundation (simulation, observation and estimation,
a basic closed-loop TMC with ramp metering), one final pathway, and for CEE 281
calibration or validation evidence and a focused study. The
[requirement map](docs/research/scope_and_assumptions.md) lists each item, its evidence
and its status. Two items are not met:

- **The final pathway.** The guide requires a CAV controller or a traffic-signal
  controller on the course's supplied intersection, "not only this common TMC".
  The project takes traffic-signal control (chosen 2026-11-19); it is not built yet.
- **Versioned code.** The branch `main` has no commit and the repository has no remote.

The observation component is met only in a minimal form: the queue estimate and the
one-interval forecast that the meter already uses are scored against simulator truth
([record](experiments/estimate_and_forecast.md)); no forecasting method was developed.

## Reproduce the mid-report

The CEE C181/C281 mid-report of 2026-11-19 is
[docs/mid_report/mid_report.pdf](docs/mid_report/mid_report.pdf), built from
[docs/mid_report/mid_report.tex](docs/mid_report/mid_report.tex), the figures in
`docs/mid_report/fig/` and the recorded result tables in `docs/mid_report/data/`. From
the repository root:

```bash
uv sync --locked
# Figures 2 to 11 from the recorded tables (seconds). Figures 2, 3, 4, 6 and 10 also read
# the PeMS extracts in data/interim/pems/ and are skipped without them, which leaves the
# committed images in place. Figure 1 is two drawings made from the AutoCAD sketch and
# kept as images.
uv run python scripts/mid_report_figures.py
# the PDF; the team number and the repository link are set in docs/mid_report/submission.tex
cd docs/mid_report && latexmk -pdf mid_report.tex
```

The recorded tables come from these commands (run folders under `results/` are not in
Git; the tables the report uses are copied to `docs/mid_report/data/`):

```bash
# PeMS station files, once (needs a PeMS session)
uv run arm-pems scan --dates 2022-10-03 2022-10-10 2022-10-11 2022-10-12 2022-10-14 2022-10-24 2022-10-25 2022-10-28
# Table 5 and Section 3.1: the bottleneck check on observed lanes
uv run python scripts/bottleneck_check.py
# Table 6: step 1 of the calibration (no simulation)
uv run python scripts/calibrate_fd.py
# Figure 5: step 2 of the calibration, 90 runs, about 10 min on 12 cores
uv run arm-study --config configs/i405_validation.yaml --output results/validation
uv run python scripts/validation_table.py results/validation/<timestamp>
# Table 7: the course formulas for every case (no simulation)
uv run arm-study --config configs/i405_ablation.yaml --analytic
# Table 8 and Figures 7 to 9: the one-factor study, 1,400 runs, about 2 h on 12 cores
uv run arm-study --config configs/i405_ablation.yaml --output results/rule-ablation
# Figure 11: the ramp and mainline mix study, 960 runs, on the model before calibration
# (commit 53ead2b; the same command now runs the calibrated model)
uv run arm-ablation --config configs/i405_mix.yaml --output results/mix-study
# Section 3.8: the queue estimate and the forecast
uv run python scripts/forecast_check.py
```

The report's simulated numbers come from the runs `20261119T200447_267513Z` (one-factor
study), `20261119T195328_824380Z` (validation) and `20261119T182607_517036Z` (mix
study). Figures 6 and 10 are single traced runs that the figure script repeats when
`docs/mid_report/data/traces/` is empty. The mid-report of 2026-11-16, on the model
before calibration, is on the branch `mid-report`.

## Setup and development

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Use **uv only**; it manages `.venv` and Python 3.14. Add a dependency with `uv add`
(`uv add --dev` for a tool) and commit `uv.lock`. Passing the tests shows that the code
does what its design says; it does not establish that the traffic model is valid.

## Data

Bulk data and generated results are ignored by Git; the directory structure and the
documentation are kept. Raw files are never edited. See [data/README.md](data/README.md)
for the conventions, the PeMS pipeline, the quality screening and the site's coverage.
Only October 2022 has both the ramp and the mainline station
observed; the mainline stations through the Sepulveda Pass are not observed at all.
