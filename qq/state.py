"""
qq/state.py
===========
Mutable run-state object for a single QQ reach processing job.

Each call to run_qq.pipeline.run() creates a fresh QQState instance.
All intermediate results, flags, dataframes, and arrays are stored here
so that every function receives a single, inspectable state rather than
dozens of loose variables.

This mirrors the SimpleNamespace `state` object used in the prototype notebook,
but as an explicit class so that attributes are documented and type-checked.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd


class QQState:
    """
    Holds all intermediate results and flags for one QQ reach processing job.

    Attributes are grouped in the order they are populated by the pipeline.
    Defaults are set to safe sentinel values so that the NetCDF writer and
    logger can always access them safely even if an earlier stage failed.
    """

    # ------------------------------------------------------------------
    # Invalid-reach flags
    # ------------------------------------------------------------------
    invalid_reach: bool
    invalid_reach_detailed_code: int
    invalid_reach_summary_code: int
    invalid_reach_detailed_codes: List[int]
    invalid_reach_messages: List[str]

    # ------------------------------------------------------------------
    # Diagnostic lists (accumulated throughout the run)
    # ------------------------------------------------------------------
    logs: List[str]
    warnings_list: List[str]
    errors_list: List[str]

    # ------------------------------------------------------------------
    # Input paths (resolved from the JSON manifest)
    # ------------------------------------------------------------------
    input_dir: Path
    input_json_path: Path
    input_swot_dir: Path
    input_sos_dir: Path
    input_sword_dir: Path
    output_dir: Path

    rid: str
    rid_swot_filename: str | None
    rid_sos_filename: str | None
    rid_sword_filename: str | None
    input_swot_path: Path | None
    input_sos_path: Path | None
    input_sword_path: Path | None

    # ------------------------------------------------------------------
    # SWOT data (populated by read_swot, clean_swot, filter_swot)
    # ------------------------------------------------------------------
    swot_reach_field_nc_metadata: dict
    swot_dc_reach_swot_df: pd.DataFrame         # raw dataframe (nt1 rows)
    swot_dc_reach_swot_df_clean: pd.DataFrame   # after cleaning  (nt2 rows)
    swot_dc_reach_swot_df_clean_filt: pd.DataFrame  # after filtering (nt3 rows)
    swot_dc_nt_2_swot_clean_filt: int           # = len(swot_dc_reach_swot_df_clean_filt)

    # ------------------------------------------------------------------
    # WSE quantile tables (populated by wse_quantile module)
    # ------------------------------------------------------------------
    swot_clean_filt_wse_n_valid: int
    swot_clean_filt_empirical_wse_quantile_table: pd.DataFrame
    QQ_wse_quant_prob: np.ndarray
    QQ_wse_quant_wse: np.ndarray
    QQ_wse_quant_interp_diag: dict
    QQ_wse_quant_flag: np.int16
    swot_wse_quantile_deliverable: dict

    # ------------------------------------------------------------------
    # SOS / FDC table (populated by input_sos module)
    # ------------------------------------------------------------------
    sos_variable_nc_metadata: dict
    sos_fdc_table: pd.DataFrame

    sos_fdc_extended_flag: int   # C.SOS_FDC_EXTENDED_FLAG_* values
    
    
    
    # ------------------------------------------------------------------
    # WSE-Q lookup table (auxiliary deliverable; populated by lookup_table.py)
    # ------------------------------------------------------------------
    QQ_lookup_table_prob: np.ndarray
    QQ_lookup_table_wse: np.ndarray
    QQ_lookup_table_q: np.ndarray
    QQ_lookup_table_flag: np.int16
    QQ_lookup_table_fail_reason: str





    # ------------------------------------------------------------------
    # Quantile matching results
    # ------------------------------------------------------------------
    qq_matched_df: pd.DataFrame
    QQ_q: np.ndarray
    QQ_time: np.ndarray
    swot_qq_deliverable: dict

    # ------------------------------------------------------------------
    # Output arrays (populated by output_arrays module)
    # ------------------------------------------------------------------
    output_q_base_df: pd.DataFrame
    QQ_q_out: np.ndarray
    QQ_q_status_flag_out: np.ndarray
    QQ_time_out: np.ndarray
    QQ_wse_quant_prob_out: np.ndarray
    QQ_wse_quant_wse_out: np.ndarray
    QQ_wse_quant_flag_out: np.int16
    qq_output_all_q_missing: bool
    output_nc_root_time_var_dtype_nc: object   # str | "f8" | "i8"
    output_nc_root_time_var_units: str
    output_nc_root_time_var_fill_value: object
    output_nc_root_time_var_missing_value: object
    
    
    QQ_lookup_table_prob_out: np.ndarray
    QQ_lookup_table_wse_out: np.ndarray
    QQ_lookup_table_q_out: np.ndarray
    QQ_lookup_table_flag_out: np.int16
    

    # ------------------------------------------------------------------
    # Output file paths (populated by output_netcdf.output_paths)
    # ------------------------------------------------------------------
    output_path: Path
    output_filename: str
    output_nc_path: Path
    log_output_path: Path
    log_filename: str
    log_file_path: Path

    # ------------------------------------------------------------------
    # Diagnostics / plot data
    # ------------------------------------------------------------------
    min_min_prob: float
    max_max_prob: float
    wse_min_min: float
    wse_max_max: float
    q_min_min: float
    q_max_max: float

    def __init__(self) -> None:
        # Invalid-reach control
        self.invalid_reach = False
        self.invalid_reach_detailed_code = 0
        self.invalid_reach_summary_code = 0
        self.invalid_reach_detailed_codes = []
        self.invalid_reach_messages = []

        # Diagnostic accumulation
        self.logs = []
        self.warnings_list = []
        self.errors_list = []

        # Metadata stores (filled in during NC read)
        self.swot_reach_field_nc_metadata = {}
        self.sos_variable_nc_metadata = {}

        self.sos_fdc_extended_flag = 0   # SOS_FDC_EXTENDED_FLAG_NOT_ATTEMPTED
