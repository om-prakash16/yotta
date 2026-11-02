# Data dictionary

Generated from `busroute/spec.py` (`python -m busroute docs`). Do not edit by hand.

Conventions: `bool` is stored as 0/1; dates are ISO `YYYY-MM-DD`; times are `HH:MM` 24h; distances in km; durations in minutes. IDs are zero-padded, immutable, and referenced verbatim across files.

## school_calendar

**Primary key:** `school_date`  
**Cardinality / relationships:** Reference list of the instructional days. 1:N to AttendanceEvent / RouteDisruption by date.  

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `school_date` | date | yes | - | - | yes | Instructional day (Mon-Fri, excludes holidays). |
| `day_index` | int | yes | 1 .. 400 | - | yes | 1-based ordinal of the school day. |

## address_zones

**Primary key:** `zone_id`  
**Cardinality / relationships:** 1:N to Student, 1:N to Stop. A zone outside the service area cannot receive stops.  

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `zone_id` | str | yes | regex `ZONE-\d{6}` | - | yes | ZONE-000001 style key. |
| `zone_name` | str | yes | - | - | no | Synthetic district label. |
| `zone_type` | str | yes | one of: urban, suburban, rural | - | no | Derived from distance of centroid to school. |
| `centroid_x_km` | float | yes | -30 .. 30 | km | no | East-west offset from the school (0,0). |
| `centroid_y_km` | float | yes | -30 .. 30 | km | no | North-south offset from the school. |
| `is_approved_service_area` | bool | yes | 0 .. 1 | - | no | 1 = inside the district service area. |

## stops

**Primary key:** `stop_id`  
**Cardinality / relationships:** N:M with Route via RouteStop; 1:N to Assignment. Only active+approved stops appear on routes.  
**Foreign keys:** `zone_id` -> `address_zones.zone_id`

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `stop_id` | str | yes | regex `STOP-\d{6}` | - | yes | STOP-000001 style key. |
| `zone_id` | str | yes | regex `ZONE-\d{6}` | - | no | FK AddressZone. |
| `stop_name` | str | yes | - | - | no | Synthetic cross-street label (no real addresses). |
| `stop_x_km` | float | yes | -30 .. 30 | km | no | Position, 3 dp. |
| `stop_y_km` | float | yes | -30 .. 30 | km | no | Position, 3 dp. |
| `is_approved` | bool | yes | 0 .. 1 | - | no | Safety-approved for pickups. 0 for proposed stops. |
| `is_wheelchair_accessible` | bool | yes | 0 .. 1 | - | no | Stop can serve wheelchair boarding. |
| `stop_status` | str | yes | one of: active, proposed | - | no | Lifecycle. is_approved = (stop_status == active). |
| `effective_from` | date | yes | - | - | no | Date the stop status took effect. |

## buses

**Primary key:** `bus_id`  
**Cardinality / relationships:** 1:1 Driver (current), 1:1 Route (AM). 1:N BusCapacityChange (history).  

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `bus_id` | str | yes | regex `BUS-\d{6}` | - | yes | BUS-000001 style key. |
| `bus_type` | str | yes | one of: mini, standard, large | - | no | Vehicle class. |
| `seat_capacity` | int | yes | 10 .. 90 | seats | no | Capacity at start of year; later changes live in bus_capacity_changes. |
| `wheelchair_positions` | int | yes | 0 .. 6 | positions | no | Securement positions. |
| `is_wheelchair_accessible` | bool | yes | 0 .. 1 | - | no | Derived: wheelchair_positions > 0. |
| `status` | str | yes | one of: in_service, maintenance | - | no | Baseline data: all in_service. |
| `effective_from` | date | yes | - | - | no | In-service date. |

## drivers

**Primary key:** `driver_id`  
**Cardinality / relationships:** 1:1 current Bus; 1:N Route over time (one AM route in this dataset).  
**Foreign keys:** `bus_id` -> `buses.bus_id`

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `driver_id` | str | yes | regex `DRV-\d{6}` | - | yes | DRV-000001 style key. |
| `bus_id` | str | yes | regex `BUS-\d{6}` | - | yes | FK Bus. |
| `driver_alias` | str | yes | - | - | no | Synthetic name. |
| `license_valid_until` | date | yes | - | - | no | Must be on/after the last school day. |
| `status` | str | yes | one of: active, inactive | - | no | Baseline data: all active. |

