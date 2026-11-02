import json
import sqlite3

import pandas as pd
import pytest

from busroute.anomalies import inject
from busroute.config import PROFILES
from busroute.evaluate import score
from busroute.export import export_all, load_csv
from busroute.generate import generate
from busroute.spec import TABLES, schema_sql
from busroute.validate import ISSUE_MAP, validate

CFG = PROFILES["test"]


@pytest.fixture(scope="module")
def base():
    return generate(CFG)


@pytest.fixture(scope="module")
def injected(base):
    return inject(base, CFG)


def test_baseline_has_zero_violations(base):
    assert len(validate(base)) == 0


def test_all_entities_present_with_requested_volumes(base):
    assert set(base) == set(TABLES)
    assert len(base["students"]) == CFG.n_students
    assert len(base["buses"]) == CFG.n_buses
    assert len(base["school_calendar"]) == CFG.n_school_days
    assert len(base["stops"]) == CFG.n_stops


def test_id_conventions(base):
    s = base["students"].student_id
    assert s.iloc[0] == "STU-000001" and s.is_monotonic_increasing
    assert base["routes"].route_id.iloc[0] == "ROUTE-2026-000001"
    a = base["assignments"]
    assert (a.assignment_id == "ASN-" + a.student_id + "-2026").all()
    assert base["notifications"].notification_id.iloc[0] == "NOT-2026-000001"


def test_exception_paths_are_exercised(base):
    reasons = set(base["assignments"].decision_reason)
    assert {"assigned_best_score", "outside_service_area", "no_stop_within_walking_distance"} <= reasons
    assert set(base["attendance_events"].status.astype(str)) >= {"present", "absent_excused", "absent_unexcused", "missed_pickup"}
    assert len(base["bus_capacity_changes"]) > 0 and len(base["route_disruptions"]) > 0


def test_capacity_and_accessibility_rules_hold_in_baseline(base):
    A, R, B = base["assignments"], base["routes"], base["buses"]
    m = A[A.route_id.notna()].merge(R[["route_id", "bus_id"]], on="route_id")
    occ = m.groupby("bus_id").size()
    cap = B.set_index("bus_id").seat_capacity
    assert (occ <= cap.reindex(occ.index)).all()
    w = m.merge(base["students"][["student_id", "needs_wheelchair"]], on="student_id").merge(B[["bus_id", "wheelchair_positions"]], on="bus_id")
    assert (w[w.needs_wheelchair == 1].wheelchair_positions > 0).all()


def test_same_seed_is_reproducible(base):
    other = generate(CFG)
    for k in base:
        pd.testing.assert_frame_equal(base[k].reset_index(drop=True), other[k].reset_index(drop=True), check_dtype=False)


def test_different_seed_differs(base):
    other = generate(CFG.with_overrides(seed=1))
    assert not other["students"].equals(base["students"])


def test_all_five_anomaly_types_injected_and_detected_exactly(injected):
    tables, gt = injected
    assert set(gt.issue_type) == {"bus_capacity_exceeded", "incompatible_route_assignment", "impossible_travel_time",
                                  "notification_invalid_contact", "unapproved_address_exposed"}
    viol = validate(tables)
    res = score(viol, gt)
    assert res["unexplained_violations"] == 0
    assert res["exact_match"], res["per_issue_type"]


def test_ground_truth_is_not_leaked_into_inputs(injected):
    tables, gt = injected
    banned = {"issue_type", "ground_truth", "is_anomaly", "issue_id", "label"}
    for name, df in tables.items():
        assert not banned & set(df.columns), name
    ids = set(gt.issue_id)
    for name, df in tables.items():
        for c in df.columns:
            assert not df[c].astype(str).isin(ids).any()


def test_injection_does_not_change_baseline_row_counts_except_capacity_events(base, injected):
    tables, _ = injected
    for k in base:
        if k != "bus_capacity_changes":
            assert len(tables[k]) == len(base[k]), k


def test_injection_does_not_mutate_baseline_frames(base, injected):
    tables, _ = injected
    expected = generate(CFG)
    mutable = {"assignments", "students", "bus_capacity_changes", "route_stops", "notifications"}
    for name, original in base.items():
        pd.testing.assert_frame_equal(original, expected[name], check_dtype=False)
        if name in mutable:
            assert tables[name] is not original
        else:
            assert tables[name] is original


def test_validator_catches_fk_break_and_duplicate_pk(base):
    t = {k: v.copy() for k, v in base.items()}
    t["assignments"].loc[0, "student_id"] = "STU-999999"
    t["buses"] = pd.concat([t["buses"], t["buses"].iloc[[0]]])
    checks = set(validate(t).check)
    assert "fk.assignments.student_id" in checks and "schema.pk_unique" in checks


def test_validator_rejects_duplicate_stop_within_route(base):
    t = {k: v.copy() for k, v in base.items()}
    route = t["route_stops"].iloc[0]
    same_route = t["route_stops"][t["route_stops"].route_id == route.route_id]
    duplicate = route.copy()
    duplicate["stop_sequence"] = int(same_route.stop_sequence.max()) + 1
    t["route_stops"] = pd.concat([t["route_stops"], duplicate.to_frame().T], ignore_index=True)
    assert "dup.route_stop_pair" in set(validate(t).check)


