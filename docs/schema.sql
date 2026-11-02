PRAGMA foreign_keys = ON;

CREATE TABLE school_calendar (
  school_date TEXT NOT NULL,
  day_index INTEGER NOT NULL CHECK (day_index BETWEEN 1 AND 400),
  PRIMARY KEY (school_date),
  UNIQUE (day_index)
);

CREATE TABLE address_zones (
  zone_id TEXT NOT NULL,
  zone_name TEXT NOT NULL,
  zone_type TEXT NOT NULL CHECK (zone_type IN ('urban', 'suburban', 'rural')),
  centroid_x_km REAL NOT NULL CHECK (centroid_x_km BETWEEN -30 AND 30),
  centroid_y_km REAL NOT NULL CHECK (centroid_y_km BETWEEN -30 AND 30),
  is_approved_service_area INTEGER NOT NULL CHECK (is_approved_service_area BETWEEN 0 AND 1),
  PRIMARY KEY (zone_id)
);

CREATE TABLE stops (
  stop_id TEXT NOT NULL,
  zone_id TEXT NOT NULL,
  stop_name TEXT NOT NULL,
  stop_x_km REAL NOT NULL CHECK (stop_x_km BETWEEN -30 AND 30),
  stop_y_km REAL NOT NULL CHECK (stop_y_km BETWEEN -30 AND 30),
  is_approved INTEGER NOT NULL CHECK (is_approved BETWEEN 0 AND 1),
  is_wheelchair_accessible INTEGER NOT NULL CHECK (is_wheelchair_accessible BETWEEN 0 AND 1),
  stop_status TEXT NOT NULL CHECK (stop_status IN ('active', 'proposed')),
  effective_from TEXT NOT NULL,
  PRIMARY KEY (stop_id),
  FOREIGN KEY (zone_id) REFERENCES address_zones(zone_id)
);

CREATE TABLE buses (
  bus_id TEXT NOT NULL,
  bus_type TEXT NOT NULL CHECK (bus_type IN ('mini', 'standard', 'large')),
  seat_capacity INTEGER NOT NULL CHECK (seat_capacity BETWEEN 10 AND 90),
  wheelchair_positions INTEGER NOT NULL CHECK (wheelchair_positions BETWEEN 0 AND 6),
  is_wheelchair_accessible INTEGER NOT NULL CHECK (is_wheelchair_accessible BETWEEN 0 AND 1),
  status TEXT NOT NULL CHECK (status IN ('in_service', 'maintenance')),
  effective_from TEXT NOT NULL,
  PRIMARY KEY (bus_id)
);

CREATE TABLE drivers (
  driver_id TEXT NOT NULL,
  bus_id TEXT NOT NULL,
  driver_alias TEXT NOT NULL,
  license_valid_until TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
  PRIMARY KEY (driver_id),
  UNIQUE (bus_id),
  FOREIGN KEY (bus_id) REFERENCES buses(bus_id)
);

CREATE TABLE students (
  student_id TEXT NOT NULL,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  grade INTEGER NOT NULL CHECK (grade BETWEEN 0 AND 12),
  zone_id TEXT NOT NULL,
  home_address_line TEXT NOT NULL,
  home_x_km REAL NOT NULL CHECK (home_x_km BETWEEN -35 AND 35),
  home_y_km REAL NOT NULL CHECK (home_y_km BETWEEN -35 AND 35),
  needs_wheelchair INTEGER NOT NULL CHECK (needs_wheelchair BETWEEN 0 AND 1),
  pickup_window_start TEXT NOT NULL,
  pickup_window_end TEXT NOT NULL,
  enrolled_on TEXT NOT NULL,
  withdrawn_on TEXT,
  status TEXT NOT NULL CHECK (status IN ('active', 'withdrawn')),
  PRIMARY KEY (student_id),
  FOREIGN KEY (zone_id) REFERENCES address_zones(zone_id)
);

CREATE TABLE guardian_contacts (
  guardian_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  guardian_alias TEXT NOT NULL,
  relationship TEXT NOT NULL CHECK (relationship IN ('mother', 'father', 'guardian', 'other')),
  is_primary INTEGER NOT NULL CHECK (is_primary BETWEEN 0 AND 1),
  phone TEXT,
  email TEXT,
  preferred_channel TEXT NOT NULL CHECK (preferred_channel IN ('sms', 'email')),
  PRIMARY KEY (guardian_id),
  UNIQUE (email),
  FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE TABLE routes (
  route_id TEXT NOT NULL,
  bus_id TEXT NOT NULL,
  driver_id TEXT NOT NULL,
  route_name TEXT NOT NULL,
  period TEXT NOT NULL CHECK (period IN ('AM')),
  start_time TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'retired')),
  effective_from TEXT NOT NULL,
  PRIMARY KEY (route_id),
  UNIQUE (bus_id),
  UNIQUE (driver_id),
  FOREIGN KEY (bus_id) REFERENCES buses(bus_id),
  FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)
);