## students

**Primary key:** `student_id`  
**Cardinality / relationships:** 1:N GuardianContact (exactly one primary). 1:1 Assignment per school year. 1:N AttendanceEvent.  
**Foreign keys:** `zone_id` -> `address_zones.zone_id`

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `student_id` | str | yes | regex `STU-\d{6}` | - | yes | STU-000001 style key. |
| `first_name` | str | yes | - | - | no | Synthetic. |
| `last_name` | str | yes | - | - | no | Synthetic. |
| `grade` | int | yes | 0 .. 12 | - | no | 0 = kindergarten. |
| `zone_id` | str | yes | regex `ZONE-\d{6}` | - | no | FK AddressZone (home zone). |
| `home_address_line` | str | yes | - | - | no | Synthetic street address. Sensitive: must never be sent in notifications. |
| `home_x_km` | float | yes | -35 .. 35 | km | no | Home position, 3 dp. |
| `home_y_km` | float | yes | -35 .. 35 | km | no | Home position, 3 dp. |
| `needs_wheelchair` | bool | yes | 0 .. 1 | - | no | Requires wheelchair-accessible bus and stop. |
| `pickup_window_start` | time | yes | regex `([01]\d|2[0-3]):[0-5]\d` | - | no | HH:MM earliest acceptable pickup. |
| `pickup_window_end` | time | yes | regex `([01]\d|2[0-3]):[0-5]\d` | - | no | HH:MM latest acceptable pickup (75 min window). |
| `enrolled_on` | date | yes | - | - | no | First day eligible for transport. |
| `withdrawn_on` | date | no | - | - | no | Last transport day if withdrawn. |
| `status` | str | yes | one of: active, withdrawn | - | no | Lifecycle; withdrawn <=> withdrawn_on present. |

## guardian_contacts

**Primary key:** `guardian_id`  
**Cardinality / relationships:** N:1 Student. Exactly one is_primary=1 per student. Only the primary is notified.  
**Foreign keys:** `student_id` -> `students.student_id`

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `guardian_id` | str | yes | regex `GRD-\d{6}` | - | yes | GRD-000001 style key. |
| `student_id` | str | yes | regex `STU-\d{6}` | - | no | FK Student. |
| `guardian_alias` | str | yes | - | - | no | Synthetic name. |
| `relationship` | str | yes | one of: mother, father, guardian, other | - | no |  |
| `is_primary` | bool | yes | 0 .. 1 | - | no |  |
| `phone` | str | no | regex `\+1-555-01\d\d` | - | no | Fictional 555-01xx number; data minimization: no real numbers. |
| `email` | str | no | regex `guardian\.\d{6}@example\.org` | - | yes | Reserved example.org address. |
| `preferred_channel` | str | yes | one of: sms, email | - | no | Must have a matching contact value. |

## routes

**Primary key:** `route_id`  
**Cardinality / relationships:** N:M with Stop via RouteStop; 1:N Assignment; 1:N RouteDisruption.  
**Foreign keys:** `bus_id` -> `buses.bus_id`; `driver_id` -> `drivers.driver_id`

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `route_id` | str | yes | regex `ROUTE-2026-\d{6}` | - | yes | ROUTE-2026-000001 style key. |
| `bus_id` | str | yes | regex `BUS-\d{6}` | - | yes | FK Bus (one AM route per bus). |
| `driver_id` | str | yes | regex `DRV-\d{6}` | - | yes | FK Driver; driver.bus_id must equal bus_id. |
| `route_name` | str | yes | - | - | no |  |
| `period` | str | yes | one of: AM | - | no |  |
| `start_time` | time | yes | regex `([01]\d|2[0-3]):[0-5]\d` | - | no | Departure from first stop (HH:MM). |
| `status` | str | yes | one of: active, retired | - | no |  |
| `effective_from` | date | yes | - | - | no |  |

