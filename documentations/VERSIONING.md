# QQ Versioning Policy

QQ uses **Semantic Versioning**:

```text
MAJOR.MINOR.PATCH
```

Example:

```text
1.0.0
```

Git release tags use:

```text
v1.0.0
```

The repository release workflow is triggered by tags matching `v*`.

## 1. PATCH — `x.y.Z`

QQ uses a patch release when the intended scientific method and public data contract do not change.

Examples:

- documentation additions or corrections;
- tests;
- logging or comments;
- metadata-only corrections;
- internal refactoring intended to preserve numerical results;
- backward-compatible bug fixes that restore the intended behavior.

Example:

```text
1.0.0 → 1.0.1
```

## 2. MINOR — `x.Y.z`

QQ uses a minor release for a backward-compatible scientific or functional change that may change results.

Examples:

- changing a scientific threshold or default constant;
- changing how the SOS FDC is screened, constructed, interpolated, or used;
- adding a new optional scientific mode;
- adding a new CLI/configuration capability while preserving existing usage;
- changing quantile-matching behavior while keeping the same basic input/output contract.

Example:

```text
1.0.1 → 1.1.0
```

For scientific reproducibility, QQ considers a default-value change that can change discharge results as a **MINOR**, not **PATCH**.

## 3. MAJOR — `X.y.z`

QQ uses a major release for an incompatible contract or a fundamental / architectural redesign.

Examples:

- requiring new input data that old workflows do not provide;
- changing the NetCDF schema incompatibly;
- removing or renaming required outputs;
- replacing the core QQ method with a substantially different methodology;
- making upstream/downstream reach information a required part of the algorithm.

Example:

```text
1.x.x → 2.0.0
```

---

# 4. Version source

The canonical QQ software version is defined only in:

```text
pyproject.toml
```

---

# 5. Release checklist for the maintainers

For each release:

1. Decide `MAJOR.MINOR.PATCH`.
2. Update `pyproject.toml`.
3. Update `documentations/CHANGELOG.md`.
4. if the methodology is updated, release an updated METHODOLOGY_vX.y.z.md document.
5. Reinstall/refresh the editable package locally.
6. Run the full test suite.
7. Commit the release changes.
8. Merge the approved branch into `main`.
9. Tag the exact release commit: matching vX.Y.Z tag. for example:

```bash
git tag -a v1.0.1 -m "QQ v1.0.1"
git push origin v1.0.1
```
