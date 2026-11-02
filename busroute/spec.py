"""Single source of truth for the data dictionary.

The same specification drives (1) docs/data_dictionary.md, (2) schema.sql with
PK/FK/CHECK constraints, and (3) the generic schema checks in validate.py.
"""
from dataclasses import dataclass

TIME_RX = r"([01]\d|2[0-3]):[0-5]\d"
RX = {
    "zone": r"ZONE-\d{6}", "stop": r"STOP-\d{6}", "bus": r"BUS-\d{6}", "stu": r"STU-\d{6}",
    "drv": r"DRV-\d{6}", "grd": r"GRD-\d{6}", "route": r"ROUTE-2026-\d{6}",
    "asn": r"ASN-STU-\d{6}-2026", "att": r"ATT-2026-\d{7}", "not": r"NOT-2026-\d{6}",
    "dis": r"DIS-2026-\d{6}", "cap": r"CAP-2026-\d{6}", "aev": r"AEV-2026-\d{6}",
}
PHONE_RX = r"\+1-555-01\d\d"                 # reserved fictional number block
EMAIL_RX = r"guardian\.\d{6}@example\.org"   # RFC 2606 reserved domain


@dataclass(frozen=True)
class F:
    name: str
    type: str                  # str | int | float | bool | date | time
    required: bool = True
    enum: tuple = ()
    regex: str = ""
    lo: float = None
    hi: float = None
    unit: str = ""
    unique: bool = False
    desc: str = ""


def f(name, type="str", req=True, *, enum=(), rx="", lo=None, hi=None, unit="", uniq=False, d=""):
    return F(name, type, req, tuple(enum), rx, lo, hi, unit, uniq, d)


ASSIGN_REASONS = ("assigned_best_score", "outside_service_area", "no_stop_within_walking_distance",
                  "no_accessible_route", "pickup_window_conflict", "capacity_full")
ATT_STATUS = ("present", "absent_excused", "absent_unexcused", "missed_pickup", "route_cancelled")
NOTIF_REASON = ("pickup_missed", "route_cancelled", "unexcused_absence")

