"""Inject labelled edge cases into an already-valid baseline.

Each injection touches the minimum number of cells, keeps every FK valid, and
is recorded ONLY in the separate ground-truth table (no flag columns in the
input tables). Candidates are chosen so that an injection does not create
secondary, unlabelled violations.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .generate import hhmm
from .validate import _tmin

GT_COLS = ["issue_id", "issue_type", "entity_type", "entity_id", "affected_field", "baseline_value", "injected_value", "expected_decision", "rule_ref"]


def inject(tables: dict, cfg: Config):
    # Only these five tables are mutated by the injectors. Share the other
    # frames with the baseline instead of copying the 900k-row attendance table
    # (and other immutable tables) a second time at full scale.
    T = dict(tables)
    for name in ("assignments", "students", "bus_capacity_changes", "route_stops", "notifications"):
        T[name] = tables[name].copy()
    rng = np.random.default_rng(cfg.seed + 1)       # independent stream: baseline unaffected by injection
    n = cfg.anomalies_per_type
    gt: list[dict] = []
    # Assignment-changing injections run before capacity anomalies. Otherwise a
    # later accessibility re-route could move a rider off a bus and silently
    # neutralise an already-injected capacity overflow.
    incompatible(T, rng, n, gt)
    cap_exceeded(T, rng, n, gt)
    impossible_travel(T, rng, n, gt)
    notification_anomalies(T, rng, n, gt)
    out = pd.DataFrame(gt, columns=GT_COLS[1:])
    out.insert(0, "issue_id", [f"GT-{i + 1:06d}" for i in range(len(out))])
    return T, out


def _gt(gt, issue, etype, eid, field, base, inj, decision, rule):
    gt.append(dict(issue_type=issue, entity_type=etype, entity_id=eid, affected_field=field, baseline_value=base,
                   injected_value=inj, expected_decision=decision, rule_ref=rule))


def _mincap(T):
    B, CC = T["buses"], T["bus_capacity_changes"]
    return pd.concat([B.set_index("bus_id").seat_capacity, CC.set_index("bus_id").new_seat_capacity]).groupby(level=0).min()


def cap_exceeded(T, rng, n, gt):
    A, R, B, CC, cal = T["assignments"], T["routes"], T["buses"], T["bus_capacity_changes"], T["school_calendar"].school_date.tolist()
    occ = A[A.route_id.notna()].merge(R[["route_id", "bus_id"]], on="route_id").groupby("bus_id").size()
    done, new_rows = 0, []
    for bus in rng.permutation(occ.index.to_numpy()):
        if done >= n or occ[bus] < 5:
            continue
        hist = CC[CC.bus_id == bus].sort_values(["effective_date", "change_id"])
        last_new = int(hist.new_seat_capacity.iloc[-1]) if len(hist) else int(B.loc[B.bus_id == bus, "seat_capacity"].iloc[0])
        last_d = hist.effective_date.iloc[-1] if len(hist) else ""
        later = [d for d in cal[len(cal) // 2:] if d > last_d]
        if not later:
            continue
        new = int(occ[bus] - rng.integers(1, 4))
        d = str(later[int(rng.integers(0, len(later)))])
        cid = f"CAP-2026-{len(CC) + len(new_rows) + 1:06d}"
        new_rows.append(dict(change_id=cid, bus_id=bus, effective_date=d, old_seat_capacity=last_new, new_seat_capacity=new, reason="seat_removal"))
        _gt(gt, "bus_capacity_exceeded", "buses", bus, "bus_capacity_changes.new_seat_capacity", f"riders={int(occ[bus])}", f"{cid}: capacity {new}",
            "flag bus over capacity; re-assign excess riders before the effective date", "assignments.riders <= min(capacity history)")
        done += 1
    if new_rows:
        T["bus_capacity_changes"] = pd.concat([CC, pd.DataFrame(new_rows)], ignore_index=True)


def incompatible(T, rng, n, gt):
    A, S, R, B, RS = T["assignments"], T["students"], T["routes"], T["buses"], T["route_stops"]
    start = _tmin(R.set_index("route_id").start_time)
    bus_of = R.set_index("route_id").bus_id
    wp = B.set_index("bus_id").wheelchair_positions
    rs = RS.assign(arr=RS.route_id.map(start) + RS.scheduled_offset_min)
    mincap = _mincap(T)
    occ = A[A.route_id.notna()].groupby("route_id").size().to_dict()
    sw = S.set_index("student_id")
    cand = A[A.route_id.notna() & A.student_id.map(sw.needs_wheelchair).eq(1)]
    done = 0
    for idx in rng.permutation(cand.index.to_numpy()):
        if done >= n:
            break
        row = A.loc[idx]
        w0, w1 = _tmin(pd.Series([sw.at[row.student_id, "pickup_window_start"], sw.at[row.student_id, "pickup_window_end"]])).tolist()
        opts = rs[(rs.stop_id == row.stop_id) & (rs.route_id != row.route_id)]
        for o in opts.itertuples():
            b = bus_of[o.route_id]
            if wp[b] == 0 and w0 <= o.arr <= w1 and occ.get(o.route_id, 0) + 1 <= mincap[b]:
                occ[row.route_id] -= 1; occ[o.route_id] = occ.get(o.route_id, 0) + 1
                A.loc[idx, "route_id"] = o.route_id
                A.loc[idx, "scheduled_pickup_time"] = hhmm(int(o.arr))
                _gt(gt, "incompatible_route_assignment", "assignments", row.assignment_id, "assignments.route_id", row.route_id, o.route_id,
                    "reject: wheelchair student must ride an accessible bus", "needs_wheelchair => bus.wheelchair_positions>0 and stop accessible")
                done += 1
                break
    if done < n:
        # Fallback (always available): an accessibility need is recorded AFTER assignment (late IEP update)
        # and the assignment is never re-evaluated -> the student sits on an inaccessible bus.
        S = S.copy()
        ok = A[A.route_id.notna() & (A.status == "active")]
        ok = ok[ok.route_id.map(bus_of).map(wp).eq(0) & ok.student_id.map(sw.needs_wheelchair).eq(0)]
        for idx in rng.permutation(ok.index.to_numpy())[: n - done]:
            row = A.loc[idx]
            S.loc[S.student_id == row.student_id, "needs_wheelchair"] = 1
            _gt(gt, "incompatible_route_assignment", "assignments", row.assignment_id, "students.needs_wheelchair", "0", "1 (recorded after assignment)",
                "re-run assignment: student now requires an accessible bus", "needs_wheelchair => bus.wheelchair_positions>0 and stop accessible")
        T["students"] = S
    T["assignments"] = A


def impossible_travel(T, rng, n, gt):
    RS, A, S, R = T["route_stops"].copy(), T["assignments"], T["students"], T["routes"]
    start = _tmin(R.set_index("route_id").start_time)
    sw = S.set_index("student_id")
    riders = A[A.route_id.notna()]
    done = 0
    routes = rng.permutation(RS.route_id.unique())
    for rid in routes:
        if done >= n:
            break
        rr = RS[RS.route_id == rid].sort_values("stop_sequence")
        cands = rr[(rr.stop_sequence >= 2) & (rr.distance_km_from_prev >= 2.0) & (rr.travel_min_from_prev >= 3)]
        for c in cands.itertuples():
            delta = c.travel_min_from_prev - 1
            later = rr[rr.stop_sequence >= c.stop_sequence]
            ok = True
            for r_ in later.itertuples():
                new_arr = start[rid] + r_.scheduled_offset_min - delta
                for a in riders[(riders.route_id == rid) & (riders.stop_id == r_.stop_id)].itertuples():
                    lo = _tmin(pd.Series([sw.at[a.student_id, "pickup_window_start"]]))[0]
                    hi = _tmin(pd.Series([sw.at[a.student_id, "pickup_window_end"]]))[0]
                    ok &= lo <= new_arr <= hi
            if not ok:
                continue
            m = (RS.route_id == rid) & (RS.stop_sequence >= c.stop_sequence)
            RS.loc[m, "scheduled_offset_min"] -= delta
            RS.loc[(RS.route_id == rid) & (RS.stop_sequence == c.stop_sequence), "travel_min_from_prev"] = 1
            for r_ in later.itertuples():     # keep derived pickup times in sync
                mm = (A.route_id == rid) & (A.stop_id == r_.stop_id)
                A.loc[mm, "scheduled_pickup_time"] = hhmm(int(start[rid] + r_.scheduled_offset_min - delta))
            _gt(gt, "impossible_travel_time", "route_stops", f"{rid}|{c.stop_sequence}", "route_stops.travel_min_from_prev",
                f"{c.travel_min_from_prev} min for {c.distance_km_from_prev} km", f"1 min for {c.distance_km_from_prev} km",
                "reject route: implied speed exceeds 80 km/h; re-plan segment", "distance/travel_time <= 80 km/h")
            done += 1
            break
    T["route_stops"], T["assignments"] = RS, A


def notification_anomalies(T, rng, n, gt):
    N, S = T["notifications"].copy(), T["students"].set_index("student_id")
    if len(N) < 2 * n:
        return
    pick = rng.permutation(N.index.to_numpy())
    for idx in pick[:n]:
        row = N.loc[idx]
        bad = (["+1-555-01", "555-0abc", "not-a-phone"] if row.channel == "sms" else ["guardian.at.example.org", "user@", "@example.org"])[int(rng.integers(0, 3))]
        N.loc[idx, "destination"] = bad
        _gt(gt, "notification_invalid_contact", "notifications", row.notification_id, "notifications.destination", row.destination, bad,
            "block send; route to school office for manual contact", "destination must match guardian contact on file and format")
    for idx in pick[n:2 * n]:
        row = N.loc[idx]
        addr = S.at[row.student_id, "home_address_line"]
        inj = f"{row.message_text} Home address on file: {addr}."
        N.loc[idx, "message_text"] = inj
        _gt(gt, "unapproved_address_exposed", "notifications", row.notification_id, "notifications.message_text", "no address", f"contains '{addr}'",
            "redact: notifications may reference only student id and approved stop", "no home address in outbound messages")
    T["notifications"] = N
