"""Decision and operating metrics derived only from source tables."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rate(series: pd.Series) -> float | None:
    return round(float(series.mean()), 4) if len(series) else None


def compute(T: dict) -> dict:
    A, E, N, R, B, RS = (T[k] for k in
                         ("assignments", "attendance_events", "notifications", "routes", "buses", "route_stops"))
    CC, D, S, Z = (T[k] for k in ("bus_capacity_changes", "route_disruptions", "students", "address_zones"))
    n = len(A)
    asg = A[A.route_id.notna()].copy()
    assigned_rate = len(asg) / n if n else 0.0

    # Load is one assigned student per route/bus in this AM-only model.
    occ = (asg.merge(R[["route_id", "bus_id"]], on="route_id")
              .groupby("bus_id").size().reindex(B.bus_id).fillna(0))
    mincap = pd.concat([B.set_index("bus_id").seat_capacity,
                        CC.set_index("bus_id").new_seat_capacity]).groupby(level=0).min()
    basecap = B.set_index("bus_id").seat_capacity
    util = (occ / basecap).replace([np.inf, -np.inf], np.nan)

    student_assignment = A.merge(S[["student_id", "needs_wheelchair", "grade", "zone_id"]], on="student_id")
    by_access = student_assignment.groupby("needs_wheelchair").route_id.apply(lambda x: float(x.notna().mean()))
    access_rates = {
        "no_wheelchair_requirement": round(float(by_access.get(0, np.nan)), 4) if 0 in by_access else None,
        "wheelchair_required": round(float(by_access.get(1, np.nan)), 4) if 1 in by_access else None,
    }
    if access_rates["no_wheelchair_requirement"] is not None and access_rates["wheelchair_required"] is not None:
        access_gap = round((access_rates["no_wheelchair_requirement"] - access_rates["wheelchair_required"]) * 100, 2)
    else:
        access_gap = None

    grade_band = pd.cut(student_assignment.grade, [-1, 5, 8, 12], labels=["K-5", "6-8", "9-12"])
    by_grade = student_assignment.assign(grade_band=grade_band).groupby("grade_band", observed=True).route_id.apply(
        lambda x: round(float(x.notna().mean()), 4)).to_dict()
    by_zone = (student_assignment.merge(Z[["zone_id", "zone_type"]], on="zone_id")
               .groupby("zone_type").route_id.apply(lambda x: round(float(x.notna().mean()), 4)).to_dict())

    status_counts = E.status.astype(str).value_counts()
    days = sorted(E.school_date.astype(str).unique())
    present = E[E.status.astype(str) == "present"]
    daily_present = present.groupby(present.school_date.astype(str)).student_id.nunique().reindex(days, fill_value=0)
    daily_records = E.groupby(E.school_date.astype(str)).size().reindex(days, fill_value=0)
    total_events = len(E)
    status_share = {str(k): round(float(v / total_events), 5) for k, v in status_counts.items()} if total_events else {}

    # Validate outbound destinations and address minimisation from the actual
    # guardian/student records; intentionally injected privacy cases remain visible.
    guardian = T["guardian_contacts"].set_index("guardian_id")
    dest_mismatch = 0
    for row in N.itertuples(index=False):
        if row.guardian_id not in guardian.index:
            dest_mismatch += 1
            continue
        g = guardian.loc[row.guardian_id]
        expected = g.phone if row.channel == "sms" else g.email
        if str(row.destination) != str(expected):
            dest_mismatch += 1
    address_by_student = S.set_index("student_id").home_address_line.to_dict()
    address_leaks = sum(
        1 for row in N.itertuples(index=False)
        if (address_by_student.get(row.student_id) and str(address_by_student[row.student_id]) in str(row.message_text))
        or "home address" in str(row.message_text).lower()
    )

    rs_last = RS.groupby("route_id").scheduled_offset_min.max()
    wheel = S[S.needs_wheelchair == 1].student_id
    return {
        "volumes": {k: int(len(v)) for k, v in T.items()},
        "assignment": {
            "students": int(n), "assigned": int(len(asg)), "unassigned": int(n - len(asg)),
            "assignment_rate": round(assigned_rate, 4),
            "decision_reason_counts": A.decision_reason.value_counts().to_dict(),
            "median_walk_km": round(float(asg.distance_to_stop_km.median()), 3) if len(asg) else None,
            "max_walk_km": round(float(asg.distance_to_stop_km.max()), 3) if len(asg) else None,
            "coverage_by_accessibility_need": access_rates,
            "accessibility_assignment_gap_percentage_points": access_gap,
            "coverage_by_grade_band": by_grade,
            "coverage_by_zone_type": by_zone,
        },
        "fleet": {
            "buses": int(len(B)), "total_base_seats": int(B.seat_capacity.sum()),
            "mean_utilization": round(float(util.mean()), 4) if len(util) else None,
            "max_utilization": round(float(util.max()), 4) if len(util) else None,
            "buses_over_95pct_baseline": int((util > 0.95).sum()),
            "buses_over_historical_min_capacity": int((occ > mincap.reindex(occ.index)).sum()),
            "capacity_changes": int(len(CC)),
            "accessible_buses": int((B.wheelchair_positions > 0).sum()),
            "wheelchair_positions": int(B.wheelchair_positions.sum()),
            "wheelchair_students": int(len(wheel)),
            "wheelchair_students_assigned": int(A[A.student_id.isin(wheel)].route_id.notna().sum()),
        },
        "routes": {
            "routes": int(len(R)),
            "mean_stops": round(float(RS.groupby("route_id").size().mean()), 2) if len(RS) else 0.0,
            "mean_duration_min": round(float(rs_last.mean()), 1) if len(rs_last) else None,
            "max_duration_min": int(rs_last.max()) if len(rs_last) else None,
            "disruptions": int(len(D)), "cancelled": int(D.is_cancelled.sum()),
            "delayed_not_cancelled": int(((D.delay_min > 0) & (D.is_cancelled == 0)).sum()),
        },
        "attendance": {
            "events": int(total_events), "school_days": int(len(days)),
            "mean_daily_attendance_records": round(float(daily_records.mean()), 1) if len(days) else None,
            "mean_daily_present_riders": round(float(daily_present.mean()), 1) if len(days) else None,
            "present_rate": round(float(status_counts.get("present", 0) / total_events), 5) if total_events else None,
            "status_share": status_share,
        },
        "notifications": {
            "total": int(len(N)), "by_reason": N.reason.value_counts().to_dict(),
            "delivery_rate": _rate((N.delivery_status == "delivered").astype(float)) if len(N) else None,
            "destination_mismatch_count": int(dest_mismatch),
            "home_address_exposure_count": int(address_leaks),
        },
    }
