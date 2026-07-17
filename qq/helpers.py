"""
qq/helpers.py
=============
Shared utility functions used by multiple modules in the QQ pipeline.

All numerical/interpolation logic below is taken verbatim from the
original notebook (0_qq_original_code.ipynb) and must not be altered
without scientific review.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from qq.config import QQConfig
    from qq.state import QQState


# ---------------------------------------------------------------------------
# NetCDF helpers
# ---------------------------------------------------------------------------

def nc_char_array_to_strings(arr, fill_value=b"") -> list:
    """Convert a masked char array to a list of plain Python strings."""
    arr = np.ma.asarray(arr).filled(fill_value)
    out = []
    for row in arr:
        row_arr = np.asarray(row)
        chars = []
        for item in row_arr:
            if np.ma.is_masked(item):
                chars.append("")
            elif isinstance(item, bytes):
                chars.append(item.decode("utf-8", errors="ignore"))
            else:
                chars.append(str(item))
        out.append("".join(chars).strip())
    return out


def get_nc_var_metadata(nc_var) -> dict:
    """Return a metadata dict for a netCDF4 Variable."""
    return {
        "dtype":         str(getattr(nc_var, "dtype", "")),
        "ndim":          getattr(nc_var, "ndim", None),
        "dimensions":    getattr(nc_var, "dimensions", None),
        "_FillValue":    getattr(nc_var, "_FillValue", None),
        "missing_value": getattr(nc_var, "missing_value", None),
        "units":         getattr(nc_var, "units", None),
        "long_name":     getattr(nc_var, "long_name", None),
    }


# ---------------------------------------------------------------------------
# Empty-dataframe constructors
# ---------------------------------------------------------------------------

def make_empty_swot_df(config) -> pd.DataFrame:
    from qq import constants as C
    return pd.DataFrame(columns=list(dict.fromkeys(
        C.SWOT_REQUIRED_REACH_FIELDS
        + C.SWOT_OPTIONAL_REACH_FIELDS
        + [C.SWOT_TIME_INDEX_COLNAME,
           C.SWOT_STATUS_COLNAME,
           C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME]
    )))


def make_empty_sos_fdc_table() -> pd.DataFrame:
    return pd.DataFrame(columns=["rank", "p_non_exceedance", "p_exceedance", "discharge_quantile"])


def make_empty_qq_matched_df(config) -> pd.DataFrame:
    from qq import constants as C
    return pd.DataFrame(columns=[
        C.SWOT_TIME_INDEX_COLNAME,
        C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME,
        C.NAME_SWOT_WSE,
        C.QQ_P_NON_EXCEEDANCE_COLNAME,
        C.SWOT_QQ_DELIVERABLE_Q_NAME,
        C.QQ_Q_IS_ESTIMATED_COLNAME,
    ])


# ---------------------------------------------------------------------------
# Interpolation utilities (exact copy of notebook logic)
# ---------------------------------------------------------------------------

def interpolate_deliverable_wse_quantile(
    config,
    state,
    deliverable_prob: np.ndarray,
    empirical_quantile_table: pd.DataFrame,
    empirical_prob_col: str,
    empirical_wse_col: str,
    extrapolate_edges: bool,
    missing_value: float,
) -> Tuple[np.ndarray, dict]:
    """
    Resample the empirical WSE quantile onto N standard probability levels.

    Interior points: linear interpolation from the empirical table.
    Edge points: linear extrapolation if extrapolate_edges=True, else fill missing_value.

    Exact logic from notebook section 2-1-3-1 / interpolate_deliverable_wse_quantile().
    """
    from qq.logger import warn

    deliverable_prob = np.asarray(deliverable_prob, dtype=float)
    out = np.full(len(deliverable_prob), missing_value, dtype=np.float64)
    diag = {
        "n_empirical_rows_used": 0,
        "empirical_prob_min": np.nan,
        "empirical_prob_max": np.nan,
        "n_interpolated": 0,
        "n_lower_edge": 0,
        "n_upper_edge": 0,
        "n_edge_missing": 0,
        "n_edge_extrapolated": 0,
        "extrapolate_edges": extrapolate_edges,
    }

    if (
        empirical_quantile_table is None
        or not isinstance(empirical_quantile_table, pd.DataFrame)
        or len(empirical_quantile_table) == 0
        or empirical_prob_col not in empirical_quantile_table.columns
        or empirical_wse_col not in empirical_quantile_table.columns
    ):
        warn(config, state,
             "Deliverable WSE quantile interpolation skipped: empirical quantile table is missing or incomplete")
        diag["n_edge_missing"] = len(deliverable_prob)
        return out, diag

    emp_df = empirical_quantile_table[[empirical_prob_col, empirical_wse_col]].copy()
    emp_df[empirical_prob_col] = pd.to_numeric(emp_df[empirical_prob_col], errors="coerce")
    emp_df[empirical_wse_col]  = pd.to_numeric(emp_df[empirical_wse_col],  errors="coerce")
    emp_df = emp_df[
        np.isfinite(emp_df[empirical_prob_col]) & np.isfinite(emp_df[empirical_wse_col])
    ].copy()
    # deduplicate probabilities: average WSE per probability
    emp_df = (
        emp_df
        .groupby(empirical_prob_col, as_index=False)[empirical_wse_col]
        .mean()
        .sort_values(empirical_prob_col)
        .reset_index(drop=True)
    )

    if len(emp_df) == 0:
        warn(config, state,
             "Deliverable WSE quantile interpolation skipped: no finite empirical quantile rows")
        diag["n_edge_missing"] = len(deliverable_prob)
        return out, diag

    p_emp   = emp_df[empirical_prob_col].to_numpy(dtype=float)
    wse_emp = emp_df[empirical_wse_col].to_numpy(dtype=float)

    diag["n_empirical_rows_used"] = len(emp_df)
    diag["empirical_prob_min"]    = float(p_emp[0])
    diag["empirical_prob_max"]    = float(p_emp[-1])

    # single-row edge case
    if len(emp_df) == 1:
        exact_mask = np.isclose(deliverable_prob, p_emp[0])
        out[exact_mask] = wse_emp[0]
        diag["n_interpolated"]  = int(exact_mask.sum())
        diag["n_edge_missing"]  = int((~exact_mask).sum())
        warn(config, state,
             "Only one empirical WSE quantile row exists; interpolation/extrapolation cannot be applied")
        return out, diag

    inside_mask     = (deliverable_prob >= p_emp[0]) & (deliverable_prob <= p_emp[-1])
    lower_edge_mask = deliverable_prob < p_emp[0]
    upper_edge_mask = deliverable_prob > p_emp[-1]

    diag["n_lower_edge"] = int(lower_edge_mask.sum())
    diag["n_upper_edge"] = int(upper_edge_mask.sum())

    if inside_mask.any():
        out[inside_mask] = np.interp(deliverable_prob[inside_mask], p_emp, wse_emp)
        diag["n_interpolated"] = int(inside_mask.sum())

    if extrapolate_edges:
        # lower edge: extend line between first two rows
        dp_low = p_emp[1] - p_emp[0]
        if dp_low != 0 and lower_edge_mask.any():
            slope_low = (wse_emp[1] - wse_emp[0]) / dp_low
            out[lower_edge_mask] = wse_emp[0] + slope_low * (deliverable_prob[lower_edge_mask] - p_emp[0])
            diag["n_edge_extrapolated"] += int(lower_edge_mask.sum())
        elif lower_edge_mask.any():
            warn(config, state,
                 "Lower-edge WSE extrapolation skipped because first two empirical probabilities are identical")

        # upper edge: extend line between last two rows
        dp_high = p_emp[-1] - p_emp[-2]
        if dp_high != 0 and upper_edge_mask.any():
            slope_high = (wse_emp[-1] - wse_emp[-2]) / dp_high
            out[upper_edge_mask] = wse_emp[-1] + slope_high * (deliverable_prob[upper_edge_mask] - p_emp[-1])
            diag["n_edge_extrapolated"] += int(upper_edge_mask.sum())
        elif upper_edge_mask.any():
            warn(config, state,
                 "Upper-edge WSE extrapolation skipped because last two empirical probabilities are identical")

    diag["n_edge_missing"] = int(np.sum(out == missing_value))
    return out, diag


def interpolate_extrapolate_probability_value(
    config,
    state,
    target_prob,
    source_prob: np.ndarray,
    source_value: np.ndarray,
    missing_value: float,
    label: str = "value",
) -> Tuple[object, dict]:
    """
    Interpolate/extrapolate a value from a probability table at target probability/ies.

    Exact logic from notebook function interpolate_extrapolate_probability_value().
    """
    from qq.logger import warn

    scalar_input = np.isscalar(target_prob)
    target_prob_arr  = np.atleast_1d(np.asarray(target_prob,  dtype=float))
    source_prob_arr  = np.asarray(source_prob,  dtype=float)
    source_value_arr = np.asarray(source_value, dtype=float)
    out = np.full(len(target_prob_arr), missing_value, dtype=np.float64)
    diag = {
        "label": label,
        "n_source_rows_used": 0,
        "source_prob_min": np.nan,
        "source_prob_max": np.nan,
        "n_interpolated": 0,
        "n_lower_extrapolated": 0,
        "n_upper_extrapolated": 0,
        "n_missing": len(target_prob_arr),
    }

    valid_mask = np.isfinite(source_prob_arr) & np.isfinite(source_value_arr)
    if valid_mask.sum() < 2:
        warn(config, state, f"{label} interpolation/extrapolation skipped: fewer than 2 valid source rows")
        return (out[0] if scalar_input else out), diag

    src_df = pd.DataFrame({
        "prob":  source_prob_arr[valid_mask],
        "value": source_value_arr[valid_mask],
    })
    src_df = (
        src_df.groupby("prob", as_index=False)["value"].mean()
        .sort_values("prob").reset_index(drop=True)
    )
    if len(src_df) < 2:
        warn(config, state, f"{label} interpolation/extrapolation skipped: fewer than 2 unique source probabilities")
        return (out[0] if scalar_input else out), diag

    p = src_df["prob"].to_numpy(dtype=float)
    v = src_df["value"].to_numpy(dtype=float)
    diag["n_source_rows_used"] = len(src_df)
    diag["source_prob_min"]    = float(p[0])
    diag["source_prob_max"]    = float(p[-1])

    inside_mask = (target_prob_arr >= p[0]) & (target_prob_arr <= p[-1])
    lower_mask  = target_prob_arr < p[0]
    upper_mask  = target_prob_arr > p[-1]

    if inside_mask.any():
        out[inside_mask] = np.interp(target_prob_arr[inside_mask], p, v)
        diag["n_interpolated"] = int(inside_mask.sum())

    if lower_mask.any():
        dp_low = p[1] - p[0]
        if dp_low != 0:
            slope_low = (v[1] - v[0]) / dp_low
            out[lower_mask] = v[0] + slope_low * (target_prob_arr[lower_mask] - p[0])
            diag["n_lower_extrapolated"] = int(lower_mask.sum())
        else:
            warn(config, state, f"{label} lower extrapolation skipped because first two probabilities are identical")

    if upper_mask.any():
        dp_high = p[-1] - p[-2]
        if dp_high != 0:
            slope_high = (v[-1] - v[-2]) / dp_high
            out[upper_mask] = v[-1] + slope_high * (target_prob_arr[upper_mask] - p[-1])
            diag["n_upper_extrapolated"] = int(upper_mask.sum())
        else:
            warn(config, state, f"{label} upper extrapolation skipped because last two probabilities are identical")

    diag["n_missing"] = int(np.sum(out == missing_value))
    return (out[0] if scalar_input else out), diag