## route_stops

**Primary key:** `route_id, stop_sequence`  
**Cardinality / relationships:** Bridge table for Route N:M Stop. A stop may appear only once per route; stops are ordered outer-to-inner (descending distance from school).  
**Foreign keys:** `route_id` -> `routes.route_id`; `stop_id` -> `stops.stop_id`
**Additional unique constraints:** (`route_id`, `stop_id`)

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `route_id` | str | yes | regex `ROUTE-2026-\d{6}` | - | no | FK Route. |
| `stop_sequence` | int | yes | 1 .. 60 | - | no | 1-based order on the route. |
| `stop_id` | str | yes | regex `STOP-\d{6}` | - | no | FK Stop (active, approved). |
| `distance_km_from_prev` | float | yes | 0 .. 60 | km | no | 1.3 x straight-line distance (road factor); 0 for first stop. |
| `travel_min_from_prev` | int | yes | 0 .. 120 | min | no | ceil(distance / segment speed 20-45 km/h), min 1; 0 for first stop. |
| `dwell_min` | int | yes | 0 .. 10 | min | no | Dwell time at this stop (1). |
| `scheduled_offset_min` | int | yes | 0 .. 300 | min | no | offset[i] = offset[i-1] + dwell[i-1] + travel[i]. |

## bus_capacity_changes

**Primary key:** `change_id`  
**Cardinality / relationships:** Event history of seat-capacity changes per bus (1:N). Chain: old = previous new.  
**Foreign keys:** `bus_id` -> `buses.bus_id`

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `change_id` | str | yes | regex `CAP-2026-\d{6}` | - | yes | CAP-2026-000001 style key. |
| `bus_id` | str | yes | regex `BUS-\d{6}` | - | no |  |
| `effective_date` | date | yes | - | - | no | Must be a school day. |
| `old_seat_capacity` | int | yes | 0 .. 90 | seats | no |  |
| `new_seat_capacity` | int | yes | 0 .. 90 | seats | no |  |
| `reason` | str | yes | one of: seat_removal, seat_restoration, vehicle_swap, repair | - | no |  |

## route_disruptions

**Primary key:** `disruption_id`  
**Cardinality / relationships:** Event table: 0..1 per route per school day (unique route_id+school_date).  
**Foreign keys:** `route_id` -> `routes.route_id`
**Additional unique constraints:** (`route_id`, `school_date`)

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `disruption_id` | str | yes | regex `DIS-2026-\d{6}` | - | yes | DIS-2026-000001 style key. |
| `route_id` | str | yes | regex `ROUTE-2026-\d{6}` | - | no |  |
| `school_date` | date | yes | - | - | no |  |
| `disruption_type` | str | yes | one of: breakdown, weather, driver_absent, traffic | - | no |  |
| `delay_min` | int | yes | 0 .. 120 | min | no | 0 when cancelled. |
| `is_cancelled` | bool | yes | 0 .. 1 | - | no | Traffic never cancels a route. |

## assignments

**Primary key:** `assignment_id`  
**Cardinality / relationships:** 1:1 Student per school year (ASN-<student-id>-2026). route_id+stop_id must exist in RouteStop. Unassigned rows keep an explicit reason.  
**Foreign keys:** `student_id` -> `students.student_id`; `route_id` -> `routes.route_id`; `stop_id` -> `stops.stop_id`

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `assignment_id` | str | yes | regex `ASN-STU-\d{6}-2026` | - | yes | ASN-<student-id>-2026. |
| `student_id` | str | yes | regex `STU-\d{6}` | - | yes |  |
| `route_id` | str | no | regex `ROUTE-2026-\d{6}` | - | no | Null when unassigned. |
| `stop_id` | str | no | regex `STOP-\d{6}` | - | no | Null when unassigned. |
| `status` | str | yes | one of: active, ended, unassigned | - | no | Lifecycle. |
| `effective_from` | date | yes | - | - | no | = student.enrolled_on. |
| `effective_to` | date | no | - | - | no | = student.withdrawn_on when ended. |
| `distance_to_stop_km` | float | no | 0 .. 5 | km | no | Straight-line home-to-stop distance (<=0.8 grades 0-5, <=1.2 otherwise). |
| `scheduled_pickup_time` | time | no | regex `([01]\d|2[0-3]):[0-5]\d` | - | no | route.start_time + stop offset; derived. |
| `decision_reason` | str | yes | one of: assigned_best_score, outside_service_area, no_stop_within_walking_distance, no_accessible_route, pickup_window_conflict, capacity_full | - | no | Explains each decision/exception. |

