"""
qq/lookup_table.py
===================
WSE–Q lookup table: relates WSE and discharge Q through the shared
non-exceedance probability axis, restricted to the overlap of the
empirical WSE quantile probability range and the SOS FDC probability
range.  No extrapolation is performed for either WSE or Q.

This is an AUXILIARY deliverable. Failure to produce it does not, by
itself, mark the reach invalid — it fails gracefully to an all-missing
table with a diagnostic flag, unless an existing upstream gate has
already marked the reach invalid.

Pipeline step
-------------
build_lookup_table(config, state)
    Runs after read_sos() and before quantile_matching().
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qq import constants as C
from qq.config import QQConfig
from qq.logger import log, log_block, log_vars, section, warn
from qq.state import QQState


def _build_lookup_probability_grid(p_min: float, p_max: float, step: float) -> np.ndarray:
    """
    Build the lookup probability grid over [p_min, p_max] with exact endpoints.

    Design:
      - The grid always starts at exactly p_min and ends at exactly p_max
        (both included verbatim, even if not on the step lattice).
      - Interior points are the regular step lattice values strictly
        between p_min and p_max (i.e. round multiples of `step` that fall
        inside the open interval), so no interior value is closer to an
        endpoint than necessary and no interior value duplicates an
        endpoint.
      - If p_min and p_max are closer together than `step`, the grid is
        just the two endpoints (or one point if p_min == p_max).

    Example (step=0.01): overlap [0.013, 0.957] ->
        [0.013, 0.02, 0.03, ..., 0.95, 0.957]
    Example (step=0.01): overlap [0.01, 0.96] ->
        [0.01, 0.02, ..., 0.96]   (endpoints already on-lattice; no duplicates)
    """
    if p_max < p_min:
        return np.array([], dtype=np.float64)
    if np.isclose(p_max, p_min):
        return np.array([p_min], dtype=np.float64)

    # First on-lattice value strictly greater than p_min (or equal, if p_min is on-lattice)
    first_idx = np.ceil(round(p_min / step, 9))
    first_on_lattice = first_idx * step

    # Last on-lattice value strictly less than p_max (or equal, if p_max is on-lattice)
    last_idx = np.floor(round(p_max / step, 9))
    last_on_lattice = last_idx * step

    if first_on_lattice > last_on_lattice + 1e-9:
        interior = np.array([], dtype=np.float64)
    else:
        n_interior = int(round((last_on_lattice - first_on_lattice) / step)) + 1
        interior = first_on_lattice + np.arange(n_interior) * step

    # Drop interior points that coincide with the endpoints (avoid duplicates)
    interior = interior[~np.isclose(interior, p_min) & ~np.isclose(interior, p_max)]

    grid = np.concatenate(([p_min], interior, [p_max]))
    return np.round(grid, 12)


def _interpolate_no_extrapolate(
    target_prob: np.ndarray,
    source_prob: np.ndarray,
    source_value: np.ndarray,
    missing_value: float,
) -> np.ndarray:
    """
    Linear interpolation only — NO extrapolation.
    Exact-match probabilities use the source value directly (via np.interp,
    which already returns the exact endpoint value at exact matches).
    Any target probability outside [source_prob.min(), source_prob.max()]
    receives missing_value.
    """
    out = np.full(len(target_prob), missing_value, dtype=np.float64)
    if len(source_prob) < 2:
        return out
    p_lo, p_hi = source_prob[0], source_prob[-1]
    inside = (target_prob >= p_lo) & (target_prob <= p_hi)
    if inside.any():
        out[inside] = np.interp(target_prob[inside], source_prob, source_value)
    return out


def build_lookup_table(config: QQConfig, state: QQState) -> None:
    """
    Build the WSE-Q lookup table (auxiliary deliverable).

    Populates on state:
        QQ_lookup_table_prob   (nlookup array, float64)
        QQ_lookup_table_wse    (nlookup array, float64, fill = QQ_NC_DOUBLE_FILL_VALUE)
        QQ_lookup_table_q      (nlookup array, float64, fill = QQ_NC_DOUBLE_FILL_VALUE)
        QQ_lookup_table_flag   (scalar, int16)

    Does NOT call fail() / does NOT set state.invalid_reach — this is an
    auxiliary deliverable and must fail gracefully. If the reach is
    already invalid via existing gates, the table is still (correctly)
    produced as all-missing, consistent with existing WSE-quantile
    fail-safe behaviour.
    """
    section(config, state, "2-3 CREATE WSE-Q LOOKUP TABLE (AUXILIARY DELIVERABLE)")

    reason = None
    lookup_prob_min = np.nan
    lookup_prob_max = np.nan
    n_lookup = 0
    n_emp = np.nan

    try:
        emp_table = getattr(state, "swot_clean_filt_empirical_wse_quantile_table", None)
        fdc_table = getattr(state, "sos_fdc_table", None)

        emp_ok = (
            isinstance(emp_table, pd.DataFrame)
            and len(emp_table) > 0
            and "empirical_p_non_exceedance" in emp_table.columns
            and "empirical_wse_quantile" in emp_table.columns
        )
        fdc_ok = (
            isinstance(fdc_table, pd.DataFrame)
            and len(fdc_table) >= C.MIN_VALID_SOS_FDC_LEN
            and "p_non_exceedance" in fdc_table.columns
            and "discharge_quantile" in fdc_table.columns
        )

        if not emp_ok:
            reason = C.LOOKUP_TABLE_FAIL_REASON_EMPIRICAL_WSE_UNAVAILABLE
        elif not fdc_ok:
            reason = C.LOOKUP_TABLE_FAIL_REASON_SOS_FDC_UNAVAILABLE

        if reason is None:
            emp_sorted = emp_table.sort_values("empirical_p_non_exceedance").reset_index(drop=True)
            fdc_sorted = fdc_table.sort_values("p_non_exceedance").reset_index(drop=True)

            emp_p = emp_sorted["empirical_p_non_exceedance"].to_numpy(dtype=float)
            emp_wse = emp_sorted["empirical_wse_quantile"].to_numpy(dtype=float)
            fdc_p = fdc_sorted["p_non_exceedance"].to_numpy(dtype=float)
            fdc_q = fdc_sorted["discharge_quantile"].to_numpy(dtype=float)

            n_emp = len(emp_p)

            lookup_prob_min = max(emp_p[0], fdc_p[0])
            lookup_prob_max = min(emp_p[-1], fdc_p[-1])

            if lookup_prob_min > lookup_prob_max:
                reason = C.LOOKUP_TABLE_FAIL_REASON_EMPTY_PROBABILITY_OVERLAP

        if reason is None:
            grid = _build_lookup_probability_grid(
                lookup_prob_min, lookup_prob_max, C.LOOKUP_TABLE_PROB_STEP_PERCENT / 100.0
            )
            n_lookup = len(grid)

            if n_lookup < C.LOOKUP_TABLE_MIN_ROWS:
                reason = C.LOOKUP_TABLE_FAIL_REASON_TOO_FEW_ROWS

        if reason is None:
            wse_vals = _interpolate_no_extrapolate(grid, emp_p, emp_wse, C.QQ_NC_DOUBLE_FILL_VALUE)
            q_vals   = _interpolate_no_extrapolate(grid, fdc_p, fdc_q,  C.QQ_NC_DOUBLE_FILL_VALUE)

            if np.all(wse_vals == C.QQ_NC_DOUBLE_FILL_VALUE) or np.all(q_vals == C.QQ_NC_DOUBLE_FILL_VALUE):
                reason = C.LOOKUP_TABLE_FAIL_REASON_INTERPOLATION_FAILED

        if reason is not None:
            warn(config, state, f"WSE-Q lookup table not produced: {reason}")
            state.QQ_lookup_table_prob = np.array([], dtype=np.float64)
            state.QQ_lookup_table_wse  = np.array([], dtype=np.float64)
            state.QQ_lookup_table_q    = np.array([], dtype=np.float64)
            state.QQ_lookup_table_flag = C.LOOKUP_TABLE_FLAG_DTYPE(C.LOOKUP_TABLE_FLAG_ALL_MISSING_VALUE)
            state.QQ_lookup_table_fail_reason = reason
        else:
            state.QQ_lookup_table_prob = grid.astype(np.float64)
            state.QQ_lookup_table_wse  = wse_vals.astype(np.float64)
            state.QQ_lookup_table_q    = q_vals.astype(np.float64)
            state.QQ_lookup_table_fail_reason = ""

            pct_change = abs(n_lookup - n_emp) / n_emp if n_emp else np.nan
            if n_lookup == n_emp:
                raw_flag = 0
            else:
                bin_idx = int(np.searchsorted(C.WSE_QUANT_FLAG_THRESHOLDS, pct_change, side="left")) + 1
                raw_flag = int(np.sign(n_emp - n_lookup)) * bin_idx
            state.QQ_lookup_table_flag = C.LOOKUP_TABLE_FLAG_DTYPE(raw_flag)

        log_vars(
            config, state,
            lookup_prob_min=lookup_prob_min,
            lookup_prob_max=lookup_prob_max,
            n_lookup=n_lookup,
            n_emp=n_emp,
            lookup_fail_reason=reason,
            QQ_lookup_table_flag=state.QQ_lookup_table_flag,
        )
        log_block(config, state, "QQ_lookup_table_prob_sample", state.QQ_lookup_table_prob[:5])
        log_block(config, state, "QQ_lookup_table_wse_sample",  state.QQ_lookup_table_wse[:5])
        log_block(config, state, "QQ_lookup_table_q_sample",    state.QQ_lookup_table_q[:5])

    except Exception as exc:
        # Auxiliary deliverable: log and degrade gracefully, do NOT fail() the reach.
        warn(config, state, f"WSE-Q lookup table build failed unexpectedly: {exc}")
        state.QQ_lookup_table_prob = np.array([], dtype=np.float64)
        state.QQ_lookup_table_wse  = np.array([], dtype=np.float64)
        state.QQ_lookup_table_q    = np.array([], dtype=np.float64)
        state.QQ_lookup_table_flag = C.LOOKUP_TABLE_FLAG_DTYPE(C.LOOKUP_TABLE_FLAG_ALL_MISSING_VALUE)
        state.QQ_lookup_table_fail_reason = C.LOOKUP_TABLE_FAIL_REASON_UNEXPECTED_ERROR