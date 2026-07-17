"""tests/test_helpers.py — Unit tests for interpolation utilities."""
import numpy as np
import pandas as pd
import pytest

from qq import constants as C
from qq.config import QQConfig
from qq.helpers import (
    interpolate_deliverable_wse_quantile,
    interpolate_extrapolate_probability_value,
    make_empty_sos_fdc_table,
    make_empty_swot_df,
)
from qq.state import QQState

# ---------------------------------------------------------------------------
# Shared minimal config/state for helper tests
# ---------------------------------------------------------------------------

@pytest.fixture
def cs():
    """Minimal (config, state) pair — no file I/O needed."""
    config = QQConfig(run_mode="RUN", print_out_statements=False, save_log_file=False)
    state  = QQState()
    return config, state


# ---------------------------------------------------------------------------
# interpolate_deliverable_wse_quantile
# ---------------------------------------------------------------------------

class TestInterpolateDeliverableWseQuantile:

    def test_interior_linear_interpolation(self, cs):
        c, s = cs
        emp = pd.DataFrame({
            "p":   [0.0, 0.5, 1.0],
            "wse": [100.0, 150.0, 200.0],
        })
        prob_out = np.array([0.25, 0.5, 0.75])
        out, diag = interpolate_deliverable_wse_quantile(
            c, s, prob_out, emp, "p", "wse", extrapolate_edges=False,
            missing_value=C.QQ_NC_DOUBLE_FILL_VALUE,
        )
        assert out[1] == pytest.approx(150.0)
        assert out[0] == pytest.approx(125.0)
        assert diag["n_interpolated"] == 3

    def test_lower_edge_extrapolation(self, cs):
        c, s = cs
        emp = pd.DataFrame({
            "p":   [0.4, 0.5, 1.0],
            "wse": [140.0, 150.0, 200.0],
        })
        prob_out = np.array([0.2])  # below min 0.4
        out, diag = interpolate_deliverable_wse_quantile(
            c, s, prob_out, emp, "p", "wse", extrapolate_edges=True,
            missing_value=C.QQ_NC_DOUBLE_FILL_VALUE,
        )
        # slope = (150-140)/(0.5-0.4) = 100; extrapolate 0.2 below 0.4:
        # wse = 140 + 100 * (0.2 - 0.4) = 120
        assert out[0] == pytest.approx(120.0)
        assert diag["n_edge_extrapolated"] == 1

    def test_missing_table_returns_fill(self, cs):
        c, s = cs
        prob_out = np.linspace(0.01, 1.0, 10)
        out, diag = interpolate_deliverable_wse_quantile(
            c, s, prob_out, None, "p", "wse", extrapolate_edges=True,
            missing_value=C.QQ_NC_DOUBLE_FILL_VALUE,
        )
        assert np.all(out == C.QQ_NC_DOUBLE_FILL_VALUE)
        assert diag["n_edge_missing"] == 10

    def test_empty_table_returns_fill(self, cs):
        c, s = cs
        prob_out = np.array([0.5])
        out, _ = interpolate_deliverable_wse_quantile(
            c, s, prob_out, pd.DataFrame(columns=["p", "wse"]),
            "p", "wse", extrapolate_edges=False,
            missing_value=C.QQ_NC_DOUBLE_FILL_VALUE,
        )
        assert out[0] == C.QQ_NC_DOUBLE_FILL_VALUE

    def test_single_row_table(self, cs):
        c, s = cs
        emp = pd.DataFrame({"p": [0.5], "wse": [150.0]})
        prob_out = np.array([0.5, 0.6])
        out, diag = interpolate_deliverable_wse_quantile(
            c, s, prob_out, emp, "p", "wse", extrapolate_edges=True,
            missing_value=C.QQ_NC_DOUBLE_FILL_VALUE,
        )
        # Exact match at 0.5; 0.6 must be fill
        assert out[0] == pytest.approx(150.0)
        assert out[1] == C.QQ_NC_DOUBLE_FILL_VALUE


# ---------------------------------------------------------------------------
# interpolate_extrapolate_probability_value
# ---------------------------------------------------------------------------

class TestInterpolateExtrapolateProbabilityValue:

    def test_scalar_interior(self, cs):
        c, s = cs
        p = np.array([0.0, 0.5, 1.0])
        v = np.array([0.0, 50.0, 100.0])
        result, _ = interpolate_extrapolate_probability_value(
            c, s, 0.25, p, v, missing_value=-1.0, label="test"
        )
        assert result == pytest.approx(25.0)

    def test_extrapolate_below(self, cs):
        c, s = cs
        p = np.array([0.4, 0.5, 1.0])
        v = np.array([40.0, 50.0, 100.0])
        result, diag = interpolate_extrapolate_probability_value(
            c, s, 0.2, p, v, missing_value=-1.0, label="test"
        )
        # slope = (50-40)/(0.5-0.4) = 100; extrapolate: 40 + 100*(0.2-0.4) = 20
        assert result == pytest.approx(20.0)
        assert diag["n_lower_extrapolated"] == 1

    def test_too_few_valid(self, cs):
        c, s = cs
        result, diag = interpolate_extrapolate_probability_value(
            c, s, 0.5, np.array([0.5]), np.array([50.0]),
            missing_value=-1.0, label="test"
        )
        assert result == -1.0


# ---------------------------------------------------------------------------
# Empty dataframe constructors
# ---------------------------------------------------------------------------

def test_make_empty_swot_df():
    from qq.config import QQConfig
    config = QQConfig(print_out_statements=False)
    df = make_empty_swot_df(config)
    assert len(df) == 0
    assert C.SWOT_TIME_INDEX_COLNAME in df.columns


def test_make_empty_sos_fdc_table():
    df = make_empty_sos_fdc_table()
    assert list(df.columns) == ["rank", "p_non_exceedance", "p_exceedance", "discharge_quantile"]