## assignment_events

**Primary key:** `assignment_event_id`  
**Cardinality / relationships:** Append-only lifecycle history for Assignment: assigned|unassigned then optionally ended.  
**Foreign keys:** `assignment_id` -> `assignments.assignment_id`

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `assignment_event_id` | str | yes | regex `AEV-2026-\d{6}` | - | yes |  |
| `assignment_id` | str | yes | regex `ASN-STU-\d{6}-2026` | - | no |  |
| `event_type` | str | yes | one of: assigned, unassigned, ended | - | no |  |
| `event_date` | date | yes | - | - | no |  |

## attendance_events

**Primary key:** `attendance_event_id`  
**Cardinality / relationships:** One row per assigned student per school day in the assignment window. route_id/stop_id are a snapshot as of the event (history is not rewritten).  
**Foreign keys:** `student_id` -> `students.student_id`; `assignment_id` -> `assignments.assignment_id`; `route_id` -> `routes.route_id`; `stop_id` -> `stops.stop_id`; `school_date` -> `school_calendar.school_date`; `disruption_id` -> `route_disruptions.disruption_id`
**Additional unique constraints:** (`student_id`, `school_date`)

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `attendance_event_id` | str | yes | regex `ATT-2026-\d{7}` | - | yes | ATT-2026-0000001 (7-digit counter; ~1M rows at full scale). |
| `student_id` | str | yes | regex `STU-\d{6}` | - | no |  |
| `assignment_id` | str | yes | regex `ASN-STU-\d{6}-2026` | - | no |  |
| `route_id` | str | yes | regex `ROUTE-2026-\d{6}` | - | no |  |
| `stop_id` | str | yes | regex `STOP-\d{6}` | - | no |  |
| `school_date` | date | yes | - | - | no |  |
| `status` | str | yes | one of: present, absent_excused, absent_unexcused, missed_pickup, route_cancelled | - | no | absent > route_cancelled > missed_pickup > present. |
| `disruption_id` | str | no | regex `DIS-2026-\d{6}` | - | no | Set when the route was disrupted that day. |

## notifications

**Primary key:** `notification_id`  
**Cardinality / relationships:** N:1 AttendanceEvent (trigger), N:1 GuardianContact (primary only). Destination is stored as sent.  
**Foreign keys:** `student_id` -> `students.student_id`; `guardian_id` -> `guardian_contacts.guardian_id`; `attendance_event_id` -> `attendance_events.attendance_event_id`
**Additional unique constraints:** (`attendance_event_id`, `guardian_id`)

| Field | Type | Req | Allowed values / validation | Unit | Unique | Notes |
|---|---|---|---|---|---|---|
| `notification_id` | str | yes | regex `NOT-2026-\d{6}` | - | yes | NOT-2026-000001 style key. |
| `student_id` | str | yes | regex `STU-\d{6}` | - | no |  |
| `guardian_id` | str | yes | regex `GRD-\d{6}` | - | no |  |
| `attendance_event_id` | str | yes | regex `ATT-2026-\d{7}` | - | no |  |
| `channel` | str | yes | one of: sms, email | - | no |  |
| `destination` | str | yes | - | - | no | Phone/email actually used (validated semantically, see validate.py). |
| `reason` | str | yes | one of: pickup_missed, route_cancelled, unexcused_absence | - | no |  |
| `message_text` | str | yes | - | - | no | Uses student_id/stop only; never a home address. |
| `sent_date` | date | yes | - | - | no | = school_date of the triggering event. |
| `delivery_status` | str | yes | one of: delivered, failed | - | no |  |
