"""The GEH statistic of the day-by-day validation table."""

import importlib.util

import pytest

spec = importlib.util.spec_from_file_location("table", "scripts/validation_table.py")
table = importlib.util.module_from_spec(spec)
spec.loader.exec_module(table)


def test_geh_is_the_fhwa_formula():
    # sqrt(2 x 100^2 / 2100) for a model of 1,100 veh/h against a count of 1,000.
    assert table.geh(1100, 1000) == pytest.approx(3.086, abs=0.001)
    assert table.geh(1000, 1000) == 0
    assert table.geh(1000, 1100) == table.geh(1100, 1000)  # symmetric
