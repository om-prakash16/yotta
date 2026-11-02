# Final submission audit

**Audit date:** 2026-11-02  
**Seed:** `20261022`  
**Environment:** Python 3.13.5, NumPy 2.3.5, pandas 2.2.3, pytest 9.0.2

## Verification results

| Check | Result |
|---|---:|
| Automated regression suite | **24 passed, 0 failed** |
| Starter dataset artefacts | **35/35 SHA-256 and byte counts verified** |
| Starter two-run reproducibility | **35/35 checksums identical** |
| Starter CSV validation | **Exact ground-truth match; no unexplained violations** |
| Starter SQL seed import | **0 foreign-key violations** |
| Full clean baseline | **0 validation violations** |
| Full exported CSV validation | **25 labelled examples; 100% precision and recall; 0 unexplained findings** |
| Full SQL seed import | **0 foreign-key violations** |
| Full two-run reproducibility | **35/35 SHA-256 hashes identical** |

The two independently generated full-profile manifests also match the checked-in `docs/reproducibility_full.json` hash maps. The full export was regenerated after adding the composite SQL constraints.

## Dataset volumes

The clean full baseline contains 5,000 students, 100 buses, 300 stops, 200 school days, 15 valid capacity-history events, 298 route disruptions, 927,001 attendance events and 19,296 notifications. It assigns 4,781 students (95.62%).

The exported post-injection full dataset contains 20 capacity-history rows: the 15 valid baseline events plus 5 deliberately injected capacity anomalies. It has 25 ground-truth anomaly examples (five per required issue type). The validator reports 30 rule hits because each invalid-contact example triggers both the destination-format and guardian-match checks.

The clean baseline metrics show 96.15% wheelchair-required assignment coverage versus 95.61% for other students, and 86.03% rural coverage. These are seeded synthetic scenario outcomes, not claims about a real transport network. Unassigned students remain explicit with decision reasons rather than being force-assigned.

## Relational hardening

The generated SQLite schema and data dictionary now declare composite uniqueness for:

- `route_stops (route_id, stop_id)` — a stop cannot appear twice on one route.
- `route_disruptions (route_id, school_date)` — at most one disruption per route per school day.
- `attendance_events (student_id, school_date)` — at most one attendance event per student per day.
- `notifications (attendance_event_id, guardian_id)` — at most one notification per guardian for a given attendance event.

The validator explicitly checks the route-stop bridge pair and the other natural-key duplicates. Regression tests verify both validator detection and SQLite enforcement.

## Full-scale reproducibility workflow

For full-scale output, follow the two independent `generate` commands and `scripts/compare_reproducibility.py` in the README. That exact workflow was run twice after the final schema update and all 35 artefact hashes matched. The single-command `reproduce --profile full` orchestration timed out in this constrained execution environment, so it is not claimed as verified here; the documented separate-build workflow is verified. The starter convenience `reproduce --profile starter` command also completed successfully.

## Known limitations to disclose

- Assignment uses deterministic greedy scoring, not a global vehicle-routing or min-cost-flow optimizer.
- Only one school year and AM routes are modelled.
- Coordinates and road distances are synthetic planar approximations, not a real street network.
- Disruptions change attendance and notifications, but the simulator does not dynamically reroute buses after an incident.
- Capacity feasibility uses the minimum capacity in each bus's history and conservatively counts all assigned students across the year, including students who later withdraw.
- The dataset is synthetic; it does not connect to live student systems, guardians, SMS, email or transport APIs.

This is a reproducible data-and-decision pipeline with auditable outputs, not a deployed transport management application.
