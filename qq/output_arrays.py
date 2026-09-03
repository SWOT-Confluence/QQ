"""
qq/output_arrays.py
===================
Prepare all output arrays for the QQ NetCDF writer.

Pipeline step
-------------
prepare_output_arrays(config, state)
    Builds the final QQ_q_out, QQ_q_status_flag_out, QQ_time_out,
    QQ_wse_quant_prob_out, QQ_wse_quant_wse_out, QQ_wse_quant_flag_out
    arrays that will be written to the NetCDF.

    This function also resolves the time format and sets the NetCDF time
    variable metadata attributes on state.

    Exact logic from notebook section 3-1 (PREPARE QQ NETCDF OUTPUT ARRAYS).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qq import constants as C
from qq.config import QQConfig
from qq.logger import fail, log, log_block, log_vars, section, warn
from qq.state import QQState


def prepare_output_arrays(config: QQConfig, state: QQState) -> None:  # noqa: PLR0912,PLR0915
    """
    Build all output arrays from the intermediate results stored on state.

    On success, sets on state:
        QQ_q_out, QQ_q_status_flag_out, QQ_time_out
        QQ_wse_quant_prob_out, QQ_wse_quant_wse_out, QQ_wse_quant_flag_out
        qq_output_all_q_missing
        output_nc_root_time_var_dtype_nc
        output_nc_root_time_var_units
        output_nc_root_time_var_fill_value
        output_nc_root_time_var_missing_value

    On any exception, sets all arrays to safe fill-value defaults and
    records the failure code -601.
    """
    section(config, state, "3-1 PREPARE QQ NETCDF OUTPUT ARRAYS")

    try:
        # ------------------------------------------------------------------
        # 3-1-0  Safety defaults for any variables not yet set
        # ------------------------------------------------------------------
        # if not hasattr(state, "QQ_wse_quant_prob") or state.QQ_wse_quant_prob is None:
        #     n = C.DELIVERABLE_WSE_QUANTILE_TABLE_N
        #     state.QQ_wse_quant_prob = np.linspace(1 / n, 1, n).astype(np.float64)
        
        if not hasattr(state, "QQ_wse_quant_prob") or state.QQ_wse_quant_prob is None:
            state.QQ_wse_quant_prob = C.DELIVERABLE_WSE_PROBABILITY_GRID.astype(np.float64)

        if not hasattr(state, "QQ_wse_quant_wse") or state.QQ_wse_quant_wse is None:
            state.QQ_wse_quant_wse = np.full(
                len(state.QQ_wse_quant_prob), C.QQ_NC_DOUBLE_FILL_VALUE, dtype=np.float64
            )

        if not hasattr(state, "QQ_wse_quant_flag") or state.QQ_wse_quant_flag is None:
            state.QQ_wse_quant_flag = C.WSE_QUANT_FLAG_DTYPE(C.WSE_QUANT_FLAG_ALL_MISSING_VALUE)
        
        if not hasattr(state, "QQ_lookup_table_prob") or state.QQ_lookup_table_prob is None:
            state.QQ_lookup_table_prob = np.array([], dtype=np.float64)
        if not hasattr(state, "QQ_lookup_table_wse") or state.QQ_lookup_table_wse is None:
            state.QQ_lookup_table_wse = np.array([], dtype=np.float64)
        if not hasattr(state, "QQ_lookup_table_q") or state.QQ_lookup_table_q is None:
            state.QQ_lookup_table_q = np.array([], dtype=np.float64)
        if not hasattr(state, "QQ_lookup_table_flag") or state.QQ_lookup_table_flag is None:
            state.QQ_lookup_table_flag = C.LOOKUP_TABLE_FLAG_DTYPE(C.LOOKUP_TABLE_FLAG_ALL_MISSING_VALUE)
            
            
        if not hasattr(state, "sos_fdc_table") or state.sos_fdc_table is None:
            from qq.helpers import make_empty_sos_fdc_table
            state.sos_fdc_table = make_empty_sos_fdc_table()

        if not hasattr(state, "qq_matched_df") or state.qq_matched_df is None:
            from qq.helpers import make_empty_qq_matched_df
            state.qq_matched_df = make_empty_qq_matched_df(config)

        if not hasattr(state, "sos_fdc_extended_flag") or state.sos_fdc_extended_flag is None:
            state.sos_fdc_extended_flag = 0   # SOS_FDC_EXTENDED_FLAG_NOT_ATTEMPTED

        # ------------------------------------------------------------------
        # 3-1-1  Control output policy constants
        # ------------------------------------------------------------------
        if C.QQ_OUTPUT_TIME_DIMENSION_SOURCE not in C.QQ_OUTPUT_TIME_DIMENSION_SOURCE_OPTIONS:
            fail(config, state,
                 f"Invalid QQ_OUTPUT_TIME_DIMENSION_SOURCE: {C.QQ_OUTPUT_TIME_DIMENSION_SOURCE}",
                 detailed_code=-601)

        if C.QQ_OUTPUT_TIME_FORMAT not in C.QQ_OUTPUT_TIME_FORMAT_OPTIONS:
            fail(config, state,
                 f"Invalid QQ_OUTPUT_TIME_FORMAT: {C.QQ_OUTPUT_TIME_FORMAT}",
                 detailed_code=-601)

        if C.QQ_OUTPUT_ALL_Q_MISSING_Q_ARRAY_MODE not in C.QQ_OUTPUT_ALL_Q_MISSING_ARRAY_MODE_OPTIONS:
            fail(config, state,
                 f"Invalid QQ_OUTPUT_ALL_Q_MISSING_Q_ARRAY_MODE: {C.QQ_OUTPUT_ALL_Q_MISSING_Q_ARRAY_MODE}",
                 detailed_code=-601)

        if C.QQ_OUTPUT_ALL_Q_MISSING_TIME_ARRAY_MODE not in C.QQ_OUTPUT_ALL_Q_MISSING_ARRAY_MODE_OPTIONS:
            fail(config, state,
                 f"Invalid QQ_OUTPUT_ALL_Q_MISSING_TIME_ARRAY_MODE: {C.QQ_OUTPUT_ALL_Q_MISSING_TIME_ARRAY_MODE}",
                 detailed_code=-601)

        # Both array modes must agree to keep q/time dimensions equal
        if C.QQ_OUTPUT_ALL_Q_MISSING_Q_ARRAY_MODE != C.QQ_OUTPUT_ALL_Q_MISSING_TIME_ARRAY_MODE:
            warn(config, state,
                 "QQ_OUTPUT_ALL_Q_MISSING_Q_ARRAY_MODE and QQ_OUTPUT_ALL_Q_MISSING_TIME_ARRAY_MODE "
                 "must be identical to keep q/time dimensions equal. "
                 f"Forcing time mode to q mode: {C.QQ_OUTPUT_ALL_Q_MISSING_Q_ARRAY_MODE}")
            # Note: constants are immutable; we document here but cannot change them.
            # The q_array_mode is authoritative.

        # ------------------------------------------------------------------
        # 3-1-2  WSE quantile output arrays
        # ------------------------------------------------------------------
        state.QQ_wse_quant_prob_out = np.asarray(state.QQ_wse_quant_prob, dtype=np.float64)

        wse_out = np.asarray(state.QQ_wse_quant_wse, dtype=np.float64)
        state.QQ_wse_quant_wse_out = np.where(
            np.isfinite(wse_out), wse_out, C.QQ_NC_DOUBLE_FILL_VALUE
        )

        state.QQ_wse_quant_flag_out = C.WSE_QUANT_FLAG_DTYPE(state.QQ_wse_quant_flag)
        
        # Lookup table arrays pass through unchanged (already fill-safe from lookup_table.py)
        state.QQ_lookup_table_prob_out = np.asarray(state.QQ_lookup_table_prob, dtype=np.float64)
        state.QQ_lookup_table_wse_out  = np.asarray(state.QQ_lookup_table_wse,  dtype=np.float64)
        state.QQ_lookup_table_q_out    = np.asarray(state.QQ_lookup_table_q,    dtype=np.float64)
        state.QQ_lookup_table_flag_out = C.LOOKUP_TABLE_FLAG_DTYPE(state.QQ_lookup_table_flag)

        # ------------------------------------------------------------------
        # 3-1-3  Select base time dimension for q/time output
        # ------------------------------------------------------------------
        if not C.QQ_OUTPUT_INCLUDE_MISSING_Q:
            # Export only estimated values
            output_q_base_df = state.qq_matched_df[
                state.qq_matched_df[C.QQ_Q_IS_ESTIMATED_COLNAME].astype(bool)
            ].copy()
            output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME] = C.QQ_Q_STATUS_VALID_CODE

        else:
            if C.QQ_OUTPUT_TIME_DIMENSION_SOURCE == "swot":
                output_q_base_df = state.swot_dc_reach_swot_df.copy()
                output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME] = (
                    C.QQ_Q_STATUS_REMOVED_BY_CLEANING_CODE
                )
                cleaned_ids = set(state.swot_dc_reach_swot_df_clean[C.SWOT_TIME_INDEX_COLNAME].to_numpy())
                output_q_base_df.loc[
                    output_q_base_df[C.SWOT_TIME_INDEX_COLNAME].isin(cleaned_ids),
                    C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME,
                ] = C.QQ_Q_STATUS_REMOVED_BY_FILTERING_CODE
                cleaned_filtered_ids = set(
                    state.swot_dc_reach_swot_df_clean_filt[C.SWOT_TIME_INDEX_COLNAME].to_numpy()
                )
                output_q_base_df.loc[
                    output_q_base_df[C.SWOT_TIME_INDEX_COLNAME].isin(cleaned_filtered_ids),
                    C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME,
                ] = C.QQ_Q_STATUS_NO_QUANTILE_APPLIED_CODE

            elif C.QQ_OUTPUT_TIME_DIMENSION_SOURCE == "swot_cleaned":
                output_q_base_df = state.swot_dc_reach_swot_df_clean.copy()
                output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME] = (
                    C.QQ_Q_STATUS_REMOVED_BY_FILTERING_CODE
                )
                cleaned_filtered_ids = set(
                    state.swot_dc_reach_swot_df_clean_filt[C.SWOT_TIME_INDEX_COLNAME].to_numpy()
                )
                output_q_base_df.loc[
                    output_q_base_df[C.SWOT_TIME_INDEX_COLNAME].isin(cleaned_filtered_ids),
                    C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME,
                ] = C.QQ_Q_STATUS_NO_QUANTILE_APPLIED_CODE

            else:  # "swot_cleaned_filtered"
                output_q_base_df = state.swot_dc_reach_swot_df_clean_filt.copy()
                output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME] = (
                    C.QQ_Q_STATUS_NO_QUANTILE_APPLIED_CODE
                )

            if state.invalid_reach:
                output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME] = (
                    C.QQ_Q_STATUS_INVALID_REACH_CODE
                )

        # ------------------------------------------------------------------
        # 3-1-4  Insert estimated discharge values into selected time dimension
        # ------------------------------------------------------------------
        output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_NAME] = C.QQ_NC_DOUBLE_FILL_VALUE

        if not state.invalid_reach and len(state.qq_matched_df) > 0:
            estimated_q_by_time_index = (
                state.qq_matched_df.loc[
                    state.qq_matched_df[C.QQ_Q_IS_ESTIMATED_COLNAME].astype(bool),
                    [C.SWOT_TIME_INDEX_COLNAME, C.SWOT_QQ_DELIVERABLE_Q_NAME],
                ]
                .set_index(C.SWOT_TIME_INDEX_COLNAME)[C.SWOT_QQ_DELIVERABLE_Q_NAME]
            )

            estimated_mask = output_q_base_df[C.SWOT_TIME_INDEX_COLNAME].isin(
                estimated_q_by_time_index.index
            )
            output_q_base_df.loc[estimated_mask, C.SWOT_QQ_DELIVERABLE_Q_NAME] = (
                output_q_base_df.loc[estimated_mask, C.SWOT_TIME_INDEX_COLNAME]
                .map(estimated_q_by_time_index)
                .astype(float)
            )
            output_q_base_df.loc[estimated_mask, C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME] = (
                C.QQ_Q_STATUS_VALID_CODE
            )

        # ------------------------------------------------------------------
        # 3-1-5  Create final Q and status arrays
        # ------------------------------------------------------------------
        QQ_q_out_raw = np.asarray(output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_NAME], dtype=np.float64)
        state.QQ_q_out = np.where(
            np.isfinite(QQ_q_out_raw), QQ_q_out_raw, C.QQ_NC_DOUBLE_FILL_VALUE
        )

        state.QQ_q_status_flag_out = np.asarray(
            output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME], dtype=np.int16
        )

        state.qq_output_all_q_missing = not np.any(
            state.QQ_q_status_flag_out == C.QQ_Q_STATUS_VALID_CODE
        )

        if state.qq_output_all_q_missing and C.QQ_OUTPUT_ALL_Q_MISSING_Q_ARRAY_MODE == "single_missing":
            log(config, state, "No discharge estimated at any timestep: using single-missing q/time output arrays")
            output_q_base_df = pd.DataFrame({
                C.SWOT_TIME_INDEX_COLNAME:               [C.QQ_NC_INT_FILL_VALUE],
                C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME:  [pd.NaT],
                C.SWOT_QQ_DELIVERABLE_Q_NAME:            [C.QQ_NC_DOUBLE_FILL_VALUE],
                C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME: [
                    C.QQ_Q_STATUS_INVALID_REACH_CODE if state.invalid_reach
                    else C.QQ_Q_STATUS_NO_QUANTILE_APPLIED_CODE
                ],
            })
            state.QQ_q_out = np.asarray(
                output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_NAME], dtype=np.float64
            )
            state.QQ_q_status_flag_out = np.asarray(
                output_q_base_df[C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME], dtype=np.int16
            )
        else:
            log_vars(config, state,
                     qq_output_all_q_missing=state.qq_output_all_q_missing,
                     qq_output_all_q_missing_q_array_mode=C.QQ_OUTPUT_ALL_Q_MISSING_Q_ARRAY_MODE,
                     qq_output_all_q_missing_time_array_mode=C.QQ_OUTPUT_ALL_Q_MISSING_TIME_ARRAY_MODE)

        # ------------------------------------------------------------------
        # 3-1-6  Create final time array as datetime64 first
        # ------------------------------------------------------------------
        QQ_time_datetime64_out = (
            pd.to_datetime(
                output_q_base_df[C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME],
                errors="coerce",
                utc=True,
            )
            .dt.tz_convert(None)
            .to_numpy("datetime64[ns]")
        )
        QQ_time_valid_mask = ~np.isnat(QQ_time_datetime64_out)

        # ------------------------------------------------------------------
        # 3-1-7  Convert final time array to selected output format
        # ------------------------------------------------------------------
        if C.QQ_OUTPUT_TIME_FORMAT == "seconds_f8":
            state.output_nc_root_time_var_dtype_nc    = "f8"
            state.output_nc_root_time_var_units       = C.QQ_NC_TIME_UNITS
            state.output_nc_root_time_var_fill_value  = C.QQ_NC_DOUBLE_FILL_VALUE
            state.output_nc_root_time_var_missing_value = C.QQ_NC_DOUBLE_FILL_VALUE

            state.QQ_time_out = np.full(len(QQ_time_datetime64_out), C.QQ_NC_DOUBLE_FILL_VALUE, dtype=np.float64)
            state.QQ_time_out[QQ_time_valid_mask] = (
                (QQ_time_datetime64_out[QQ_time_valid_mask] - C.QQ_NC_TIME_EPOCH)
                / np.timedelta64(1, "s")
            ).astype(np.float64)

        elif C.QQ_OUTPUT_TIME_FORMAT == "seconds_i8":
            state.output_nc_root_time_var_dtype_nc    = "i8"
            state.output_nc_root_time_var_units       = C.QQ_NC_TIME_UNITS
            state.output_nc_root_time_var_fill_value  = C.QQ_NC_INT_FILL_VALUE
            state.output_nc_root_time_var_missing_value = C.QQ_NC_INT_FILL_VALUE

            state.QQ_time_out = np.full(len(QQ_time_datetime64_out), C.QQ_NC_INT_FILL_VALUE, dtype=np.int64)
            state.QQ_time_out[QQ_time_valid_mask] = (
                (QQ_time_datetime64_out[QQ_time_valid_mask] - C.QQ_NC_TIME_EPOCH)
                / np.timedelta64(1, "s")
            ).astype(np.int64)

        elif C.QQ_OUTPUT_TIME_FORMAT == "nanoseconds_i8":
            state.output_nc_root_time_var_dtype_nc    = "i8"
            state.output_nc_root_time_var_units       = "nanoseconds since 2000-01-01 00:00:00.000"
            state.output_nc_root_time_var_fill_value  = C.QQ_NC_INT_FILL_VALUE
            state.output_nc_root_time_var_missing_value = C.QQ_NC_INT_FILL_VALUE

            state.QQ_time_out = np.full(len(QQ_time_datetime64_out), C.QQ_NC_INT_FILL_VALUE, dtype=np.int64)
            state.QQ_time_out[QQ_time_valid_mask] = (
                (QQ_time_datetime64_out[QQ_time_valid_mask] - C.QQ_NC_TIME_EPOCH)
                / np.timedelta64(1, "ns")
            ).astype(np.int64)

        elif C.QQ_OUTPUT_TIME_FORMAT == "iso_string":
            state.output_nc_root_time_var_dtype_nc    = str
            state.output_nc_root_time_var_units       = "ISO-8601 datetime string"
            state.output_nc_root_time_var_fill_value  = None
            state.output_nc_root_time_var_missing_value = C.QQ_NC_STR_FILL_VALUE

            state.QQ_time_out = np.full(len(QQ_time_datetime64_out), C.QQ_NC_STR_FILL_VALUE, dtype=object)
            state.QQ_time_out[QQ_time_valid_mask] = (
                pd.to_datetime(QQ_time_datetime64_out[QQ_time_valid_mask])
                .strftime("%Y-%m-%dT%H:%M:%S")
                .to_numpy()
            )

        # ------------------------------------------------------------------
        # 3-1-8  Final control: time and q must have same length
        # ------------------------------------------------------------------
        if len(state.QQ_time_out) != len(state.QQ_q_out):
            fail(config, state,
                 f"Output time/q length mismatch: {len(state.QQ_time_out)} vs {len(state.QQ_q_out)}",
                 detailed_code=-602)
            state.QQ_time_out          = np.array([C.QQ_NC_DOUBLE_FILL_VALUE], dtype=np.float64)
            state.QQ_q_out             = np.array([C.QQ_NC_DOUBLE_FILL_VALUE], dtype=np.float64)
            state.QQ_q_status_flag_out = np.array([C.QQ_Q_STATUS_INVALID_REACH_CODE], dtype=np.int16)
            state.output_nc_root_time_var_dtype_nc    = "f8"
            state.output_nc_root_time_var_units       = C.QQ_NC_TIME_UNITS
            state.output_nc_root_time_var_fill_value  = C.QQ_NC_DOUBLE_FILL_VALUE
            state.output_nc_root_time_var_missing_value = C.QQ_NC_DOUBLE_FILL_VALUE

        state.output_q_base_df = output_q_base_df

        log_vars(
            config, state,
            qq_output_include_missing_q=C.QQ_OUTPUT_INCLUDE_MISSING_Q,
            qq_output_time_dimension_source=C.QQ_OUTPUT_TIME_DIMENSION_SOURCE,
            qq_output_time_format=C.QQ_OUTPUT_TIME_FORMAT,
            QQ_time_out_len=len(state.QQ_time_out),
            QQ_q_out_len=len(state.QQ_q_out),
            QQ_q_status_flag_out_len=len(state.QQ_q_status_flag_out),
            QQ_wse_quant_prob_out_len=len(state.QQ_wse_quant_prob_out),
            QQ_wse_quant_wse_out_len=len(state.QQ_wse_quant_wse_out),
            QQ_wse_quant_flag_out=state.QQ_wse_quant_flag_out,
            qq_output_all_q_missing=state.qq_output_all_q_missing,
        )
        log_block(config, state, "output_q_base_df_head", output_q_base_df.head())

    except Exception as exc:
        fail(config, state, f"Output array preparation failed: {exc}", detailed_code=-601)
        _set_fail_safe_arrays(state)


# def _set_fail_safe_arrays(state: QQState) -> None:
#     """Set all output arrays to safe fill-value defaults after a -601 failure."""
#     n = C.DELIVERABLE_WSE_QUANTILE_TABLE_N
#     state.QQ_wse_quant_prob_out = np.linspace(1 / n, 1, n).astype(np.float64)
#     state.QQ_wse_quant_wse_out  = np.full(n, C.QQ_NC_DOUBLE_FILL_VALUE, dtype=np.float64)

# def _set_fail_safe_arrays(state: QQState) -> None:
#     """Set all output arrays to safe fill-value defaults after a -601 failure."""
    # _grid = C.DELIVERABLE_WSE_PROBABILITY_GRID
    # state.QQ_wse_quant_prob_out = _grid.astype(np.float64)
    # state.QQ_wse_quant_wse_out  = np.full(len(_grid), C.QQ_NC_DOUBLE_FILL_VALUE, dtype=np.float64)
    # state.QQ_wse_quant_flag_out = C.WSE_QUANT_FLAG_DTYPE(C.WSE_QUANT_FLAG_ALL_MISSING_VALUE)
    
def _set_fail_safe_arrays(state: QQState) -> None:
    """Set all output arrays to safe fill-value defaults after a -601 failure."""
    _grid = C.DELIVERABLE_WSE_PROBABILITY_GRID
    state.QQ_wse_quant_prob_out = _grid.astype(np.float64)
    state.QQ_wse_quant_wse_out  = np.full(len(_grid), C.QQ_NC_DOUBLE_FILL_VALUE, dtype=np.float64)
    state.QQ_wse_quant_flag_out = C.WSE_QUANT_FLAG_DTYPE(C.WSE_QUANT_FLAG_ALL_MISSING_VALUE)
    state.QQ_lookup_table_prob_out  = np.array([], dtype=np.float64)
    state.QQ_lookup_table_wse_out   = np.array([], dtype=np.float64)
    state.QQ_lookup_table_q_out     = np.array([], dtype=np.float64)
    state.QQ_lookup_table_flag_out  = C.LOOKUP_TABLE_FLAG_DTYPE(C.LOOKUP_TABLE_FLAG_ALL_MISSING_VALUE)
    state.QQ_time_out          = np.array([C.QQ_NC_DOUBLE_FILL_VALUE], dtype=np.float64)
    state.QQ_q_out             = np.array([C.QQ_NC_DOUBLE_FILL_VALUE], dtype=np.float64)
    state.QQ_q_status_flag_out = np.array([C.QQ_Q_STATUS_INVALID_REACH_CODE], dtype=np.int16)
    state.qq_output_all_q_missing = True
    state.output_nc_root_time_var_dtype_nc    = "f8"
    state.output_nc_root_time_var_units       = C.QQ_NC_TIME_UNITS
    state.output_nc_root_time_var_fill_value  = C.QQ_NC_DOUBLE_FILL_VALUE
    state.output_nc_root_time_var_missing_value = C.QQ_NC_DOUBLE_FILL_VALUE