# Ordered parents -> children (also the SQL creation order).
TABLES = {
    "school_calendar": dict(
        pk=["school_date"], fks=[],
        card="Reference list of the instructional days. 1:N to AttendanceEvent / RouteDisruption by date.",
        fields=[
            f("school_date", "date", uniq=True, d="Instructional day (Mon-Fri, excludes holidays)."),
            f("day_index", "int", lo=1, hi=400, uniq=True, d="1-based ordinal of the school day."),
        ]),
    "address_zones": dict(
        pk=["zone_id"], fks=[],
        card="1:N to Student, 1:N to Stop. A zone outside the service area cannot receive stops.",
        fields=[
            f("zone_id", rx=RX["zone"], uniq=True, d="ZONE-000001 style key."),
            f("zone_name", d="Synthetic district label."),
            f("zone_type", enum=("urban", "suburban", "rural"), d="Derived from distance of centroid to school."),
            f("centroid_x_km", "float", lo=-30, hi=30, unit="km", d="East-west offset from the school (0,0)."),
            f("centroid_y_km", "float", lo=-30, hi=30, unit="km", d="North-south offset from the school."),
            f("is_approved_service_area", "bool", lo=0, hi=1, d="1 = inside the district service area."),
        ]),
    "stops": dict(
        pk=["stop_id"], fks=[("zone_id", "address_zones", "zone_id")],
        card="N:M with Route via RouteStop; 1:N to Assignment. Only active+approved stops appear on routes.",
        fields=[
            f("stop_id", rx=RX["stop"], uniq=True, d="STOP-000001 style key."),
            f("zone_id", rx=RX["zone"], d="FK AddressZone."),
            f("stop_name", d="Synthetic cross-street label (no real addresses)."),
            f("stop_x_km", "float", lo=-30, hi=30, unit="km", d="Position, 3 dp."),
            f("stop_y_km", "float", lo=-30, hi=30, unit="km", d="Position, 3 dp."),
            f("is_approved", "bool", lo=0, hi=1, d="Safety-approved for pickups. 0 for proposed stops."),
            f("is_wheelchair_accessible", "bool", lo=0, hi=1, d="Stop can serve wheelchair boarding."),
            f("stop_status", enum=("active", "proposed"), d="Lifecycle. is_approved = (stop_status == active)."),
            f("effective_from", "date", d="Date the stop status took effect."),
        ]),
    "buses": dict(
        pk=["bus_id"], fks=[],
        card="1:1 Driver (current), 1:1 Route (AM). 1:N BusCapacityChange (history).",
        fields=[
            f("bus_id", rx=RX["bus"], uniq=True, d="BUS-000001 style key."),
            f("bus_type", enum=("mini", "standard", "large"), d="Vehicle class."),
            f("seat_capacity", "int", lo=10, hi=90, unit="seats", d="Capacity at start of year; later changes live in bus_capacity_changes."),
            f("wheelchair_positions", "int", lo=0, hi=6, unit="positions", d="Securement positions."),
            f("is_wheelchair_accessible", "bool", lo=0, hi=1, d="Derived: wheelchair_positions > 0."),
            f("status", enum=("in_service", "maintenance"), d="Baseline data: all in_service."),
            f("effective_from", "date", d="In-service date."),
        ]),
    "drivers": dict(
        pk=["driver_id"], fks=[("bus_id", "buses", "bus_id")],
        card="1:1 current Bus; 1:N Route over time (one AM route in this dataset).",
        fields=[
            f("driver_id", rx=RX["drv"], uniq=True, d="DRV-000001 style key."),
            f("bus_id", rx=RX["bus"], uniq=True, d="FK Bus."),
            f("driver_alias", d="Synthetic name."),
            f("license_valid_until", "date", d="Must be on/after the last school day."),
            f("status", enum=("active", "inactive"), d="Baseline data: all active."),
        ]),
    "students": dict(
        pk=["student_id"], fks=[("zone_id", "address_zones", "zone_id")],
        card="1:N GuardianContact (exactly one primary). 1:1 Assignment per school year. 1:N AttendanceEvent.",
        fields=[
            f("student_id", rx=RX["stu"], uniq=True, d="STU-000001 style key."),
            f("first_name", d="Synthetic."), f("last_name", d="Synthetic."),
            f("grade", "int", lo=0, hi=12, d="0 = kindergarten."),
            f("zone_id", rx=RX["zone"], d="FK AddressZone (home zone)."),
            f("home_address_line", d="Synthetic street address. Sensitive: must never be sent in notifications."),
            f("home_x_km", "float", lo=-35, hi=35, unit="km", d="Home position, 3 dp."),
            f("home_y_km", "float", lo=-35, hi=35, unit="km", d="Home position, 3 dp."),
            f("needs_wheelchair", "bool", lo=0, hi=1, d="Requires wheelchair-accessible bus and stop."),
            f("pickup_window_start", "time", rx=TIME_RX, d="HH:MM earliest acceptable pickup."),
            f("pickup_window_end", "time", rx=TIME_RX, d="HH:MM latest acceptable pickup (75 min window)."),
            f("enrolled_on", "date", d="First day eligible for transport."),
            f("withdrawn_on", "date", False, d="Last transport day if withdrawn."),
            f("status", enum=("active", "withdrawn"), d="Lifecycle; withdrawn <=> withdrawn_on present."),
        ]),
    "guardian_contacts": dict(
        pk=["guardian_id"], fks=[("student_id", "students", "student_id")],
        card="N:1 Student. Exactly one is_primary=1 per student. Only the primary is notified.",
        fields=[
            f("guardian_id", rx=RX["grd"], uniq=True, d="GRD-000001 style key."),
            f("student_id", rx=RX["stu"], d="FK Student."),
            f("guardian_alias", d="Synthetic name."),
            f("relationship", enum=("mother", "father", "guardian", "other")),
            f("is_primary", "bool", lo=0, hi=1),
            f("phone", "str", False, rx=PHONE_RX, d="Fictional 555-01xx number; data minimization: no real numbers."),
            f("email", "str", False, rx=EMAIL_RX, uniq=True, d="Reserved example.org address."),
            f("preferred_channel", enum=("sms", "email"), d="Must have a matching contact value."),
        ]),
    "routes": dict(
        pk=["route_id"], fks=[("bus_id", "buses", "bus_id"), ("driver_id", "drivers", "driver_id")],
        card="N:M with Stop via RouteStop; 1:N Assignment; 1:N RouteDisruption.",
        fields=[
            f("route_id", rx=RX["route"], uniq=True, d="ROUTE-2026-000001 style key."),
            f("bus_id", rx=RX["bus"], uniq=True, d="FK Bus (one AM route per bus)."),
            f("driver_id", rx=RX["drv"], uniq=True, d="FK Driver; driver.bus_id must equal bus_id."),
            f("route_name"), f("period", enum=("AM",)),
            f("start_time", "time", rx=TIME_RX, d="Departure from first stop (HH:MM)."),
            f("status", enum=("active", "retired")),
            f("effective_from", "date"),
        ]),
    "route_stops": dict(
        pk=["route_id", "stop_sequence"],
        unique_together=[["route_id", "stop_id"]],
        fks=[("route_id", "routes", "route_id"), ("stop_id", "stops", "stop_id")],
        card="Bridge table for Route N:M Stop. A stop may appear only once per route; stops are ordered outer-to-inner (descending distance from school).",
        fields=[
            f("route_id", rx=RX["route"], d="FK Route."),
            f("stop_sequence", "int", lo=1, hi=60, d="1-based order on the route."),
            f("stop_id", rx=RX["stop"], d="FK Stop (active, approved)."),
            f("distance_km_from_prev", "float", lo=0, hi=60, unit="km", d="1.3 x straight-line distance (road factor); 0 for first stop."),
            f("travel_min_from_prev", "int", lo=0, hi=120, unit="min", d="ceil(distance / segment speed 20-45 km/h), min 1; 0 for first stop."),
            f("dwell_min", "int", lo=0, hi=10, unit="min", d="Dwell time at this stop (1)."),
            f("scheduled_offset_min", "int", lo=0, hi=300, unit="min", d="offset[i] = offset[i-1] + dwell[i-1] + travel[i]."),
        ]),
    "bus_capacity_changes": dict(
        pk=["change_id"], fks=[("bus_id", "buses", "bus_id")],
        card="Event history of seat-capacity changes per bus (1:N). Chain: old = previous new.",
        fields=[
            f("change_id", rx=RX["cap"], uniq=True, d="CAP-2026-000001 style key."),
            f("bus_id", rx=RX["bus"]),
            f("effective_date", "date", d="Must be a school day."),
            f("old_seat_capacity", "int", lo=0, hi=90, unit="seats"),
            f("new_seat_capacity", "int", lo=0, hi=90, unit="seats"),
            f("reason", enum=("seat_removal", "seat_restoration", "vehicle_swap", "repair")),
        ]),
    "route_disruptions": dict(
        pk=["disruption_id"], unique_together=[["route_id", "school_date"]],
        fks=[("route_id", "routes", "route_id")],
        card="Event table: 0..1 per route per school day (unique route_id+school_date).",
        fields=[
            f("disruption_id", rx=RX["dis"], uniq=True, d="DIS-2026-000001 style key."),
            f("route_id", rx=RX["route"]),
            f("school_date", "date"),
            f("disruption_type", enum=("breakdown", "weather", "driver_absent", "traffic")),
            f("delay_min", "int", lo=0, hi=120, unit="min", d="0 when cancelled."),
            f("is_cancelled", "bool", lo=0, hi=1, d="Traffic never cancels a route."),
        ]),
    "assignments": dict(
        pk=["assignment_id"],
        fks=[("student_id", "students", "student_id"), ("route_id", "routes", "route_id"), ("stop_id", "stops", "stop_id")],
        card="1:1 Student per school year (ASN-<student-id>-2026). route_id+stop_id must exist in RouteStop. Unassigned rows keep an explicit reason.",
        fields=[
            f("assignment_id", rx=RX["asn"], uniq=True, d="ASN-<student-id>-2026."),
            f("student_id", rx=RX["stu"], uniq=True),
            f("route_id", "str", False, rx=RX["route"], d="Null when unassigned."),
            f("stop_id", "str", False, rx=RX["stop"], d="Null when unassigned."),
            f("status", enum=("active", "ended", "unassigned"), d="Lifecycle."),
            f("effective_from", "date", d="= student.enrolled_on."),
            f("effective_to", "date", False, d="= student.withdrawn_on when ended."),
            f("distance_to_stop_km", "float", False, lo=0, hi=5, unit="km", d="Straight-line home-to-stop distance (<=0.8 grades 0-5, <=1.2 otherwise)."),
            f("scheduled_pickup_time", "time", False, rx=TIME_RX, d="route.start_time + stop offset; derived."),
            f("decision_reason", enum=ASSIGN_REASONS, d="Explains each decision/exception."),
        ]),
    "assignment_events": dict(
        pk=["assignment_event_id"], fks=[("assignment_id", "assignments", "assignment_id")],
        card="Append-only lifecycle history for Assignment: assigned|unassigned then optionally ended.",
        fields=[
            f("assignment_event_id", rx=RX["aev"], uniq=True),
            f("assignment_id", rx=RX["asn"]),
            f("event_type", enum=("assigned", "unassigned", "ended")),
            f("event_date", "date"),
        ]),
    "attendance_events": dict(
        pk=["attendance_event_id"], unique_together=[["student_id", "school_date"]],
        fks=[("student_id", "students", "student_id"), ("assignment_id", "assignments", "assignment_id"),
             ("route_id", "routes", "route_id"), ("stop_id", "stops", "stop_id"),
             ("school_date", "school_calendar", "school_date"), ("disruption_id", "route_disruptions", "disruption_id")],
        card="One row per assigned student per school day in the assignment window. route_id/stop_id are a snapshot as of the event (history is not rewritten).",
        fields=[
            f("attendance_event_id", rx=RX["att"], uniq=True, d="ATT-2026-0000001 (7-digit counter; ~1M rows at full scale)."),
            f("student_id", rx=RX["stu"]), f("assignment_id", rx=RX["asn"]),
            f("route_id", rx=RX["route"]), f("stop_id", rx=RX["stop"]),
            f("school_date", "date"),
            f("status", enum=ATT_STATUS, d="absent > route_cancelled > missed_pickup > present."),
            f("disruption_id", "str", False, rx=RX["dis"], d="Set when the route was disrupted that day."),
        ]),
    "notifications": dict(
        pk=["notification_id"], unique_together=[["attendance_event_id", "guardian_id"]],
        fks=[("student_id", "students", "student_id"), ("guardian_id", "guardian_contacts", "guardian_id"),
             ("attendance_event_id", "attendance_events", "attendance_event_id")],
        card="N:1 AttendanceEvent (trigger), N:1 GuardianContact (primary only). Destination is stored as sent.",
        fields=[
            f("notification_id", rx=RX["not"], uniq=True, d="NOT-2026-000001 style key."),
            f("student_id", rx=RX["stu"]), f("guardian_id", rx=RX["grd"]),
            f("attendance_event_id", rx=RX["att"]),
            f("channel", enum=("sms", "email")),
            f("destination", d="Phone/email actually used (validated semantically, see validate.py)."),
            f("reason", enum=NOTIF_REASON),
            f("message_text", d="Uses student_id/stop only; never a home address."),
            f("sent_date", "date", d="= school_date of the triggering event."),
            f("delivery_status", enum=("delivered", "failed")),
        ]),
}

