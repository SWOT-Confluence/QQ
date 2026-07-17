"""
tests/conftest.py
=================
Pytest fixtures that build minimal synthetic NetCDF files in a temporary
directory.  All fixtures use simple, analytically known values so that test
assertions can be derived without real SWOT or SOS data.
"""

from __future__ import annotations

import json
import tempfile
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qq.config import QQConfig

# ---------------------------------------------------------------------------
# Shared parameters
# ---------------------------------------------------------------------------
REACH_ID  = "73240000011"
N_OBS     = 60      # > MIN_CLEAN_FILT_SWOT_WSE_LEN (50)
N_FDC     = 100
WSE_BASE  = 200.0
WSE_RANGE = 5.0
Q_BASE    = 500.0
Q_RANGE   = 400.0


# ---------------------------------------------------------------------------
# Helper: write a SWOT NC for a given reach_id and n observations
# ---------------------------------------------------------------------------

def _write_swot_nc(path: Path, reach_id: str, n: int) -> None:
    """Write a minimal synthetic SWOT per-reach NetCDF to *path*."""
    from netCDF4 import Dataset

    NCHAR = 25
    epoch = np.datetime64("2000-01-01T00:00:00", "ns")
    times_ns = (
        np.datetime64("2016-01-01T00:00:00", "ns")
        + np.arange(n) * np.timedelta64(21 * 86400, "s")
    )
    times_s = ((times_ns - epoch) / np.timedelta64(1, "s")).astype(float)

    with Dataset(path, "w", format="NETCDF4") as ds:
        ds.createDimension("time",  n)
        ds.createDimension("nchar", NCHAR)

        # Root scalars
        nt_v = ds.createVariable("nt", "i4", ())
        nt_v.assignValue(np.int32(n))
        nx_v = ds.createVariable("nx", "i4", ())
        nx_v.assignValue(np.int32(1))

        # observations: char array [n, NCHAR]
        obs_v = ds.createVariable("observations", "S1", ("time", "nchar"))
        obs_data = np.zeros((n, NCHAR), dtype="S1")
        for i in range(n):
            label = f"pass_{i:05d}"[:NCHAR].ljust(NCHAR)
            for j, c in enumerate(label):
                obs_data[i, j] = c.encode("ascii")
        obs_v[:] = obs_data

        # reach group
        rg = ds.createGroup("reach")
        rid_v = rg.createVariable("reach_id", "i8", ())
        rid_v.assignValue(np.int64(int(reach_id)))

        # time
        tv       = rg.createVariable("time", "f8", ("time",))
        tv.units = "seconds since 2000-01-01 00:00:00.000"
        tv[:]    = times_s

        # time_str: ISO strings as char array
        ts_v = rg.createVariable("time_str", "S1", ("time", "nchar"))
        ts_data = np.zeros((n, NCHAR), dtype="S1")
        for i, t_ns in enumerate(times_ns):
            iso = pd.Timestamp(t_ns).isoformat(timespec="seconds")[:NCHAR].ljust(NCHAR)
            for j, c in enumerate(iso):
                ts_data[i, j] = c.encode("ascii")
        ts_v[:] = ts_data

        # wse: linearly increasing (predictable quantile)
        wse_v       = rg.createVariable("wse", "f8", ("time",), fill_value=-9.99e11)
        wse_v.units = "m"
        wse_v[:]    = WSE_BASE + np.linspace(0, WSE_RANGE, n)

        # n_good_nod
        nod_v    = rg.createVariable("n_good_nod", "i4", ("time",))
        nod_v[:] = np.full(n, 5, dtype=np.int32)

        # reach_q: all 0 (good quality — nothing filtered)
        rq_v    = rg.createVariable("reach_q", "i1", ("time",))
        rq_v[:] = np.zeros(n, dtype=np.int8)


