"""
qq/wse_quantile.py
==================
WSE quantile computation functions.

Pipeline steps
--------------
empirical_wse_quantile(config, state)
    Build the empirical WSE quantile table from the clean+filtered SWOT WSE
    observations (section 2-1-3 of the original notebook).

deliverable_wse_quantile(config, state)
    Resample the empirical table onto a fixed N-point probability grid to
    produce the standardised deliverable quantile arrays (section 2-1-3-1).

deliverable_wse_flag(config, state)
    Compute the resampling quality flag for the deliverable quantile
    (section 2-1-3-1-1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qq import constants as C
from qq.config import QQConfig
from qq.helpers import interpolate_deliverable_wse_quantile
from qq.logger import fail, log, log_block, log_vars, section, warn
from qq.state import QQState


def empirical_wse_quantile(config: QQConfig, state: QQState) -> None:
    """
    Build state.swot_clean_filt_empirical_wse_quantile_table from the
    clean+filtered SWOT WSE observations.

    The table has columns:
        empirical_rank               (1-based integer)
        empirical_p_non_exceedance   (rank / n, in [1/n, 1])
        empirical_p_exceedance       (1 - p_non_exceedance)
        empirical_wse_quantile       (WSE value at that probability)
    """
    section(config, state, "2-1-3 CREATE EMPIRICAL WSE QUANTILE TABLE")

    if state.invalid_reach:
        log(config, state, "Skipped empirical WSE quantile table because invalid_reach=True")
        return

    try:
        # wse = state.swot_dc_reach_swot_df_clean_filt[C.NAME_SWOT_WSE].astype(float)
        # wse_sorted = wse.sort_values().reset_index(drop=True)
        # n = len(wse_sorted)
        # state.swot_clean_filt_wse_n_valid = n

        # p = np.arange(1, n + 1) / n

        # state.swot_clean_filt_empirical_wse_quantile_table = pd.DataFrame({
        #     "empirical_rank":             np.arange(1, n + 1),
        #     "empirical_p_non_exceedance": p,
        #     "empirical_p_exceedance":     1.0 - p,
        #     "empirical_wse_quantile":     wse_sorted.to_numpy(),
        # })
        
        
        wse = state.swot_dc_reach_swot_df_clean_filt[C.NAME_SWOT_WSE].astype(float)
        wse_sorted = wse.sort_values().reset_index(drop=True)
        n = len(wse_sorted)
        state.swot_clean_filt_wse_n_valid = n

        # Assign empirical non-exceedance probabilities by scaling 1-based rank
        # linearly from WSE_PROB_GRID_MIN_PCT/100 to WSE_PROB_GRID_MAX_PCT/100.
        # Default: rank 1 → 0.00, rank n → 1.00 (both endpoints included).
        p_min = C.WSE_PROB_GRID_MIN_PCT / 100.0
        p_max = C.WSE_PROB_GRID_MAX_PCT / 100.0
        if n == 1:
            p = np.array([0.5 * (p_min + p_max)])
        else:
            p = p_min + (np.arange(1, n + 1) - 1) / (n - 1) * (p_max - p_min)

        state.swot_clean_filt_empirical_wse_quantile_table = pd.DataFrame({
            "empirical_rank":             np.arange(1, n + 1),
            "empirical_p_non_exceedance": p,
            "empirical_p_exceedance":     1.0 - p,
            "empirical_wse_quantile":     wse_sorted.to_numpy(),
        })

        log_vars(config, state, swot_clean_filt_wse_n_valid=n)
        log_block(config, state, "swot_clean_filt_empirical_wse_quantile_table_head",
                  state.swot_clean_filt_empirical_wse_quantile_table.head())

    except Exception as exc:
        fail(config, state, f"Empirical WSE quantile table failed: {exc}", detailed_code=-330)


def deliverable_wse_quantile(config: QQConfig, state: QQState) -> None:
    """
    Resample the empirical WSE quantile onto the configurable probability grid
    defined by C.DELIVERABLE_WSE_PROBABILITY_GRID (default: [0.00, 0.01, …, 1.00],
    101 points, both endpoints included).

    Populates on state:
        QQ_wse_quant_prob         (nwseq array, float64)
        QQ_wse_quant_wse          (nwseq array, float64, fill = QQ_NC_DOUBLE_FILL_VALUE)
        QQ_wse_quant_interp_diag  (dict, for logging)
        swot_wse_quantile_deliverable (dict with prob + wse arrays)
    """
    section(config, state, "2-1-3-1 CREATE DELIVERABLE WSE QUANTILE TABLE / ARRAYS")

    try:
        # n = C.DELIVERABLE_WSE_QUANTILE_TABLE_N
        # state.QQ_wse_quant_prob = np.linspace(1 / n, 1, n).astype(np.float64)
        
        state.QQ_wse_quant_prob = C.DELIVERABLE_WSE_PROBABILITY_GRID.astype(np.float64)

        # Decide whether to produce the quantile
        produce = (not state.invalid_reach) or C.PRODUCE_WSE_QUANTILE_IF_INVALID_REACH

        # Additional gate: if WSE count is below the quantile threshold
        if (
            hasattr(state, "swot_dc_nt_2_swot_clean_filt")
            and state.swot_dc_nt_2_swot_clean_filt < C.MIN_CLEAN_FILT_SWOT_WSE_LEN_FOR_WSE_QUANTILE
        ):
            produce = produce and C.PRODUCE_WSE_QUANTILE_IF_CLEAN_FILT_WSE_BELOW_THRESHOLD

        if (
            produce
            and not state.invalid_reach
            and hasattr(state, "swot_clean_filt_empirical_wse_quantile_table")
        ):
            state.QQ_wse_quant_wse, state.QQ_wse_quant_interp_diag = (
                interpolate_deliverable_wse_quantile(
                    config, state,
                    state.QQ_wse_quant_prob,
                    state.swot_clean_filt_empirical_wse_quantile_table,
                    "empirical_p_non_exceedance",
                    "empirical_wse_quantile",
                    C.DELIVERABLE_WSE_QUANTILE_EXTRAPOLATE_EDGES,
                    C.QQ_NC_DOUBLE_FILL_VALUE,
                )
            )
        else:
            state.QQ_wse_quant_wse = np.full(
                len(state.QQ_wse_quant_prob), C.QQ_NC_DOUBLE_FILL_VALUE, dtype=np.float64
            )
            state.QQ_wse_quant_interp_diag = {
                "n_empirical_rows_used": 0,
                "empirical_prob_min":    np.nan,
                "empirical_prob_max":    np.nan,
                "n_interpolated":        0,
                "n_lower_edge":          0,
                "n_upper_edge":          0,
                "n_edge_missing":        len(state.QQ_wse_quant_prob),
                "n_edge_extrapolated":   0,
                "extrapolate_edges":     C.DELIVERABLE_WSE_QUANTILE_EXTRAPOLATE_EDGES,
            }

        state.swot_wse_quantile_deliverable = {
            C.SWOT_QQ_DELIVERABLE_WSE_QUANT_PROB_NAME: state.QQ_wse_quant_prob,
            C.SWOT_QQ_DELIVERABLE_WSE_QUANT_WSE_NAME:  state.QQ_wse_quant_wse,
        }

        log_vars(
            config, state,
            # deliverable_wse_quantile_table_n=n,
            deliverable_wse_quantile_table_n=len(state.QQ_wse_quant_prob),
            QQ_wse_quant_prob_len=len(state.QQ_wse_quant_prob),
            QQ_wse_quant_wse_len=len(state.QQ_wse_quant_wse),
            invalid_reach=state.invalid_reach,
            deliverable_wse_quantile_extrapolate_edges=C.DELIVERABLE_WSE_QUANTILE_EXTRAPOLATE_EDGES,
            QQ_wse_quant_interp_diag=state.QQ_wse_quant_interp_diag,
        )
        log_block(config, state, "QQ_wse_quant_prob_sample", state.QQ_wse_quant_prob[:5])
        log_block(config, state, "QQ_wse_quant_wse_sample",  state.QQ_wse_quant_wse[:5])

    except Exception as exc:
        # fail(config, state, f"Deliverable WSE quantile table failed: {exc}", detailed_code=-331)
        # n = C.DELIVERABLE_WSE_QUANTILE_TABLE_N
        # state.QQ_wse_quant_prob = np.linspace(1 / n, 1, n).astype(np.float64)
        # state.QQ_wse_quant_wse  = np.full(
        #     len(state.QQ_wse_quant_prob), C.QQ_NC_DOUBLE_FILL_VALUE, dtype=np.float64
        # )
        # state.QQ_wse_quant_interp_diag = {
        #     "n_empirical_rows_used": 0, "empirical_prob_min": np.nan,
        #     "empirical_prob_max": np.nan, "n_interpolated": 0,
        #     "n_lower_edge": 0, "n_upper_edge": 0,
        #     "n_edge_missing": len(state.QQ_wse_quant_prob),
        #     "n_edge_extrapolated": 0,
        #     "extrapolate_edges": C.DELIVERABLE_WSE_QUANTILE_EXTRAPOLATE_EDGES,
        # }
        
        fail(config, state, f"Deliverable WSE quantile table failed: {exc}", detailed_code=-331)
        state.QQ_wse_quant_prob = C.DELIVERABLE_WSE_PROBABILITY_GRID.astype(np.float64)
        state.QQ_wse_quant_wse  = np.full(
            len(state.QQ_wse_quant_prob), C.QQ_NC_DOUBLE_FILL_VALUE, dtype=np.float64
        )
        state.QQ_wse_quant_interp_diag = {
            "n_empirical_rows_used": 0, "empirical_prob_min": np.nan,
            "empirical_prob_max": np.nan, "n_interpolated": 0,
            "n_lower_edge": 0, "n_upper_edge": 0,
            "n_edge_missing": len(state.QQ_wse_quant_prob),
            "n_edge_extrapolated": 0,
            "extrapolate_edges": C.DELIVERABLE_WSE_QUANTILE_EXTRAPOLATE_EDGES,
        }


def deliverable_wse_flag(config: QQConfig, state: QQState) -> None:
    """
    Compute the WSE quantile resampling quality flag.

    Flag meaning:
        0       same length (n_standard == n_empirical)
        +k      downsampled by factor in the k-th threshold bin
        -k      upsampled by factor in the k-th threshold bin
        -999    all WSE quantile values are missing
    """
    section(config, state, "2-1-3-1-1 CREATE FLAG FOR DELIVERABLE WSE QUANTILE TABLE / ARRAYS")

    try:
        if np.all(state.QQ_wse_quant_wse == C.QQ_NC_DOUBLE_FILL_VALUE):
            # All missing
            n_std = len(state.QQ_wse_quant_prob)
            n_emp = np.nan
            pct_change = np.nan
            state.QQ_wse_quant_flag = C.WSE_QUANT_FLAG_DTYPE(C.WSE_QUANT_FLAG_ALL_MISSING_VALUE)

        elif not state.invalid_reach:
            n_std = len(state.QQ_wse_quant_prob)
            n_emp = state.swot_clean_filt_wse_n_valid
            pct_change = abs(n_std - n_emp) / n_emp

            if n_std == n_emp:
                raw_flag = 0
            else:
                bin_idx = int(np.searchsorted(C.WSE_QUANT_FLAG_THRESHOLDS, pct_change, side="left")) + 1
                raw_flag = int(np.sign(n_emp - n_std)) * bin_idx

            state.QQ_wse_quant_flag = C.WSE_QUANT_FLAG_DTYPE(raw_flag)

        else:
            n_std = len(state.QQ_wse_quant_prob)
            n_emp = np.nan
            pct_change = np.nan
            state.QQ_wse_quant_flag = C.WSE_QUANT_FLAG_DTYPE(C.WSE_QUANT_FLAG_ALL_MISSING_VALUE)

        # Add to the deliverable dict
        if hasattr(state, "swot_wse_quantile_deliverable"):
            state.swot_wse_quantile_deliverable[C.SWOT_QQ_DELIVERABLE_WSE_QUANT_FLAG_NAME] = (
                state.QQ_wse_quant_flag
            )

        log_vars(
            config, state,
            n_std=n_std, n_emp=n_emp, pct_change=pct_change,
            QQ_wse_quant_flag=state.QQ_wse_quant_flag,
            invalid_reach=state.invalid_reach,
        )

    except Exception as exc:
        fail(config, state, f"Deliverable WSE quantile flag failed: {exc}", detailed_code=-331)
        state.QQ_wse_quant_flag = C.WSE_QUANT_FLAG_DTYPE(C.WSE_QUANT_FLAG_ALL_MISSING_VALUE)