_SQL = {"str": "TEXT", "int": "INTEGER", "float": "REAL", "bool": "INTEGER", "date": "TEXT", "time": "TEXT"}


def schema_sql() -> str:
    out = ["PRAGMA foreign_keys = ON;"]
    for name, t in TABLES.items():
        cols, cons = [], []
        for fl in t["fields"]:
            c = f"  {fl.name} {_SQL[fl.type]}{' NOT NULL' if fl.required else ''}"
            if fl.enum:
                c += " CHECK (%s IN (%s))" % (fl.name, ", ".join(f"'{e}'" for e in fl.enum))
            if fl.lo is not None and fl.hi is not None:
                c += f" CHECK ({fl.name} BETWEEN {fl.lo} AND {fl.hi})"
            cols.append(c)
            if fl.unique and [fl.name] != t["pk"]:
                cons.append(f"  UNIQUE ({fl.name})")
        cons.insert(0, f"  PRIMARY KEY ({', '.join(t['pk'])})")
        for unique_cols in t.get("unique_together", []):
            cons.append(f"  UNIQUE ({', '.join(unique_cols)})")
        for col, parent, pcol in t["fks"]:
            cons.append(f"  FOREIGN KEY ({col}) REFERENCES {parent}({pcol})")
        out.append(f"CREATE TABLE {name} (\n" + ",\n".join(cols + cons) + "\n);")
    return "\n\n".join(out) + "\n"


