"""
qq/input_swot.py
================
Read, clean, and filter the SWOT per-reach NetCDF file.

Pipeline steps
--------------
read_swot(config, state)
    Open the per-reach SWOT NetCDF, extract the 'reach' group variables into a
    pandas DataFrame, and store metadata.  Handles char arrays, masked arrays,
    and optional/required fields.

clean_swot(config, state)
    Apply internal cleaning criteria (drop rows where WSE or time_str are fill /
    sentinel values).  Controlled by SWOT_INTERNAL_CLEANING_APPLY.

filter_swot(config, state)
    Apply internal filtering criteria (drop rows where reach_q == 3).
    Controlled by SWOT_INTERNAL_FILTERING_APPLY.

control_wse_count(config, state)
    Gate: fail the reach if fewer than MIN_CLEAN_FILT_SWOT_WSE_LEN valid
    observations remain after cleaning+filtering.

All steps skip silently if state.invalid_reach is already True.
All errors call logger.fail(), which in RUN mode keeps the pipeline alive.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from qq import constants as C
from qq.config import QQConfig
from qq.helpers import (
    get_nc_var_metadata,
    make_empty_swot_df,
    nc_char_array_to_strings,
)
from qq.logger import fail, log, log_block, log_vars, section, warn
from qq.state import QQState


def read_swot(config: QQConfig, state: QQState) -> None:
    """
    Open the per-reach SWOT NetCDF and build state.swot_dc_reach_swot_df.

    Expected file structure (produced by the Confluence input module):
        Root variables: nt, nx, observations
        Group 'reach': reach_id, time, time_str, wse, n_good_nod[, reach_q]
    """
    log(config, state, "-" * 100)
    log(config, state, "2-1-1 READ INPUT SWOT NC")
    log(config, state, "-" * 100)

    if state.invalid_reach:
        log(config, state, "Skipped SWOT NC read because invalid_reach=True")
        state.swot_dc_reach_swot_df = make_empty_swot_df(config)
        return

    try:
        from netCDF4 import Dataset  # type: ignore

        if state.input_swot_path is None or not Path(state.input_swot_path).exists():
            fail(config, state, f"SWOT file not found: {state.input_swot_path}", detailed_code=-301)
            state.swot_dc_reach_swot_df = make_empty_swot_df(config)
            return

        swot_dc = Dataset(state.input_swot_path)

        # Validate required root groups
        if C.NAME_SWOT_REACH_GP not in swot_dc.groups:
            fail(config, state, f"Missing SWOT group: {C.NAME_SWOT_REACH_GP}", detailed_code=-304)
            state.swot_dc_reach_swot_df = make_empty_swot_df(config)
            return

        # Validate required root variables (nt, nx, observations)
        missing_root_vars = [
            v for v in [C.NAME_SWOT_NT_VAR, C.NAME_SWOT_NX_VAR, C.NAME_SWOT_OBSERVATIONS_VAR]
            if v not in swot_dc.variables
        ]
        if missing_root_vars:
            fail(config, state, f"Missing SWOT root variables: {missing_root_vars}", detailed_code=-303)
            state.swot_dc_reach_swot_df = make_empty_swot_df(config)
            return

        # Read root dimension variables (kept for logging/metadata only)
        swot_dc_nt_var = swot_dc.variables[C.NAME_SWOT_NT_VAR][:]
        swot_dc_nx_var = swot_dc.variables[C.NAME_SWOT_NX_VAR][:]
        swot_observations_var = nc_char_array_to_strings(
            swot_dc.variables[C.NAME_SWOT_OBSERVATIONS_VAR][:], fill_value=b""
        )

        # Read reach group variables
        swot_dc_reach_gp = swot_dc[C.NAME_SWOT_REACH_GP]
        fields: list[str] = []

        for field in C.SWOT_REQUIRED_REACH_FIELDS:
            if field in swot_dc_reach_gp.variables:
                state.swot_reach_field_nc_metadata[field] = get_nc_var_metadata(
                    swot_dc_reach_gp[field]
                )
                fields.append(field)
            else:
                fail(config, state, f"Missing required SWOT reach variable: {field}", detailed_code=-303)

        if state.invalid_reach:
            state.swot_dc_reach_swot_df = make_empty_swot_df(config)
            return

        for field in C.SWOT_OPTIONAL_REACH_FIELDS:
            if field in swot_dc_reach_gp.variables:
                state.swot_reach_field_nc_metadata[field] = get_nc_var_metadata(
                    swot_dc_reach_gp[field]
                )
                fields.append(field)
            else:
                warn(config, state, f"Optional SWOT reach variable not found and will not be used: {field}")

        # Count the number of time steps from the time variable
        swot_dc_nt_1 = len(swot_dc_reach_gp[C.NAME_SWOT_LEN_COUNT_COL][:])

        # Build the main SWOT DataFrame
        row_data: dict = {}
        for k in fields:
            var = swot_dc_reach_gp[k]
            if var.ndim == 2:
                # Char array (e.g., time_str)
                row_data[k] = nc_char_array_to_strings(var[:], fill_value=b"")
            elif var.ndim == 0:
                # Scalar variable — broadcast to all time steps
                scalar_val = var[()]
                val = "" if np.ma.is_masked(scalar_val) else scalar_val
                row_data[k] = [val] * swot_dc_nt_1
            else:
                # Standard 1-D array
                row_data[k] = var[:]

        df = pd.DataFrame(row_data)
        df[C.SWOT_TIME_INDEX_COLNAME] = np.arange(swot_dc_nt_1, dtype=np.int32)
        df[C.SWOT_STATUS_COLNAME] = C.SWOT_STATUS_VALID

        if C.NAME_SWOT_TIME_STR_COL in df.columns:
            df[C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME] = pd.to_datetime(
                df[C.NAME_SWOT_TIME_STR_COL], errors="coerce", utc=True
            )
        else:
            warn(config, state,
                 f"Datetime conversion not applied: missing column '{C.NAME_SWOT_TIME_STR_COL}'")

        state.swot_dc_reach_swot_df = df

        log_vars(
            config, state,
            swot_observations_var_len=len(swot_observations_var),
            swot_observations_var_sample=swot_observations_var[:5],
            swot_dc_nt_1=swot_dc_nt_1,
            swot_dc_reach_swot_df_shape=df.shape,
        )
        if config.run_mode == "AUDIT":
            log_block(config, state, "swot_reach_field_nc_metadata", state.swot_reach_field_nc_metadata)
        log_block(config, state, "swot_dc_reach_swot_df_head", df.head())

    except Exception as exc:
        fail(config, state, f"SWOT NC read failed: {exc}", detailed_code=-302)
        state.swot_dc_reach_swot_df = make_empty_swot_df(config)


def clean_swot(config: QQConfig, state: QQState) -> None:
    """
    Remove rows where WSE or time_str have fill / sentinel values.

    Cleaning is controlled by C.SWOT_INTERNAL_CLEANING_APPLY.
    Removed rows are flagged with SWOT_STATUS_CLEANED in swot_dc_reach_swot_df.
    """
    section(config, state, "2-1-1-1 OPTIONAL: CLEAN SWOT DF")

    if state.invalid_reach:
        log(config, state, "Skipped SWOT cleaning because invalid_reach=True")
        state.swot_dc_reach_swot_df_clean = make_empty_swot_df(config)
        return

    try:
        df = state.swot_dc_reach_swot_df

        if C.SWOT_INTERNAL_CLEANING_APPLY:
            log(config, state, "SWOT cleaning is applied")
            cleaning_mask = pd.Series(True, index=df.index)

            # NaN / NaT removal on key numeric and string columns
            for col in [C.NAME_SWOT_WSE, C.NAME_SWOT_TIME_COL, C.NAME_SWOT_TIME_STR_COL]:
                if col in df.columns:
                    cleaning_mask &= df[col].notna()
                else:
                    warn(config, state, f"NaN cleaning not applied: missing column '{col}'")

            # Custom criteria from constants
            for col, criterion in C.SWOT_CLEAN_CRITERIA.items():
                if col in df.columns:
                    cleaning_mask &= criterion(df[col])
                else:
                    warn(config, state, f"SWOT cleaning not applied: missing column '{col}'")

            state.swot_dc_reach_swot_df_clean = df[cleaning_mask].copy()
            state.swot_dc_reach_swot_df.loc[~cleaning_mask, C.SWOT_STATUS_COLNAME] = C.SWOT_STATUS_CLEANED

        else:
            log(config, state, "SWOT cleaning is skipped")
            cleaning_mask = pd.Series(True, index=df.index)
            state.swot_dc_reach_swot_df_clean = df.copy()

        # Ensure datetime column is present in the cleaned dataframe
        clean_df = state.swot_dc_reach_swot_df_clean
        if C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME not in clean_df.columns:
            if C.NAME_SWOT_TIME_STR_COL in clean_df.columns:
                clean_df[C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME] = pd.to_datetime(
                    clean_df[C.NAME_SWOT_TIME_STR_COL], errors="coerce", utc=True
                )
            else:
                warn(config, state,
                     f"Datetime conversion not applied: missing column '{C.NAME_SWOT_TIME_STR_COL}'")

        log_vars(
            config, state,
            swot_internal_cleaning_apply=C.SWOT_INTERNAL_CLEANING_APPLY,
            cleaning_mask_true=cleaning_mask.sum(),
            cleaning_mask_false=(~cleaning_mask).sum(),
            swot_dc_reach_swot_df_shape=df.shape,
            swot_dc_reach_swot_df_clean_shape=state.swot_dc_reach_swot_df_clean.shape,
        )
        log_block(config, state, "swot_dc_reach_swot_df_clean_head", state.swot_dc_reach_swot_df_clean.head())

    except Exception as exc:
        fail(config, state, f"SWOT cleaning failed: {exc}", detailed_code=-310)
        state.swot_dc_reach_swot_df_clean = make_empty_swot_df(config)


def filter_swot(config: QQConfig, state: QQState) -> None:
    """
    Remove rows based on SWOT quality flag (reach_q == 3 → bad quality).

    Filtering is controlled by C.SWOT_INTERNAL_FILTERING_APPLY.
    Applied to swot_dc_reach_swot_df_clean.
    """
    section(config, state, "2-1-1-2 OPTIONAL: FILTER CLEANED SWOT DF")

    if state.invalid_reach:
        log(config, state, "Skipped SWOT filtering because invalid_reach=True")
        state.swot_dc_reach_swot_df_clean_filt = make_empty_swot_df(config)
        state.swot_dc_nt_2_swot_clean_filt = 0
        return

    try:
        clean_df = state.swot_dc_reach_swot_df_clean

        if C.SWOT_INTERNAL_FILTERING_APPLY:
            log(config, state, "SWOT filtering is applied")
            active = {
                k: f for k, f in C.SWOT_FILT_CRITERIA.items()
                if k in clean_df.columns
            }
            for k in C.SWOT_FILT_CRITERIA:
                if k not in clean_df.columns:
                    warn(config, state, f"SWOT filter not applied: missing column '{k}'")

            if active:
                mask = pd.concat(
                    {k: f(clean_df[k]) for k, f in active.items()}, axis=1
                ).all(axis=1)
            else:
                mask = pd.Series(True, index=clean_df.index)

            state.swot_dc_reach_swot_df_clean_filt = clean_df[mask].copy()

            # Back-propagate filter status to the full (original) dataframe
            filtered_out_ids = clean_df.loc[~mask, C.SWOT_TIME_INDEX_COLNAME]
            full_df = state.swot_dc_reach_swot_df
            full_df.loc[
                full_df[C.SWOT_TIME_INDEX_COLNAME].isin(filtered_out_ids),
                C.SWOT_STATUS_COLNAME,
            ] = C.SWOT_STATUS_FILTERED

        else:
            log(config, state, "SWOT filtering is skipped")
            active = {}
            mask = pd.Series(True, index=clean_df.index)
            state.swot_dc_reach_swot_df_clean_filt = clean_df.copy()

        state.swot_dc_nt_2_swot_clean_filt = len(state.swot_dc_reach_swot_df_clean_filt)

        log_vars(
            config, state,
            swot_internal_filtering_apply=C.SWOT_INTERNAL_FILTERING_APPLY,
            swot_filter_criteria_active=list(active.keys()),
            swot_filt_mask_true=mask.sum(),
            swot_filt_mask_false=(~mask).sum(),
            swot_dc_reach_swot_df_clean_shape=clean_df.shape,
            swot_dc_reach_swot_df_clean_filt_shape=state.swot_dc_reach_swot_df_clean_filt.shape,
            swot_dc_nt_2_swot_clean_filt=state.swot_dc_nt_2_swot_clean_filt,
        )
        log_block(config, state, "swot_dc_reach_swot_df_clean_filt_head",
                  state.swot_dc_reach_swot_df_clean_filt.head())

    except Exception as exc:
        fail(config, state, f"SWOT filtering failed: {exc}", detailed_code=-320)
        state.swot_dc_reach_swot_df_clean_filt = make_empty_swot_df(config)
        state.swot_dc_nt_2_swot_clean_filt = 0


def control_wse_count(config: QQConfig, state: QQState) -> None:
    """
    Gate: invalidate the reach if the number of clean+filtered WSE observations
    is below C.MIN_CLEAN_FILT_SWOT_WSE_LEN.
    """
    section(config, state, "2-1-2 CONTROL: NO. OF SWOT WSE")
    log(config, state, "Control if enough WSE observations exist after cleaning/filtering")

    if state.invalid_reach:
        log(config, state, "Skipped SWOT WSE count control because invalid_reach=True")
        return

    try:
        n = state.swot_dc_nt_2_swot_clean_filt
        if n < C.MIN_CLEAN_FILT_SWOT_WSE_LEN:
            fail(
                config, state,
                f"Invalid reach: only {n} clean/filtered SWOT WSE observations "
                f"(< {C.MIN_CLEAN_FILT_SWOT_WSE_LEN})",
                detailed_code=-321,
            )
        else:
            log(config, state, "Reach passed minimum clean/filtered SWOT WSE count control")
    except Exception as exc:
        fail(config, state, f"SWOT WSE count control failed: {exc}", detailed_code=-321)

    log_vars(
        config, state,
        invalid_reach=state.invalid_reach,
        swot_dc_nt_2_swot_clean_filt=state.swot_dc_nt_2_swot_clean_filt,
        min_clean_filt_swot_wse_len=C.MIN_CLEAN_FILT_SWOT_WSE_LEN,
    )
