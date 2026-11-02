# Audit and improvement log

## Final submission hardening

- Added structural validator handling for missing tables, missing fields and wrong table types.
- Added positive scale and calendar preconditions to `Config`.
- Added a strict output-format parser and fail-closed CLI exit codes.
- Replaced broad output-directory deletion with ownership-marker-based cleanup.
- Added CSV export round-trip validation to the generation quality gate.
- Expanded reproducibility hashing to include `metrics.json` and `validation_summary.json` as well as data and ground truth.
- Added environment versions and a complete synthetic-data provenance statement to the manifest.
- Added accessibility, grade-band and geographic coverage metrics, plus contact mismatch and address-leak counts.
- Changed stop placement to blend population demand and equal service-zone coverage; adjusted route start-time generation and capacity-aware scoring; increased wheelchair-accessible stop availability to 96% and vehicle availability to 90%/75%/75% by vehicle type. The full-seed assignment gap between wheelchair-required and other students improved from 9.75 percentage points to 0.54 percentage points in the final fixed-seed scenario. These assumptions are described in `ASSUMPTIONS.md`.
- Added a standalone SQLite seed verification script so the full-scale 119 MB SQL export can be imported and checked with `PRAGMA foreign_key_check` without holding a duplicate staging database inside the main generation process.
- Reordered anomaly injection so assignment changes happen before capacity-overflow injection, preventing a downstream mutation from accidentally removing an already-labelled overflow.
- Expanded the regression suite from 15 to 22 tests, then added two relational-integrity regression tests (24 total).
- Added a manifest-comparison utility for two independent full-scale builds; the starter convenience command continues to use isolated Python processes.
- Changed anomaly injection to copy only the five tables it mutates, sharing immutable tables to avoid duplicating the full attendance event table in memory.
- Added composite uniqueness constraints for route-stop bridge pairs, route/day disruptions, student/day attendance events, and attendance-event/guardian notifications; validator now explicitly rejects a stop repeated within a route.
- Moved reproducibility temp builds to the system temp directory and deferred NumPy/pandas imports in the parent CLI process to reduce full-profile peak memory.
- Added a full-scale verification evidence bundle documenting clean-baseline validation, exported CSV validation, SQL import/FK checks, and two-run checksums.

The generator remains deterministic for the same seed and configuration. No anomaly labels are added to input feature columns.