def data_dictionary_md() -> str:
    L = ["# Data dictionary", "",
         "Generated from `busroute/spec.py` (`python -m busroute docs`). Do not edit by hand.", "",
         "Conventions: `bool` is stored as 0/1; dates are ISO `YYYY-MM-DD`; times are `HH:MM` 24h; "
         "distances in km; durations in minutes. IDs are zero-padded, immutable, and referenced verbatim across files.", ""]
    for name, t in TABLES.items():
        L += [f"## {name}", "", f"**Primary key:** `{', '.join(t['pk'])}`  ", f"**Cardinality / relationships:** {t['card']}  "]
        if t["fks"]:
            L.append("**Foreign keys:** " + "; ".join(f"`{c}` -> `{p}.{pc}`" for c, p, pc in t["fks"]))
        if t.get("unique_together"):
            L.append("**Additional unique constraints:** " + "; ".join(
                "(" + ", ".join(f"`{c}`" for c in cols) + ")" for cols in t["unique_together"]))
        L += ["", "| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |", "|---|---|---|---|---|---|---|"]
        for fl in t["fields"]:
            rule = []
            if fl.enum: rule.append("one of: " + ", ".join(fl.enum))
            if fl.regex: rule.append(f"regex `{fl.regex}`")
            if fl.lo is not None: rule.append(f"{fl.lo} .. {fl.hi}")
            L.append(f"| `{fl.name}` | {fl.type} | {'yes' if fl.required else 'no'} | {'; '.join(rule) or '-'} | "
                     f"{fl.unit or '-'} | {'yes' if fl.unique or [fl.name] == t['pk'] else 'no'} | {fl.desc} |")
        L.append("")
    return "\n".join(L)
