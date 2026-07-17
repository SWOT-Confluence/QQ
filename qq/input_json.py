"""
qq/input_json.py
================
Reads the JSON manifest file and resolves per-reach input paths.

Production contract
-------------------
The JSON manifest is located at:
    <input_dir>/reaches.json

It is a JSON array where each element is a dict with fields:
    {
        "reach_id": "<11-digit SWORD reach ID>",
        "swot":     "<filename>.nc",
        "sos":      "<filename>.nc",
        "sword":    "<filename>.nc"
    }

The reach to process is selected by the index (from AWS_BATCH_JOB_ARRAY_INDEX
or --index CLI argument).

SWOT files are in <input_dir>/swot/<filename>.
SOS  files are in <input_dir>/sos/<filename>.
SWORD files are in <input_dir>/sword/<filename>.

Setup and JSON reading are always the first pipeline steps.
All errors set state.invalid_reach = True via logger.fail(),
which in RUN/AUDIT mode allows the pipeline to continue and
produce a fill-value NetCDF output.
"""

from __future__ import annotations

import json
from pathlib import Path

from qq import constants as C
from qq.config import QQConfig
from qq.helpers import make_empty_swot_df, make_empty_sos_fdc_table, make_empty_qq_matched_df
from qq.logger import fail, log, log_vars, section
from qq.state import QQState


def setup_inputs_and_defaults(config: QQConfig, state: QQState) -> None:
    """
    Resolve input/output directory paths and set safe default values on state.

    Must run before any other pipeline step so that state always has valid
    path attributes, even if subsequent steps fail.
    """
    section(config, state, "1-3 INPUTS")
    log(config, state, "-" * 100)
    log(config, state, "1-3-1 CLI - INDEX, INPUT DIR, JSON PATH, SWOT DIR, SOS DIR, SWORD DIR, OUTPUT DIR")
    log(config, state, "-" * 100)

    state.input_dir = config.input_dir
    state.input_json_path = config.input_dir / "reaches.json"
    state.input_swot_dir = config.input_dir / C.SWOT_FOLDER_IN_INPUT_DIR
    state.input_sos_dir = config.input_dir / C.SOS_FOLDER_IN_INPUT_DIR
    state.input_sword_dir = config.input_dir / C.SWORD_FOLDER_IN_INPUT_DIR
    state.output_dir = config.output_dir

    log_vars(
        config, state,
        index=config.index,
        input_dir=state.input_dir,
        input_json_path=state.input_json_path,
        input_swot_dir=state.input_swot_dir,
        input_sos_dir=state.input_sos_dir,
        input_sword_dir=state.input_sword_dir,
        output_dir=state.output_dir,
    )

    # Safety defaults: filled in properly by read_json() below.
    section(config, state, "1-4 SAFETY DEFAULT HELPERS")
    state.rid = f"unknown_reach_index_{config.index}"
    state.rid_swot_filename = None
    state.rid_sos_filename = None
    state.rid_sword_filename = None
    state.input_swot_path = None
    state.input_sos_path = None
    state.input_sword_path = None
    state.swot_dc_reach_swot_df = make_empty_swot_df(config)
    state.swot_dc_reach_swot_df_clean = make_empty_swot_df(config)
    state.swot_dc_reach_swot_df_clean_filt = make_empty_swot_df(config)
    state.sos_fdc_table = make_empty_sos_fdc_table()
    state.qq_matched_df = make_empty_qq_matched_df(config)

    import numpy as np
    state.QQ_q = np.array([], dtype=float)
    state.QQ_time = np.array([], dtype="datetime64[ns]")
    state.swot_dc_nt_2_swot_clean_filt = 0

    log_vars(
        config, state,
        rid=state.rid,
        input_swot_path=state.input_swot_path,
        input_sos_path=state.input_sos_path,
        input_sword_path=state.input_sword_path,
    )


def read_json(config: QQConfig, state: QQState) -> None:
    """
    Read the reaches.json manifest and extract the per-reach metadata.

    Populates on state:
        rid, rid_swot_filename, rid_sos_filename, rid_sword_filename,
        input_swot_path, input_sos_path, input_sword_path
    """
    section(config, state, "2 READING INPUTS")
    log(config, state, "-" * 100)
    log(config, state,
        "2-1 READ INPUT JSON FILE ---> EXTRACT: REACH_ID, SWOT FILENAME, SOS FILENAME, SWORD FILENAME")
    log(config, state, "-" * 100)

    reach_ids: list | None = None
    selected_reach: dict | None = None

    try:
        if not state.input_json_path.exists():
            fail(config, state, f"Input JSON file not found: {state.input_json_path}", detailed_code=-201)
            return

        with open(state.input_json_path, "r", encoding="utf-8") as f:
            reach_ids = json.load(f)

        if config.index < 0 or config.index >= len(reach_ids):
            fail(
                config, state,
                f"Reach index out of range: index={config.index}, reach_ids_len={len(reach_ids)}",
                detailed_code=-203,
            )
            return

        selected_reach = reach_ids[config.index]

        required_fields = [
            C.REACH_ID_FIELD_IN_REACHES_JSON,
            C.SWOT_FIELD_IN_REACHES_JSON,
            C.SOS_FIELD_IN_REACHES_JSON,
            C.SWORD_FIELD_IN_REACHES_JSON,
        ]
        missing_fields = [k for k in required_fields if k not in selected_reach]
        if missing_fields:
            fail(
                config, state,
                f"Missing required JSON fields: {missing_fields}",
                detailed_code=-204,
            )
            return

        state.rid = selected_reach[C.REACH_ID_FIELD_IN_REACHES_JSON]
        state.rid_swot_filename = selected_reach[C.SWOT_FIELD_IN_REACHES_JSON]
        state.rid_sos_filename = selected_reach[C.SOS_FIELD_IN_REACHES_JSON]
        state.rid_sword_filename = selected_reach[C.SWORD_FIELD_IN_REACHES_JSON]
        state.input_swot_path = state.input_swot_dir / state.rid_swot_filename
        state.input_sos_path = state.input_sos_dir / state.rid_sos_filename
        state.input_sword_path = state.input_sword_dir / state.rid_sword_filename

        log_vars(
            config, state,
            reach_ids_len=len(reach_ids),
            selected_reach=selected_reach,
            rid=state.rid,
            rid_swot_filename=state.rid_swot_filename,
            rid_sos_filename=state.rid_sos_filename,
            rid_sword_filename=state.rid_sword_filename,
            input_swot_path=state.input_swot_path,
            input_sos_path=state.input_sos_path,
            input_sword_path=state.input_sword_path,
        )

    except Exception as exc:
        fail(
            config, state,
            f"Input JSON read/path construction failed: {exc}",
            detailed_code=-202,
        )
