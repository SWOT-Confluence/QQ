# QQ — Quantile-Quantile Discharge Estimation

A reach-based Discharge Estimation algorithm for the [SWOT-Confluence](https://github.com/SWOT-Confluence) pipeline. QQ estimates river discharge from SWOT water surface elevation (WSE) observations by mapping WSE rank to discharge rank via the SOS Flow Duration Curve (FDC) — no hydraulic model, channel geometry, or calibration parameters required.

---

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Input Contract](#input-contract)
- [Output Contract](#output-contract)
- [CLI Reference](#cli-reference)
- [Repository Structure](#repository-structure)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [SWOT-Confluence Integration](#swot-confluence-integration)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Maintainers](#maintainers)

---

## Overview

QQ (Quantile-Quantile) matching is a statistical, prior-based discharge estimation algorithm. For each reach, it:

1. Ranks clean, quality-filtered SWOT WSE observations to build an **empirical non-exceedance probability curve**.
2. Resamples that curve onto a standardized **deliverable probability grid** for NetCDF output.
3. Maps each observation's probability to a discharge value using the **SOS Flow Duration Curve** at the same probability level.
4. Writes a per-reach NetCDF discharge time series, always — including a fill-value file for reaches that fail quality gates.

Unlike hydraulic FLPE algorithms, QQ requires no channel geometry, no Manning's roughness coefficient, and no rating-curve calibration. It depends only on the assumption that WSE rank approximates discharge rank over the observation period, and that the SOS FDC is representative of that period.

<!-- See [`docs/methodology.md`](docs/methodology.md) for the full scientific description. -->

---

## Requirements

- Python **3.11+**
- `netCDF4`, `numpy`, `pandas` (see [`requirements.txt`](requirements.txt))
- Git

---

## Installation

### 1. Navigate to the folder before repository root
```bash
cd path\to\folder\of\your\choice
```

### 2. Clone the QQ repository
```bash
git clone https://github.com/SWOT-Confluence/QQ.git
cd QQ
```

### 3. Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
```

### 4. Install dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Editable install (optional, for development)
```bash
python -m pip install -e .
```

### 6. Smoke test — CLI help
```bash
python run_qq.py --help
```

### 7. Run all tests
```bash
python -m pip install pytest
python -m pytest tests -v
```

### 8. Run the tool over a reach of interest, locally (required inputs are: reaches.json as a list of dictionaries, reach-based swot, continental sos, and (optionally) continental sword netCDF files)

On windows:

```bash
python run_qq.py Path\to\input\dir\input\reaches.json `
    --input_dir  Path\to\input\dir\input `
    --output_dir Path\to\input\dir\output `
    --index      19 `
    --mode       RUN

```

---

## Quick Start

```bash
python run_qq.py /path/to/input/reaches.json \
    --input_dir  /path/to/input \
    --output_dir /path/to/output \
    -i 0 \
    --mode RUN
```

Output appears at:
```
<output_dir>/<reach_id>_qq.nc
<output_dir>/logs/<reach_id>_qq.log
```

Run the test suite:
```bash
pytest tests/ -v
```

---

## Input Contract

```
<input_dir>/
├── reaches.json          # manifest: [{reach_id, swot, sos, sword}, ...]
├── swot/
│   └── <reach_id>_SWOT.nc
└── sos/
    └── <continent>_SOS.nc
```

**`reaches.json`** — one entry per reach:
```json
[
  {
    "reach_id": "21101200141",
    "swot":  "21101200141_SWOT.nc",
    "sos":   "eu_sword_v17c_SOS_priors.nc",
    "sword": "eu_sword_v17b.nc"
  }
]
```

> `sword` is required in the manifest for schema completeness but is **not read** by QQ.

The reach to process is selected by index into this array:
`AWS_BATCH_JOB_ARRAY_INDEX` (env var) → `-i` / `--index` (CLI) → `0` (default).

---

## Output Contract

**File:** `<output_dir>/<reach_id>_qq.nc` — always written, for both valid and invalid reaches.

```
Root
  Dimensions: nt, nwseq (101 by default)
  Variables:  QQ_time(nt), QQ_invalid_reach_detailed_flag, QQ_invalid_reach_summary_flag
  Attrs:      algorithm, reach_id, is_valid, source_swot_file, source_sos_file, run_mode, ...

Group "q"
  QQ_q(nt)                f8   discharge [m³/s]
  QQ_q_status_flag(nt)    i2   0=valid 1=cleaned 2=filtered 3=no_quantile 4=invalid −999=missing

Group "wse_quantile"
  QQ_wse_quant_prob(nwseq)  f8  non-exceedance probabilities
  QQ_wse_quant_wse(nwseq)   f8  WSE at each quantile level [m]
  QQ_wse_quant_flag         i2  scalar resampling quality flag

Group "lookup_table"
  QQ_lookup_table_prob(nlookup)  f8  probabilities within [max(emp_min, fdc_min), min(emp_max, fdc_max)]
  QQ_lookup_table_wse(nlookup)   f8  WSE at each lookup probability (interpolated, no extrapolation)
  QQ_lookup_table_q(nlookup)     f8  discharge at each lookup probability (interpolated, no extrapolation)
  QQ_lookup_table_flag           i2  scalar resampling flag (same sign convention as QQ_wse_quant_flag)
```

Fill / missing values: `f8` → `-999999999999.0`, `i2` flags → `-999`, `i4` scalars → `-999999999`.
(The WSE-Q lookup table reuses these same values — no new fill-value convention was introduced.)

Full schema in [`docs/architecture.md`](docs/architecture.md).

---

## CLI Reference

```
python run_qq.py <reach_file> [OPTIONS]

Positional:
  reach_file            Path to reaches.json manifest

Options:
  -i, --index INT       0-based reach index (default: 0)
                        Overridden by $AWS_BATCH_JOB_ARRAY_INDEX
  --input_dir DIR       Root input directory (default: /mnt/data/input)
  --output_dir DIR      Output directory (default: /mnt/data/output)
  --mode {RUN,DEBUG,AUDIT}
                        RUN   = production; errors non-fatal, fill-value NC written
                        DEBUG = raises immediately on error
                        AUDIT = RUN + extra diagnostic logging
  --quiet               Suppress stdout/stderr logging
  --no-log              Skip writing the .log file
  --plots               Generate optional Plotly diagnostic plots
```

**Exit codes:** `0` = success or recoverable invalid reach (fill-value NC written) · `1` = unrecoverable infrastructure failure only.

---

## Repository Structure

```
QQ/
├── qq/                          Python package
│   ├── constants.py             All scientific + ecosystem constants
│   ├── config.py                Runtime configuration (from CLI/env)
│   ├── state.py                 Mutable per-reach run state
│   ├── logger.py                 Logging + fault-survival helpers
│   ├── helpers.py                Interpolation utilities
│   ├── input_json.py             Manifest reading, path resolution
│   ├── input_swot.py             SWOT read → clean → filter → gate
│   ├── input_sos.py              SOS FDC extraction
│   ├── wse_quantile.py           Empirical + deliverable WSE quantile
│   ├── quantile_matching.py      Core WSE → probability → discharge
│   ├── output_arrays.py          Final output array preparation
│   ├── output_netcdf.py          NetCDF writer + log saver
│   ├── diagnostics.py            Optional Plotly plots
│   └── pipeline.py               Orchestrator
├── tests/                       60 automated tests
├── docs/                        Full documentation suite
├── confluence/templates/modules/qq.sh.j2   run-confluence-locally SLURM template
├── deploy/deploy.sh              5-argument deploy script
├── terraform/                    AWS Batch + ECR infrastructure
├── .github/workflows/            CI (test.yml) + CD (release.yml)
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── run_qq.py                     CLI entry point
```

---

## Configuration

All scientific constants live in [`qq/constants.py`](qq/constants.py), including:

| Constant | Default | Purpose |
|---|---|---|
| `MIN_CLEAN_FILT_SWOT_WSE_LEN` | `50` | Minimum observations required per reach |
| `WSE_PROB_GRID_MIN_PCT` / `MAX_PCT` / `STEP_PCT` | `0 / 100 / 1` | Deliverable probability grid bounds |
| `QUANTILE_MATCHING_PREDEFINED_EXTREMES_ESTIMATION` | `True` | Disables fixed 5–95% clip |
| `QUANTILE_MATCHING_FDC_EXTREMES_ESTIMATION` | `False` | Clips matching to FDC's own probability range |
| `FDC_MAX_MISSING_PERC_TO_PROCEED` | `50.0` | SOS FDC quality gate |

Runtime settings (paths, index, mode) are resolved separately in `qq/config.py` from CLI arguments — see [CLI Reference](#cli-reference).

---

## Testing

```bash
pytest tests/ -v
```

| File | Coverage |
|---|---|
| `test_constants.py` | Constant values, dtypes, fill values |
| `test_helpers.py` | Interpolation utilities |
| `test_pipeline.py` | End-to-end pipeline, valid + invalid reach, CLI exit codes |

60 tests total, all passing on Python 3.11+.

---


## License

Distributed under NASA/CNES SWOT-Confluence project terms. See the organization-level license policy at [SWOT-Confluence](https://github.com/SWOT-Confluence).
