"""
qq/constants.py
===============
All algorithm-level constants for the SWOT-QQ Discharge Estimation algorithm.

These constants are extracted directly from build_config() in the prototype notebook
and must not be changed without scientific review. They are intentionally verbose and
named to match the notebook so that changes can be traced back to the prototype.

Runtime-mutable settings (paths, index, run mode) are NOT here; those live in config.py.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Algorithm identity
# ---------------------------------------------------------------------------

ALGO_NAME: str = "qq"
ALGO_OUTPUT_FOLDER_NAME: str = "qq"
LOG_OUTPUT_FOLDER_NAME: str = "logs"
LOG_FILE_SUFFIX: str = "log"

# ---------------------------------------------------------------------------
# Run mode options
# ---------------------------------------------------------------------------

RUN_MODE_OPTIONS: list[str] = ["RUN", "DEBUG", "AUDIT"]

# ---------------------------------------------------------------------------
# Invalid-reach flag dictionaries
# ---------------------------------------------------------------------------
# Detailed codes map to a specific failure point in the pipeline.
# Summary codes map to a broad failure category.
# Both are stored in the output NetCDF as scalar i4 variables.

INVALID_REACH_DETAILED_FLAG_DICT: dict[int, str] = {
    0:    "valid",
    -101: "imports_failed",
    -102: "invalid_configuration",
    -103: "invalid_run_mode",
    -201: "input_json_not_found",
    -202: "input_json_read_failed",
    -203: "reach_index_not_found",
    -204: "required_json_field_missing",
    -205: "input_path_construction_failed",
    -301: "swot_file_not_found",
    -302: "swot_file_read_failed",
    -303: "swot_required_variable_missing",
    -304: "swot_required_group_missing",
    -305: "swot_dataframe_creation_failed",
    -310: "swot_cleaning_failed",
    -311: "swot_cleaned_wse_too_short",
    -320: "swot_filtering_failed",
    -321: "swot_cleaned_filtered_wse_too_short",
    -330: "empirical_wse_quantile_failed",
    -331: "deliverable_wse_quantile_all_missing",
    -401: "sos_file_not_found",
    -402: "sos_file_read_failed",
    -403: "sos_required_variable_missing",
    -404: "sos_reach_id_not_found",
    -410: "sos_probability_invalid",
    -420: "sos_fdc_too_many_missing",
    -421: "sos_fdc_gap_too_long",
    -422: "sos_fdc_too_short",
    -423: "sos_fdc_table_creation_failed",
    -501: "quantile_matching_failed",
    -502: "no_discharge_estimated",
    -503: "probability_range_empty",
    -601: "output_array_preparation_failed",
    -602: "output_time_q_length_mismatch",
    -701: "output_directory_creation_failed",
    -702: "output_netcdf_write_failed",
    -703: "log_file_write_failed",
    -999: "unknown_error",
}

INVALID_REACH_SUMMARY_FLAG_DICT: dict[int, str] = {
    0:    "valid",
    -1:   "pre_input_setup_error",
    -2:   "json_input_error",
    -3:   "swot_error",
    -4:   "sos_error",
    -5:   "quantile_matching_error",
    -6:   "output_preparation_error",
    -7:   "output_writing_error",
    -999: "unknown_error",
}

# ---------------------------------------------------------------------------
# JSON manifest field names
# ---------------------------------------------------------------------------

REACH_ID_FIELD_IN_REACHES_JSON: str = "reach_id"
SWOT_FIELD_IN_REACHES_JSON: str = "swot"
SOS_FIELD_IN_REACHES_JSON: str = "sos"
SWORD_FIELD_IN_REACHES_JSON: str = "sword"

# ---------------------------------------------------------------------------
# Input subdirectory names (within the input directory)
# ---------------------------------------------------------------------------

SWOT_FOLDER_IN_INPUT_DIR: str = "swot"
SOS_FOLDER_IN_INPUT_DIR: str = "sos"
SWORD_FOLDER_IN_INPUT_DIR: str = "sword"

# ---------------------------------------------------------------------------
# SWOT NetCDF field and group names
# ---------------------------------------------------------------------------

NAME_SWOT_LEN_COUNT_COL: str = "time"
NAME_SWOT_TIME_COL: str = "time"
NAME_SWOT_TIME_STR_COL: str = "time_str"
NAME_SWOT_WSE: str = "wse"
NAME_SWOT_NT_VAR: str = "nt"
NAME_SWOT_NX_VAR: str = "nx"
NAME_SWOT_OBSERVATIONS_VAR: str = "observations"
NAME_SWOT_REACH_GP: str = "reach"

SWOT_STATUS_COLNAME: str = "swot_status"
SWOT_STATUS_VALID: str = "valid"
SWOT_STATUS_CLEANED: str = "cleaned"
SWOT_STATUS_FILTERED: str = "filtered"

SWOT_DATETIME_CORRECT_FORMAT_COLNAME: str = "datetime"
SWOT_TIME_INDEX_COLNAME: str = "swot_time_index"

SWOT_REQUIRED_REACH_FIELDS: list[str] = [
    "reach_id",
    NAME_SWOT_TIME_COL,
    NAME_SWOT_TIME_STR_COL,
    NAME_SWOT_WSE,
    "n_good_nod",
]
SWOT_OPTIONAL_REACH_FIELDS: list[str] = ["reach_q"]

SWOT_REACH_FIELD_MISSING_VALUES: dict = {
    NAME_SWOT_WSE:          [-999, -9999, -999999999999.0, np.nan],
    NAME_SWOT_TIME_COL:     [-999, -9999, -999999999999.0, np.nan],
    NAME_SWOT_TIME_STR_COL: ["no_data", "", "None", None],
    "n_good_nod":           [-999, -9999, -999999999999.0, np.nan],
}

# ---------------------------------------------------------------------------
# SWOT internal cleaning strategy
# ---------------------------------------------------------------------------
# Cleaning: drop rows where WSE or time_str are fill / sentinel values.
# Applied before filtering.

SWOT_INTERNAL_CLEANING_APPLY: bool = True

# Lambda criteria: return True for rows that should be KEPT.
SWOT_CLEAN_CRITERIA: dict = {
    NAME_SWOT_WSE:          lambda x: x >= -999,
    NAME_SWOT_TIME_STR_COL: lambda x: x != "no_data",
}

# ---------------------------------------------------------------------------
# SWOT internal filtering strategy
# ---------------------------------------------------------------------------
# Filtering: drop rows based on SWOT quality flag (reach_q != 3).
# Applied after cleaning.

SWOT_INTERNAL_FILTERING_APPLY: bool = True

# Lambda criteria: return True for rows that should be KEPT.
SWOT_FILT_CRITERIA: dict = {
    "reach_q": lambda x: __import__("pandas").to_numeric(x, errors="coerce") != 3,
}

# Minimum number of clean+filtered SWOT WSE observations required to proceed.
MIN_CLEAN_FILT_SWOT_WSE_LEN: int = 50

# ---------------------------------------------------------------------------
# Deliverable WSE quantile table constants
# ---------------------------------------------------------------------------

# DELIVERABLE_WSE_QUANTILE_TABLE_N: int = 100
# WSE_QUANT_FLAG_THRESHOLDS: np.ndarray = np.array([0.10, 0.25, 0.50, 0.75, np.inf])

# ---------------------------------------------------------------------------
# WSE probability grid — controls BOTH empirical probability assignment
# and the deliverable output table written to NetCDF (nwseq dimension).
# All three values are in percent (0–100). The grid runs from MIN to MAX
# inclusive in steps of STEP, giving round((MAX-MIN)/STEP)+1 points.
# Default: [0.00, 0.01, …, 1.00]  →  101 points, both endpoints included.
# ---------------------------------------------------------------------------
WSE_PROB_GRID_MIN_PCT: float = 0.0
WSE_PROB_GRID_MAX_PCT: float = 100.0
WSE_PROB_GRID_STEP_PCT: float = 1.0

def _build_wse_probability_grid() -> np.ndarray:
    p_min  = WSE_PROB_GRID_MIN_PCT  / 100.0
    p_max  = WSE_PROB_GRID_MAX_PCT  / 100.0
    p_step = WSE_PROB_GRID_STEP_PCT / 100.0
    n_pts  = round((p_max - p_min) / p_step) + 1
    return np.linspace(p_min, p_max, n_pts)

DELIVERABLE_WSE_PROBABILITY_GRID: np.ndarray = _build_wse_probability_grid()

WSE_QUANT_FLAG_THRESHOLDS: np.ndarray = np.array([0.10, 0.25, 0.50, 0.75, np.inf])





WSE_QUANT_FLAG_DTYPE = np.int16
WSE_QUANT_FLAG_ALL_MISSING_VALUE: np.int16 = np.int16(-999)

WSE_QUANT_FLAG_DEFINITION: dict[int, str] = {
     0:    "same_length: standard_table_N == n_empirical_obs",
     1:    "downsampled_10pct: standard_N < empirical by 0-10%",
     2:    "downsampled_25pct: standard_N < empirical by 10-25%",
     3:    "downsampled_50pct: standard_N < empirical by 25-50%",
     4:    "downsampled_75pct: standard_N < empirical by 50-75%",
     5:    "downsampled_extreme: standard_N < empirical by >75%",
    -1:    "upsampled_10pct: standard_N > empirical by 0-10%",
    -2:    "upsampled_25pct: standard_N > empirical by 10-25%",
    -3:    "upsampled_50pct: standard_N > empirical by 25-50%",
    -4:    "upsampled_75pct: standard_N > empirical by 50-75%",
    -5:    "upsampled_extreme: standard_N > empirical by >75%",
    -999:  "all_missing: WSE quantile table could not be produced",
}



# ---------------------------------------------------------------------------
# WSE–Q lookup table constants
# ---------------------------------------------------------------------------
# The lookup table relates WSE and discharge Q through a shared
# non-exceedance probability axis, restricted to the OVERLAP of:
#   - the empirical WSE quantile probability range
#   - the SOS FDC probability range
# No extrapolation is performed for either WSE or Q.

LOOKUP_TABLE_PROB_STEP_PERCENT: float = 1.0     # step, in percent, of the regular interior grid
LOOKUP_TABLE_MIN_ROWS: int = 2                  # minimum rows required to produce a usable table

LOOKUP_TABLE_FLAG_DTYPE = np.int16
LOOKUP_TABLE_FLAG_ALL_MISSING_VALUE: np.int16 = np.int16(-999)

# Distinct failure sub-codes (all map to the same overall "missing" scalar
# flag value -999 above; these finer-grained codes are logged only, not
# written as a separate NetCDF variable, to avoid inventing a new flag
# variable beyond what was requested).
LOOKUP_TABLE_FAIL_REASON_EMPIRICAL_WSE_UNAVAILABLE: str = "empirical_wse_table_unavailable"
LOOKUP_TABLE_FAIL_REASON_SOS_FDC_UNAVAILABLE: str = "sos_fdc_table_unavailable"
LOOKUP_TABLE_FAIL_REASON_EMPTY_PROBABILITY_OVERLAP: str = "empty_probability_overlap"
LOOKUP_TABLE_FAIL_REASON_TOO_FEW_ROWS: str = "too_few_overlap_rows"
LOOKUP_TABLE_FAIL_REASON_INTERPOLATION_FAILED: str = "interpolation_failed"
LOOKUP_TABLE_FAIL_REASON_UNEXPECTED_ERROR: str = "unexpected_error"

LOOKUP_TABLE_FLAG_DEFINITION: dict[int, str] = {
     0:    "same_length: lookup_table_N == n_empirical_obs",
     1:    "downsampled_10pct: lookup_N < empirical by 0-10%",
     2:    "downsampled_25pct: lookup_N < empirical by 10-25%",
     3:    "downsampled_50pct: lookup_N < empirical by 25-50%",
     4:    "downsampled_75pct: lookup_N < empirical by 50-75%",
     5:    "downsampled_extreme: lookup_N < empirical by >75%",
    -1:    "upsampled_10pct: lookup_N > empirical by 0-10%",
    -2:    "upsampled_25pct: lookup_N > empirical by 10-25%",
    -3:    "upsampled_50pct: lookup_N > empirical by 25-50%",
    -4:    "upsampled_75pct: lookup_N > empirical by 50-75%",
    -5:    "upsampled_extreme: lookup_N > empirical by >75%",
    -999:  "all_missing: lookup table could not be produced",
}

# NetCDF variable / group / dimension names (mirrors SWOT_QQ_DELIVERABLE_* naming style)
SWOT_QQ_LOOKUP_TABLE_PROB_NAME: str = "QQ_lookup_table_prob"
SWOT_QQ_LOOKUP_TABLE_WSE_NAME: str = "QQ_lookup_table_wse"
SWOT_QQ_LOOKUP_TABLE_Q_NAME: str = "QQ_lookup_table_q"
SWOT_QQ_LOOKUP_TABLE_FLAG_NAME: str = "QQ_lookup_table_flag"

OUTPUT_NC_LOOKUP_TABLE_GP_NAME: str = "lookup_table"
OUTPUT_NC_ROOT_DIM_NLOOKUP_NAME: str = "nlookup"







PRODUCE_WSE_QUANTILE_IF_INVALID_REACH: bool = True
PRODUCE_WSE_QUANTILE_IF_NO_Q_ESTIMATED: bool = True
PRODUCE_WSE_QUANTILE_IF_CLEAN_FILT_WSE_BELOW_THRESHOLD: bool = False
MIN_CLEAN_FILT_SWOT_WSE_LEN_FOR_WSE_QUANTILE: int = 10

DELIVERABLE_WSE_QUANTILE_EXTRAPOLATE_EDGES: bool = True
DELIVERABLE_WSE_QUANTILE_MIN_POINTS_FOR_EXTRAPOLATION: int = 2

# ---------------------------------------------------------------------------
# Quantile matching limits
# ---------------------------------------------------------------------------
# If quantile_matching_predefined_extremes_estimation=False,
# we clip the matching range to [predefined_min, predefined_max].
# If quantile_matching_fdc_extremes_estimation=False,
# we further clip to the FDC probability range.

# QUANTILE_MATCHING_PREDEFINED_EXTREMES_ESTIMATION:
#   True  (default) = fixed 5%–95% clip is DISABLED; only FDC range applies.
#   False           = fixed clip to [PREDEFINED_MIN, PREDEFINED_MAX] is active.
# QUANTILE_MATCHING_FDC_EXTREMES_ESTIMATION:
#   False (default) = clip p to [min(FDC p), max(FDC p)].
#   True            = allow p outside the FDC range (no FDC clip).

QUANTILE_MATCHING_PREDEFINED_EXTREMES_ESTIMATION: bool = True   # True = do NOT apply fixed clip
QUANTILE_MATCHING_PREDEFINED_MIN_EXTREME_PROB: float = 0.05     # only used if above is False
QUANTILE_MATCHING_PREDEFINED_MAX_EXTREME_PROB: float = 0.95     # only used if above is False
QUANTILE_MATCHING_FDC_EXTREMES_ESTIMATION: bool = False         # False = clip to FDC range (active)

# ---------------------------------------------------------------------------
# Deliverable output variable names (written to NetCDF)
# ---------------------------------------------------------------------------

SWOT_QQ_DELIVERABLE_Q_NAME: str = "QQ_q"
SWOT_QQ_DELIVERABLE_TIME_NAME: str = "QQ_time"
SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME: str = "QQ_q_status_flag"
SWOT_QQ_DELIVERABLE_WSE_QUANT_PROB_NAME: str = "QQ_wse_quant_prob"
SWOT_QQ_DELIVERABLE_WSE_QUANT_WSE_NAME: str = "QQ_wse_quant_wse"
SWOT_QQ_DELIVERABLE_WSE_QUANT_FLAG_NAME: str = "QQ_wse_quant_flag"
SWOT_QQ_DELIVERABLE_INVALID_REACH_DETAILED_FLAG_NAME: str = "QQ_invalid_reach_detailed_flag"
SWOT_QQ_DELIVERABLE_INVALID_REACH_SUMMARY_FLAG_NAME: str = "QQ_invalid_reach_summary_flag"

# ---------------------------------------------------------------------------
# SOS NetCDF group and variable names
# ---------------------------------------------------------------------------

NAME_SOS_REACHES_GP: str = "reaches"
NAME_SOS_REACHES_GP_REACH_ID_VAR: str = "reach_id"
NAME_SOS_MODEL_GP: str = "model"
NAME_SOS_MODEL_GP_FDC_VAR: str = "flow_duration_q"
NAME_SOS_MODEL_GP_PROB_VAR: str = "probability"

SOS_VARIABLE_MISSING_VALUES: dict = {
    NAME_SOS_MODEL_GP_PROB_VAR: [-999, -9999, -999999999999.0, np.nan],
    NAME_SOS_MODEL_GP_FDC_VAR:  [-999, -9999, -999999999999.0, np.nan],
}

FDC_MAX_MISSING_PERC_TO_PROCEED: float = 50.0
FDC_MAX_CONSECUTIVE_MISSING_GAP_TO_PROCEED: int = 25
MIN_VALID_SOS_FDC_LEN: int = 2

# ---------------------------------------------------------------------------
# Output policy constants
# ---------------------------------------------------------------------------
# qq_output_time_dimension_source: which SWOT dataframe drives the time dimension
#   "swot"                 = all original observations (nt1)
#   "swot_cleaned"         = after cleaning  (nt2 <= nt1)
#   "swot_cleaned_filtered"= after cleaning+filtering (nt3 <= nt2)  [DEFAULT]
#
# qq_output_time_format: how time is stored in the NetCDF
#   "seconds_f8"  = float64 seconds since epoch  [DEFAULT]
#   "seconds_i8"  = int64 seconds since epoch
#   "nanoseconds_i8" = int64 nanoseconds since epoch
#   "iso_string"  = ISO-8601 string
#
# qq_output_all_q_missing_array_mode: behaviour when no discharge was estimated
#   "selected_time_dimension" = write arrays of fill values (length = nt of output)
#   "single_missing"          = write a single fill-value element

QQ_OUTPUT_INCLUDE_MISSING_Q: bool = True
QQ_OUTPUT_TIME_DIMENSION_SOURCE: str = "swot_cleaned_filtered"
QQ_OUTPUT_TIME_FORMAT: str = "seconds_f8"
QQ_OUTPUT_ALL_Q_MISSING_Q_ARRAY_MODE: str = "selected_time_dimension"
QQ_OUTPUT_ALL_Q_MISSING_TIME_ARRAY_MODE: str = "selected_time_dimension"

QQ_OUTPUT_TIME_DIMENSION_SOURCE_OPTIONS: list[str] = [
    "swot", "swot_cleaned", "swot_cleaned_filtered"
]
QQ_OUTPUT_TIME_FORMAT_OPTIONS: list[str] = [
    "seconds_f8", "seconds_i8", "nanoseconds_i8", "iso_string"
]
QQ_OUTPUT_ALL_Q_MISSING_ARRAY_MODE_OPTIONS: list[str] = [
    "selected_time_dimension", "single_missing"
]

# ---------------------------------------------------------------------------
# NetCDF fill / missing values and time convention
# ---------------------------------------------------------------------------

QQ_NC_DOUBLE_FILL_VALUE: np.float64 = np.float64(-999999999999.0)
QQ_NC_INT_FILL_VALUE: np.int64 = np.int64(-999999999999)
# QQ_NC_FLAG_FILL_VALUE: np.int8 = np.int8(-127)
QQ_NC_FLAG_FILL_VALUE: np.int16 = np.int16(-999)

QQ_NC_STR_FILL_VALUE: str = ""
QQ_NC_TIME_UNITS: str = "seconds since 2000-01-01 00:00:00.000"
QQ_NC_TIME_EPOCH: np.datetime64 = np.datetime64("2000-01-01T00:00:00", "ns")

# ---------------------------------------------------------------------------
# Internal column names (used in intermediate DataFrames, not in NetCDF output)
# ---------------------------------------------------------------------------

QQ_P_NON_EXCEEDANCE_COLNAME: str = "QQ_p_non_exceedance"
QQ_Q_IS_ESTIMATED_COLNAME: str = "QQ_q_is_estimated"

# ---------------------------------------------------------------------------
# Q-status flag values (written to the q group in the NetCDF)
# ---------------------------------------------------------------------------

# QQ_Q_STATUS_VALID_CODE: np.int8 = np.int8(0)
# QQ_Q_STATUS_REMOVED_BY_CLEANING_CODE: np.int8 = np.int8(1)
# QQ_Q_STATUS_REMOVED_BY_FILTERING_CODE: np.int8 = np.int8(2)
# QQ_Q_STATUS_NO_QUANTILE_APPLIED_CODE: np.int8 = np.int8(3)
# QQ_Q_STATUS_INVALID_REACH_CODE: np.int8 = np.int8(4)
# QQ_Q_STATUS_MISSING_CODE: np.int8 = QQ_NC_FLAG_FILL_VALUE

# QQ_Q_STATUS_FLAG_VALUES: np.ndarray = np.array([
#     QQ_Q_STATUS_VALID_CODE,
#     QQ_Q_STATUS_REMOVED_BY_CLEANING_CODE,
#     QQ_Q_STATUS_REMOVED_BY_FILTERING_CODE,
#     QQ_Q_STATUS_NO_QUANTILE_APPLIED_CODE,
#     QQ_Q_STATUS_INVALID_REACH_CODE,
#     QQ_Q_STATUS_MISSING_CODE,
# ], dtype=np.int8)

QQ_Q_STATUS_VALID_CODE: np.int16 = np.int16(0)
QQ_Q_STATUS_REMOVED_BY_CLEANING_CODE: np.int16 = np.int16(1)
QQ_Q_STATUS_REMOVED_BY_FILTERING_CODE: np.int16 = np.int16(2)
QQ_Q_STATUS_NO_QUANTILE_APPLIED_CODE: np.int16 = np.int16(3)
QQ_Q_STATUS_INVALID_REACH_CODE: np.int16 = np.int16(4)
QQ_Q_STATUS_MISSING_CODE: np.int16 = QQ_NC_FLAG_FILL_VALUE

QQ_Q_STATUS_FLAG_VALUES: np.ndarray = np.array([
    QQ_Q_STATUS_VALID_CODE,
    QQ_Q_STATUS_REMOVED_BY_CLEANING_CODE,
    QQ_Q_STATUS_REMOVED_BY_FILTERING_CODE,
    QQ_Q_STATUS_NO_QUANTILE_APPLIED_CODE,
    QQ_Q_STATUS_INVALID_REACH_CODE,
    QQ_Q_STATUS_MISSING_CODE,
], dtype=np.int16)


QQ_Q_STATUS_FLAG_MEANINGS: str = (
    "valid_q_estimated removed_by_cleaning removed_by_filtering "
    "no_quantile_applied invalid_reach missing"
)

QQ_Q_STATUS_FLAG_DEFINITION: dict[int, str] = {
    int(QQ_Q_STATUS_VALID_CODE):               "valid_q_estimated",
    int(QQ_Q_STATUS_REMOVED_BY_CLEANING_CODE): "removed_by_cleaning",
    int(QQ_Q_STATUS_REMOVED_BY_FILTERING_CODE):"removed_by_filtering",
    int(QQ_Q_STATUS_NO_QUANTILE_APPLIED_CODE): "no_quantile_applied",
    int(QQ_Q_STATUS_INVALID_REACH_CODE):       "invalid_reach",
    int(QQ_Q_STATUS_MISSING_CODE):             "missing",
}

# ---------------------------------------------------------------------------
# NetCDF root-level metadata
# ---------------------------------------------------------------------------

OUTPUT_NC_ROOT_CONVENTIONS: str = "CF-1.8"

OUTPUT_NC_ROOT_DIM_NT_NAME: str = "nt"
OUTPUT_NC_ROOT_DIM_NWSEQ_NAME: str = "nwseq"
OUTPUT_NC_Q_GP_NAME: str = "q"
OUTPUT_NC_WSE_QUANT_GP_NAME: str = "wse_quantile"
