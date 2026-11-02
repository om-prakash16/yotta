# School-bus routing and attendance operations simulator

A deterministic, parameterised decision-data pipeline for the YottaFlex Associate AI Forward Deployed Engineer challenge. It assigns synthetic students to approved pickup stops and AM routes while enforcing service-area, walking-distance, accessibility, pickup-window and bus-capacity constraints. It then simulates daily attendance, route disruptions, missed pickups and privacy-safe guardian notifications.

The project is deliberately **rules-first and reproducible**: labels are derived from documented business rules, injected anomalies are stored separately as ground truth, and the same fixed seed regenerates the same artefacts.

## What it delivers

- 11 required entities plus calendar, capacity history, route disruptions and append-only assignment events.
- Deterministic, traceable assignment decisions with explicit reasons for every unassigned student.
- Event-level attendance across 200 school days, including absences, cancelled routes and missed pickups.
- Synthetic guardian notifications with contact matching and home-address leakage checks.
- Five labelled negative scenarios, a separate ground-truth dataset and per-class precision/recall evaluation.
- CSV, JSON and SQLite-compatible SQL seed exports, a data dictionary, a schema, quality summaries, operational metrics and SHA-256 manifests.
- Composite uniqueness is enforced for route-stop bridge pairs, one disruption per route/day, one attendance event per student/day, and one guardian notification per attendance event.
- A two-run reproducibility command that compares all generated data, metrics and validation-summary artefacts.

## Quick start

Python 3.11+ is recommended. The pinned environment below is the one used for the final verification in this repository (Python 3.13.5, NumPy 2.3.5, pandas 2.2.3 and pytest 9.0.2).

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pytest -q
python -m busroute generate --profile starter
python -m busroute validate \
  --data datasets/starter/data \
  --ground-truth datasets/starter/ground_truth/ground_truth.csv
```

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python -m pytest -q
python -m busroute generate --profile starter
python -m busroute validate --data datasets/starter/data --ground-truth datasets/starter/ground_truth/ground_truth.csv
```

The validator command exits `0` only when all expected anomalies match ground truth exactly and there are no unexplained rule violations. Validating an intentionally injected dataset without `--ground-truth` is expected to return a non-zero exit code.

## Dataset profiles

| Profile | Students | Buses | Stops | School days | Anomalies per type |
|---|---:|---:|---:|---:|---:|
| `starter` | 500 | 20 | 60 | 30 | 3 |
| `full` | 5,000 | 100 | 300 | 200 | 5 |
| `test` | 600 | 15 | 45 | 15 | 2 |

All profiles use the same generator. The full profile produces approximately 900,000 attendance events. Scale is parameterised, for example:

```bash
python -m busroute generate --profile full --students 2000 --buses 40 --stops 120 --days 60
python -m busroute generate --profile full --formats csv,json,sql --out datasets/full_run1
python -m busroute validate --data datasets/full_run1/data --ground-truth datasets/full_run1/ground_truth/ground_truth.csv
python scripts/verify_sqlite_seed.py --seed datasets/full_run1/data/seed.sql
python -m busroute generate --profile full --formats csv,json,sql --out datasets/full_run2
python scripts/compare_reproducibility.py --first datasets/full_run1 --second datasets/full_run2 --out docs/reproducibility_full.json
```

