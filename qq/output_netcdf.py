"""
qq/output_netcdf.py
===================
Write the per-reach QQ output NetCDF and save the run log file.

Pipeline steps
--------------
output_paths(config, state)
    Resolve all output file paths (NC file, log file) and create the
    output and log directories.  Must run before any other output step.

write_nc(config, state)
    Write the full QQ output NetCDF file.  This function must produce a
    file in all cases, including invalid reaches.  Mirrors exactly the
    structure from notebook section 4-1.

save_log(config, state)
    Write the accumulated log string to a .log text file (section 5).

NetCDF structure produced
-------------------------
Root
    Dimensions:  nt, nwseq
    Variables:   nt(nt), nwseq(nwseq), QQ_time(nt),
                 QQ_invalid_reach_detailed_flag (scalar),
                 QQ_invalid_reach_summary_flag  (scalar)

    Global attrs:
        title
        institution
        algorithm
        software_name
        software_version
        software_git_commit
        software_git_describe
        software_repository
        software_authors
        software_maintainers
        date_created
        source
        history
        references
        comment
        reach_id
        is_valid
        Conventions
        source_swot_file
        source_sos_file
        warnings
        errors
        run_mode
        invalid_reach_detailed_code
        invalid_reach_summary_code
        invalid_reach_detailed_codes
        invalid_reach_messages

Group "q"
    Variables:   QQ_q(nt), QQ_q_status_flag(nt)

Group "wse_quantile"
    Variables:   QQ_wse_quant_prob(nwseq), QQ_wse_quant_wse(nwseq),
                 QQ_wse_quant_flag (scalar)

Group "lookup_table"
    Variables:   QQ_lookup_table_prob(nlookup), QQ_lookup_table_wse(nlookup),
                 QQ_lookup_table_q(nlookup), QQ_lookup_table_flag (scalar)

"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from qq import constants as C
from qq import metadata as M

from qq.config import QQConfig
from qq.logger import fail, log, log_vars, section
from qq.state import QQState


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def output_paths(config: QQConfig, state: QQState) -> None:
    """
    Resolve all output file paths and create directories.

    Production output convention (SWOT-Confluence):
        NC file  → <output_dir>/<reach_id>_qq.nc
        Log file → <output_dir>/logs/<reach_id>_qq.log

    Matches notebook section 4 exactly.
    """
    section(config, state, "4 OUTPUT DIR AND NC CREATION")

    try:
        # Write directly into output_dir — no extra qq/ subfolder.
        #
        # Production mount convention (run-confluence-locally j2 template):
        #   --bind mnt_dir/flpe/qq:/mnt/data/flpe/qq
        #   --output_dir /mnt/data/flpe/qq
        #
        # Files land at:
        #   <output_dir>/<reach_id>_qq.nc
        #   <output_dir>/logs/<reach_id>_qq.log


        output_path = state.output_dir
        output_path.mkdir(parents=True, exist_ok=True)

        output_filename = f"{state.rid}_{C.ALGO_NAME}.nc"
        output_nc_path  = output_path / output_filename

        log_output_path = output_path / C.LOG_OUTPUT_FOLDER_NAME
        log_output_path.mkdir(parents=True, exist_ok=True)

        log_filename  = f"{state.rid}_{C.ALGO_NAME}.{C.LOG_FILE_SUFFIX}"
        log_file_path = log_output_path / log_filename

        state.output_path     = output_path
        state.output_filename = output_filename
        state.output_nc_path  = output_nc_path
        state.log_output_path = log_output_path
        state.log_filename    = log_filename
        state.log_file_path   = log_file_path

    except Exception as exc:
        fail(config, state, f"Output directory/path creation failed: {exc}", detailed_code=-701)
        cwd = Path(".")
        rid = getattr(state, "rid", "unknown")
        state.output_path     = cwd
        state.output_filename = f"{rid}_{C.ALGO_NAME}.nc"
        state.output_nc_path  = cwd / state.output_filename
        state.log_output_path = cwd
        state.log_filename    = f"{rid}_{C.ALGO_NAME}.{C.LOG_FILE_SUFFIX}"
        state.log_file_path   = cwd / state.log_filename

    log_vars(
        config, state,
        output_dir=state.output_dir,
        output_path=state.output_path,
        output_filename=state.output_filename,
        output_nc_path=state.output_nc_path,
        log_output_path=state.log_output_path,
        log_filename=state.log_filename,
        log_file_path=state.log_file_path,
        invalid_reach=state.invalid_reach,
    )


# ---------------------------------------------------------------------------
# NetCDF writer
# ---------------------------------------------------------------------------

def write_nc(config: QQConfig, state: QQState) -> None:
    """
    Write the QQ output NetCDF.

    The file is always written — even for invalid reaches the structure is
    complete with fill values, so that downstream modules can safely open it.

    Mirrors notebook section 4-1-2 exactly.
    """
    section(config, state, "4-1 WRITE QQ OUTPUT NETCDF")

    # For every generated NetCDF, QQ determines:
    created_utc = M.utc_now_iso()                   # when it was created
    software_git_commit = M.get_git_commit()        # which exact Git commit produced it
    software_git_describe = M.get_git_describe()    # which tag/description/dirty state produced it

    # -----------------------------------------------------------------------
    # Run-specific root metadata (computed here, not in constants)
    # -----------------------------------------------------------------------
    output_nc_root_run_mode = config.run_mode
    output_nc_root_invalid_reach_detailed_code  = np.int32(state.invalid_reach_detailed_code)
    output_nc_root_invalid_reach_summary_code   = np.int32(state.invalid_reach_summary_code)
    output_nc_root_invalid_reach_detailed_codes = " | ".join(map(str, state.invalid_reach_detailed_codes))
    output_nc_root_invalid_reach_messages       = " | ".join(map(str, state.invalid_reach_messages))
    output_nc_root_algorithm    = C.ALGO_NAME
    output_nc_root_reach_id     = str(state.rid)
    output_nc_root_is_valid     = np.int32(not state.invalid_reach)
    output_nc_root_source_swot_file = str(getattr(state, "input_swot_path", ""))
    output_nc_root_source_sos_file  = str(getattr(state, "input_sos_path",  ""))
    output_nc_root_warnings = " | ".join(map(str, state.warnings_list))
    output_nc_root_errors   = " | ".join(map(str, state.errors_list))

    log_vars(
        config, state,
        output_nc_root_algorithm=output_nc_root_algorithm,
        output_nc_root_reach_id=output_nc_root_reach_id,
        output_nc_root_is_valid=output_nc_root_is_valid,
        output_nc_root_source_swot_file=output_nc_root_source_swot_file,
        output_nc_root_source_sos_file=output_nc_root_source_sos_file,
    )

    # -----------------------------------------------------------------------
    # Determine time variable dtype and write parameters
    # (set by output_arrays.py; fall back to f8 if not set)
    # -----------------------------------------------------------------------
    time_dtype_nc     = getattr(state, "output_nc_root_time_var_dtype_nc",     "f8")
    time_units        = getattr(state, "output_nc_root_time_var_units",         C.QQ_NC_TIME_UNITS)
    time_fill_value   = getattr(state, "output_nc_root_time_var_fill_value",    C.QQ_NC_DOUBLE_FILL_VALUE)
    time_missing      = getattr(state, "output_nc_root_time_var_missing_value", C.QQ_NC_DOUBLE_FILL_VALUE)

    try:
        from netCDF4 import Dataset  # type: ignore

        with Dataset(state.output_nc_path, "w", format="NETCDF4") as qq_nc:


            # ----------------------------------------------------------------
            # GLOBAL METADATA
            # ----------------------------------------------------------------

            # Dataset identity
            qq_nc.title = f"{C.ALGO_NAME.upper()} discharge output"
            # qq_nc.institution = M.PROJECT_AUTHOR
            qq_nc.institution = M.PROJECT_OWNER
            qq_nc.software_authors = M.PROJECT_AUTHOR
            if M.PROJECT_MAINTAINER:
                qq_nc.software_maintainers = M.PROJECT_MAINTAINER

            qq_nc.algorithm = output_nc_root_algorithm

            # Software identity / reproducibility
            qq_nc.software_name = M.PROJECT_NAME
            qq_nc.software_version = M.PROJECT_VERSION
            qq_nc.software_git_commit = software_git_commit
            qq_nc.software_git_describe = software_git_describe
            qq_nc.software_repository = M.REPOSITORY_URL

            # Creation provenance
            qq_nc.date_created = created_utc
            qq_nc.source = f"{M.PROJECT_NAME} {M.PROJECT_VERSION}"
            qq_nc.history = (
                f"{created_utc}: generated by "
                f"{M.PROJECT_NAME} {M.PROJECT_VERSION}; "
                f"git_commit={software_git_commit}"
            )
            qq_nc.references = M.REPOSITORY_URL
            qq_nc.comment = M.PROJECT_DESCRIPTION

            # Data conventions
            qq_nc.Conventions = C.OUTPUT_NC_ROOT_CONVENTIONS

            # Reach/run metadata
            qq_nc.reach_id = output_nc_root_reach_id
            qq_nc.is_valid = output_nc_root_is_valid

            qq_nc.source_swot_file = output_nc_root_source_swot_file
            qq_nc.source_sos_file  = output_nc_root_source_sos_file
            qq_nc.warnings      = output_nc_root_warnings
            qq_nc.errors        = output_nc_root_errors
            qq_nc.run_mode      = output_nc_root_run_mode
            qq_nc.invalid_reach_detailed_code  = output_nc_root_invalid_reach_detailed_code
            qq_nc.invalid_reach_summary_code   = output_nc_root_invalid_reach_summary_code
            qq_nc.invalid_reach_detailed_codes = output_nc_root_invalid_reach_detailed_codes
            qq_nc.invalid_reach_messages       = output_nc_root_invalid_reach_messages

            # ----------------------------------------------------------------
            # ROOT DIMENSIONS
            # ----------------------------------------------------------------
            qq_nc.createDimension(C.OUTPUT_NC_ROOT_DIM_NT_NAME,   len(state.QQ_time_out))
            qq_nc.createDimension(C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME, len(state.QQ_wse_quant_prob_out))

            # ----------------------------------------------------------------
            # ROOT VARIABLE: nt (integer index coordinate)
            # ----------------------------------------------------------------
            # nt_var = qq_nc.createVariable(
            #     C.OUTPUT_NC_ROOT_DIM_NT_NAME, "i4", (C.OUTPUT_NC_ROOT_DIM_NT_NAME,)
            # )

            nt_var = qq_nc.createVariable(
                C.OUTPUT_NC_ROOT_DIM_NT_NAME, "i4", (C.OUTPUT_NC_ROOT_DIM_NT_NAME,),
                fill_value=np.int32(-999999999),
            )

            nt_var.long_name = "time_step_index"
            nt_var.units     = "1"
            nt_var[:]        = np.arange(len(state.QQ_time_out), dtype=np.int32)

            # ----------------------------------------------------------------
            # ROOT VARIABLE: nwseq (integer index coordinate)
            # ----------------------------------------------------------------
            # nwseq_var = qq_nc.createVariable(
            #     C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME, "i4", (C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME,)
            # )

            nwseq_var = qq_nc.createVariable(
                C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME, "i4", (C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME,),
                fill_value=np.int32(-999999999),
            )

            nwseq_var.long_name = "wse_quantile_index"
            nwseq_var.units     = "1"
            nwseq_var[:]        = np.arange(len(state.QQ_wse_quant_prob_out), dtype=np.int32)

            # ----------------------------------------------------------------
            # ROOT VARIABLE: QQ_time
            # ----------------------------------------------------------------
            if time_dtype_nc is str:
                time_var = qq_nc.createVariable(
                    C.SWOT_QQ_DELIVERABLE_TIME_NAME,
                    str,
                    (C.OUTPUT_NC_ROOT_DIM_NT_NAME,),
                )
            else:
                time_var = qq_nc.createVariable(
                    C.SWOT_QQ_DELIVERABLE_TIME_NAME,
                    time_dtype_nc,
                    (C.OUTPUT_NC_ROOT_DIM_NT_NAME,),
                    fill_value=time_fill_value,
                )
                time_var.missing_value = time_missing

            time_var.long_name = "QQ_observation_time"
            time_var.units     = time_units
            time_var[:]        = state.QQ_time_out

            # ----------------------------------------------------------------
            # ROOT SCALAR: QQ_invalid_reach_detailed_flag
            # ----------------------------------------------------------------
            # det_flag_var = qq_nc.createVariable(
            #     C.SWOT_QQ_DELIVERABLE_INVALID_REACH_DETAILED_FLAG_NAME, "i4", ()
            # )

            det_flag_var = qq_nc.createVariable(
                C.SWOT_QQ_DELIVERABLE_INVALID_REACH_DETAILED_FLAG_NAME, "i4", (),
                fill_value=np.int32(-999999999),
            )

            det_flag_var.long_name       = "QQ_invalid_reach_detailed_reason_flag"
            det_flag_var.units           = "1"
            det_flag_var.flag_definition = json.dumps(C.INVALID_REACH_DETAILED_FLAG_DICT)
            det_flag_var.assignValue(np.int32(state.invalid_reach_detailed_code))

            # ----------------------------------------------------------------
            # ROOT SCALAR: QQ_invalid_reach_summary_flag
            # ----------------------------------------------------------------
            # sum_flag_var = qq_nc.createVariable(
            #     C.SWOT_QQ_DELIVERABLE_INVALID_REACH_SUMMARY_FLAG_NAME, "i4", ()
            # )

            sum_flag_var = qq_nc.createVariable(
                C.SWOT_QQ_DELIVERABLE_INVALID_REACH_SUMMARY_FLAG_NAME, "i4", (),
                fill_value=np.int32(-999999999),
            )

            sum_flag_var.long_name       = "QQ_invalid_reach_summary_reason_flag"
            sum_flag_var.units           = "1"
            sum_flag_var.flag_definition = json.dumps(C.INVALID_REACH_SUMMARY_FLAG_DICT)
            sum_flag_var.assignValue(np.int32(state.invalid_reach_summary_code))

            # ----------------------------------------------------------------
            # GROUP "q"
            # ----------------------------------------------------------------
            q_gp          = qq_nc.createGroup(C.OUTPUT_NC_Q_GP_NAME)
            q_gp.long_name = "QQ discharge estimates"

            q_var = q_gp.createVariable(
                C.SWOT_QQ_DELIVERABLE_Q_NAME, "f8",
                (C.OUTPUT_NC_ROOT_DIM_NT_NAME,),
                fill_value=C.QQ_NC_DOUBLE_FILL_VALUE,
            )
            q_var.long_name      = "QQ_discharge"
            q_var.units          = "m^3/s"
            q_var.missing_value  = C.QQ_NC_DOUBLE_FILL_VALUE
            q_var[:]             = state.QQ_q_out

            # qs_var = q_gp.createVariable(
            #     C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME, "i1",
            #     (C.OUTPUT_NC_ROOT_DIM_NT_NAME,),
            #     fill_value=C.QQ_NC_FLAG_FILL_VALUE,
            # )
            # qs_var.long_name      = "QQ_discharge_estimation_status_flag"
            # qs_var.units          = "1"
            # qs_var.missing_value  = C.QQ_NC_FLAG_FILL_VALUE
            # qs_var.flag_values    = C.QQ_Q_STATUS_FLAG_VALUES
            # qs_var.flag_meanings  = C.QQ_Q_STATUS_FLAG_MEANINGS
            # qs_var[:]             = state.QQ_q_status_flag_out

            qs_var = q_gp.createVariable(
                C.SWOT_QQ_DELIVERABLE_Q_STATUS_FLAG_NAME, "i2",
                (C.OUTPUT_NC_ROOT_DIM_NT_NAME,),
                fill_value=C.QQ_NC_FLAG_FILL_VALUE,
            )
            qs_var.long_name        = "QQ_discharge_estimation_status_flag"
            qs_var.units            = "1"
            qs_var.missing_value    = C.QQ_NC_FLAG_FILL_VALUE
            qs_var.flag_values      = C.QQ_Q_STATUS_FLAG_VALUES
            qs_var.flag_meanings    = C.QQ_Q_STATUS_FLAG_MEANINGS
            qs_var.flag_definition  = json.dumps(C.QQ_Q_STATUS_FLAG_DEFINITION)
            qs_var[:]               = state.QQ_q_status_flag_out

            # ----------------------------------------------------------------
            # GROUP "wse_quantile"
            # ----------------------------------------------------------------
            wq_gp          = qq_nc.createGroup(C.OUTPUT_NC_WSE_QUANT_GP_NAME)
            wq_gp.long_name = "QQ standardized WSE quantile table"

            prob_var = wq_gp.createVariable(
                C.SWOT_QQ_DELIVERABLE_WSE_QUANT_PROB_NAME, "f8",
                (C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME,),
                fill_value=C.QQ_NC_DOUBLE_FILL_VALUE,
            )
            prob_var.long_name     = "WSE_non_exceedance_probability"
            prob_var.units         = "1"
            prob_var.missing_value = C.QQ_NC_DOUBLE_FILL_VALUE
            prob_var[:]            = state.QQ_wse_quant_prob_out

            wse_var = wq_gp.createVariable(
                C.SWOT_QQ_DELIVERABLE_WSE_QUANT_WSE_NAME, "f8",
                (C.OUTPUT_NC_ROOT_DIM_NWSEQ_NAME,),
                fill_value=C.QQ_NC_DOUBLE_FILL_VALUE,
            )
            wse_var.long_name     = "WSE_quantile"
            wse_var.units         = "m"
            wse_var.missing_value = C.QQ_NC_DOUBLE_FILL_VALUE
            wse_var[:]            = state.QQ_wse_quant_wse_out

            # flag_var = wq_gp.createVariable(
            #     C.SWOT_QQ_DELIVERABLE_WSE_QUANT_FLAG_NAME, "i2", (),
            #     fill_value=C.WSE_QUANT_FLAG_ALL_MISSING_VALUE,
            # )
            # flag_var.long_name     = "WSE_quantile_table_resampling_flag"
            # flag_var.units         = "1"
            # flag_var.missing_value = C.WSE_QUANT_FLAG_ALL_MISSING_VALUE
            # flag_var.flag_meanings = (
            #     "0_same_length positive_downsampled negative_upsampled -999_all_missing"
            # )
            # flag_var.assignValue(state.QQ_wse_quant_flag_out)

            flag_var = wq_gp.createVariable(
                C.SWOT_QQ_DELIVERABLE_WSE_QUANT_FLAG_NAME, "i2", (),
                fill_value=C.WSE_QUANT_FLAG_ALL_MISSING_VALUE,
            )
            flag_var.long_name       = "WSE_quantile_table_resampling_flag"
            flag_var.units           = "1"
            flag_var.missing_value   = C.WSE_QUANT_FLAG_ALL_MISSING_VALUE
            flag_var.flag_definition = json.dumps(C.WSE_QUANT_FLAG_DEFINITION)
            flag_var.assignValue(state.QQ_wse_quant_flag_out)


            # ----------------------------------------------------------------
            # GROUP "lookup_table"  —  WSE-Q lookup table (auxiliary deliverable)
            # ----------------------------------------------------------------
            qq_nc.createDimension(
                C.OUTPUT_NC_ROOT_DIM_NLOOKUP_NAME, len(state.QQ_lookup_table_prob_out)
            )

            lut_gp          = qq_nc.createGroup(C.OUTPUT_NC_LOOKUP_TABLE_GP_NAME)
            lut_gp.long_name = "QQ WSE-discharge lookup table (probability overlap only, no extrapolation)"

            lut_prob_var = lut_gp.createVariable(
                C.SWOT_QQ_LOOKUP_TABLE_PROB_NAME, "f8",
                (C.OUTPUT_NC_ROOT_DIM_NLOOKUP_NAME,),
                fill_value=C.QQ_NC_DOUBLE_FILL_VALUE,
            )
            lut_prob_var.long_name     = "lookup_table_non_exceedance_probability"
            lut_prob_var.units         = "1"
            lut_prob_var.missing_value = C.QQ_NC_DOUBLE_FILL_VALUE
            lut_prob_var[:]            = state.QQ_lookup_table_prob_out

            lut_wse_var = lut_gp.createVariable(
                C.SWOT_QQ_LOOKUP_TABLE_WSE_NAME, "f8",
                (C.OUTPUT_NC_ROOT_DIM_NLOOKUP_NAME,),
                fill_value=C.QQ_NC_DOUBLE_FILL_VALUE,
            )
            lut_wse_var.long_name     = "lookup_table_WSE"
            lut_wse_var.units         = "m"
            lut_wse_var.missing_value = C.QQ_NC_DOUBLE_FILL_VALUE
            lut_wse_var[:]            = state.QQ_lookup_table_wse_out

            lut_q_var = lut_gp.createVariable(
                C.SWOT_QQ_LOOKUP_TABLE_Q_NAME, "f8",
                (C.OUTPUT_NC_ROOT_DIM_NLOOKUP_NAME,),
                fill_value=C.QQ_NC_DOUBLE_FILL_VALUE,
            )
            lut_q_var.long_name     = "lookup_table_discharge"
            lut_q_var.units         = "m^3/s"
            lut_q_var.missing_value = C.QQ_NC_DOUBLE_FILL_VALUE
            lut_q_var[:]            = state.QQ_lookup_table_q_out

            lut_flag_var = lut_gp.createVariable(
                C.SWOT_QQ_LOOKUP_TABLE_FLAG_NAME, "i2", (),
                fill_value=C.LOOKUP_TABLE_FLAG_ALL_MISSING_VALUE,
            )
            lut_flag_var.long_name       = "lookup_table_resampling_flag"
            lut_flag_var.units           = "1"
            lut_flag_var.missing_value   = C.LOOKUP_TABLE_FLAG_ALL_MISSING_VALUE
            lut_flag_var.flag_definition = json.dumps(C.LOOKUP_TABLE_FLAG_DEFINITION)
            lut_flag_var.assignValue(state.QQ_lookup_table_flag_out)

    except Exception as exc:
        fail(config, state, f"Output NetCDF write failed: {exc}", detailed_code=-702)

    log_vars(
        config, state,
        output_nc_path=state.output_nc_path,
        invalid_reach=state.invalid_reach,
        warnings_list=state.warnings_list,
        errors_list=state.errors_list,
    )


# ---------------------------------------------------------------------------
# Log file writer
# ---------------------------------------------------------------------------

def save_log(config: QQConfig, state: QQState) -> None:
    """Write the accumulated log to a plain-text .log file (section 5)."""
    section(config, state, "5 SAVE LOG FILE")

    if not config.save_log_file:
        log(config, state, "Log file saving is disabled (save_log_file=False)")
        return

    try:
        state.log_output_path.mkdir(parents=True, exist_ok=True)

        log_vars(
            config, state,
            log_output_path=state.log_output_path,
            log_filename=state.log_filename,
            log_file_path=state.log_file_path,
        )

        with open(state.log_file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(state.logs))

    except Exception as exc:
        fail(config, state, f"Log file write failed: {exc}", detailed_code=-703)