def test_validator_catches_bad_enum_and_date_order(base):
    t = {k: v.copy() for k, v in base.items()}
    t["buses"].loc[0, "bus_type"] = "rocket"
    assert "schema.enum" in set(validate(t).check)
    t = {k: v.copy() for k, v in base.items()}
    i = t["assignments"].index[t["assignments"].route_id.notna()][0]
    t["assignments"].loc[i, "effective_to"] = "2000-01-01"
    assert "date.assignment_order" in set(validate(t).check)


def test_exports_roundtrip_and_sql_foreign_keys(injected, tmp_path):
    tables, gt = injected
    info = export_all(tables, gt, tmp_path)
    assert info["sqlite_foreign_key_check_violations"] == 0
    again = validate(load_csv(tmp_path / "data"))
    assert score(again, pd.read_csv(tmp_path / "ground_truth" / "ground_truth.csv"))["exact_match"]
    con = sqlite3.connect(":memory:")
    con.executescript((tmp_path / "data" / "seed.sql").read_text())
    assert con.execute("select count(*) from students").fetchone()[0] == CFG.n_students
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert json.loads((tmp_path / "data" / "buses.json").read_text())[0]["bus_id"] == "BUS-000001"


def test_schema_sql_is_valid_sqlite():
    sqlite3.connect(":memory:").executescript(schema_sql())


def test_schema_sql_enforces_natural_composite_keys(injected, tmp_path):
    tables, gt = injected
    export_all(tables, gt, tmp_path)
    con = sqlite3.connect(":memory:")
    con.executescript((tmp_path / "data" / "seed.sql").read_text())
    route_id, stop_id, seq = con.execute(
        "SELECT route_id, stop_id, MAX(stop_sequence) + 1 FROM route_stops GROUP BY route_id LIMIT 1"
    ).fetchone()
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO route_stops (route_id, stop_sequence, stop_id, distance_km_from_prev, "
            "travel_min_from_prev, dwell_min, scheduled_offset_min) VALUES (?, ?, ?, 0, 1, 1, 1)",
            (route_id, seq, stop_id),
        )
    con.close()


def test_sensitive_contact_data_is_synthetic_and_minimised(base):
    g = base["guardian_contacts"]
    assert g.phone.dropna().str.fullmatch(r"\+1-555-01\d\d").all()
    assert g.email.dropna().str.endswith("@example.org").all()
    n = base["notifications"]
    s = base["students"].set_index("student_id")
    assert not any(s.at[sid, "home_address_line"] in msg for sid, msg in zip(n.student_id, n.message_text))


def test_validator_reports_missing_table_and_column_without_crashing(base):
    from busroute.validate import validate

    missing_column = {k: v.copy() for k, v in base.items()}
    missing_column["students"] = missing_column["students"].drop(columns=["home_address_line"])
    v1 = validate(missing_column)
    assert "schema.missing_column" in set(v1.check)

    missing_table = {k: v.copy() for k, v in base.items() if k != "buses"}
    v2 = validate(missing_table)
    assert "schema.missing_table" in set(v2.check)


def test_config_rejects_scales_that_break_calendar_or_route_invariants():
    from busroute.config import Config

    with pytest.raises(ValueError, match="n_school_days"):
        Config(n_school_days=3)
    with pytest.raises(ValueError, match="n_stops"):
        Config(n_stops=5)
    with pytest.raises(ValueError, match="n_zones"):
        Config(n_zones=5)


def test_metrics_report_fairness_and_privacy_injected_cases(injected):
    from busroute.metrics import compute

    tables, _ = injected
    m = compute(tables)
    assert m["assignment"]["coverage_by_accessibility_need"]["wheelchair_required"] is not None
    assert m["assignment"]["accessibility_assignment_gap_percentage_points"] is not None
    assert set(m["assignment"]["coverage_by_grade_band"]) == {"K-5", "6-8", "9-12"}
    assert m["notifications"]["destination_mismatch_count"] == 2
    assert m["notifications"]["home_address_exposure_count"] == 2
    assert "mean_daily_present_riders" in m["attendance"]


def test_generate_run_writes_manifest_hashes_for_all_artifacts(tmp_path):
    import json
    from busroute.cli import run

    out = tmp_path / "generated"
    m = run(CFG, out, ("csv", "sql"), "pytest")
    assert m["quality_gate"]["passed"]
    assert "metrics.json" in m["files"]
    assert "validation_summary.json" in m["files"]
    saved = json.loads((out / "manifest.json").read_text())
    assert saved["environment"]["python"]
    assert saved["quality_gate"]["passed"]
    assert saved["elapsed_s"] >= 0


def test_cli_output_refuses_to_delete_unowned_directory(tmp_path):
    from busroute.cli import _prepare_output

    out = tmp_path / "valuable"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_text("do not delete")
    with pytest.raises(ValueError, match="non-empty unowned"):
        _prepare_output(out)
    assert keep.read_text() == "do not delete"


def test_reproduce_cli_compares_two_fresh_process_runs(tmp_path):
    import os
    import subprocess
    import sys

    out = tmp_path / "reproducibility"
    project_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "busroute", "reproduce", "--profile", "test",
         "--formats", "csv,sql", "--out", str(out)],
        cwd=project_root, capture_output=True, text=True, check=True,
    )
    report = json.loads((out / "reproducibility_report.json").read_text())
    assert report["identical_checksums"] is True
    assert report["quality_gate_passed_both_runs"] is True
    assert report["files_compared"] > 0
    assert len(report["sha256_run1"]) == report["files_compared"]
    assert report["sha256_run1"] == report["sha256_run2"]
    assert all(value is not None and value >= 0 for value in report["elapsed_seconds_by_run"])
