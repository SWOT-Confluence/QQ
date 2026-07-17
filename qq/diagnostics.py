"""
qq/diagnostics.py
=================
Optional diagnostic plot generation (notebook section 3-1-9 and 3-2).

Plots are produced only when config.make_interactive_plots is True and
plotly is installed.  Silently skipped otherwise.  Plots are never written
in production containers by default.

The extreme-limit preparation (section 3-1-9) is included here because it
feeds directly into the plots and has no downstream effect on NC output.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qq import constants as C
from qq.config import QQConfig
from qq.helpers import interpolate_extrapolate_probability_value
from qq.logger import log, log_block, log_vars, section, warn
from qq.state import QQState

# ---------------------------------------------------------------------------
# Extreme-limit preparation (section 3-1-9)
# ---------------------------------------------------------------------------

def prepare_plot_limits(config: QQConfig, state: QQState) -> None:
    """
    Compute min/max extremes for WSE, probability, and discharge axes used
    in diagnostic plots.  Stored on state as loose scalars.

    Exact logic from notebook section 3-1-9.
    """
    section(config, state, "3-1-9 PREPARE APPLIED EXTREME LIMITS FOR PLOTS")

    # safe defaults
    state.min_min_prob = np.nan
    state.max_max_prob = np.nan
    state.wse_min_min  = np.nan
    state.wse_max_max  = np.nan
    state.q_min_min    = np.nan
    state.q_max_max    = np.nan

    try:
        # ---------------------------------------------------------------
        # Probability range applied during quantile matching
        # ---------------------------------------------------------------
        p_min_match, p_max_match = 0.0, 1.0
        if not C.QUANTILE_MATCHING_PREDEFINED_EXTREMES_ESTIMATION:
            p_min_match = max(p_min_match, C.QUANTILE_MATCHING_PREDEFINED_MIN_EXTREME_PROB)
            p_max_match = min(p_max_match, C.QUANTILE_MATCHING_PREDEFINED_MAX_EXTREME_PROB)

        fdc_ok = isinstance(state.sos_fdc_table, pd.DataFrame) and len(state.sos_fdc_table) >= 2
        if not C.QUANTILE_MATCHING_FDC_EXTREMES_ESTIMATION and fdc_ok:
            p_min_match = max(p_min_match, state.sos_fdc_table["p_non_exceedance"].min())
            p_max_match = min(p_max_match, state.sos_fdc_table["p_non_exceedance"].max())

        if p_min_match <= p_max_match:
            state.min_min_prob = float(p_min_match)
            state.max_max_prob = float(p_max_match)

        # ---------------------------------------------------------------
        # WSE range: from empirical WSE quantile via probability extremes
        # ---------------------------------------------------------------
        emp_ok = (
            hasattr(state, "swot_clean_filt_empirical_wse_quantile_table")
            and isinstance(state.swot_clean_filt_empirical_wse_quantile_table, pd.DataFrame)
            and len(state.swot_clean_filt_empirical_wse_quantile_table) >= 2
        )

        if emp_ok and np.isfinite(state.min_min_prob):
            src_p   = state.swot_clean_filt_empirical_wse_quantile_table["empirical_p_non_exceedance"].to_numpy(float)
            src_wse = state.swot_clean_filt_empirical_wse_quantile_table["empirical_wse_quantile"].to_numpy(float)

            wse_min, _ = interpolate_extrapolate_probability_value(
                config, state, state.min_min_prob, src_p, src_wse,
                missing_value=np.nan, label="wse_min"
            )
            wse_max, _ = interpolate_extrapolate_probability_value(
                config, state, state.max_max_prob, src_p, src_wse,
                missing_value=np.nan, label="wse_max"
            )
            state.wse_min_min = float(wse_min) if np.isfinite(wse_min) else np.nan
            state.wse_max_max = float(wse_max) if np.isfinite(wse_max) else np.nan

        # ---------------------------------------------------------------
        # Discharge range: from SOS FDC via probability extremes
        # ---------------------------------------------------------------
        if fdc_ok and np.isfinite(state.min_min_prob):
            src_p = state.sos_fdc_table["p_non_exceedance"].to_numpy(float)
            src_q = state.sos_fdc_table["discharge_quantile"].to_numpy(float)

            q_min, _ = interpolate_extrapolate_probability_value(
                config, state, state.min_min_prob, src_p, src_q,
                missing_value=np.nan, label="q_min"
            )
            q_max, _ = interpolate_extrapolate_probability_value(
                config, state, state.max_max_prob, src_p, src_q,
                missing_value=np.nan, label="q_max"
            )
            state.q_min_min = float(q_min) if np.isfinite(q_min) else np.nan
            state.q_max_max = float(q_max) if np.isfinite(q_max) else np.nan

        log_vars(
            config, state,
            min_min_prob=state.min_min_prob,
            max_max_prob=state.max_max_prob,
            wse_min_min=state.wse_min_min,
            wse_max_max=state.wse_max_max,
            q_min_min=state.q_min_min,
            q_max_max=state.q_max_max,
        )

    except Exception as exc:
        warn(config, state, f"Plot limit preparation failed (non-fatal): {exc}")


# ---------------------------------------------------------------------------
# Interactive plot generation (section 3-2)
# ---------------------------------------------------------------------------

def make_plots(config: QQConfig, state: QQState) -> None:
    """
    Generate Plotly diagnostic plots (section 3-2).

    Silently skipped if config.make_interactive_plots is False or if
    plotly is not installed.
    """
    section(config, state, "3-2 INTERACTIVE DIAGNOSTIC PLOTS")

    if not config.make_interactive_plots:
        log(config, state, "Interactive plots disabled (make_interactive_plots=False)")
        return

    try:
        import plotly.graph_objects as go  # type: ignore
        from plotly.subplots import make_subplots  # type: ignore
    except ImportError:
        warn(config, state, "plotly not installed; skipping diagnostic plots")
        return

    try:
        # ----------------------------------------------------------------
        # Plot 1: Empirical WSE quantile curve
        # ----------------------------------------------------------------
        emp_ok = (
            hasattr(state, "swot_clean_filt_empirical_wse_quantile_table")
            and isinstance(state.swot_clean_filt_empirical_wse_quantile_table, pd.DataFrame)
            and len(state.swot_clean_filt_empirical_wse_quantile_table) > 0
        )
        fdc_ok = isinstance(state.sos_fdc_table, pd.DataFrame) and len(state.sos_fdc_table) >= 2
        match_ok = isinstance(state.qq_matched_df, pd.DataFrame) and len(state.qq_matched_df) > 0

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Empirical SWOT WSE quantile",
                "SOS Flow Duration Curve",
                "WSE → Probability mapping",
                "Estimated Q time series",
            ),
        )

        if emp_ok:
            t = state.swot_clean_filt_empirical_wse_quantile_table
            fig.add_trace(
                go.Scatter(
                    x=t["empirical_p_non_exceedance"],
                    y=t["empirical_wse_quantile"],
                    mode="lines+markers",
                    name="Empirical WSE quantile",
                    marker=dict(size=4),
                ),
                row=1, col=1,
            )

        if fdc_ok:
            fig.add_trace(
                go.Scatter(
                    x=state.sos_fdc_table["p_non_exceedance"],
                    y=state.sos_fdc_table["discharge_quantile"],
                    mode="lines",
                    name="SOS FDC",
                    line=dict(color="blue"),
                ),
                row=1, col=2,
            )

        if match_ok and C.QQ_P_NON_EXCEEDANCE_COLNAME in state.qq_matched_df.columns:
            df = state.qq_matched_df
            fig.add_trace(
                go.Scatter(
                    x=df[C.NAME_SWOT_WSE],
                    y=df[C.QQ_P_NON_EXCEEDANCE_COLNAME],
                    mode="markers",
                    name="WSE→Prob",
                    marker=dict(size=4, color="orange"),
                ),
                row=2, col=1,
            )

        if match_ok and C.SWOT_QQ_DELIVERABLE_Q_NAME in state.qq_matched_df.columns:
            df = state.qq_matched_df
            dt_col = C.SWOT_DATETIME_CORRECT_FORMAT_COLNAME
            if dt_col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df[dt_col],
                        y=df[C.SWOT_QQ_DELIVERABLE_Q_NAME],
                        mode="markers+lines",
                        name="Estimated Q",
                        marker=dict(size=5, color="green"),
                    ),
                    row=2, col=2,
                )

        fig.update_layout(
            title_text=f"QQ diagnostics — reach {state.rid}",
            height=700,
        )

        # Save as HTML next to the NC file when possible
        if hasattr(state, "output_path") and state.output_path.exists():
            plot_path = state.output_path / f"{state.rid}_{C.ALGO_NAME}_diag.html"
            fig.write_html(str(plot_path))
            log(config, state, f"Diagnostic plot written to: {plot_path}")
        else:
            fig.show()

    except Exception as exc:
        warn(config, state, f"Diagnostic plot generation failed (non-fatal): {exc}")
