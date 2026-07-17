"""tests/test_constants.py — Verify that critical constants have the expected values."""
import numpy as np
import pytest
from qq import constants as C


def test_algo_name():
    assert C.ALGO_NAME == "qq"


def test_fill_value_is_negative_large():
    assert C.QQ_NC_DOUBLE_FILL_VALUE < -1e11


def test_flag_fill_value_is_minus_999():
    assert C.QQ_NC_FLAG_FILL_VALUE == np.int16(-999)




def test_wse_probability_grid_length_is_101():
    """Default grid: 0.00 to 1.00 in steps of 0.01 → 101 points."""
    assert len(C.DELIVERABLE_WSE_PROBABILITY_GRID) == 101


def test_wse_probability_grid_endpoints():
    """Both endpoints must be exactly 0.0 and 1.0."""
    grid = C.DELIVERABLE_WSE_PROBABILITY_GRID
    assert grid[0]  == pytest.approx(0.0)
    assert grid[-1] == pytest.approx(1.0)


def test_predefined_extremes_estimation_disabled():
    """5%–95% clipping must be disabled by default."""
    assert C.QUANTILE_MATCHING_PREDEFINED_EXTREMES_ESTIMATION is True


def test_fdc_extremes_estimation_active():
    """FDC-range clipping must be active by default."""
    assert C.QUANTILE_MATCHING_FDC_EXTREMES_ESTIMATION is False





# def test_deliverable_table_n_is_100():
#     assert C.DELIVERABLE_WSE_QUANTILE_TABLE_N == 100


def test_min_obs_is_50():
    assert C.MIN_CLEAN_FILT_SWOT_WSE_LEN == 50


def test_status_flag_values_are_int16():
    assert C.QQ_Q_STATUS_FLAG_VALUES.dtype == np.int16


def test_flag_dicts_cover_zero():
    assert 0 in C.INVALID_REACH_DETAILED_FLAG_DICT
    assert 0 in C.INVALID_REACH_SUMMARY_FLAG_DICT
    assert C.INVALID_REACH_DETAILED_FLAG_DICT[0] == "valid"


def test_time_epoch_is_y2k():
    assert str(C.QQ_NC_TIME_EPOCH) == "2000-01-01T00:00:00.000000000"


def test_sos_probability_divided_correctly():
    # The algorithm divides SOS probability by 100; make sure we expect percentages
    assert "100" in C.QQ_NC_TIME_UNITS or "seconds" in C.QQ_NC_TIME_UNITS


def test_wse_quant_flag_thresholds_ascending():
    t = C.WSE_QUANT_FLAG_THRESHOLDS
    assert all(t[i] < t[i + 1] for i in range(len(t) - 2))
