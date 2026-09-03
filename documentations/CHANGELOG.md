# QQ Change Record

This file records user-visible and scientifically relevant changes between QQ versions.


## [1.0.0] — Initial release

### Included development commits

#### **1. July 17, 2026 — Initial production package (`30ce4ba`):**
- Initial commit: SWOT-QQ Discharge Estimation algorithm production package
- https://github.com/SWOT-Confluence/QQ/commit/30ce4ba8be1f5a769be316014af3aa174079181d

**Scientific method**

- Introduced reach-based quantile-quantile discharge estimation.
- Constructed an empirical non-exceedance distribution from cleaned and filtered SWOT WSE observations.
- Matched SWOT WSE probability to discharge through the reach-specific SOS FDC.
- Restricted default discharge matching to the probability range available in the SOS FDC.
- Added a standardized WSE quantile product on the default 0–1 probability grid.
- Added an auxiliary WSE-Q lookup table over the empirical-WSE/SOS-FDC probability overlap.

**Quality control**

- Added SWOT cleaning and optional `reach_q` filtering.
- Added a minimum clean/filtered SWOT WSE count.
- Added SOS FDC missing-data and minimum-length quality gates.
- Added detailed and summary invalid-reach flags.

**Outputs**

- Added per-reach QQ discharge NetCDF output.
- Added discharge status flags.
- Added standardized WSE quantile outputs and resampling flag.
- Added WSE-Q lookup-table outputs and flag.
- Added run logging and optional diagnostic plots.

**Execution**

- Added `RUN`, `DEBUG`, and `AUDIT` modes.
- Added local/container CLI execution and AWS Batch index support.
- Added automated tests for constants, helper/interpolation logic, lookup-table behavior, end-to-end valid/invalid reaches, and CLI exit behavior.


#### **2. July 19, 2026 — Added WSE-Q lookup table (`bf02287`):**

- Add Lookup Table
- https://github.com/SWOT-Confluence/QQ/commit/bf022871f8f805c96a45e72e0f9f7e51f25e7496


## [1.0.1] — Aug 27, 2026

**Metadata and provenance**

- Centralized static project metadata in `pyproject.toml`.
- Added `qq/metadata.py` for runtime package metadata and Git provenance.
- Added QQ software version and Git provenance to NetCDF global attributes.
- Added dataset creation timestamp, software repository, authorship,
  source, history, references, and description metadata.
- Added Git commit and release-tag provenance to production Docker builds.

**Documentation**

- Added v1.0.0 methodology documentation.
- Added architecture documentation.
- Added semantic versioning policy.
- Added this change record.
- Updated README metadata, input examples, documentation links, and output descriptions.

**Testing and deployment**

- Added package installation to CI.
- Added metadata/provenance tests.
- Added release-tag/package-version consistency validation.

**Scientific behavior**

- No QQ scientific algorithm change.
- No scientific constant/default change.
- No quantile-matching change.
- No FDC-processing change.
- No change to the scientific NetCDF variables, dimensions, groups, flags, or fill values.
- Corrected text descriptions of the WSE-quantile resampling flag and the WSE-Q
  lookup-table resampling flag in `qq/constants.py`; the downsampled/upsampled
  direction labels were textually inverted in v1.0.0. No numeric flag value,
  algorithm behavior, or output array changed.

**Compatibility**

- Added backward-compatible NetCDF global attributes.
- Existing QQ scientific output variables and file naming remain unchanged.



## [1.1.0] — Unreleased: Under Development

**Scientific behavior**

- Changed default `QQ_OUTPUT_TIME_DIMENSION_SOURCE` from `"swot_cleaned_filtered"` to `"swot"`.
  The output NetCDF `nt` dimension now spans all original SWOT observations (nt1), not only
  the clean+filtered subset (nt3). The `QQ_q_status_flag` variable distinguishes each row:
  `removed_by_cleaning`, `removed_by_filtering`, `no_quantile_applied`, or `valid_q_estimated`.
  This increases the output file size proportionally but preserves the full SWOT timeline.

- Added optional SOS FDC extension (`use_extended_fdc_from_sos_qMinMax`, default True).
  When enabled, the SOS flow-duration curve is extended to probability 0.0 using q_min
  and to probability 1.0 using q_max (both read from the SOS model group for the reach),
  creating `fdc_extended_q_MinMax`. The extended FDC is used in place of the original
  throughout the pipeline (quantile matching and WSE-Q lookup table). This enables
  discharge estimation across the full 0–100 % probability range, including extreme flows.
  If the extension cannot be created (q_min/q_max missing or invalid), the code falls
  back transparently to the original FDC and records the failure in the new
  `QQ_sos_fdc_extended_flag` NetCDF variable. No change when the flag is False.

- The WSE empirical quantile already covered [0, 1] inclusive via `WSE_PROB_GRID_MIN_PCT=0.0`
  and `WSE_PROB_GRID_MAX_PCT=100.0` (no change). Confirmed by this release.

- Extreme flow estimation: with the extended FDC covering p∈[0, 1], the existing
  `QUANTILE_MATCHING_FDC_EXTREMES_ESTIMATION=False` clip becomes [0.0, 1.0] — trivially
  non-restrictive. No change to quantile-matching constants was required.

**New CLI arguments**

- `-k` / `--skip_existing`: skip writing the output NetCDF if the file already exists.
  Default False (always overwrite). Useful for resuming interrupted batch runs.

- `--min_wse_len INT`: runtime override for the minimum clean+filtered SWOT WSE
  observation count (default 50, matching `MIN_CLEAN_FILT_SWOT_WSE_LEN`).

- `--use_extended_fdc` / `--no-use_extended_fdc`: toggle the FDC extension described
  above. Default True.

**New constants**

- `NAME_SOS_MODEL_GP_QMIN_VAR`, `NAME_SOS_MODEL_GP_QMAX_VAR`: SOS model group variable
  names for the per-reach minimum and maximum discharge.
- `FDC_EXTENDED_PROB_AT_QMIN = 0.0`, `FDC_EXTENDED_PROB_AT_QMAX = 1.0`: probability
  anchors for the q_min and q_max extension rows.
- `USE_EXTENDED_FDC_FROM_SOS_QMINMAX`: default True; controls the FDC extension.
- `SOS_FDC_EXTENDED_FLAG_*`: flag integer constants and dictionary.
- `SWOT_QQ_DELIVERABLE_SOS_FDC_EXTENDED_FLAG_NAME`: NetCDF variable name for the flag.

**New NetCDF output**

- `QQ_sos_fdc_extended_flag` (scalar i2, root): records whether the FDC extension was
  not attempted (0), succeeded (1), or fell back to the original FDC with a reason code
  (−1 q_min unavailable, −2 q_max unavailable, −3 creation failed).

**New runtime config fields**

- `QQConfig.skip_existing`, `QQConfig.min_clean_filt_swot_wse_len`,
  `QQConfig.use_extended_fdc_from_sos_qminmax`.

**Compatibility**

- The `QQ_sos_fdc_extended_flag` variable is a new addition; existing readers ignoring
  unknown variables are unaffected.
- The `nt` dimension size change (from nt3 to nt1) is a breaking schema change for
  downstream consumers that rely on the dimension size matching the clean+filtered count.
  All SWOT-Confluence pipeline modules that read QQ output should be verified.
