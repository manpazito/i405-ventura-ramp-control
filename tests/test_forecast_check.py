"""The short-horizon forecasts of the forecast check, on hand-written counts."""

import importlib.util

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("check", "scripts/forecast_check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_forecasts_use_only_earlier_intervals_and_skip_missing_ones():
    table = check.forecasts(np.array([2.0, 4.0, np.nan, 6.0, 8.0]))
    # The first interval has nothing before it; the fourth follows a missing report.
    assert np.isnan(table["last_value"][0]) and np.isnan(table["moving_average"][0])
    assert table["last_value"].tolist()[1:] == [2.0, 4.0, 4.0, 6.0]
    assert table["moving_average"].tolist()[1:] == [2.0, 3.0, 3.0, 4.0]
    # Errors are scored where the true count is known: |2-4|, |4-6|, |6-8| and |2-4|, |3-6|, |4-8|.
    rows = np.array([False, True, True, True, True])
    assert check.mean_absolute_error(table, "last_value", rows) == pytest.approx(2.0)
    assert check.mean_absolute_error(table, "moving_average", rows) == pytest.approx(
        3.0
    )
