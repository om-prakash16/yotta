"""CSV / JSON / SQLite seed exports plus reproducible SHA-256 manifests."""
from __future__ import annotations

import hashlib
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from .spec import TABLES, schema_sql


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sql_value(value, field) -> str:
    """Encode one scalar as a SQLite literal, using the data-dictionary type."""
    if value is None:
        return "NULL"
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return "NULL"
    if field.type in ("int", "bool"):
        return str(int(value))
    if field.type == "float":
        return repr(float(value))
    return "'" + str(value).replace("'", "''") + "'"


def write_sql_seed(T: dict, path: Path, batch_rows: int = 250) -> None:
    """Stream a deterministic SQLite seed script without loading ~1M rows into SQLite.

    Foreign-key enforcement is disabled only during the bulk import. The generated
    script re-enables it after COMMIT; reviewers can then run PRAGMA foreign_key_check.
    Application-level FK checks are run against the full in-memory tables before export.
    """
    with open(path, "w", encoding="utf-8", buffering=1 << 20, newline="\n") as fh:
        fh.write("-- Synthetic student transportation seed; SQLite-compatible SQL.\n")
        fh.write("-- Foreign keys are disabled only during ordered bulk insert.\n")
        fh.write("PRAGMA foreign_keys = OFF;\n")
        # schema_sql() starts with PRAGMA foreign_keys=ON; omit that initial pragma
        # because SQLite will ignore attempts to change FK mode inside a transaction.
        ddl = schema_sql().replace("PRAGMA foreign_keys = ON;\n", "", 1)
        fh.write(ddl)
        fh.write("\nBEGIN TRANSACTION;\n")
        for name, spec in TABLES.items():
            fields = spec["fields"]
            cols = [f.name for f in fields]
            df = T[name][cols]
            quoted_cols = ", ".join(f'"{c}"' for c in cols)
            prefix = f'INSERT INTO "{name}" ({quoted_cols}) VALUES\n'
            batch = []
            for row in df.itertuples(index=False, name=None):
                batch.append("(" + ", ".join(_sql_value(v, fl) for v, fl in zip(row, fields)) + ")")
                if len(batch) >= batch_rows:
                    fh.write(prefix)
                    fh.write(",\n".join(batch))
                    fh.write(";\n")
                    batch.clear()
            if batch:
                fh.write(prefix)
                fh.write(",\n".join(batch))
                fh.write(";\n")
        fh.write("COMMIT;\n")
        fh.write("PRAGMA foreign_keys = ON;\n")
        fh.write("-- Optional integrity assertion: PRAGMA foreign_key_check;\n")


def build_sqlite(T: dict) -> sqlite3.Connection:
    """Load a modest profile into SQLite for an independent PRAGMA FK audit."""
    con = sqlite3.connect(":memory:")
    con.executescript(schema_sql())
    con.execute("PRAGMA foreign_keys = OFF")
    con.execute("PRAGMA synchronous = OFF")
    con.execute("PRAGMA temp_store = MEMORY")
    for name, spec in TABLES.items():
        cols = [f.name for f in spec["fields"]]
        T[name][cols].to_sql(name, con, if_exists="append", index=False, chunksize=1000, method="multi")
    con.commit()
    con.execute("PRAGMA foreign_keys = ON")
    return con


def export_all(T: dict, gt: pd.DataFrame, out: Path, formats=("csv", "json", "sql")) -> dict:
    data, gtd = out / "data", out / "ground_truth"
    data.mkdir(parents=True, exist_ok=True)
    gtd.mkdir(parents=True, exist_ok=True)
    files = []
    for name, spec in TABLES.items():
        df = T[name][[f.name for f in spec["fields"]]]
        if "csv" in formats:
            path = data / f"{name}.csv"
            df.to_csv(path, index=False)
            files.append(path)
        if "json" in formats:
            path = data / f"{name}.json"
            df.to_json(path, orient="records")
            files.append(path)
    gt_csv, gt_json = gtd / "ground_truth.csv", gtd / "ground_truth.json"
    gt.to_csv(gt_csv, index=False)
    gt.to_json(gt_json, orient="records", indent=2)
    files += [gt_csv, gt_json]

    total_rows = sum(len(T[name]) for name in TABLES)
    sqlite_check_performed = False
    sqlite_fk_violations = None
    if "sql" in formats:
        sql_path = data / "seed.sql"
        write_sql_seed(T, sql_path)
        files.append(sql_path)
        # A full-profile SQLite staging database is very expensive to materialize
        # solely for export. Full-profile FKs are exhaustively checked by validate().
        # Retain independent SQLite execution/FK checks for starter/test-sized runs.
        if total_rows <= 100_000:
            con = build_sqlite(T)
            fk_rows = con.execute("PRAGMA foreign_key_check").fetchall()
            sqlite_fk_violations = len(fk_rows)
            sqlite_check_performed = True
            con.close()

    return {
        "files": {str(p.relative_to(out)): {"sha256": sha256(p), "bytes": p.stat().st_size}
                  for p in sorted(files)},
        "sqlite_foreign_key_check_performed": sqlite_check_performed,
        "sqlite_foreign_key_check_violations": sqlite_fk_violations,
        "foreign_key_validation_method": "sqlite_and_application" if sqlite_check_performed else "application_validator",
    }


def load_csv(data_dir: Path) -> dict:
    return {n: pd.read_csv(data_dir / f"{n}.csv", dtype=str, keep_default_na=False, na_values=[""]) for n in TABLES}
