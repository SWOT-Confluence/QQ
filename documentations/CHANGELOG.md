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

**Compatibility**

- Added backward-compatible NetCDF global attributes.
- Existing QQ scientific output variables and file naming remain unchanged.



## [1.1.0] — Unreleased: Under Development
