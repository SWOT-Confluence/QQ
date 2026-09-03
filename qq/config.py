"""
qq/config.py
============
Runtime configuration for a single QQ processing job.

QQConfig is constructed from the parsed CLI arguments (see run_qq.py).
It holds only the values that change between runs: file paths, the reach
index, the run mode, and output verbosity options.

All scientific constants remain in qq/constants.py.

Production path contract (SWOT-Confluence):
    - Input data is mounted at /mnt/data (entire EFS mount).
    - The JSON manifest (reaches.json) lives at <input_dir>/reaches.json.
    - SWOT files are at <input_dir>/swot/<filename>.
    - SOS files are at <input_dir>/sos/<filename>.
    - SWORD files are at <input_dir>/sword/<filename>.
    - Output NetCDFs go to <output_dir>/<reach_id>_qq.nc.
    - Log files go to <output_dir>/logs/<reach_id>_qq.log.
    - The reach index is taken from AWS_BATCH_JOB_ARRAY_INDEX if set,
      otherwise from --index (default 0).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# Default production paths (inside the container).
# These match the EFS mount convention used by all SWOT-Confluence FLPE modules.
DEFAULT_INPUT_DIR: Path = Path("/mnt/data/input")
DEFAULT_OUTPUT_DIR: Path = Path("/mnt/data/flpe/qq")


@dataclass
class QQConfig:
    """
    Runtime configuration for one QQ processing invocation.

    Parameters
    ----------
    index : int
        0-based index into the JSON reach manifest. Selects which reach to
        process.  Resolved from AWS_BATCH_JOB_ARRAY_INDEX → --index → 0.
    input_dir : Path
        Root input directory.  Contains reaches.json, swot/, sos/, sword/.
    output_dir : Path
        Directory where per-reach NetCDF files are written.
    run_mode : str
        "RUN"   — production: errors are non-fatal; a fill-value output is
                  written and execution continues.
        "DEBUG" — developer: errors raise RuntimeError immediately.
        "AUDIT" — like RUN but logs additional NC metadata blocks.
    print_out_statements : bool
        Whether to emit log lines to stdout/stderr (via the logging module).
    save_log_file : bool
        Whether to write the accumulated log to a .log text file.
    make_interactive_plots : bool
        Whether to render Plotly diagnostic plots (requires plotly to be
        installed; silently skipped if not available or if False).

    skip_existing : bool
        If True, skip writing the output NetCDF when it already exists at the
        expected path.  Default False (always overwrite).
    min_clean_filt_swot_wse_len : int
        Runtime override for the minimum clean+filtered SWOT WSE observation
        count required to proceed.  Default matches C.MIN_CLEAN_FILT_SWOT_WSE_LEN (50).
    use_extended_fdc_from_sos_qminmax : bool
        If True, extend the SOS FDC with q_min (at p=0.0) and q_max (at p=1.0)
        from the SOS model group before quantile matching.  Default True.
    """

    index: int = 0
    input_dir: Path = field(default_factory=lambda: DEFAULT_INPUT_DIR)
    output_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR)
    run_mode: str = "RUN"
    print_out_statements: bool = True
    save_log_file: bool = True
    make_interactive_plots: bool = False
    skip_existing: bool = False
    min_clean_filt_swot_wse_len: int = 50
    use_extended_fdc_from_sos_qminmax: bool = True

    # Resolved lazily during the first pipeline step.
    _json_path: Path | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.input_dir = Path(self.input_dir)
        self.output_dir = Path(self.output_dir)
        if self.run_mode not in ("RUN", "DEBUG", "AUDIT"):
            raise ValueError(
                f"Invalid run_mode={self.run_mode!r}. "
                "Must be one of: 'RUN', 'DEBUG', 'AUDIT'."
            )

    @classmethod
    def from_args(cls, args: object) -> "QQConfig":
        """
        Construct a QQConfig from the parsed argparse Namespace.

        AWS_BATCH_JOB_ARRAY_INDEX takes precedence over --index.
        """
        env_index = os.environ.get("AWS_BATCH_JOB_ARRAY_INDEX")
        if env_index is not None:
            index = int(env_index)
        else:
            index = int(args.index)

        return cls(
            index=index,
            input_dir=Path(args.input_dir),
            output_dir=Path(args.output_dir),
            run_mode=args.mode.upper(),
            print_out_statements=not getattr(args, "quiet", False),
            save_log_file=not getattr(args, "no_log", False),
            make_interactive_plots=getattr(args, "plots", False),
            skip_existing=getattr(args, "skip_existing", False),
            min_clean_filt_swot_wse_len=getattr(args, "min_wse_len", 50),
            use_extended_fdc_from_sos_qminmax=getattr(args, "use_extended_fdc", True),
        )
