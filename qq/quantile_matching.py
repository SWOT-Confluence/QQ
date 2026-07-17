"""
qq/quantile_matching.py
=======================
Core QQ discharge estimation: quantile matching.

Pipeline step
-------------
quantile_matching(config, state)
    Maps each SWOT WSE observation to a non-exceedance probability via the
    empirical WSE quantile table, then maps that probability to a discharge
    value via the SOS FDC.  This is the scientific core of the QQ algorithm.

    Exact logic from notebook section 3 (QUANTILE MATCHING).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qq import constants as C
from qq.config import QQConfig
from qq.helpers import make_empty_qq_matched_df
from qq.logger import fail, log, log_block, log_vars, section, warn
from qq.state import QQState


def quantile_matching(config: QQConfig, state: QQState) -> None:
    """
    Estimate discharge for each clean+filtered SWOT observation.

    Algorithm:
    1. For each observed WSE, look up its non-exceedance probability p in the
       empirical WSE quantile table (linear interpolation via np.interp).
    2. Clip p to the allowed matching range [p_min, p_max].
    3. For observations within range, look up the corresponding discharge Q
       in the SOS FDC (linear interpolation via np.interp).
    4. Observations outside range get NaN (marked in QQ_q_is_estimated flag).

    Populates on state:
        qq_matched_df        (per-observation matched DataFrame)
        QQ_q                 (raw discharge array, may contain NaN)
        QQ_time              (datetime64[ns] array aligned to QQ_q)
        swot_qq_deliverable  (dict with QQ_q, QQ_time)
    """
    section(config, state, "3 QUANTILE MATCHING")

    fdc_ready = (
        isinstance(state.sos_fdc_table, pd.DataFrame)
        and len(state.sos_fdc_table) >= 2
    )

    if not state.invalid_reach and fdc_ready:
        try:
            # Working DataFrame: cleaned+filtered observations
            qq_matched_df = state.swot_dc_reach_swot_df_clean_filt[[
                C.SWOT_TIME_INDEX_COLNAME,
                C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME,
                C.NAME_SWOT_WSE,
            ]].copy()

            # ----------------------------------------------------------------
            # Step 1: WSE → non-exceedance probability
            # ----------------------------------------------------------------
            # Average WSE per empirical probability level (handles duplicates)
            wse_p_table = (
                state.swot_clean_filt_empirical_wse_quantile_table
                .groupby("empirical_wse_quantile", as_index=False)["empirical_p_non_exceedance"]
                .mean()
            )

            qq_matched_df[C.QQ_P_NON_EXCEEDANCE_COLNAME] = np.interp(
                qq_matched_df[C.NAME_SWOT_WSE].astype(float),
                wse_p_table["empirical_wse_quantile"],
                wse_p_table["empirical_p_non_exceedance"],
            )

            # ----------------------------------------------------------------
            # Step 2: Determine allowed probability range [p_min, p_max]
            # ----------------------------------------------------------------
            p_min, p_max = 0.0, 1.0

            # Clip to predefined extremes if requested
            if not C.QUANTILE_MATCHING_PREDEFINED_EXTREMES_ESTIMATION:
                p_min = max(p_min, C.QUANTILE_MATCHING_PREDEFINED_MIN_EXTREME_PROB)
                p_max = min(p_max, C.QUANTILE_MATCHING_PREDEFINED_MAX_EXTREME_PROB)

            # Clip to FDC probability range if requested
            if not C.QUANTILE_MATCHING_FDC_EXTREMES_ESTIMATION:
                p_min = max(p_min, state.sos_fdc_table["p_non_exceedance"].min())
                p_max = min(p_max, state.sos_fdc_table["p_non_exceedance"].max())

            if p_min > p_max:
                fail(
                    config, state,
                    f"Invalid reach: empty quantile matching probability range: "
                    f"p_min={p_min}, p_max={p_max}",
                    detailed_code=-503,
                )
                ok = pd.Series(False, index=qq_matched_df.index)
            else:
                ok = qq_matched_df[C.QQ_P_NON_EXCEEDANCE_COLNAME].between(p_min, p_max)

            # ----------------------------------------------------------------
            # Step 3: Probability → discharge (FDC interpolation)
            # ----------------------------------------------------------------
            fdc = state.sos_fdc_table.sort_values("p_non_exceedance")
            p   = qq_matched_df[C.QQ_P_NON_EXCEEDANCE_COLNAME].to_numpy(float)

            qq_matched_df[C.SWOT_QQ_DELIVERABLE_Q_NAME] = np.nan
            qq_matched_df[C.QQ_Q_IS_ESTIMATED_COLNAME]  = ok.to_numpy(dtype=bool)

            if ok.any():
                qq_matched_df.loc[ok, C.SWOT_QQ_DELIVERABLE_Q_NAME] = np.interp(
                    p[ok.to_numpy()],
                    fdc["p_non_exceedance"],
                    fdc["discharge_quantile"],
                )
            else:
                warn(config, state, "No discharge values estimated during quantile matching")

            # ----------------------------------------------------------------
            # Store results on state
            # ----------------------------------------------------------------
            state.qq_matched_df = qq_matched_df
            state.QQ_q = qq_matched_df[C.SWOT_QQ_DELIVERABLE_Q_NAME].to_numpy(dtype=float)
            state.QQ_time = (
                pd.to_datetime(
                    qq_matched_df[C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME],
                    errors="coerce",
                    utc=True,
                )
                .dt.tz_convert(None)
                .to_numpy("datetime64[ns]")
            )

            log_vars(
                config, state,
                qq_matched_df_shape=qq_matched_df.shape,
                wse_p_table_shape=wse_p_table.shape,
                sos_fdc_table_shape=state.sos_fdc_table.shape,
                p_min=p_min,
                p_max=p_max,
                ok_true=ok.sum(),
                ok_false=(~ok).sum(),
                QQ_q_len=len(state.QQ_q),
                QQ_time_len=len(state.QQ_time),
            )
            log_block(config, state, "qq_matched_df_head",  qq_matched_df.head())
            log_block(config, state, "wse_p_table_head",    wse_p_table.head())
            log_block(config, state, "fdc_head",            fdc.head())
            log_block(config, state, "QQ_q_sample",         state.QQ_q[:5])
            log_block(config, state, "QQ_time_sample",      state.QQ_time[:5])

        except Exception as exc:
            fail(config, state, f"Quantile matching failed: {exc}", detailed_code=-501)
            state.qq_matched_df = make_empty_qq_matched_df(config)
            state.QQ_q    = np.array([], dtype=float)
            state.QQ_time = np.array([], dtype="datetime64[ns]")

    else:
        if not state.invalid_reach:
            fail(
                config, state,
                "Invalid reach: quantile matching not applied because SOS FDC table is missing or too short",
                detailed_code=-501,
            )
        else:
            log(config, state, "Skipped quantile matching because invalid_reach=True")

        state.qq_matched_df = make_empty_qq_matched_df(config)
        state.QQ_q    = np.array([], dtype=float)
        state.QQ_time = np.array([], dtype="datetime64[ns]")

    # Always store the deliverable dict (may be empty arrays for invalid reaches)
    state.swot_qq_deliverable = {
        C.SWOT_QQ_DELIVERABLE_Q_NAME:    state.QQ_q,
        C.SWOT_QQ_DELIVERABLE_TIME_NAME: state.QQ_time,
    }
    log_vars(config, state, swot_qq_deliverable_keys=list(state.swot_qq_deliverable.keys()))
