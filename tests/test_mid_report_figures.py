"""Helpers of the mid-report figures: row labels and the decision rule (no plotting)."""

import importlib.util

import pytest

spec = importlib.util.spec_from_file_location(
    "mid_report_figures", "scripts/mid_report_figures.py"
)
figures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(figures)


@pytest.mark.parametrize(
    ("case", "label"),
    [
        ({"id": "baseline"}, "Baseline (observed day)"),
        ({"id": "x", "variant": {"kind": "scale", "factor": 0.9}}, "All demand × 0.9"),
        (
            {
                "id": "x",
                "variant": {"kind": "scale", "factor": 1.0, "ramp_factor": 1.25},
            },
            "Ramp demand × 1.25",
        ),
        (
            {"id": "x", "variant": {"kind": "scale", "factor": 1.0, "free_exit": True}},
            "Free exit",
        ),
        (
            {"id": "x", "variant": {"kind": "sine", "amplitude": 0.5, "period_s": 600}},
            "Demand wave, 10 min",
        ),
        ({"id": "x", "set": {"micro.vehicle.idm.time_gap_s": 1.21}}, "$T$ = 1.21 s"),
        ({"id": "x", "set": {"micro.vehicle.idm.delta": 4}}, r"$\delta$ = 4"),
    ],
)
def test_case_label_states_what_the_case_changes(case, label):
    assert figures.case_label(case) == label


def test_every_plotted_case_of_the_record_has_its_own_label():
    _, labels = figures.study()
    plotted = [member for _, members in figures.GROUPS for member in members]
    assert sorted(labels) == sorted(plotted)
    assert len(set(labels.values())) == len(plotted)


def test_a_difference_counts_only_past_zero_and_past_the_smallest_difference():
    assert figures.counted("congested_min", -6.0, -9.0, -3.0, 5)
    assert not figures.counted("congested_min", -4.8, -8.2, -1.5, 5)  # below 5 minutes
    assert not figures.counted(
        "congested_min", -6.3, -14.3, 1.6, 5
    )  # interval holds zero
    assert figures.counted("time_per_veh_min", 0.08, 0.03, 0.12, 5)  # interval alone
    assert not figures.counted("time_per_veh_min", -0.05, -0.53, 0.43, 5)


def test_rows_leave_out_skipped_cases_and_empty_groups():
    cases, heads = figures.rows(skip=("baseline", "detector_fault"))
    assert "baseline" not in [c for _, c in cases]
    assert [title for _, title in heads] == ["Demand", "Car following", "Drivers"]
    assert all(a[0] > b[0] for a, b in zip(cases, cases[1:]))  # from the top down
