"""Baseline (valid) data generation. Everything derives from documented rules;
labelled anomalies are injected afterwards by anomalies.py."""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .config import Config

ROAD_FACTOR = 1.3      # road distance = 1.3 x straight line
DWELL_MIN = 1
WALK_LIMIT_KM = {"elementary": 0.8, "other": 1.2}
HOLIDAYS = [(date(2026, 9, 7), date(2026, 9, 7)), (date(2026, 10, 12), date(2026, 10, 12)),
            (date(2026, 11, 11), date(2026, 11, 11)), (date(2026, 11, 26), date(2026, 11, 27)),
            (date(2026, 12, 21), date(2027, 1, 1)), (date(2027, 1, 18), date(2027, 1, 18)),
            (date(2027, 2, 15), date(2027, 2, 15)), (date(2027, 3, 22), date(2027, 3, 26)),
            (date(2027, 5, 31), date(2027, 5, 31))]
FIRST = ["Ava", "Liam", "Noah", "Mia", "Zoe", "Ethan", "Isla", "Lucas", "Aria", "Omar", "Priya", "Kenji",
         "Sofia", "Mateo", "Amara", "Leo", "Nora", "Ravi", "Maya", "Hugo"]
LAST = ["Smith", "Garcia", "Chen", "Patel", "Kim", "Nguyen", "Brown", "Lopez", "Khan", "Silva", "Novak",
        "Okafor", "Rossi", "Haddad", "Singh", "Tanaka", "Weber", "Costa", "Ivanov", "Reyes"]
STREETS = ["Maple", "Oak", "Cedar", "Elm", "Pine", "Birch", "Willow", "Aspen", "Lake", "Hill", "River", "Park",
           "Mill", "Spring", "Forest", "Sunset", "Meadow", "Harbor", "Ridge", "Orchard"]
SUFFIX = ["St", "Ave", "Rd", "Ln", "Dr", "Ct"]


def hhmm(m: int) -> str:
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def build_calendar(cfg: Config) -> list[date]:
    d, out = date.fromisoformat(cfg.first_school_day), []
    while len(out) < cfg.n_school_days:
        if d.weekday() < 5 and not any(a <= d <= b for a, b in HOLIDAYS):
            out.append(d)
        d += timedelta(days=1)
    return out


def _names(rng, lst, n):
    return [lst[i] for i in rng.integers(0, len(lst), n)]


