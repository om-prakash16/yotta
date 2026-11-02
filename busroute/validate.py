"""Validation suite. Works on in-memory frames or frames re-read from CSV.

Returns a DataFrame of violations (check, entity_type, entity_id, detail).
A clean baseline must return zero rows; injected anomalies must be explained
by exactly the checks listed in ISSUE_MAP.
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from .spec import TABLES, EMAIL_RX, PHONE_RX

ISSUE_MAP = {
    "rule.bus_capacity_exceeded": "bus_capacity_exceeded",
    "rule.accessibility_incompatible": "incompatible_route_assignment",
    "rule.impossible_travel": "impossible_travel_time",
    "rule.notification_destination_format": "notification_invalid_contact",
    "rule.notification_matches_guardian": "notification_invalid_contact",
    "rule.address_exposed": "unapproved_address_exposed",
}
COLS = ["check", "entity_type", "entity_id", "detail"]
NOTIFY_STATUS = {"absent_unexcused": "unexcused_absence", "missed_pickup": "pickup_missed", "route_cancelled": "route_cancelled"}
MAX_SPEED_KMH = 80.0


def _ids(df, pk):
    if len(df) == 0:
        return []
    d = df[pk].copy()
    for c in pk:                      # canonical floats -> "3" not "3.0"
        if d[c].dtype.kind == "f":
            d[c] = d[c].astype("Int64")
    return d[pk[0]].astype(str).tolist() if len(pk) == 1 else d.astype(str).agg("|".join, axis=1).tolist()


def _out(check, etype, sub, pk, detail):
    return [(check, etype, i, detail) for i in _ids(sub, pk)]


def _tmin(s):
    s = s.astype(object)
    ok = s.notna()
    out = pd.Series(np.nan, index=s.index)
    out[ok] = s[ok].str.slice(0, 2).astype(float) * 60 + s[ok].str.slice(3, 5).astype(float)
    return out


def canon(name, df):
    """Cast to a uniform representation (strings stay str, numbers float, NaN = null)."""
    v, out = [], pd.DataFrame(index=range(len(df)))
    df = df.reset_index(drop=True)
    spec = TABLES[name]
    for fl in spec["fields"]:
        if fl.name not in df.columns:
            v.append(("schema.missing_column", name, fl.name, "column absent")); continue
        s = df[fl.name]
        if s.dtype.name == "category":
            s = s.astype(object)
        if fl.type in ("int", "float", "bool"):
            raw = s.astype(object).where(s.notna(), None)
            num = pd.to_numeric(s, errors="coerce")
            bad = raw.notna() & num.isna() & (raw.astype(str).str.strip() != "")
            if bad.any():
                v += [("schema.type", name, str(i), f"{fl.name} not numeric") for i in df.index[bad]]
            if fl.type in ("int", "bool"):
                nonint = num.notna() & (num != np.floor(num.fillna(0)))
                v += [("schema.type", name, str(i), f"{fl.name} not integer") for i in df.index[nonint]]
            out[fl.name] = num.astype(float)
        else:
            s = s.astype(object).where(s.notna(), None)
            s = s.map(lambda x: None if x is None or (isinstance(x, str) and x == "") else x)
            if fl.type == "date":
                ok = pd.to_datetime(s.dropna(), format="%Y-%m-%d", errors="coerce")
                badd = ok.index[ok.isna()]
                v += [("schema.type", name, str(i), f"{fl.name} not ISO date") for i in badd]
            out[fl.name] = s
    return out, v


def schema_checks(T):
    V = []
    for name, spec in TABLES.items():
        df, pk = T[name], spec["pk"]
        for fl in spec["fields"]:
            if fl.name not in df.columns:
                continue
            s = df[fl.name]
            if fl.required:
                V += _out("schema.required", name, df[s.isna()], pk, f"{fl.name} is null")
            nn = s.notna()
            if fl.enum:
                V += _out("schema.enum", name, df[nn & ~s.isin(fl.enum)], pk, f"{fl.name} not in allowed values")
            if fl.regex:
                bad = nn & ~s.astype(str).str.fullmatch(fl.regex)
                V += _out("schema.regex", name, df[bad], pk, f"{fl.name} violates {fl.regex}")
            if fl.lo is not None and fl.type in ("int", "float", "bool"):
                V += _out("schema.range", name, df[nn & ((s < fl.lo) | (s > fl.hi))], pk, f"{fl.name} outside {fl.lo}..{fl.hi}")
            if fl.unique and [fl.name] != pk:
                V += _out("schema.unique", name, df[nn & s.duplicated(keep=False)], pk, f"{fl.name} not unique")
        # A missing PK column has already been reported by canon(); do not let
        # a malformed input turn validation into a KeyError.
        if all(c in df.columns for c in pk):
            V += _out("schema.pk_unique", name, df[df.duplicated(pk, keep=False)], pk, "duplicate primary key")
    return V


def fk_checks(T):
    V = []
    for name, spec in TABLES.items():
        df = T[name]
        for col, parent, pcol in spec["fks"]:
            # Missing source/parent fields have their own schema violations.
            # Skip the dependent FK check instead of masking them with a crash.
            if col not in df.columns or parent not in T or pcol not in T[parent].columns:
                continue
            if not all(c in df.columns for c in spec["pk"]):
                continue
            s = df[col]
            bad = s.notna() & ~s.isin(set(T[parent][pcol].dropna()))
            V += _out(f"fk.{name}.{col}", name, df[bad], spec["pk"], f"{col} has no parent in {parent}")
    return V


def semantic_checks(T):
    V = []
    S, A, R, RS, ST = T["students"], T["assignments"], T["routes"], T["route_stops"], T["stops"]
    B, CC, D, DRV, G = T["buses"], T["bus_capacity_changes"], T["route_disruptions"], T["drivers"], T["guardian_contacts"]
    E, N, AE, CAL = T["attendance_events"], T["notifications"], T["assignment_events"], T["school_calendar"]
    cal = sorted(CAL.school_date.dropna())
    calset = set(cal)

    # ---- students / guardians / calendar ---------------------------------
    V += _out("lifecycle.student_status", "students", S[(S.status == "withdrawn") != S.withdrawn_on.notna()], ["student_id"], "status vs withdrawn_on")
    V += _out("date.student_order", "students", S[(S.withdrawn_on.notna() & (S.withdrawn_on < S.enrolled_on)) | (~S.enrolled_on.isin(calset))
                                                   | (S.withdrawn_on.notna() & ~S.withdrawn_on.isin(calset))], ["student_id"], "enrol/withdraw dates")
    V += _out("rule.pickup_window_width", "students", S[_tmin(S.pickup_window_end) - _tmin(S.pickup_window_start) != 75], ["student_id"], "window must be 75 min")
    prim = G[G.is_primary == 1].groupby("student_id").size()
    cnt = S.student_id.map(prim).fillna(0)
    V += _out("rule.one_primary_guardian", "students", S[cnt != 1], ["student_id"], "need exactly one primary guardian")
    V += _out("rule.guardian_contact", "guardian_contacts", G[G.phone.isna() & G.email.isna()], ["guardian_id"], "no contact value")
    V += _out("rule.guardian_contact", "guardian_contacts", G[((G.preferred_channel == "sms") & G.phone.isna()) | ((G.preferred_channel == "email") & G.email.isna())],
              ["guardian_id"], "preferred channel has no value")
    V += _out("date.capacity_change_day", "bus_capacity_changes", CC[~CC.effective_date.isin(calset)], ["change_id"], "not a school day")
    V += _out("date.disruption_day", "route_disruptions", D[~D.school_date.isin(calset)], ["disruption_id"], "not a school day")
    V += _out("rule.disruption_unique", "route_disruptions", D[D.duplicated(["route_id", "school_date"], keep=False)], ["disruption_id"], "duplicate route/day")
    V += _out("rule.disruption_fields", "route_disruptions", D[((D.is_cancelled == 1) & (D.delay_min != 0)) | ((D.is_cancelled == 1) & (D.disruption_type == "traffic"))], ["disruption_id"], "cancel/delay inconsistent")

    # ---- fleet ------------------------------------------------------------
    V += _out("recon.bus_accessible_flag", "buses", B[B.is_wheelchair_accessible != (B.wheelchair_positions > 0).astype(float)], ["bus_id"], "flag != positions>0")
    M = R.merge(DRV[["driver_id", "bus_id", "license_valid_until", "status"]].rename(columns={"bus_id": "drv_bus", "status": "drv_status"}), on="driver_id", how="left")
    V += _out("rule.driver_bus", "routes", M[M.drv_bus != M.bus_id], ["route_id"], "driver not assigned to route bus")
    V += _out("rule.driver_license", "routes", M[(M.license_valid_until < cal[-1]) | (M.drv_status != "active")], ["route_id"], "driver license/status")

    cc = CC.sort_values(["bus_id", "effective_date", "change_id"])
    prev = cc.groupby("bus_id").new_seat_capacity.shift(1)
    base = cc.bus_id.map(B.set_index("bus_id").seat_capacity)
    exp = prev.fillna(base)
    V += _out("recon.capacity_chain", "bus_capacity_changes", cc[cc.old_seat_capacity != exp], ["change_id"], "old != previous new capacity")

    # ---- route stops ------------------------------------------------------
    rs = RS.sort_values(["route_id", "stop_sequence"]).reset_index(drop=True)
    seq = rs.groupby("route_id").cumcount() + 1
    V += _out("rule.route_stop_sequence", "route_stops", rs[rs.stop_sequence != seq], ["route_id", "stop_sequence"], "sequence not contiguous 1..k")
    V += _out("dup.route_stop_pair", "route_stops", RS[RS.duplicated(["route_id", "stop_id"], keep=False)],
              ["route_id", "stop_sequence"], "same stop appears more than once on a route")
    pdwell = rs.groupby("route_id").dwell_min.shift(1).fillna(0)
    expo = (rs.travel_min_from_prev + pdwell).groupby(rs.route_id).cumsum()
    V += _out("recon.route_stop_offsets", "route_stops", rs[rs.scheduled_offset_min != expo], ["route_id", "stop_sequence"], "offset != cumulative travel+dwell")
    V += _out("rule.route_stop_first", "route_stops", rs[(seq == 1) & ((rs.travel_min_from_prev != 0) | (rs.distance_km_from_prev != 0))], ["route_id", "stop_sequence"], "first stop must have 0 travel")
    rsx = rs.merge(ST[["stop_id", "stop_x_km", "stop_y_km", "is_approved", "stop_status"]], on="stop_id", how="left")
    px_, py_ = rsx.stop_x_km.groupby(rsx.route_id).shift(1), rsx.stop_y_km.groupby(rsx.route_id).shift(1)
    geo = (1.3 * np.hypot(rsx.stop_x_km - px_, rsx.stop_y_km - py_)).fillna(0)
    V += _out("recon.route_stop_distance", "route_stops", rsx[(rsx.distance_km_from_prev - geo).abs() > 0.002], ["route_id", "stop_sequence"], "distance != 1.3 x geometry")
    speed = rsx.distance_km_from_prev / (rsx.travel_min_from_prev.replace(0, np.nan) / 60)
    bad = (speed > MAX_SPEED_KMH) | ((rsx.travel_min_from_prev == 0) & (rsx.distance_km_from_prev > 0))
    V += _out("rule.impossible_travel", "route_stops", rsx[bad], ["route_id", "stop_sequence"], f"implied speed > {MAX_SPEED_KMH} km/h")
    V += _out("rule.route_stop_unapproved", "route_stops", rsx[(rsx.is_approved != 1) | (rsx.stop_status != "active")], ["route_id", "stop_sequence"], "unapproved stop on route")
    V += _out("rule.stop_approval_flag", "stops", ST[(ST.is_approved == 1) != (ST.stop_status == "active")], ["stop_id"], "is_approved != status")

    # ---- assignments ------------------------------------------------------
    V += _out("rule.assignment_id_format", "assignments", A[A.assignment_id != "ASN-" + A.student_id.astype(str) + "-2026"], ["assignment_id"], "ASN id != ASN-<student>-2026")
    un = A.status == "unassigned"
    V += _out("rule.assignment_nulls", "assignments", A[(un & (A.route_id.notna() | A.stop_id.notna() | A.scheduled_pickup_time.notna())) |
                                                          (~un & (A.route_id.isna() | A.stop_id.isna() | A.scheduled_pickup_time.isna()))], ["assignment_id"], "route/stop nullness vs status")
    V += _out("rule.assignment_reason", "assignments", A[un == (A.decision_reason == "assigned_best_score")], ["assignment_id"], "reason vs status")
    sj = A.merge(S[["student_id", "enrolled_on", "withdrawn_on", "status", "needs_wheelchair", "grade", "home_x_km", "home_y_km",
                    "pickup_window_start", "pickup_window_end"]].rename(columns={"status": "stu_status"}), on="student_id", how="left")
    V += _out("date.assignment_order", "assignments", sj[(sj.effective_from != sj.enrolled_on) | (sj.effective_to.notna() & (sj.effective_to < sj.effective_from))], ["assignment_id"], "effective dates")
    V += _out("lifecycle.assignment_vs_student", "assignments", sj[((sj.status == "ended") != (sj.stu_status == "withdrawn") & ~un) |
                                                                   ((sj.status == "ended") & (sj.effective_to != sj.withdrawn_on))], ["assignment_id"], "ended vs withdrawn")
    ev = AE.pivot_table(index="assignment_id", columns="event_type", values="event_date", aggfunc="count", fill_value=0)
    for c in ("assigned", "unassigned", "ended"):
        if c not in ev: ev[c] = 0
    evx = A[["assignment_id", "status", "effective_from", "effective_to"]].merge(ev, left_on="assignment_id", right_index=True, how="left").fillna({"assigned": 0, "unassigned": 0, "ended": 0})
    expc = {"active": (1, 0, 0), "ended": (1, 0, 1), "unassigned": (0, 1, 0)}
    okc = evx.apply(lambda r_: (r_.assigned, r_.unassigned, r_.ended) == expc.get(r_.status), axis=1) if len(evx) else pd.Series(dtype=bool)
    V += _out("lifecycle.assignment_events", "assignments", evx[~okc.astype(bool)], ["assignment_id"], "event history inconsistent with status")
    ends = AE[AE.event_type == "ended"].merge(A[["assignment_id", "effective_to"]], on="assignment_id", how="left")
    V += _out("lifecycle.assignment_events", "assignment_events", ends[ends.event_date != ends.effective_to], ["assignment_event_id"], "ended date != effective_to")

    As = A[A.route_id.notna()]
    m = (As.merge(sj[["assignment_id", "needs_wheelchair", "grade", "home_x_km", "home_y_km", "pickup_window_start", "pickup_window_end"]], on="assignment_id")
           .merge(RS[["route_id", "stop_id", "scheduled_offset_min"]], on=["route_id", "stop_id"], how="left")
           .merge(R[["route_id", "bus_id", "start_time"]], on="route_id", how="left")
           .merge(B[["bus_id", "seat_capacity", "wheelchair_positions"]], on="bus_id", how="left")
           .merge(ST[["stop_id", "stop_x_km", "stop_y_km", "is_wheelchair_accessible", "is_approved"]], on="stop_id", how="left"))
    V += _out("rule.assignment_stop_on_route", "assignments", m[m.scheduled_offset_min.isna()], ["assignment_id"], "(route,stop) not in route_stops")
    arr = _tmin(m.start_time) + m.scheduled_offset_min
    V += _out("recon.scheduled_pickup_time", "assignments", m[(arr - _tmin(m.scheduled_pickup_time)).abs() > 0.5], ["assignment_id"], "pickup time != start+offset")
    t = _tmin(m.scheduled_pickup_time)
    V += _out("rule.pickup_window", "assignments", m[(t < _tmin(m.pickup_window_start)) | (t > _tmin(m.pickup_window_end))], ["assignment_id"], "pickup outside student window")
    dist = np.hypot(m.home_x_km - m.stop_x_km, m.home_y_km - m.stop_y_km)
    V += _out("recon.assignment_distance", "assignments", m[(dist - m.distance_to_stop_km).abs() > 0.002], ["assignment_id"], "stored distance != geometry")
    V += _out("rule.walking_distance", "assignments", m[dist > np.where(m.grade <= 5, 0.8, 1.2) + 0.002], ["assignment_id"], "stop too far to walk")
    V += _out("rule.assignment_stop_approved", "assignments", m[m.is_approved != 1], ["assignment_id"], "unapproved stop")
    V += _out("rule.accessibility_incompatible", "assignments", m[(m.needs_wheelchair == 1) & ((m.wheelchair_positions == 0) | (m.is_wheelchair_accessible != 1))], ["assignment_id"], "wheelchair student on inaccessible bus/stop")
    occ = m.groupby("bus_id").size()
    mincap = pd.concat([B.set_index("bus_id").seat_capacity, CC.set_index("bus_id").new_seat_capacity]).groupby(level=0).min()
    over = occ[occ > mincap.reindex(occ.index)]
    V += [("rule.bus_capacity_exceeded", "buses", b, f"riders {int(occ[b])} > min capacity {int(mincap[b])}") for b in over.index]
    wocc = m[(m.needs_wheelchair == 1) & (m.wheelchair_positions > 0)].groupby("bus_id").size()
    wover = wocc[wocc > B.set_index("bus_id").wheelchair_positions.reindex(wocc.index)]
    V += [("rule.wheelchair_positions_exceeded", "buses", b, "wheelchair riders > positions") for b in wover.index]

    # ---- attendance -------------------------------------------------------
    E = E.assign(**{c: E[c].astype(object) for c in ("student_id", "assignment_id", "route_id", "stop_id", "school_date", "status", "disruption_id")})
    V += _out("dup.attendance", "attendance_events", E[E.duplicated(["student_id", "school_date"], keep=False)], ["attendance_event_id"], "duplicate student/day")
    ej = E.merge(A[["assignment_id", "student_id", "status", "effective_from", "effective_to"]].rename(columns={"student_id": "a_stu", "status": "a_status"}), on="assignment_id", how="left")
    V += _out("recon.attendance_assignment", "attendance_events", ej[(ej.a_stu != ej.student_id) | (ej.a_status == "unassigned")], ["attendance_event_id"], "event vs assignment mismatch")
    V += _out("date.attendance_window", "attendance_events", ej[(ej.school_date < ej.effective_from) | (ej.effective_to.notna() & (ej.school_date > ej.effective_to))], ["attendance_event_id"], "event outside assignment window")
    lo_i = np.searchsorted(cal, As.effective_from.values, side="left")
    hi_i = np.where(As.effective_to.notna(), np.searchsorted(cal, As.effective_to.fillna("").values, side="right"), len(cal))
    expd = pd.Series(hi_i - lo_i, index=As.assignment_id.values)
    got = E.groupby("assignment_id").size().reindex(expd.index).fillna(0)
    badc = expd[expd != got]
    V += [("recon.attendance_coverage", "assignments", a, f"expected {int(expd[a])} events, found {int(got[a])}") for a in badc.index]
    rsp = set(zip(RS.route_id, RS.stop_id))
    pairs = E[["route_id", "stop_id"]].drop_duplicates()
    badp = {p for p in zip(pairs.route_id, pairs.stop_id) if p not in rsp}
    if badp:
        V += _out("rule.attendance_stop_on_route", "attendance_events", E[[p in badp for p in zip(E.route_id, E.stop_id)]], ["attendance_event_id"], "(route,stop) not on route")
    ed = E.merge(D[["route_id", "school_date", "disruption_id", "is_cancelled"]].rename(columns={"disruption_id": "d_id"}), on=["route_id", "school_date"], how="left")
    absent = ed.status.isin(["absent_excused", "absent_unexcused"])
    V += _out("rule.attendance_disruption", "attendance_events", ed[ed.disruption_id.fillna("") != ed.d_id.fillna("")], ["attendance_event_id"], "disruption_id mismatch")
    V += _out("rule.attendance_disruption", "attendance_events", ed[(ed.is_cancelled == 1) & ~absent & (ed.status != "route_cancelled")], ["attendance_event_id"], "cancelled route not reflected")
    V += _out("rule.attendance_disruption", "attendance_events", ed[(ed.status == "route_cancelled") & (ed.is_cancelled != 1)], ["attendance_event_id"], "route_cancelled without cancellation")

    # ---- notifications ----------------------------------------------------
    nj = (N.merge(G[["guardian_id", "student_id", "is_primary", "phone", "email"]].rename(columns={"student_id": "g_stu"}), on="guardian_id", how="left")
            .merge(E[["attendance_event_id", "student_id", "school_date", "status"]].rename(columns={"student_id": "e_stu"}), on="attendance_event_id", how="left")
            .merge(S[["student_id", "home_address_line"]], on="student_id", how="left"))
    V += _out("rule.notification_primary_only", "notifications", nj[(nj.g_stu != nj.student_id) | (nj.is_primary != 1)], ["notification_id"], "not the student's primary guardian")
    V += _out("rule.notification_trigger", "notifications", nj[(nj.e_stu != nj.student_id) | (nj.sent_date != nj.school_date) | (nj.status.map(NOTIFY_STATUS) != nj.reason)], ["notification_id"], "trigger event mismatch")
    okfmt = np.where(nj.channel == "sms", nj.destination.astype(str).str.fullmatch(PHONE_RX), nj.destination.astype(str).str.fullmatch(EMAIL_RX))
    V += _out("rule.notification_destination_format", "notifications", nj[~okfmt.astype(bool)], ["notification_id"], "destination is not a valid contact")
    want = np.where(nj.channel == "sms", nj.phone, nj.email)
    V += _out("rule.notification_matches_guardian", "notifications", nj[nj.destination.astype(object) != pd.Series(want, index=nj.index).astype(object)], ["notification_id"], "destination != guardian contact on file")
    V += _out("dup.notification", "notifications", N[N.duplicated(["attendance_event_id", "guardian_id"], keep=False)], ["notification_id"], "duplicate notification")
    leak = [(a is not None and isinstance(a, str) and a in str(mt)) or ("home address" in str(mt).lower()) for a, mt in zip(nj.home_address_line, nj.message_text)]
    V += _out("rule.address_exposed", "notifications", nj[leak], ["notification_id"], "message exposes home address")
    V += _out("rule.notification_message_ref", "notifications", nj[[s not in str(mt) for s, mt in zip(nj.student_id, nj.message_text)]], ["notification_id"], "message lacks student id")
    need = E[E.status.isin(list(NOTIFY_STATUS))]
    miss = need[~need.attendance_event_id.isin(set(N.attendance_event_id))]
    V += _out("recon.notification_coverage", "attendance_events", miss, ["attendance_event_id"], "notifiable event has no notification")
    return V


def validate(raw: dict) -> pd.DataFrame:
    """Validate generated or externally supplied tables without crashing on schema drift.

    Missing tables/columns are reported as violations. Semantic checks run only
    when the input is structurally sound and all foreign keys resolve.
    """
    T, V = {}, []
    for name, spec in TABLES.items():
        if name not in raw:
            V.append(("schema.missing_table", name, name, "table absent"))
            # Keep an empty, correctly shaped frame so independent schema/FK
            # checks on the remaining tables can still run safely.
            T[name] = pd.DataFrame(columns=[fl.name for fl in spec["fields"]])
            continue
        if not isinstance(raw[name], pd.DataFrame):
            V.append(("schema.table_type", name, name, "expected pandas.DataFrame"))
            T[name] = pd.DataFrame(columns=[fl.name for fl in spec["fields"]])
            continue
        T[name], v = canon(name, raw[name])
        V += v
    V += schema_checks(T) + fk_checks(T)
    if not V:                       # semantic checks assume structurally sound tables
        V += semantic_checks(T)
    return pd.DataFrame(V, columns=COLS)


def summarize(v: pd.DataFrame) -> dict:
    return {"total_violations": int(len(v)), "by_check": v.groupby("check").size().sort_values(ascending=False).to_dict() if len(v) else {}}