The full CSV/JSON/SQL dataset is intentionally not committed because it is large (the full SQL seed alone is over 100 MB, beyond GitHub's per-file limit). Run `generate --profile full` locally to materialise it. The committed `starter` dataset is a compact, inspectable sample; `docs/full_manifest.json` records the full-scale environment, row counts, source provenance and artefact hashes; `docs/reproducibility_full.json` contains the two-run checksum comparison; `docs/full_scale_verification.json` records the baseline, exported-data and SQL integrity checks.

## Decision logic

1. Generate approved service zones, stops, buses, drivers, students and guardian contacts. Student and stop coordinates are synthetic; stop allocation blends demand-weighted placement with an even zone-coverage share so rural areas are not ignored.
2. Build overlapping route candidates. Each active stop is available on multiple routes through the `route_stops` bridge table. Route-stop offsets are derived from segment distance, travel speed and dwell time.
3. Assign wheelchair-required students first. A candidate must satisfy all hard constraints: approved service area and stop, grade-specific walking distance, wheelchair-accessible stop and bus, pickup window, total seats and wheelchair positions.
4. Choose among feasible candidates using `distance_to_stop + 1.5 × route_load_ratio`. This deterministic heuristic balances proximity and remaining capacity; it is not claimed to be a globally optimal vehicle-routing solver.
5. Record one assignment decision per student and an append-only lifecycle event. Students who cannot be safely assigned retain a reason such as `outside_service_area`, `no_stop_within_walking_distance`, `no_accessible_route`, `pickup_window_conflict` or `capacity_full`.
6. Simulate 200 school days. Attendance precedence is documented as absent, then route-cancelled, then missed pickup, then present. Route disruptions are reflected in events; notifications go only to the primary synthetic guardian contact.
7. Inject deliberate edge cases only after generating a valid baseline. Ground-truth labels never appear in input table columns.

The chosen geometry, walking limits, accessible-resource assumptions, scoring function and lifecycle semantics are documented in [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

## Required negative scenarios

| `issue_type` | Injection | Expected response | Validator rule |
|---|---|---|---|
| `bus_capacity_exceeded` | Capacity-change event reduces seats below assigned riders | Reject the change or reassign riders before the effective date | `rule.bus_capacity_exceeded` |
| `incompatible_route_assignment` | Wheelchair student is moved to a non-accessible route, or an accessibility need arrives late | Block assignment or re-run assignment | `rule.accessibility_incompatible` |
| `impossible_travel_time` | Route segment travel time is set to an impossible value | Reject route and recalculate schedule | `rule.impossible_travel` |
| `notification_invalid_contact` | Notification destination is malformed / does not match guardian record | Block send and route to manual contact workflow | `rule.notification_destination_format`, `rule.notification_matches_guardian` |
| `unapproved_address_exposed` | Student home address is appended to an outbound message | Redact message and prevent disclosure | `rule.address_exposed` |

The anomaly injector performs assignment-changing mutations before the capacity anomaly. This ordering prevents a later re-route from accidentally removing a previously injected capacity overflow.

## Output layout

Each `datasets/<profile>/` directory contains:

| File / directory | Purpose |
|---|---|
| `data/*.csv`, `data/*.json`, `data/seed.sql` | Input data tables in requested formats |
| `ground_truth/ground_truth.csv`, `ground_truth/ground_truth.json` | Separate labelled anomalies and expected decisions |
| `validation_summary.json` | Baseline/ground-truth results, CSV round-trip status, FK validation method and exception counts. The full profile defers CSV reload to the explicit `validate` command to avoid duplicating nearly one million attendance rows in memory. |
| `metrics.json` | Assignment, fleet, accessibility/grade/zone coverage, attendance, disruption and notification metrics |
| `manifest.json` | Generator/config/environment provenance, row counts, quality gate and SHA-256/byte size for every generated artefact except the manifest itself |
| `.busroute-generated` | Ownership marker used to safely replace only this tool's generated output on a repeat run |

`docs/data_dictionary.md` and `docs/schema.sql` are generated from the same field specification in `busroute/spec.py`.

## Quality gates and reproducibility

The final full profile was independently verified with:

- **5,000 students, 100 buses, 300 stops and 200 school days**.
- **0 baseline validation violations** in a separate clean-baseline validation.
- All five anomaly categories detected with **precision = 1.0 and recall = 1.0**; zero unexplained violations after CSV reload.
- The 119 MB SQLite seed imported successfully; `PRAGMA foreign_key_check` returned **0 violations**.
- Two independent full-profile runs produced matching SHA-256 checksums for all **35 artefacts**, including CSV, JSON, SQL, ground truth, metrics and validation summary.

Re-run full data verification with:

```bash
python -m busroute generate --profile full --formats csv,json,sql --out datasets/full_run1
python -m busroute validate --data datasets/full_run1/data --ground-truth datasets/full_run1/ground_truth/ground_truth.csv
python scripts/verify_sqlite_seed.py --seed datasets/full_run1/data/seed.sql
python -m busroute generate --profile full --formats csv,json,sql --out datasets/full_run2
python scripts/compare_reproducibility.py --first datasets/full_run1 --second datasets/full_run2 --out docs/reproducibility_full.json
```

For a full-scale reproducibility proof, run the generator twice in separate CLI invocations, then compare the two manifests with `scripts/compare_reproducibility.py`. This avoids retaining two near-million-row builds in one Python process. The resulting report contains both SHA-256 maps; the checked-in report is `docs/reproducibility_full.json`. For the smaller profile, `python -m busroute reproduce --profile starter` performs both runs automatically and is covered by the automated tests. For the full profile, use the explicit two-build sequence above and compare the manifests; this is the verified full-scale workflow and keeps the two large builds in separate processes.

## Current full-profile operating picture

The full profile assigns **4,781 of 5,000 students (95.62%)** in the clean baseline. Wheelchair-required coverage is **96.15%** versus **95.61%** for students without that requirement (a 0.54 percentage-point advantage in this seeded scenario). Rural coverage remains lower at **86.03%**, compared with **97.70%** suburban and **99.39%** urban. These gaps are explicit operating signals for further route/stop optimisation; the model does not force an unsafe assignment just to raise the headline rate.

## Known limitations

- The assignment engine is deterministic greedy scoring, not a global min-cost-flow or vehicle-routing optimiser. It can be improved with local search / rebalancing while keeping the same validation contract.
- One school year and AM routes only are modelled. PM service, multi-school bell times and mid-year route redesign are out of scope.
- Coordinates represent a synthetic planar toy city; the road-distance multiplier is not a real street network or travel-time API.
- Capacity feasibility is deliberately conservative: it counts all assigned students across the school year, including late enrollees and students who later withdraw. Daily capacity optimisation is not implemented.
- Disruptions alter daily attendance outcomes, but the simulator does not dynamically re-optimise routes and notify every affected family after a route redesign.
- All data and contact details are fictional. No real guardian can be contacted; no external dataset or live service is used.

## Project structure

```text
busroute/              generator, business rules, validator, anomaly injector, CLI and metrics
 tests/                regression and pipeline tests
datasets/starter/      committed compact sample (CSV/JSON/SQL + ground truth)
docs/                  assumptions, AI-use disclosure, schema, data dictionary and reproducibility reports
prompts/               prompt log used during initial AI-assisted development
```

See [`docs/REVIEWER_WALKTHROUGH.md`](docs/REVIEWER_WALKTHROUGH.md) for a concise demo and technical explanation, [`docs/FINAL_AUDIT.md`](docs/FINAL_AUDIT.md) for the final verification results and known limitations, [`docs/full_scale_verification.json`](docs/full_scale_verification.json) for machine-readable full-profile evidence, and [`docs/AI_USAGE.md`](docs/AI_USAGE.md) for the AI-use disclosure.
