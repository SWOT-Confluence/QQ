#!/usr/bin/env python3
"""
run_qq.py
=========
SWOT-Confluence FLPE algorithm: QQ discharge estimation.
CLI entry point — compatible with run-confluence-locally and AWS Batch.

Production invocation (inside container):
    python run_qq.py /mnt/data/input/reaches.json

With optional overrides:
    python run_qq.py /mnt/data/input/reaches.json \\
        --input_dir  /mnt/data/input \\
        --output_dir /mnt/data/flpe/qq \\
        --mode       RUN \\
        --index      0

Local single-reach invocation:
    python run_qq.py /path/to/reaches.json --index 0

Reach selection
---------------
The reach to process is selected from the JSON manifest by an integer index.
Precedence (highest first):
  1. Environment variable AWS_BATCH_JOB_ARRAY_INDEX (set by AWS Batch / SLURM)
  2. CLI flag --index
  3. Default: 0

Exit codes
----------
  0  Success OR invalid/incomplete reach (fill-value output was written).
  1  Infrastructure failure (missing input dir, JSON not found, unrecoverable
     exception before any output could be produced).
"""

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_qq.py",
        description="SWOT-Confluence QQ FLPE algorithm — per-reach discharge estimation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument(
        "reach_file",
        type=str,
        help=(
            "Path to the reaches.json manifest file. "
            "Must be a JSON array of objects with fields: "
            "reach_id, swot, sos, sword."
        ),
    )

    p.add_argument(
        "--input_dir",
        type=str,
        default="/mnt/data/input",
        help=(
            "Root input directory containing reaches.json, swot/, sos/, sword/ "
            "(default: /mnt/data/input). "
            "Ignored if reach_file path already points to the correct location."
        ),
    )

    p.add_argument(
        "--output_dir",
        type=str,
        default="/mnt/data/flpe/qq",
        help="Output directory for per-reach NetCDF files (default: /mnt/data/flpe/qq).",
    )

    p.add_argument(
        "-i", "--index",
        type=int,
        default=0,
        help=(
            "0-based index into the JSON manifest selecting which reach to process. "
            "Overridden by AWS_BATCH_JOB_ARRAY_INDEX if set (default: 0). "
            "Short form -i matches the convention used by run-confluence-locally "
            "j2 templates (e.g. momma, hivdi)."
        ),
    )

    p.add_argument(
        "--mode",
        type=str,
        default="RUN",
        choices=["RUN", "DEBUG", "AUDIT"],
        help=(
            "Run mode: "
            "RUN=production (errors non-fatal, fill-value output written); "
            "DEBUG=raises immediately on error; "
            "AUDIT=like RUN with extra diagnostic logging. "
            "(default: RUN)"
        ),
    )

    p.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress log output to stdout/stderr.",
    )

    p.add_argument(
        "--no-log",
        dest="no_log",
        action="store_true",
        default=False,
        help="Do not write a .log file to the output directory.",
    )

    p.add_argument(
        "--plots",
        action="store_true",
        default=False,
        help=(
            "Generate interactive Plotly diagnostic plots (requires plotly). "
            "Disabled by default in production."
        ),
    )

    return p


def main() -> int:
    """
    Main entry point.

    Returns
    -------
    int
        0 for success or recoverable invalid-reach.
        1 for unrecoverable infrastructure failure.
    """
    # -----------------------------------------------------------------------
    # Parse CLI
    # -----------------------------------------------------------------------
    parser = _build_parser()
    args   = parser.parse_args()

    # -----------------------------------------------------------------------
    # Set up logging before importing the pipeline
    # -----------------------------------------------------------------------
    from qq.logger import setup_logging
    setup_logging(verbose=(args.mode == "DEBUG" or not args.quiet))

    # -----------------------------------------------------------------------
    # Resolve input directory from the reach_file path if not explicitly given
    # The production convention: reach_file IS inside input_dir.
    # We allow the reach_file argument to override the JSON path completely.
    # -----------------------------------------------------------------------
    reach_file_path = Path(args.reach_file)
    input_dir       = Path(args.input_dir)

    # If the reach_file exists at the given path, use its parent as the
    # input directory (backwards-compatible with notebook approach where the
    # JSON is in input_dir/reaches.json).
    # If it does not exist at the given path, try input_dir / basename.
    if not reach_file_path.exists():
        candidate = input_dir / reach_file_path.name
        if candidate.exists():
            reach_file_path = candidate

    # The production convention: input_dir is always passed explicitly.
    # We pass it directly through to config; the JSON reading module resolves
    # the full path as input_dir / "reaches.json".

    # -----------------------------------------------------------------------
    # Build config
    # -----------------------------------------------------------------------
    from qq.config import QQConfig
    try:
        config = QQConfig.from_args(args)
        # Allow reach_file argument to override the json path location
        if reach_file_path.parent != Path("."):
            config.input_dir = reach_file_path.parent
    except Exception as exc:
        import logging
        logging.getLogger("qq").error(f"Configuration error: {exc}")
        return 1

    # -----------------------------------------------------------------------
    # Run pipeline
    # -----------------------------------------------------------------------
    try:
        from qq.pipeline import run
        state = run(config)
    except RuntimeError:
        # Only raised in DEBUG mode (from logger.fail).
        # In DEBUG mode, the stack trace is the useful output; exit 1.
        return 1
    except Exception as exc:
        import logging
        logging.getLogger("qq").error(f"Unhandled pipeline exception: {exc}", exc_info=True)
        return 1

    # -----------------------------------------------------------------------
    # Exit code: 0 for both success and invalid-reach (per SWOT-Confluence
    # convention — a fill-value output file was written in both cases).
    # -----------------------------------------------------------------------
    return 0


if __name__ == "__main__":
    sys.exit(main())