def generate(cfg: Config) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(cfg.seed)
    cal = [d.isoformat() for d in build_calendar(cfg)]
    nd, n, nb, ns, nz = len(cal), cfg.n_students, cfg.n_buses, cfg.n_stops, cfg.n_zones
    first_day = cal[0]
    T: dict[str, pd.DataFrame] = {}
    T["school_calendar"] = pd.DataFrame({"school_date": cal, "day_index": np.arange(1, nd + 1)})

    # ---- address zones ---------------------------------------------------
    R = max(4.0, 12 * math.sqrt(ns / 300))      # keep stop density constant across scales
    r = R * np.sqrt(rng.random(nz)); th = 2 * np.pi * rng.random(nz)
    zx, zy = np.round(r * np.cos(th), 3), np.round(r * np.sin(th), 3)
    ztype = np.where(r < R / 3, "urban", np.where(r < 2 * R / 3, "suburban", "rural"))
    zappr = (rng.random(nz) < 0.94).astype(int)
    zappr[:2] = 1
    if nz >= 6:
        zappr[-1] = 0          # guarantee at least one out-of-service-area zone (exception path)
    zw = np.array([{"urban": 2.0, "suburban": 1.5, "rural": 0.8}[t] for t in ztype])
    T["address_zones"] = pd.DataFrame({
        "zone_id": [f"ZONE-{i + 1:06d}" for i in range(nz)], "zone_name": [f"District {i + 1:02d}" for i in range(nz)],
        "zone_type": ztype, "centroid_x_km": zx, "centroid_y_km": zy, "is_approved_service_area": zappr})

    # ---- stops -----------------------------------------------------------
    appr = np.flatnonzero(zappr == 1)
    demand_share = zw[appr] / zw[appr].sum()
    equity_share = np.full(len(appr), 1.0 / len(appr))
    # Blend demand-weighted stops with a minimum-coverage allocation so rural
    # service areas are not starved of pickup infrastructure.
    w = 0.50 * demand_share + 0.50 * equity_share
    stop_zone = rng.choice(appr, size=ns, p=w)
    sx = np.round(zx[stop_zone] + rng.normal(0, 0.5, ns), 3)
    sy = np.round(zy[stop_zone] + rng.normal(0, 0.5, ns), 3)
    proposed = np.zeros(ns, int)
    proposed[rng.choice(ns, max(1, round(0.04 * ns)), replace=False)] = 1
    s_acc = (rng.random(ns) < 0.96).astype(int)
    s_names = [f"{STREETS[a]} & {STREETS[b]}" for a, b in zip(rng.integers(0, 20, ns), rng.integers(0, 20, ns))]
    stop_ids = [f"STOP-{i + 1:06d}" for i in range(ns)]
    T["stops"] = pd.DataFrame({
        "stop_id": stop_ids, "zone_id": [f"ZONE-{z + 1:06d}" for z in stop_zone], "stop_name": s_names,
        "stop_x_km": sx, "stop_y_km": sy, "is_approved": 1 - proposed, "is_wheelchair_accessible": s_acc,
        "stop_status": np.where(proposed == 1, "proposed", "active"), "effective_from": first_day})

    # ---- buses & drivers -------------------------------------------------
    types = np.array(["mini", "standard", "large"])
    tix = rng.choice(3, nb, p=[0.15, 0.55, 0.30])
    bus_cap = np.array([30, 54, 72])[tix]
    p_acc = np.array([0.90, 0.75, 0.75])[tix]
    bus_wp = np.where(rng.random(nb) < p_acc, np.array([2, 2, 4])[tix], 0)
    bus_ids = [f"BUS-{i + 1:06d}" for i in range(nb)]
    T["buses"] = pd.DataFrame({
        "bus_id": bus_ids, "bus_type": types[tix], "seat_capacity": bus_cap, "wheelchair_positions": bus_wp,
        "is_wheelchair_accessible": (bus_wp > 0).astype(int), "status": "in_service", "effective_from": first_day})
    lic = [date(2027, 7, 1) + timedelta(days=int(k)) for k in rng.integers(0, 900, nb)]
    drv_ids = [f"DRV-{i + 1:06d}" for i in range(nb)]
    T["drivers"] = pd.DataFrame({
        "driver_id": drv_ids, "bus_id": bus_ids,
        "driver_alias": [f"{a} {b}" for a, b in zip(_names(rng, FIRST, nb), _names(rng, LAST, nb))],
        "license_valid_until": [d.strftime("%Y-%m-%d") for d in lic], "status": "active"})

    # ---- students --------------------------------------------------------
    szone = rng.choice(nz, n, p=zw / zw.sum())
    px = np.round(zx[szone] + rng.normal(0, 0.5, n), 3)
    py = np.round(zy[szone] + rng.normal(0, 0.5, n), 3)
    grade = rng.integers(0, 13, n)
    wstart = np.select([grade <= 5, grade <= 8], [6 * 60 + 45, 6 * 60 + 35], 6 * 60 + 25)
    wend = wstart + 75
    wheel = (rng.random(n) < 0.015).astype(int)
    late = rng.random(n) < 0.05
    enr_idx = np.where(late, rng.integers(1, max(2, int(0.6 * nd)), n), 0)
    wd = rng.random(n) < 0.03
    lo = np.minimum(enr_idx + 3, nd - 1)
    wd_idx = np.minimum(lo + (rng.random(n) * (nd - lo)).astype(int), nd - 1)
    wd = wd & (wd_idx > enr_idx)
    sid = [f"STU-{i + 1:06d}" for i in range(n)]
    T["students"] = pd.DataFrame({
        "student_id": sid, "first_name": _names(rng, FIRST, n), "last_name": _names(rng, LAST, n), "grade": grade,
        "zone_id": [f"ZONE-{z + 1:06d}" for z in szone],
        "home_address_line": [f"{a} {STREETS[b]} {SUFFIX[c]}" for a, b, c in
                              zip(rng.integers(100, 9999, n), rng.integers(0, 20, n), rng.integers(0, 6, n))],
        "home_x_km": px, "home_y_km": py, "needs_wheelchair": wheel,
        "pickup_window_start": [hhmm(m) for m in wstart], "pickup_window_end": [hhmm(m) for m in wend],
        "enrolled_on": [cal[i] for i in enr_idx], "withdrawn_on": [cal[i] if w_ else None for i, w_ in zip(wd_idx, wd)],
        "status": np.where(wd, "withdrawn", "active")})

    # ---- guardians -------------------------------------------------------
    rel = _names(rng, ["mother", "father", "guardian", "other"], n)
    contact_mode = rng.choice(3, n, p=[0.85, 0.10, 0.05])    # both | phone only | email only
    pref = np.where(rng.random(n) < 0.7, "sms", "email")
    pref = np.where(contact_mode == 1, "sms", np.where(contact_mode == 2, "email", pref))
    has_sec = rng.random(n) < 0.4
    g_rows, g_n = [], 0
    prim_gid, prim_dest = [None] * n, [None] * n
    for i in range(n):
        for primary in ([1, 0] if has_sec[i] else [1]):
            g_n += 1
            mode = contact_mode[i] if primary else 0
            phone = f"+1-555-01{rng.integers(0, 100):02d}" if mode in (0, 1) else None
            email = f"guardian.{g_n:06d}@example.org" if mode in (0, 2) else None
            ch = pref[i] if primary else ("sms" if phone else "email")
            g_rows.append((f"GRD-{g_n:06d}", sid[i], f"{FIRST[g_n % 20]} {T['students'].last_name.iat[i]}",
                           rel[i] if primary else "guardian", primary, phone, email, ch))
            if primary:
                prim_gid[i], prim_dest[i] = g_rows[-1][0], (phone if ch == "sms" else email)
    T["guardian_contacts"] = pd.DataFrame(g_rows, columns=[
        "guardian_id", "student_id", "guardian_alias", "relationship", "is_primary", "phone", "email", "preferred_channel"])

    # ---- route candidates: overlapping angular windows of active stops ---
    act = np.flatnonzero(proposed == 0)
    na = len(act)
    order = act[np.argsort(np.arctan2(sy[act], sx[act]), kind="stable")]
    W = max(3, min(na, round(2 * na / nb)))
    step = na / nb
    route_stops_idx = []
    for ri in range(nb):
        st = int(math.floor(ri * step))
        idxs = [int(order[(st + k) % na]) for k in range(W)]
        route_stops_idx.append(sorted(idxs, key=lambda s: (-math.hypot(sx[s], sy[s]), s)))
    stop_nroutes = np.zeros(ns, int)
    for idxs in route_stops_idx:
        for s in idxs:
            stop_nroutes[s] += 1

    # demand estimate per route -> match bigger buses to higher-demand routes
    stu_stop = np.full(n, -1)
    for i in range(n):
        if zappr[szone[i]]:
            d = np.hypot(sx[act] - px[i], sy[act] - py[i])
            j = int(np.argmin(d))
            if d[j] <= (0.8 if grade[i] <= 5 else 1.2):
                stu_stop[i] = act[j]
    dem = np.bincount(stu_stop[stu_stop >= 0], minlength=ns).astype(float)
    wdem = np.bincount(stu_stop[(stu_stop >= 0) & (wheel == 1)], minlength=ns).astype(float)
    rdem = np.array([sum(dem[s] / stop_nroutes[s] for s in idxs) for idxs in route_stops_idx])
    rwd = np.array([sum(wdem[s] / stop_nroutes[s] for s in idxs) for idxs in route_stops_idx])
    rdem_noisy = rdem * np.exp(rng.normal(0, 0.15, nb))
    acc_buses = [b for b in np.argsort(-bus_cap, kind="stable") if bus_wp[b] > 0]
    other_buses = [b for b in np.argsort(-bus_cap, kind="stable") if bus_wp[b] == 0]
    route_bus = np.full(nb, -1)
    for ri in [r_ for r_ in np.argsort(-rwd, kind="stable") if rwd[r_] > 0][:len(acc_buses)]:
        route_bus[ri] = acc_buses.pop(0)
    rest_buses = sorted(acc_buses + other_buses, key=lambda b: (-bus_cap[b], b))
    for ri in [r_ for r_ in np.argsort(-rdem_noisy, kind="stable") if route_bus[r_] < 0]:
        route_bus[ri] = rest_buses.pop(0)

    start_min = 395 + 5 * rng.integers(0, 3, nb)      # 06:35 .. 06:45; keep stop times inside overlapping grade windows
    rs_rows, offsets = [], []
    for ri, idxs in enumerate(route_stops_idx):
        off, prev, offs = 0, None, []
        speeds = np.clip(rng.normal(32, 5, len(idxs)), 20, 45)
        for k, s in enumerate(idxs):
            if prev is None:
                dist, trav = 0.0, 0
            else:
                dist = round(ROAD_FACTOR * math.hypot(sx[s] - sx[prev], sy[s] - sy[prev]), 3)
                trav = max(1, math.ceil(dist / speeds[k] * 60))
                off += DWELL_MIN + trav
            offs.append(off)
            rs_rows.append((f"ROUTE-2026-{ri + 1:06d}", k + 1, stop_ids[s], dist, trav, DWELL_MIN, off))
            prev = s
        offsets.append(offs)
    route_ids = [f"ROUTE-2026-{i + 1:06d}" for i in range(nb)]
    T["routes"] = pd.DataFrame({
        "route_id": route_ids, "bus_id": [bus_ids[b] for b in route_bus], "driver_id": [drv_ids[b] for b in route_bus],
        "route_name": [f"AM Route {i + 1}" for i in range(nb)], "period": "AM", "start_time": [hhmm(m) for m in start_min],
        "status": "active", "effective_from": first_day})
    T["route_stops"] = pd.DataFrame(rs_rows, columns=[
        "route_id", "stop_sequence", "stop_id", "distance_km_from_prev", "travel_min_from_prev", "dwell_min", "scheduled_offset_min"])

    # ---- assignment: rule-based, deterministic order ---------------------
    stop_routes = {int(s): [] for s in act}
    for ri, idxs in enumerate(route_stops_idx):
        for k, s in enumerate(idxs):
            stop_routes[s].append((ri, int(start_min[ri]) + offsets[ri][k]))
    occ, wocc = np.zeros(nb, int), np.zeros(nb, int)
    a_route, a_stop = np.full(n, -1), np.full(n, -1)
    a_dist, a_arr, reason = np.full(n, np.nan), np.full(n, -1), [""] * n
    ax, ay = sx[act], sy[act]
    # wheelchair students are placed first so scarce accessible positions are not consumed by
    # students who could ride any bus; everyone else follows in ID order (still deterministic)
    for i in np.concatenate([np.flatnonzero(wheel == 1), np.flatnonzero(wheel == 0)]):
        if not zappr[szone[i]]:
            reason[i] = "outside_service_area"; continue
        d = np.hypot(ax - px[i], ay - py[i])
        ok = d <= (0.8 if grade[i] <= 5 else 1.2)
        if wheel[i]:                       # only wheelchair-accessible stops are usable candidates
            ok &= s_acc[act] == 1
        cand = np.flatnonzero(ok)
        if cand.size == 0:
            reason[i] = "no_accessible_route" if wheel[i] and (d <= (0.8 if grade[i] <= 5 else 1.2)).any() \
                else "no_stop_within_walking_distance"
            continue
        cand = cand[np.argsort(d[cand], kind="stable")][:6]
        best, fail = None, set()
        for c in cand:
            s = int(act[c])
            for ri, arr in stop_routes[s]:
                b = route_bus[ri]
                if wheel[i] and (bus_wp[b] == 0 or s_acc[s] == 0):
                    fail.add("acc"); continue
                if not (wstart[i] <= arr <= wend[i]):
                    fail.add("win"); continue
                if occ[ri] >= bus_cap[b] or (wheel[i] and wocc[ri] >= bus_wp[b]):
                    fail.add("cap"); continue
                score = d[c] + 1.5 * occ[ri] / bus_cap[b]
                if best is None or score < best[0]:
                    best = (score, ri, s, arr, d[c])
        if best is None:
            reason[i] = ("capacity_full" if "cap" in fail else
                         "pickup_window_conflict" if "win" in fail else "no_accessible_route")
        else:
            _, ri, s, arr, dd_ = best
            a_route[i], a_stop[i], a_arr[i], a_dist[i] = ri, s, arr, round(float(dd_), 3)
            occ[ri] += 1; wocc[ri] += wheel[i]; reason[i] = "assigned_best_score"
    asg_ids = [f"ASN-{s}-2026" for s in sid]
    assigned = a_route >= 0
    status = np.where(~assigned, "unassigned", np.where(wd, "ended", "active"))
    T["assignments"] = pd.DataFrame({
        "assignment_id": asg_ids, "student_id": sid,
        "route_id": [route_ids[r_] if r_ >= 0 else None for r_ in a_route],
        "stop_id": [stop_ids[s] if s >= 0 else None for s in a_stop], "status": status,
        "effective_from": T["students"].enrolled_on.values,
        "effective_to": [T["students"].withdrawn_on.iat[i] if status[i] == "ended" else None for i in range(n)],
        "distance_to_stop_km": a_dist, "scheduled_pickup_time": [hhmm(a) if a >= 0 else None for a in a_arr],
        "decision_reason": reason})
    ev = []
    for i in range(n):
        ev.append((T["assignments"].effective_from.iat[i], i, asg_ids[i], "assigned" if assigned[i] else "unassigned"))
        if status[i] == "ended":
            ev.append((T["assignments"].effective_to.iat[i], i, asg_ids[i], "ended"))
    ev.sort(key=lambda e: (e[0], e[1], e[3] == "ended"))
    T["assignment_events"] = pd.DataFrame({
        "assignment_event_id": [f"AEV-2026-{k + 1:06d}" for k in range(len(ev))],
        "assignment_id": [e[2] for e in ev], "event_type": [e[3] for e in ev], "event_date": [e[0] for e in ev]})

    # ---- capacity change history (never below current ridership) ---------
    occ_bus = np.zeros(nb, int)
    for ri in range(nb):
        occ_bus[route_bus[ri]] = occ[ri]
    rows = []
    for b in sorted(rng.choice(nb, max(1, round(0.15 * nb)), replace=False)):
        cap, d1 = int(bus_cap[b]), int(rng.integers(3, max(4, int(nd * 0.7))))
        if rng.random() < 0.6:
            new = max(int(occ_bus[b]), cap - int(rng.choice([6, 12])))
            if new < cap:
                rows.append((d1, b, cap, new, "seat_removal" if rng.random() < 0.5 else "repair"))
                d2 = d1 + int(rng.integers(3, 30))
                if rng.random() < 0.5 and d2 < nd:
                    rows.append((d2, b, new, cap, "seat_restoration"))
        else:
            rows.append((d1, b, cap, cap + 12, "vehicle_swap"))
    rows.sort(key=lambda r_: (r_[0], r_[1]))
    T["bus_capacity_changes"] = pd.DataFrame({
        "change_id": [f"CAP-2026-{k + 1:06d}" for k in range(len(rows))], "bus_id": [bus_ids[r_[1]] for r_ in rows],
        "effective_date": [cal[r_[0]] for r_ in rows], "old_seat_capacity": [r_[2] for r_ in rows],
        "new_seat_capacity": [r_[3] for r_ in rows], "reason": [r_[4] for r_ in rows]},
        columns=["change_id", "bus_id", "effective_date", "old_seat_capacity", "new_seat_capacity", "reason"])

    # ---- route disruptions ----------------------------------------------
    dmask = rng.random((nd, nb)) < 0.015
    dd, dr = np.nonzero(dmask)
    dtype = np.array(["breakdown", "weather", "driver_absent", "traffic"])[rng.choice(4, len(dd), p=[.3, .2, .2, .3])]
    dcanc = (rng.random(len(dd)) < 0.3) & (dtype != "traffic")
    ddelay = np.where(dcanc, 0, rng.integers(10, 46, len(dd)))
    dis_ids = [f"DIS-2026-{k + 1:06d}" for k in range(len(dd))]
    T["route_disruptions"] = pd.DataFrame({
        "disruption_id": dis_ids, "route_id": [route_ids[r_] for r_ in dr], "school_date": [cal[d_] for d_ in dd],
        "disruption_type": dtype, "delay_min": ddelay, "is_cancelled": dcanc.astype(int)},
        columns=["disruption_id", "route_id", "school_date", "disruption_type", "delay_min", "is_cancelled"])
    dnum = np.full((nd, nb), len(dd), int); dnum[dd, dr] = np.arange(len(dd))
    canc_m = np.zeros((nd, nb), bool); canc_m[dd, dr] = dcanc
    delay_m = np.zeros((nd, nb), int); delay_m[dd, dr] = ddelay

    # ---- daily attendance simulation -------------------------------------
    A = np.flatnonzero(assigned)
    ri_a = a_route[A]
    end_idx = np.where(wd[A], wd_idx[A], nd - 1)
    dgrid = np.arange(nd)[:, None]
    valid = (dgrid >= enr_idx[A][None, :]) & (dgrid <= end_idx[None, :])
    month = np.array([int(c[5:7]) for c in cal])
    season = np.where(np.isin(month, [12, 1, 2]), 1.6, 1.0)[:, None]
    prop = np.clip(rng.gamma(2.0, 0.02, len(A)), 0, 0.35)
    absent = rng.random((nd, len(A))) < prop[None, :] * season
    excused = rng.random((nd, len(A))) < 0.7
    rcanc, rdelay = canc_m[:, ri_a], delay_m[:, ri_a]
    miss = rng.random((nd, len(A))) < (0.004 + 0.03 * (rdelay > 0))
    code = np.select([absent & excused, absent & ~excused, rcanc, miss], [1, 2, 4, 3], 0)
    day_i, a_i = np.nonzero(valid)
    st_code = code[day_i, a_i]
    stu_i = A[a_i]
    dnums = dnum[day_i, ri_a[a_i]]
    dis_arr = np.array(dis_ids + [None], dtype=object)
    m = len(day_i)
    cats = lambda codes, categories: pd.Categorical.from_codes(codes, categories=categories)
    E = pd.DataFrame({
        "attendance_event_id": [f"ATT-2026-{k + 1:07d}" for k in range(m)],
        "student_id": cats(stu_i, sid), "assignment_id": cats(stu_i, asg_ids),
        "route_id": cats(a_route[stu_i], route_ids), "stop_id": cats(a_stop[stu_i], stop_ids),
        "school_date": cats(day_i, cal), "status": cats(st_code, list(("present", "absent_excused", "absent_unexcused", "missed_pickup", "route_cancelled"))),
        "disruption_id": dis_arr[dnums]})
    T["attendance_events"] = E

    # ---- notifications to the primary guardian ---------------------------
    sel = np.flatnonzero(np.isin(st_code, [2, 3, 4]))
    rmap = {2: "unexcused_absence", 3: "pickup_missed", 4: "route_cancelled"}
    nn = len(sel)
    assert nn < 1_000_000, "NOT-2026 counter overflow"
    deliver = rng.random(nn) < 0.975
    rows = []
    for k, e in enumerate(sel):
        i, c, dte = int(stu_i[e]), int(st_code[e]), cal[day_i[e]]
        if c == 3:
            msg = f"Student {sid[i]}: bus pickup at {stop_ids[a_stop[i]]} ({s_names[a_stop[i]]}) was missed on {dte}."
        elif c == 4:
            msg = f"Student {sid[i]}: route {route_ids[a_route[i]]} was cancelled on {dte}; no bus service."
        else:
            msg = f"Student {sid[i]} was marked absent on {dte} without an excuse. Please contact the school."
        ch = "sms" if prim_dest[i].startswith("+") else "email"
        rows.append((f"NOT-2026-{k + 1:06d}", sid[i], prim_gid[i], f"ATT-2026-{e + 1:07d}", ch, prim_dest[i],
                     rmap[c], msg, dte, "delivered" if deliver[k] else "failed"))
    T["notifications"] = pd.DataFrame(rows, columns=[
        "notification_id", "student_id", "guardian_id", "attendance_event_id", "channel", "destination",
        "reason", "message_text", "sent_date", "delivery_status"])
    from .spec import TABLES
    return {k: T[k] for k in TABLES}
