# AI usage disclosure

This project was developed with AI assistance using advanced LLM coding assistants for architecture design, synthetic data pipeline drafting, technical auditing, and automated verification as permitted under the challenge guidelines.

## AI-assisted work

- Translating the challenge brief into the entity model, rules, anomaly scenarios and test plan.
- Drafting and iterating on the synthetic-data generator, validator, anomaly injector, exporters, metrics, CLI, tests and documentation.
- Debugging deterministic generation, data types, join integrity, schedule reconciliation and anomaly-injection interactions.
- Reviewing generated metrics and improving coverage allocation and assignment scheduling while retaining the stated hard constraints.

## Changes in the final audit pass

- Hardened validation so missing tables and fields produce schema violations rather than uncaught exceptions.
- Made CLI validation fail closed when the expected ground-truth match is not exact.
- Added a quality gate for the clean baseline, CSV round-trip, anomaly evaluation and SQLite foreign-key check.
- Expanded the manifest and reproducibility checks to cover metrics and validation-summary artefacts.
- Added accessibility, grade-band and zone coverage metrics; corrected attendance metric names; added contact-mismatch and home-address-exposure counts. Improved the seeded accessibility allocation so wheelchair-required coverage is 96.15% versus 95.61% for other students.
- Added safe output-directory handling so the generator does not recursively delete an arbitrary non-empty directory.
- Fixed an anomaly-injection ordering issue where an accessibility re-route could neutralise a previously injected capacity overflow.
- Added regression tests for malformed input, scale validation, output safety, metrics and generated-artifact integrity.
- Streamed SQLite SQL seed generation in bounded batches, added a separate full-seed SQLite import/FK verification script, and separated full-profile CSV reload validation from the primary build to avoid a second near-million-row in-memory copy.

## Candidate ownership

AI-generated code is not a substitute for candidate understanding. The candidate must personally run the tests and generation commands, review the assumptions, understand the decision and validation logic, and be ready to explain the trade-offs and limitations. No claim is made that the candidate has completed that personal review merely because an AI assistant audited the repository.

## Verification in this environment

The final audited package was tested with Python 3.13.5, NumPy 2.3.5, pandas 2.2.3 and pytest 9.0.2. The test suite, starter generation, full-profile CSV reload validation, direct SQLite import/FK check and independently compared full-profile checksums are recorded in the repository artefacts. The full profile uses synthetic data only; no external dataset or real personal contact information is used.
