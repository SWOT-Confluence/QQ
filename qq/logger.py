"""
qq/logger.py
============
Logging utilities for the QQ algorithm.

The prototype notebook used print-based logging with a growing list of log
strings. This module reproduces that behaviour faithfully while also routing
messages through Python's stdlib `logging` module so that container stdout/
stderr capture works correctly in SLURM and AWS Batch environments.

Functions
---------
setup_logging(verbose)
    Configure the root logger once, at process startup.

log(config, state, msg, level)
    Append a formatted line to state.logs and emit via logging.

section(config, state, title)
    Emit a section header block (===== lines) as an INFO log.

warn(config, state, msg)
    Emit a WARNING log and add the message to state.warnings_list.

fail(config, state, msg, detailed_code)
    Mark the reach as invalid, store the error, and either log it (RUN/AUDIT
    mode) or raise RuntimeError (DEBUG mode).

log_vars(config, state, **kwargs)
    Emit a table of key=value pairs as INFO.

log_block(config, state, name, value, line)
    Emit a labelled block (separator + content) as INFO.

invalid_reach_detailed_to_summary_code(code)
    Convert a detailed flag code to its summary category code.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qq.config import QQConfig
    from qq.state import QQState


_logger = logging.getLogger("qq")


def setup_logging(verbose: bool = False) -> None:
    """Configure the root 'qq' logger.

    Should be called once at process startup (from run_qq.py).
    Idempotent: subsequent calls are no-ops if handlers already exist.
    """
    if _logger.handlers:
        return

    level = logging.DEBUG if verbose else logging.INFO
    _logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    handler.setFormatter(fmt)
    _logger.addHandler(handler)


# ---------------------------------------------------------------------------
# Core log helpers (mirror notebook functions)
# ---------------------------------------------------------------------------

def log(config: "QQConfig", state: "QQState", msg: str = "", level: str = "INFO") -> None:
    """Append a line to state.logs and emit via logging."""
    line = f"[{level}] {msg}" if msg else ""
    state.logs.append(line)
    if config.print_out_statements:
        if level == "ERROR":
            _logger.error(msg)
        elif level == "WARNING":
            _logger.warning(msg)
        elif level == "DEBUG":
            _logger.debug(msg)
        else:
            _logger.info(msg)


def section(config: "QQConfig", state: "QQState", title: str) -> None:
    """Emit a section header block."""
    log(config, state)
    log(config, state, "=" * 100)
    log(config, state, title)
    log(config, state, "=" * 100)
    log(config, state)


def warn(config: "QQConfig", state: "QQState", msg: str) -> None:
    """Emit a WARNING and accumulate in state.warnings_list."""
    state.warnings_list.append(msg)
    log(config, state, msg, "WARNING")


def invalid_reach_detailed_to_summary_code(code: int) -> int:
    """Map a detailed flag code to its summary category code."""
    if code == 0:
        return 0
    if -199 <= code <= -101:
        return -1
    if -299 <= code <= -201:
        return -2
    if -399 <= code <= -301:
        return -3
    if -499 <= code <= -401:
        return -4
    if -599 <= code <= -501:
        return -5
    if -699 <= code <= -601:
        return -6
    if -799 <= code <= -701:
        return -7
    return -999


def fail(
    config: "QQConfig",
    state: "QQState",
    msg: str,
    detailed_code: int = -999,
) -> None:
    """
    Mark the current reach as invalid.

    - Sets state.invalid_reach = True.
    - Records the detailed and summary codes (first failure wins for primary codes).
    - Appends to state.errors_list and state.invalid_reach_detailed_codes.
    - In DEBUG mode: raises RuntimeError immediately.
    - In RUN/AUDIT mode: logs the error and continues (fault-surviving).
    """
    state.invalid_reach = True
    state.invalid_reach_detailed_codes.append(detailed_code)
    state.invalid_reach_messages.append(msg)

    # First failure wins for the primary code displayed in the NetCDF scalar variable.
    if state.invalid_reach_detailed_code == 0:
        state.invalid_reach_detailed_code = detailed_code
        state.invalid_reach_summary_code = invalid_reach_detailed_to_summary_code(detailed_code)

    state.errors_list.append(msg)
    log(config, state, msg, "ERROR")

    if config.run_mode == "DEBUG":
        raise RuntimeError(msg)


def log_vars(config: "QQConfig", state: "QQState", **kwargs: Any) -> None:
    """Emit a table of key=value pairs."""
    for k, v in kwargs.items():
        log(config, state, f"{k:<45} = {v}")
    log(config, state)


def log_block(
    config: "QQConfig",
    state: "QQState",
    name: str,
    value: Any,
    line: str = "-",
) -> None:
    """Emit a labelled block (separator lines around a value's repr)."""
    log(config, state, line * 100)
    log(config, state, f"{name} =")
    log(config, state)
    log(config, state, str(value))
    log(config, state, line * 100)
    log(config, state)
