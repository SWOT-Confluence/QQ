# QQ Methodology — Version 1.0.0

## 1. Scope

QQ is a reach-based SWOT-Confluence FLPE algorithm that estimates river discharge from SWOT water-surface-elevation (WSE) observations by quantile matching against the SOS flow-duration curve (FDC).

Version 1.0.0 is a **single-reach, prior-based statistical method**. It does not use a hydraulic model, channel geometry, calibration parameters, or upstream/downstream reach information.

The implementation described here follows the code in `qq/pipeline.py` and its called modules.

## 2. Core idea

For one river reach:

1. Read and quality-control the SWOT WSE time series.
2. Rank the retained WSE observations and assign empirical non-exceedance probabilities.
3. Read the SOS discharge FDC for the same reach.
4. Convert each retained SWOT WSE to a non-exceedance probability.
5. Convert that probability to discharge using the SOS FDC.
6. Write the discharge time series and supporting diagnostic products to NetCDF.

The scientific assumption is that **WSE rank is a useful proxy for discharge rank**, and that the SOS FDC is representative for the reach.

---

# 3. Inputs

QQ selects one entry from `reaches.json` using a zero-based index.

Each entry must provide:

```json
{
  "reach_id": 12221500011,
  "swot": "12221500011_SWOT.nc",
  "sos": "af_sword_v17c_SOS_priors.nc",
  "sword": "af_sword_v17c.nc"
}
```

QQ v1.0.0 reads:

- the reach-specific SWOT NetCDF;
- the continental SOS prior NetCDF.

The `sword` field is required by the manifest schema and its path is constructed, but the SWORD NetCDF is not used in the v1.0.0 calculation.

---

# 4. High-level methodology

## 4.1 SWOT preparation

QQ reads the SWOT `reach` group and requires:

- `reach_id`
- `time`
- `time_str`
- `wse`
- `n_good_nod`

`reach_q` is optional.

The default processing then:

- removes rows with missing/invalid WSE or time information;
- if `reach_q` exists, removes rows with `reach_q == 3`;
- requires at least **50** clean and filtered WSE observations.

A reach failing a required quality gate is marked invalid.

## 4.2 Empirical WSE distribution

The retained WSE values are sorted in ascending order.

For `n` observations, their empirical non-exceedance probabilities are assigned linearly from:

```text
0.0 → 1.0
```

including both endpoints.

Thus, for the default v1.0.0 probability convention:

```text
smallest retained WSE → p = 0
largest retained WSE  → p = 1
```

## 4.3 Standard WSE quantile product

The empirical WSE curve is resampled onto the standard probability grid:

```text
0.00, 0.01, 0.02, ..., 1.00
```

for a total of **101 probability levels**.

Interior values are linearly interpolated. Edge extrapolation is enabled by default, although with the default empirical probability range of 0–1 a valid empirical table already spans the full deliverable range.

## 4.4 SOS flow-duration curve

For the selected reach, QQ reads:

```text
/reaches/reach_id
/model/probability
/model/flow_duration_q
```

SOS probabilities are stored as percentages and converted to `[0, 1]`.

The FDC must pass the default quality controls:

- missing FDC values ≤ 50%;
- longest consecutive missing gap ≤ 25 entries;
- at least 2 valid FDC values.

Valid FDC rows are sorted by non-exceedance probability.

## 4.5 Quantile matching

For every clean and filtered SWOT observation:

```text
WSE
 ↓
empirical WSE distribution
 ↓
non-exceedance probability p
 ↓
SOS FDC
 ↓
discharge Q
```

The WSE-to-probability and probability-to-discharge mappings use linear interpolation.

In v1.0.0 default settings:

- no fixed 5–95% probability clipping is applied;
- matching **is restricted to the probability range covered by the SOS FDC**;
- no discharge is estimated outside that FDC probability range.

## 4.6 WSE-Q lookup table

QQ also creates an auxiliary lookup table over the probability overlap between:

- the empirical WSE distribution; and
- the SOS FDC.

The default grid spacing is 1%.

Both WSE and Q are linearly interpolated on this common probability grid, with **no extrapolation** outside the shared range.

Failure of this auxiliary lookup table does not by itself invalidate the reach.

---

# 5. Low-level pipeline order

`qq.pipeline.run()` executes these steps in this exact order:

1. `setup_inputs_and_defaults()`
2. `read_json()`
3. `read_swot()`
4. `clean_swot()`
5. `filter_swot()`
6. `control_wse_count()`
7. `empirical_wse_quantile()`
8. `deliverable_wse_quantile()`
9. `deliverable_wse_flag()`
10. `read_sos()`
11. `build_lookup_table()`
12. `quantile_matching()`
13. `prepare_output_arrays()`
14. `prepare_plot_limits()`
15. `output_paths()`
16. `write_nc()`
17. `make_plots()`
18. `save_log()`

The mutable per-reach state is carried through these steps by `QQState`.

Scientific and ecosystem constants are centralized in `qq/constants.py`; run-specific paths, index, mode, logging and plotting settings are handled by `QQConfig`.

---

# 6. Output behavior

The main file is:

```text
<output_dir>/<reach_id>_qq.nc
```

Main products are:

```text
Root
├── QQ_time
├── QQ_invalid_reach_detailed_flag
├── QQ_invalid_reach_summary_flag
├── q/
│   ├── QQ_q
│   └── QQ_q_status_flag
├── wse_quantile/
│   ├── QQ_wse_quant_prob
│   ├── QQ_wse_quant_wse
│   └── QQ_wse_quant_flag
└── lookup_table/
    ├── QQ_lookup_table_prob
    ├── QQ_lookup_table_wse
    ├── QQ_lookup_table_q
    └── QQ_lookup_table_flag
```

Default discharge/time output uses the **cleaned and filtered SWOT time dimension**.

Missing discharge values are retained as fill values and accompanied by `QQ_q_status_flag`.

---

# 7. Fault handling

QQ v1.0.0 is designed to be fault-surviving in `RUN` and `AUDIT` modes.

A recoverable scientific/data failure:

- marks the reach invalid;
- records detailed and summary failure codes;
- continues far enough to produce a NetCDF output, generally with fill values.

In `DEBUG` mode, failures raise immediately to support development.

The CLI therefore returns success for both:

- a scientifically valid reach; and
- a recoverably invalid reach for which the expected fill-value output was written.

---

# 8. Main v1.0.0 scientific defaults

| Setting | v1.0.0 default |
|---|---:|
| Minimum clean/filtered SWOT WSE observations | `50` |
| WSE probability range | `0–100%` |
| WSE probability step | `1%` |
| Standard WSE quantile length | `101` |
| Remove `reach_q == 3` when available | Yes |
| Maximum missing SOS FDC percentage | `50%` |
| Maximum consecutive missing FDC gap | `25` |
| Minimum valid SOS FDC values | `2` |
| Fixed 5–95% clipping | Disabled |
| Restrict matching to SOS FDC probability range | Yes |
| Lookup-table probability step | `1%` |
| Lookup-table extrapolation | No |

For the exact implementation and all flags/fill values, `qq/constants.py` remains the authoritative source for v1.0.0.
