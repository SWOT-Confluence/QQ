"""
qq/pipeline.py
==============
Main pipeline orchestrator for the QQ algorithm.

run(config) -> QQState
    Executes every pipeline step in the exact order defined in the original
    notebook (0_qq_original_code.ipynb).  Returns the populated QQState for
    inspection, testing, or downstream use.

The pipeline is fault-surviving in RUN and AUDIT modes: a failed step marks
the reach as invalid (state.invalid_reach = True) and sets its error code,
but execution continues through all subsequent steps so that a valid output
file is always written.

In DEBUG mode, the first call to logger.fail() raises RuntimeError
immediately, useful for local development and debugging.

Pipeline execution order
------------------------
 1. setup_inputs_and_defaults  (input_json.py)
 2. read_json                  (input_json.py)
 3. read_swot                  (input_swot.py)
 4. clean_swot                 (input_swot.py)
 5. filter_swot                (input_swot.py)
 6. control_wse_count          (input_swot.py)
 7. empirical_wse_quantile     (wse_quantile.py)
 8. deliverable_wse_quantile   (wse_quantile.py)
 9. deliverable_wse_flag       (wse_quantile.py)
10. read_sos                   (input_sos.py)
11. quantile_matching          (quantile_matching.py)
12. prepare_output_arrays      (output_arrays.py)
13. prepare_plot_limits        (diagnostics.py)
14. output_paths               (output_netcdf.py)
15. write_nc                   (output_netcdf.py)
16. make_plots                 (diagnostics.py)
17. save_log                   (output_netcdf.py)
"""

from __future__ import annotations

from qq.config import QQConfig
from qq.diagnostics import make_plots, prepare_plot_limits
from qq.input_json import read_json, setup_inputs_and_defaults
from qq.input_sos import read_sos
from qq.input_swot import clean_swot, control_wse_count, filter_swot, read_swot
from qq.logger import log, section
from qq.output_arrays import prepare_output_arrays
from qq.output_netcdf import output_paths, save_log, write_nc
from qq.quantile_matching import quantile_matching
from qq.state import QQState
from qq.wse_quantile import deliverable_wse_flag, deliverable_wse_quantile, empirical_wse_quantile


def run(config: QQConfig) -> QQState:
    """
    Execute the full QQ pipeline for one reach.

    Parameters
    ----------
    config : QQConfig
        Runtime configuration (paths, index, run mode).

    Returns
    -------
    state : QQState
        Fully populated run state.  Use state.invalid_reach and
        state.invalid_reach_detailed_code to check the outcome.
    """
    state = QQState()

    # ------------------------------------------------------------------
    # Step 1-2: Input setup and JSON manifest reading
    # ------------------------------------------------------------------
    setup_inputs_and_defaults(config, state)
    read_json(config, state)

    # ------------------------------------------------------------------
    # Steps 3-6: SWOT reading and quality gates
    # ------------------------------------------------------------------
    read_swot(config, state)
    clean_swot(config, state)
    filter_swot(config, state)
    control_wse_count(config, state)

    # ------------------------------------------------------------------
    # Steps 7-9: WSE quantile computation
    # ------------------------------------------------------------------
    empirical_wse_quantile(config, state)
    deliverable_wse_quantile(config, state)
    deliverable_wse_flag(config, state)

    # ------------------------------------------------------------------
    # Step 10: SOS FDC extraction
    # ------------------------------------------------------------------
    read_sos(config, state)

    # ------------------------------------------------------------------
    # Step 11: Core QQ quantile matching
    # ------------------------------------------------------------------
    quantile_matching(config, state)

    # ------------------------------------------------------------------
    # Step 12: Prepare all output arrays
    # ------------------------------------------------------------------
    prepare_output_arrays(config, state)

    # ------------------------------------------------------------------
    # Step 13: Prepare diagnostic plot limits (non-fatal)
    # ------------------------------------------------------------------
    prepare_plot_limits(config, state)

    # ------------------------------------------------------------------
    # Steps 14-15: Resolve output paths and write NetCDF
    # ------------------------------------------------------------------
    output_paths(config, state)
    write_nc(config, state)

    # ------------------------------------------------------------------
    # Step 16: Optional diagnostic plots (non-fatal)
    # ------------------------------------------------------------------
    make_plots(config, state)

    # ------------------------------------------------------------------
    # Step 17: Save log file
    # ------------------------------------------------------------------
    save_log(config, state)

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------
    section(config, state, "PIPELINE COMPLETE")
    log(config, state, f"reach_id          = {state.rid}")
    log(config, state, f"invalid_reach     = {state.invalid_reach}")
    log(config, state, f"detailed_code     = {state.invalid_reach_detailed_code}")
    log(config, state, f"summary_code      = {state.invalid_reach_summary_code}")
    log(config, state, f"output_nc_path    = {getattr(state, 'output_nc_path', 'N/A')}")
    log(config, state, f"warnings          = {len(state.warnings_list)}")
    log(config, state, f"errors            = {len(state.errors_list)}")

    return state
