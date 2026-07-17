"""
tests/test_pipeline.py
======================
End-to-end integration tests.  Run the full QQ pipeline against the
synthetic NetCDF fixtures from conftest.py and verify outputs.
"""

from __future__ import annotations

import numpy as np
import pytest
from netCDF4 import Dataset

from qq import constants as C
from qq.config import QQConfig
from tests.conftest import N_OBS, REACH_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def open_nc(state):
    return Dataset(state.output_nc_path)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

class TestPipelineSuccess:
    """Full pipeline on a reach with 60 good observations."""

    @pytest.fixture(scope="class")
    def state(self, qq_config):
        from qq.pipeline import run
        return run(qq_config)

    # --- basic validity ---

    def test_reach_is_valid(self, state):
        assert not state.invalid_reach, (
            f"Expected valid reach, got code {state.invalid_reach_detailed_code}: "
            f"{state.invalid_reach_messages}"
        )

    def test_detailed_code_is_zero(self, state):
        assert state.invalid_reach_detailed_code == 0

    # --- output file ---

    def test_output_nc_exists(self, state):
        assert state.output_nc_path.exists()

    def test_output_nc_filename_convention(self, state):
        expected = f"{REACH_ID}_{C.ALGO_NAME}.nc"
        assert state.output_nc_path.name == expected

    # --- array shapes ---

    def test_q_and_time_same_length(self, state):
        assert len(state.QQ_q_out) == len(state.QQ_time_out)

    def test_q_status_flag_same_length_as_q(self, state):
        assert len(state.QQ_q_status_flag_out) == len(state.QQ_q_out)
        
        
    def test_quantile_matching_uses_only_fdc_range(self, state):
        """With predefined extremes disabled, every valid Q must have p within FDC range."""
        import pandas as pd
        fdc = state.sos_fdc_table
        if len(fdc) < 2:
            return  # skip if FDC table unavailable
        p_fdc_min = fdc["p_non_exceedance"].min()
        p_fdc_max = fdc["p_non_exceedance"].max()
        # All matched probabilities (is_estimated=True) must be within FDC bounds
        if hasattr(state, "qq_matched_df") and len(state.qq_matched_df) > 0:
            from qq import constants as C
            estimated = state.qq_matched_df[state.qq_matched_df[C.QQ_Q_IS_ESTIMATED_COLNAME]]
            if len(estimated) > 0:
                p_vals = estimated[C.QQ_P_NON_EXCEEDANCE_COLNAME]
                assert p_vals.min() >= p_fdc_min - 1e-9
                assert p_vals.max() <= p_fdc_max + 1e-9





    # def test_wse_quant_prob_length_is_100(self, state):
    #     assert len(state.QQ_wse_quant_prob_out) == C.DELIVERABLE_WSE_QUANTILE_TABLE_N

    # def test_wse_quant_wse_length_is_100(self, state):
    #     assert len(state.QQ_wse_quant_wse_out) == C.DELIVERABLE_WSE_QUANTILE_TABLE_N
    
    

    def test_wse_quant_prob_length_matches_grid(self, state):
        assert len(state.QQ_wse_quant_prob_out) == len(C.DELIVERABLE_WSE_PROBABILITY_GRID)

    def test_wse_quant_wse_length_matches_grid(self, state):
        assert len(state.QQ_wse_quant_wse_out) == len(C.DELIVERABLE_WSE_PROBABILITY_GRID)
        
        



    # --- scientific sanity ---

    def test_some_q_values_are_valid(self, state):
        assert np.any(state.QQ_q_status_flag_out == C.QQ_Q_STATUS_VALID_CODE), \
            "No valid discharge estimates were produced for the synthetic reach"

    def test_q_values_positive_or_fill(self, state):
        q = state.QQ_q_out
        valid_q = q[state.QQ_q_status_flag_out == C.QQ_Q_STATUS_VALID_CODE]
        assert np.all(valid_q > 0), "Some valid Q values are not positive"

    def test_wse_quant_prob_monotone_increasing(self, state):
        p = state.QQ_wse_quant_prob_out
        assert np.all(np.diff(p) > 0)

    def test_wse_quant_wse_monotone_increasing(self, state):
        # Synthetic WSE is linearly increasing, so the quantile table should be too
        wse = state.QQ_wse_quant_wse_out
        finite = wse[wse != C.QQ_NC_DOUBLE_FILL_VALUE]
        if len(finite) > 1:
            assert np.all(np.diff(finite) >= 0), \
                "WSE quantile table is not monotonically non-decreasing"

    def test_no_errors_in_state(self, state):
        assert len(state.errors_list) == 0

    # --- NetCDF structure ---

    def test_nc_global_attr_algorithm(self, state):
        with open_nc(state) as nc:
            assert nc.algorithm == C.ALGO_NAME

    def test_nc_global_attr_reach_id(self, state):
        with open_nc(state) as nc:
            assert nc.reach_id == REACH_ID

    def test_nc_global_attr_is_valid(self, state):
        with open_nc(state) as nc:
            assert int(nc.is_valid) == 1

    def test_nc_conventions(self, state):
        with open_nc(state) as nc:
            assert nc.Conventions == C.OUTPUT_NC_ROOT_CONVENTIONS

    def test_nc_root_dimensions(self, state):
        with open_nc(state) as nc:
            assert C.OUTPUT_NC_ROOT_DIM_NT_NAME    in nc.dimensions
            assert C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME in nc.dimensions

    # def test_nc_nwseq_dimension_is_100(self, state):
    #     with open_nc(state) as nc:
    #         assert nc.dimensions[C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME].size == 100


    def test_nc_nwseq_dimension_matches_grid(self, state):
        with open_nc(state) as nc:
            assert nc.dimensions[C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME].size == len(C.DELIVERABLE_WSE_PROBABILITY_GRID)
            


    def test_nc_time_variable_exists(self, state):
        with open_nc(state) as nc:
            assert C.SWOT_QQ_DELIVERABLE_TIME_NAME in nc.variables

    def test_nc_flag_scalars_exist(self, state):
        with open_nc(state) as nc:
            assert C.SWOT_QQ_DELIVERABLE_INVALID_REACH_DETAILED_FLAG_NAME in nc.variables
            assert C.SWOT_QQ_DELIVERABLE_INVALID_REACH_SUMMARY_FLAG_NAME  in nc.variables

    def test_nc_invalid_flag_zero_for_valid_reach(self, state):
        with open_nc(state) as nc:
            v = int(nc.variables[C.SWOT_QQ_DELIVERABLE_INVALID_REACH_DETAILED_FLAG_NAME][:])
            assert v == 0

    def test_nc_q_group_exists(self, state):
        with open_nc(state) as nc:
            assert C.OUTPUT_NC_Q_GP_NAME in nc.groups

    def test_nc_q_variable_in_q_group(self, state):
        with open_nc(state) as nc:
            assert C.SWOT_QQ_DELIVERABLE_Q_NAME in nc[C.OUTPUT_NC_Q_GP_NAME].variables

    def test_nc_q_status_flag_in_q_group(self, state):
        with open_nc(state) as nc:
            assert C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME in nc[C.OUTPUT_NC_Q_GP_NAME].variables

    def test_nc_wse_quant_group_exists(self, state):
        with open_nc(state) as nc:
            assert C.OUTPUT_NC_WSE_QUANT_GP_NAME in nc.groups

    def test_nc_wse_quant_prob_variable(self, state):
        with open_nc(state) as nc:
            wq = nc[C.OUTPUT_NC_WSE_QUANT_GP_NAME]
            assert C.SWOT_QQ_DELIVERABLE_WSE_QUANT_PROB_NAME in wq.variables

    def test_nc_wse_quant_wse_variable(self, state):
        with open_nc(state) as nc:
            wq = nc[C.OUTPUT_NC_WSE_QUANT_GP_NAME]
            assert C.SWOT_QQ_DELIVERABLE_WSE_QUANT_WSE_NAME in wq.variables

    def test_nc_wse_quant_flag_scalar(self, state):
        with open_nc(state) as nc:
            wq = nc[C.OUTPUT_NC_WSE_QUANT_GP_NAME]
            assert C.SWOT_QQ_DELIVERABLE_WSE_QUANT_FLAG_NAME in wq.variables

    def test_nc_q_fill_value_is_ecosystem_value(self, state):
        with open_nc(state) as nc:
            q_var = nc[C.OUTPUT_NC_Q_GP_NAME][C.SWOT_QQ_DELIVERABLE_Q_NAME]
            fv = float(q_var._FillValue)
            assert abs(fv - C.QQ_NC_DOUBLE_FILL_VALUE) < 1.0, \
                f"Fill value {fv} does not match expected {C.QQ_NC_DOUBLE_FILL_VALUE}"


