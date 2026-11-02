from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Config:
    """All scale knobs. Starter and full datasets use the same generator."""
    seed: int = 20261022
    n_students: int = 5000
    n_buses: int = 100
    n_stops: int = 300
    n_school_days: int = 200
    n_zones: int = 40
    first_school_day: str = "2026-08-24"
    anomalies_per_type: int = 5
    school_year: int = 2026

    def __post_init__(self):
        positive = ("n_students", "n_buses", "n_stops", "n_school_days", "n_zones")
        for field in positive:
            value = getattr(self, field)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field} must be a positive integer")
        if self.n_stops < 6:
            raise ValueError("n_stops must be >= 6 so route candidates remain meaningful")
        if self.n_school_days < 4:
            raise ValueError("n_school_days must be >= 4 so dated capacity events fit the calendar")
        if self.n_zones < 6:
            raise ValueError("n_zones must be >= 6 to include an explicit out-of-service zone")
        if not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        if not isinstance(self.anomalies_per_type, int) or self.anomalies_per_type < 0:
            raise ValueError("anomalies_per_type must be a non-negative integer")
        from datetime import date
        try:
            date.fromisoformat(self.first_school_day)
        except (TypeError, ValueError) as exc:
            raise ValueError("first_school_day must be an ISO date (YYYY-MM-DD)") from exc

    def with_overrides(self, **kw):
        return replace(self, **{k: v for k, v in kw.items() if v is not None})


PROFILES = {
    "full": Config(),
    "starter": Config(n_students=500, n_buses=20, n_stops=60, n_school_days=30,
                      n_zones=12, anomalies_per_type=3),
    # tiny profile used by the unit tests (runs in a couple of seconds)
    "test": Config(n_students=600, n_buses=15, n_stops=45, n_school_days=15,
                   n_zones=10, anomalies_per_type=2),
}
