"""tests/test_lookup_table.py — Unit tests for lookup grid + interpolation logic."""
import numpy as np
import pytest
from qq.lookup_table import _build_lookup_probability_grid, _interpolate_no_extrapolate


class TestBuildLookupProbabilityGrid:

    def test_on_lattice_endpoints_no_duplicates(self):
        grid = _build_lookup_probability_grid(0.01, 0.96, 0.01)
        assert grid[0] == pytest.approx(0.01)
        assert grid[-1] == pytest.approx(0.96)
        assert len(grid) == len(np.unique(np.round(grid, 8)))  # no duplicates

    def test_off_lattice_endpoints_included_exactly(self):
        grid = _build_lookup_probability_grid(0.013, 0.957, 0.01)
        assert grid[0] == pytest.approx(0.013)
        assert grid[-1] == pytest.approx(0.957)
        assert grid[1] == pytest.approx(0.02)
        assert grid[-2] == pytest.approx(0.95)

    def test_empty_when_min_greater_than_max(self):
        grid = _build_lookup_probability_grid(0.9, 0.1, 0.01)
        assert len(grid) == 0

    def test_single_point_when_min_equals_max(self):
        grid = _build_lookup_probability_grid(0.5, 0.5, 0.01)
        assert len(grid) == 1
        assert grid[0] == pytest.approx(0.5)

    def test_monotone_increasing(self):
        grid = _build_lookup_probability_grid(0.02, 0.88, 0.01)
        assert np.all(np.diff(grid) > 0)


class TestInterpolateNoExtrapolate:

    def test_interior_interpolation(self):
        out = _interpolate_no_extrapolate(
            np.array([0.5]), np.array([0.0, 1.0]), np.array([0.0, 100.0]), -999.0
        )
        assert out[0] == pytest.approx(50.0)

    def test_below_range_is_missing(self):
        out = _interpolate_no_extrapolate(
            np.array([-0.1]), np.array([0.0, 1.0]), np.array([0.0, 100.0]), -999.0
        )
        assert out[0] == -999.0

    def test_above_range_is_missing(self):
        out = _interpolate_no_extrapolate(
            np.array([1.1]), np.array([0.0, 1.0]), np.array([0.0, 100.0]), -999.0
        )
        assert out[0] == -999.0

    def test_exact_match_uses_source_value(self):
        out = _interpolate_no_extrapolate(
            np.array([0.0, 1.0]), np.array([0.0, 1.0]), np.array([10.0, 20.0]), -999.0
        )
        assert out[0] == pytest.approx(10.0)
        assert out[1] == pytest.approx(20.0)