# ---------------------------------------------------------------------------
# Invalid-reach path: too few observations (5 < 50 threshold)
# ---------------------------------------------------------------------------

class TestPipelineInvalidReachTooFewObs:
    """Pipeline must write a fill-value NC and exit cleanly (no exception)."""

    @pytest.fixture(scope="class")
    def state(self, invalid_reach_env):
        config, rid = invalid_reach_env
        from qq.pipeline import run
        return run(config)

    def test_reach_is_marked_invalid(self, state):
        assert state.invalid_reach, "Expected invalid_reach=True for 5-observation reach"

    def test_detailed_code_is_swot_wse_too_short(self, state):
        # -321 = swot_cleaned_filtered_wse_too_short
        assert state.invalid_reach_detailed_code == -321, \
            f"Expected -321, got {state.invalid_reach_detailed_code}"

    def test_output_nc_still_written(self, state):
        assert hasattr(state, "output_nc_path"), "output_nc_path not set on state"
        assert state.output_nc_path.exists(), \
            f"Output NC missing at {state.output_nc_path}"

    def test_nc_is_valid_is_zero(self, state):
        with open_nc(state) as nc:
            assert int(nc.is_valid) == 0

    def test_nc_invalid_flag_is_minus_321(self, state):
        with open_nc(state) as nc:
            v = int(nc.variables[C.SWOT_QQ_DELIVERABLE_INVALID_REACH_DETAILED_FLAG_NAME][:])
            assert v == -321

    def test_wse_quant_all_fill(self, state):
        with open_nc(state) as nc:
            wse = nc[C.OUTPUT_NC_WSE_QUANT_GP_NAME][C.SWOT_QQ_DELIVERABLE_WSE_QUANT_WSE_NAME][:]
            assert np.all(np.ma.filled(wse, C.QQ_NC_DOUBLE_FILL_VALUE) == C.QQ_NC_DOUBLE_FILL_VALUE)

    def test_no_valid_q_flags(self, state):
        assert not np.any(state.QQ_q_status_flag_out == C.QQ_Q_STATUS_VALID_CODE), \
            "Unexpected valid Q flag on an invalid reach"

    def test_q_all_fill_value(self, state):
        assert np.all(state.QQ_q_out == C.QQ_NC_DOUBLE_FILL_VALUE)


# ---------------------------------------------------------------------------
# CLI exit code tests
# ---------------------------------------------------------------------------

class TestCLIExitCode:
    """run_qq.py must exit 0 for both valid and invalid reaches."""

    def test_exit_0_valid_reach(self, qq_config, tmp_path):
        """Import main() and verify it returns 0 for a good reach."""
        import sys
        sys.argv = [
            "run_qq.py",
            str(qq_config.input_dir / "reaches.json"),
            "--input_dir",  str(qq_config.input_dir),
            "--output_dir", str(tmp_path),
            "--index", "0",
            "--mode", "RUN",
            "--no-log",
        ]
        from run_qq import main
        rc = main()
        assert rc == 0

    def test_exit_0_invalid_reach(self, invalid_reach_env, tmp_path):
        """main() must also return 0 when a reach is invalid (fill NC written)."""
        import sys
        config, _ = invalid_reach_env
        sys.argv = [
            "run_qq.py",
            str(config.input_dir / "reaches.json"),
            "--input_dir",  str(config.input_dir),
            "--output_dir", str(tmp_path),
            "--index", "0",
            "--mode", "RUN",
            "--no-log",
        ]
        from run_qq import main
        rc = main()
        assert rc == 0
