#!/usr/bin/env python3
"""Import a generated SQLite seed and independently check every foreign key.

Usage:
  python scripts/verify_sqlite_seed.py --seed datasets/full/data/seed.sql
  python scripts/verify_sqlite_seed.py --seed datasets/full/data/seed.sql --database /tmp/busroute.sqlite
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from busroute.spec import TABLES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=Path, help="Path to generated data/seed.sql")
    parser.add_argument("--database", default=":memory:", help="SQLite database path (default: in-memory)")
    args = parser.parse_args()
    if not args.seed.is_file():
        parser.error(f"SQL seed file not found: {args.seed}")

    con = sqlite3.connect(args.database)
    try:
        with args.seed.open("r", encoding="utf-8") as source:
            con.executescript(source.read())
        fk_violations = con.execute("PRAGMA foreign_key_check").fetchall()
        row_counts = {name: int(con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]) for name in TABLES}
        report = {
            "seed_file": str(args.seed),
            "seed_bytes": args.seed.stat().st_size,
            "foreign_keys_enabled_after_import": con.execute("PRAGMA foreign_keys").fetchone()[0] == 1,
            "foreign_key_violations": len(fk_violations),
            "row_counts": row_counts,
            "passed": len(fk_violations) == 0,
        }
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