def _write_sos_nc(path: Path, reach_id: str) -> None:
    """Write a minimal synthetic continent-level SOS NetCDF to *path*."""
    from netCDF4 import Dataset

    with Dataset(path, "w", format="NETCDF4") as ds:
        ds.createDimension("n_reaches", 1)
        ds.createDimension("n_prob",    N_FDC)

        rg       = ds.createGroup("reaches")
        rid_v    = rg.createVariable("reach_id", "i8", ("n_reaches",))
        rid_v[:] = np.array([int(reach_id)], dtype=np.int64)

        mg           = ds.createGroup("model")
        prob_v       = mg.createVariable("probability", "f8", ("n_prob",))
        prob_v.units = "percent"
        prob_v[:]    = np.linspace(1, 100, N_FDC)   # 1..100 → divided by 100 in algorithm

        # Simple linear FDC: Q = Q_BASE + Q_RANGE * (p/100)
        fdc         = Q_BASE + Q_RANGE * np.linspace(0.01, 1.0, N_FDC)
        fdc_v       = mg.createVariable("flow_duration_q", "f8", ("n_reaches", "n_prob"))
        fdc_v.units = "m3 s-1"
        fdc_v[0, :] = fdc


# ---------------------------------------------------------------------------
# Session-scoped temp directory + input tree
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tmp_input_dir(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("confluence_input")
    (base / "swot").mkdir()
    (base / "sos").mkdir()
    (base / "sword").mkdir()
    return base


@pytest.fixture(scope="session")
def swot_nc(tmp_input_dir) -> Path:
    path = tmp_input_dir / "swot" / f"{REACH_ID}_SWOT.nc"
    _write_swot_nc(path, REACH_ID, N_OBS)
    return path


@pytest.fixture(scope="session")
def sos_nc(tmp_input_dir) -> Path:
    path = tmp_input_dir / "sos" / "NA_sword_v17_SOS.nc"
    _write_sos_nc(path, REACH_ID)
    return path


@pytest.fixture(scope="session")
def reaches_json(tmp_input_dir, swot_nc, sos_nc) -> Path:
    manifest = [
        {
            "reach_id": REACH_ID,
            "swot":     swot_nc.name,
            "sos":      sos_nc.name,
            "sword":    "NA_sword_v17.nc",
        }
    ]
    json_path = tmp_input_dir / "reaches.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    return json_path


@pytest.fixture(scope="session")
def qq_config(tmp_input_dir, tmp_path_factory, reaches_json) -> QQConfig:
    out_dir = tmp_path_factory.mktemp("qq_output")
    return QQConfig(
        index=0,
        input_dir=tmp_input_dir,
        output_dir=out_dir,
        run_mode="RUN",
        print_out_statements=False,
        save_log_file=False,
        make_interactive_plots=False,
    )


# ---------------------------------------------------------------------------
# Fixture factory for invalid-reach scenarios (too few observations)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def invalid_reach_env(tmp_path_factory, sos_nc):
    """
    A self-contained input environment for a reach with only 5 SWOT observations
    (well below the 50-observation gate).  Returns (QQConfig, reach_id).
    """
    RID = "73240000099"
    base    = tmp_path_factory.mktemp("invalid_input")
    out_dir = tmp_path_factory.mktemp("invalid_output")

    (base / "swot").mkdir()
    (base / "sos").mkdir()
    (base / "sword").mkdir()

    # 5-observation SWOT file for this reach
    _write_swot_nc(base / "swot" / f"{RID}_SWOT.nc", RID, n=5)

    # Copy the shared SOS file
    shutil.copy(sos_nc, base / "sos" / sos_nc.name)

    # Write a per-reach SOS that includes the new reach_id
    sos_path = base / "sos" / sos_nc.name
    # Overwrite with one that has this reach_id instead
    _write_sos_nc(sos_path, RID)

    manifest = [
        {
            "reach_id": RID,
            "swot":     f"{RID}_SWOT.nc",
            "sos":      sos_nc.name,
            "sword":    "NA_sword_v17.nc",
        }
    ]
    with open(base / "reaches.json", "w") as f:
        json.dump(manifest, f)

    config = QQConfig(
        index=0,
        input_dir=base,
        output_dir=out_dir,
        run_mode="RUN",
        print_out_statements=False,
        save_log_file=False,
        make_interactive_plots=False,
    )
    return config, RID
