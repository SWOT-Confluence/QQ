"""
qq/input_sos.py
===============
Read the SOS (Seasonal Observations and Statistics) NetCDF and extract the
Flow Duration Curve (FDC) for the current reach.

Exact logic from notebook section 2-2 (READ SOS AND EXTRACT REACH-FDC TABLE).

SOS file structure expected:
    Group 'reaches':  reach_id [n_reaches]
    Group 'model':    probability [n_prob]  (stored as percentages 0-100, divided by 100 here)
                      flow_duration_q [n_reaches, n_prob]
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from qq import constants as C
from qq.config import QQConfig
from qq.helpers import get_nc_var_metadata, make_empty_sos_fdc_table
from qq.logger import fail, log, log_block, log_vars, section, warn
from qq.state import QQState


def read_sos(config: QQConfig, state: QQState) -> None:
    """
    Open the SOS NetCDF and build state.sos_fdc_table for the current reach.

    On success, state.sos_fdc_table is a DataFrame with columns:
        rank, p_non_exceedance, p_exceedance, discharge_quantile
    sorted by p_non_exceedance, with only valid (finite) rows.

    On any failure, state.invalid_reach is set True via fail(), and
    state.sos_fdc_table is set to an empty DataFrame.
    """
    section(config, state, "2-2 READ SOS AND EXTRACT REACH-FDC TABLE")

    if state.invalid_reach:
        log(config, state, "Skipped SOS FDC extraction because invalid_reach=True")
        state.sos_fdc_table = make_empty_sos_fdc_table()
        return

    # Local references for variables that may not be assigned if we fail early
    sos_reach_ids = None
    sos_rid_matches = None
    sos_rid_ridx = None
    fdc_missing_perc = None
    fdc_longest_missing_gap = None

    try:
        # ------------------------------------------------------------------
        # File existence check
        # ------------------------------------------------------------------
        if state.input_sos_path is None or not Path(state.input_sos_path).exists():
            fail(config, state, f"SOS file not found: {state.input_sos_path}", detailed_code=-401)
            state.sos_fdc_table = make_empty_sos_fdc_table()
            return

        from netCDF4 import Dataset  # type: ignore

        sos_dc = Dataset(state.input_sos_path)

        # ------------------------------------------------------------------
        # Group existence checks
        # ------------------------------------------------------------------
        if C.NAME_SOS_REACHES_GP not in sos_dc.groups:
            fail(config, state, f"Missing SOS group: {C.NAME_SOS_REACHES_GP}", detailed_code=-403)

        if C.NAME_SOS_MODEL_GP not in sos_dc.groups:
            fail(config, state, f"Missing SOS group: {C.NAME_SOS_MODEL_GP}", detailed_code=-403)

        if state.invalid_reach:
            state.sos_fdc_table = make_empty_sos_fdc_table()
            return

        sos_dc_reaches_gp = sos_dc[C.NAME_SOS_REACHES_GP]
        sos_dc_model_gp   = sos_dc[C.NAME_SOS_MODEL_GP]

        # ------------------------------------------------------------------
        # Variable existence checks
        # ------------------------------------------------------------------
        if C.NAME_SOS_REACHES_GP_REACH_ID_VAR not in sos_dc_reaches_gp.variables:
            fail(config, state,
                 f"Missing SOS reaches variable: {C.NAME_SOS_REACHES_GP_REACH_ID_VAR}",
                 detailed_code=-403)

        for sos_var_name in [C.NAME_SOS_MODEL_GP_PROB_VAR, C.NAME_SOS_MODEL_GP_FDC_VAR]:
            if sos_var_name in sos_dc_model_gp.variables:
                state.sos_variable_nc_metadata[sos_var_name] = get_nc_var_metadata(
                    sos_dc_model_gp[sos_var_name]
                )
            else:
                fail(config, state, f"Missing SOS model variable: {sos_var_name}", detailed_code=-403)

        if state.invalid_reach:
            state.sos_fdc_table = make_empty_sos_fdc_table()
            return

        # Optional SOS variables — collect metadata if present (non-fatal if absent)
        for sos_var_name in [C.NAME_SOS_MODEL_GP_QMIN_VAR, C.NAME_SOS_MODEL_GP_QMAX_VAR]:
            if sos_var_name in sos_dc_model_gp.variables:
                state.sos_variable_nc_metadata[sos_var_name] = get_nc_var_metadata(
                    sos_dc_model_gp[sos_var_name]
                )

        # ------------------------------------------------------------------
        # Reach ID lookup
        # ------------------------------------------------------------------
        sos_reach_ids = np.asarray(sos_dc_reaches_gp[C.NAME_SOS_REACHES_GP_REACH_ID_VAR][:])
        sos_rid_matches = np.where(
            sos_reach_ids == np.asarray(state.rid, dtype=sos_reach_ids.dtype)
        )[0]

        if len(sos_rid_matches) == 0:
            fail(config, state,
                 f"Invalid reach: reach_id '{state.rid}' not found in SOS file",
                 detailed_code=-404)
            state.sos_fdc_table = make_empty_sos_fdc_table()
            return

        sos_rid_ridx = sos_rid_matches.item()

        # ------------------------------------------------------------------
        # Read and validate probability array
        # ------------------------------------------------------------------
        # SOS stores probabilities as percentages (0-100); divide by 100 to get [0, 1].
        sos_model_gp_prob = np.asarray(
            sos_dc_model_gp[C.NAME_SOS_MODEL_GP_PROB_VAR][:],
            dtype=float,
        ) / 100.0

        if np.any(~np.isfinite(sos_model_gp_prob)):
            fail(config, state, "SOS probability contains non-finite values", detailed_code=-410)
        elif np.nanmin(sos_model_gp_prob) < 0 or np.nanmax(sos_model_gp_prob) > 1:
            fail(config, state, "SOS probability outside [0, 1]", detailed_code=-410)
        elif not np.all(np.diff(sos_model_gp_prob) >= 0):
            warn(config, state,
                 "SOS probability is not monotonically increasing; "
                 "SOS FDC table will be sorted before interpolation")

        if state.invalid_reach:
            state.sos_fdc_table = make_empty_sos_fdc_table()
            return

        # ------------------------------------------------------------------
        # Read FDC for this reach
        # ------------------------------------------------------------------
        sos_rid_fdc = np.ma.asarray(
            sos_dc_model_gp[C.NAME_SOS_MODEL_GP_FDC_VAR][sos_rid_ridx]
        ).squeeze()
        sos_rid_fdc_arr = np.ma.asarray(sos_rid_fdc).filled(np.nan).astype(float)

        # Quality gates: missing percentage, consecutive gap length, minimum valid count
        fdc_missing_mask = ~np.isfinite(sos_rid_fdc_arr)
        fdc_missing_perc = 100.0 * fdc_missing_mask.sum() / len(sos_model_gp_prob)

        fdc_gap_groups = np.split(
            fdc_missing_mask,
            np.where(np.diff(fdc_missing_mask.astype(int)) != 0)[0] + 1,
        )
        fdc_longest_missing_gap = max(
            (len(g) for g in fdc_gap_groups if len(g) > 0 and g[0]),
            default=0,
        )

        if fdc_missing_perc > C.FDC_MAX_MISSING_PERC_TO_PROCEED:
            fail(config, state,
                 f"SOS FDC missing percentage too high: "
                 f"{fdc_missing_perc:.1f}% > {C.FDC_MAX_MISSING_PERC_TO_PROCEED}%",
                 detailed_code=-420)
        elif fdc_longest_missing_gap > C.FDC_MAX_CONSECUTIVE_MISSING_GAP_TO_PROCEED:
            fail(config, state,
                 f"SOS FDC longest missing gap too long: "
                 f"{fdc_longest_missing_gap} > {C.FDC_MAX_CONSECUTIVE_MISSING_GAP_TO_PROCEED}",
                 detailed_code=-421)
        elif (~fdc_missing_mask).sum() < C.MIN_VALID_SOS_FDC_LEN:
            fail(config, state, "SOS FDC has fewer than 2 valid values", detailed_code=-422)

        if state.invalid_reach:
            state.sos_fdc_table = make_empty_sos_fdc_table()
            return

        # ------------------------------------------------------------------
        # Build the FDC table (valid rows only, sorted by p_non_exceedance)
        # ------------------------------------------------------------------
        is_valid = ~fdc_missing_mask
        state.sos_fdc_table = pd.DataFrame({
            "rank":               np.arange(1, is_valid.sum() + 1),
            "p_non_exceedance":   sos_model_gp_prob[is_valid],
            "p_exceedance":       1.0 - sos_model_gp_prob[is_valid],
            "discharge_quantile": sos_rid_fdc_arr[is_valid],
        }).sort_values("p_non_exceedance").reset_index(drop=True)

        log_vars(
            config, state,
            sos_reach_ids_len=len(sos_reach_ids) if sos_reach_ids is not None else None,
            sos_rid_matches=sos_rid_matches,
            sos_rid_ridx=sos_rid_ridx,
            fdc_missing_perc=fdc_missing_perc,
            fdc_longest_missing_gap=fdc_longest_missing_gap,
            sos_fdc_table_shape=state.sos_fdc_table.shape,
        )
        log_block(config, state, "sos_fdc_table_head", state.sos_fdc_table.head())

        # ------------------------------------------------------------------
        # Step 2-2-1  OPTIONAL: Extend SOS FDC to [q_min, q_max] endpoints
        # Gate: FDC table was built successfully above (we would have returned
        # earlier if any FDC quality gate failed).
        # ------------------------------------------------------------------
        section(config, state, "2-2-1 OPTIONAL: EXTEND SOS FDC TO q_min/q_max ENDPOINTS")

        if config.use_extended_fdc_from_sos_qminmax:
            try:
                # ---- Read q_min ----
                if C.NAME_SOS_MODEL_GP_QMIN_VAR not in sos_dc_model_gp.variables:
                    warn(config, state,
                         f"FDC extension: variable '{C.NAME_SOS_MODEL_GP_QMIN_VAR}' not found "
                         "in SOS model group; falling back to original FDC")
                    state.sos_fdc_extended_flag = C.SOS_FDC_EXTENDED_FLAG_FAILED_QMIN
                else:
                    q_min_val = float(np.squeeze(
                        np.ma.asarray(
                            sos_dc_model_gp[C.NAME_SOS_MODEL_GP_QMIN_VAR][sos_rid_ridx]
                        ).filled(np.nan)
                    ))

                    # ---- Read q_max ----
                    if C.NAME_SOS_MODEL_GP_QMAX_VAR not in sos_dc_model_gp.variables:
                        warn(config, state,
                             f"FDC extension: variable '{C.NAME_SOS_MODEL_GP_QMAX_VAR}' not found "
                             "in SOS model group; falling back to original FDC")
                        state.sos_fdc_extended_flag = C.SOS_FDC_EXTENDED_FLAG_FAILED_QMAX
                    else:
                        q_max_val = float(np.squeeze(
                            np.ma.asarray(
                                sos_dc_model_gp[C.NAME_SOS_MODEL_GP_QMAX_VAR][sos_rid_ridx]
                            ).filled(np.nan)
                        ))

                        # ---- Validate q_min ----
                        if not np.isfinite(q_min_val) or q_min_val < 0:
                            warn(config, state,
                                 f"FDC extension: q_min is invalid ({q_min_val:.6g}); "
                                 "falling back to original FDC")
                            state.sos_fdc_extended_flag = C.SOS_FDC_EXTENDED_FLAG_FAILED_QMIN

                        # ---- Validate q_max ----
                        elif not np.isfinite(q_max_val) or q_max_val < 0:
                            warn(config, state,
                                 f"FDC extension: q_max is invalid ({q_max_val:.6g}); "
                                 "falling back to original FDC")
                            state.sos_fdc_extended_flag = C.SOS_FDC_EXTENDED_FLAG_FAILED_QMAX

                        elif q_max_val < q_min_val:
                            warn(config, state,
                                 f"FDC extension: q_max ({q_max_val:.4f}) < q_min ({q_min_val:.4f}); "
                                 "falling back to original FDC")
                            state.sos_fdc_extended_flag = C.SOS_FDC_EXTENDED_FLAG_FAILED_QMAX

                        else:
                            # ---- Build extension rows ----
                            p_lo = C.FDC_EXTENDED_PROB_AT_QMIN
                            p_hi = C.FDC_EXTENDED_PROB_AT_QMAX

                            fdc_orig = state.sos_fdc_table.copy()
                            ext_parts = []

                            # Prepend q_min at p=0.0 only if not already present
                            if not np.any(np.isclose(fdc_orig["p_non_exceedance"].values, p_lo)):
                                ext_parts.append(pd.DataFrame([{
                                    "rank":               0,
                                    "p_non_exceedance":   p_lo,
                                    "p_exceedance":       1.0 - p_lo,
                                    "discharge_quantile": q_min_val,
                                }]))
                                log(config, state,
                                    f"FDC extension: prepending p={p_lo} with "
                                    f"q_min={q_min_val:.4f} m3/s")
                            else:
                                log(config, state,
                                    f"FDC extension: p={p_lo} already present in FDC; "
                                    "q_min row not prepended")

                            ext_parts.append(fdc_orig)

                            # Append q_max at p=1.0 only if not already present
                            if not np.any(np.isclose(fdc_orig["p_non_exceedance"].values, p_hi)):
                                ext_parts.append(pd.DataFrame([{
                                    "rank":               len(fdc_orig) + 1,
                                    "p_non_exceedance":   p_hi,
                                    "p_exceedance":       1.0 - p_hi,
                                    "discharge_quantile": q_max_val,
                                }]))
                                log(config, state,
                                    f"FDC extension: appending p={p_hi} with "
                                    f"q_max={q_max_val:.4f} m3/s")
                            else:
                                log(config, state,
                                    f"FDC extension: p={p_hi} already present in FDC; "
                                    "q_max row not appended")

                            # ---- Assemble and validate ----
                            fdc_extended = (
                                pd.concat(ext_parts, ignore_index=True)
                                .sort_values("p_non_exceedance")
                                .reset_index(drop=True)
                            )

                            if len(fdc_extended) < C.MIN_VALID_SOS_FDC_LEN:
                                warn(config, state,
                                     "FDC extension produced a table shorter than "
                                     f"MIN_VALID_SOS_FDC_LEN ({C.MIN_VALID_SOS_FDC_LEN}); "
                                     "falling back to original FDC")
                                state.sos_fdc_extended_flag = C.SOS_FDC_EXTENDED_FLAG_FAILED_CREATION

                            else:
                                # ---- Success: replace FDC table ----
                                state.sos_fdc_table = fdc_extended
                                state.sos_fdc_extended_flag = C.SOS_FDC_EXTENDED_FLAG_SUCCESS

                                log_vars(
                                    config, state,
                                    q_min=q_min_val,
                                    q_max=q_max_val,
                                    fdc_original_len=len(fdc_orig),
                                    fdc_extended_len=len(fdc_extended),
                                    fdc_extended_p_min=fdc_extended["p_non_exceedance"].min(),
                                    fdc_extended_p_max=fdc_extended["p_non_exceedance"].max(),
                                    sos_fdc_extended_flag=state.sos_fdc_extended_flag,
                                )
                                log_block(config, state,
                                          "sos_fdc_extended_head", state.sos_fdc_table.head())
                                log_block(config, state,
                                          "sos_fdc_extended_tail", state.sos_fdc_table.tail())

            except Exception as ext_exc:
                warn(config, state,
                     f"FDC extension failed with unexpected error: {ext_exc}; "
                     "falling back to original FDC")
                state.sos_fdc_extended_flag = C.SOS_FDC_EXTENDED_FLAG_FAILED_CREATION

        else:
            state.sos_fdc_extended_flag = C.SOS_FDC_EXTENDED_FLAG_NOT_ATTEMPTED
            log(config, state,
                "FDC extension not attempted (use_extended_fdc_from_sos_qMinMax=False); "
                "using original FDC")

    except Exception as exc:
        fail(config, state, f"SOS FDC extraction failed: {exc}", detailed_code=-402)
        state.sos_fdc_table = make_empty_sos_fdc_table()