CREATE TABLE route_stops (
  route_id TEXT NOT NULL,
  stop_sequence INTEGER NOT NULL CHECK (stop_sequence BETWEEN 1 AND 60),
  stop_id TEXT NOT NULL,
  distance_km_from_prev REAL NOT NULL CHECK (distance_km_from_prev BETWEEN 0 AND 60),
  travel_min_from_prev INTEGER NOT NULL CHECK (travel_min_from_prev BETWEEN 0 AND 120),
  dwell_min INTEGER NOT NULL CHECK (dwell_min BETWEEN 0 AND 10),
  scheduled_offset_min INTEGER NOT NULL CHECK (scheduled_offset_min BETWEEN 0 AND 300),
  PRIMARY KEY (route_id, stop_sequence),
  UNIQUE (route_id, stop_id),
  FOREIGN KEY (route_id) REFERENCES routes(route_id),
  FOREIGN KEY (stop_id) REFERENCES stops(stop_id)
);

CREATE TABLE bus_capacity_changes (
  change_id TEXT NOT NULL,
  bus_id TEXT NOT NULL,
  effective_date TEXT NOT NULL,
  old_seat_capacity INTEGER NOT NULL CHECK (old_seat_capacity BETWEEN 0 AND 90),
  new_seat_capacity INTEGER NOT NULL CHECK (new_seat_capacity BETWEEN 0 AND 90),
  reason TEXT NOT NULL CHECK (reason IN ('seat_removal', 'seat_restoration', 'vehicle_swap', 'repair')),
  PRIMARY KEY (change_id),
  FOREIGN KEY (bus_id) REFERENCES buses(bus_id)
);

CREATE TABLE route_disruptions (
  disruption_id TEXT NOT NULL,
  route_id TEXT NOT NULL,
  school_date TEXT NOT NULL,
  disruption_type TEXT NOT NULL CHECK (disruption_type IN ('breakdown', 'weather', 'driver_absent', 'traffic')),
  delay_min INTEGER NOT NULL CHECK (delay_min BETWEEN 0 AND 120),
  is_cancelled INTEGER NOT NULL CHECK (is_cancelled BETWEEN 0 AND 1),
  PRIMARY KEY (disruption_id),
  UNIQUE (route_id, school_date),
  FOREIGN KEY (route_id) REFERENCES routes(route_id)
);

CREATE TABLE assignments (
  assignment_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  route_id TEXT,
  stop_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('active', 'ended', 'unassigned')),
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  distance_to_stop_km REAL CHECK (distance_to_stop_km BETWEEN 0 AND 5),
  scheduled_pickup_time TEXT,
  decision_reason TEXT NOT NULL CHECK (decision_reason IN ('assigned_best_score', 'outside_service_area', 'no_stop_within_walking_distance', 'no_accessible_route', 'pickup_window_conflict', 'capacity_full')),
  PRIMARY KEY (assignment_id),
  UNIQUE (student_id),
  FOREIGN KEY (student_id) REFERENCES students(student_id),
  FOREIGN KEY (route_id) REFERENCES routes(route_id),
  FOREIGN KEY (stop_id) REFERENCES stops(stop_id)
);

CREATE TABLE assignment_events (
  assignment_event_id TEXT NOT NULL,
  assignment_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('assigned', 'unassigned', 'ended')),
  event_date TEXT NOT NULL,
  PRIMARY KEY (assignment_event_id),
  FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id)
);

CREATE TABLE attendance_events (
  attendance_event_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  assignment_id TEXT NOT NULL,
  route_id TEXT NOT NULL,
  stop_id TEXT NOT NULL,
  school_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('present', 'absent_excused', 'absent_unexcused', 'missed_pickup', 'route_cancelled')),
  disruption_id TEXT,
  PRIMARY KEY (attendance_event_id),
  UNIQUE (student_id, school_date),
  FOREIGN KEY (student_id) REFERENCES students(student_id),
  FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id),
  FOREIGN KEY (route_id) REFERENCES routes(route_id),
  FOREIGN KEY (stop_id) REFERENCES stops(stop_id),
  FOREIGN KEY (school_date) REFERENCES school_calendar(school_date),
  FOREIGN KEY (disruption_id) REFERENCES route_disruptions(disruption_id)
);

CREATE TABLE notifications (
  notification_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  guardian_id TEXT NOT NULL,
  attendance_event_id TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('sms', 'email')),
  destination TEXT NOT NULL,
  reason TEXT NOT NULL CHECK (reason IN ('pickup_missed', 'route_cancelled', 'unexcused_absence')),
  message_text TEXT NOT NULL,
  sent_date TEXT NOT NULL,
  delivery_status TEXT NOT NULL CHECK (delivery_status IN ('delivered', 'failed')),
  PRIMARY KEY (notification_id),
  UNIQUE (attendance_event_id, guardian_id),
  FOREIGN KEY (student_id) REFERENCES students(student_id),
  FOREIGN KEY (guardian_id) REFERENCES guardian_contacts(guardian_id),
  FOREIGN KEY (attendance_event_id) REFERENCES attendance_events(attendance_event_id)
);
