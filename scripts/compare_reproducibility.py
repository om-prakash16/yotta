#!/usr/bin/env python3
"""Compare two independently generated BusRoute output directories.

Usage:
  python scripts/compare_reproducibility.py --first datasets/full_run1 --second datasets/full_run2
  python scripts/compare_reproducibility.py --first /tmp/run1 --second /tmp/run2 --out docs/reproducibility_full.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def read_manifest(folder: Path) -> dict:
    path = folder / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read valid JSON manifest at {path}: {exc}") from exc
    required = {"seed", "config", "row_counts", "quality_gate", "files"}
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"manifest {path} is missing required keys: {missing}")
    if not isinstance(data["files"], dict) or not data["files"]:
        raise ValueError(f"manifest {path} has an empty/invalid files map")
    return data


def file_hashes(manifest: dict) -> dict[str, str]:
    result = {}
    for name, meta in manifest["files"].items():
        if not isinstance(meta, dict) or not isinstance(meta.get("sha256"), str):
            raise ValueError(f"invalid SHA-256 entry for artefact {name!r}")
        result[name] = meta["sha256"]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", required=True, type=Path, help="First generated output directory")
    parser.add_argument("--second", required=True, type=Path, help="Second generated output directory")
    parser.add_argument("--out", type=Path, help="Optional JSON report destination")
    args = parser.parse_args(argv)

    try:
        first, second = read_manifest(args.first), read_manifest(args.second)
        hashes1, hashes2 = file_hashes(first), file_hashes(second)
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    identity_fields = ("seed", "config", "row_counts")
    matching_config = all(first[k] == second[k] for k in identity_fields)
    same_hashes = hashes1 == hashes2
    quality_ok = bool(first["quality_gate"].get("passed") and second["quality_gate"].get("passed"))
    same_keys = set(hashes1) == set(hashes2)
    passed = matching_config and same_hashes and quality_ok and same_keys

    report = {
        "seed": first["seed"],
        "runs": 2,
        "identical_checksums": bool(same_hashes and same_keys),
        "same_configuration_and_row_counts": bool(matching_config),
        "quality_gate_passed_both_runs": quality_ok,
        "files_compared": len(hashes1) if same_keys else len(set(hashes1) & set(hashes2)),
        "row_counts": first["row_counts"],
        "elapsed_seconds_by_run": [first.get("elapsed_s"), second.get("elapsed_s")],
        "sha256_run1": hashes1,
        "sha256_run2": hashes2,
        "passed": passed,
    }
    rendered = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": passed,
        "identical_checksums": report["identical_checksums"],
        "same_configuration_and_row_counts": report["same_configuration_and_row_counts"],
        "quality_gate_passed_both_runs": quality_ok,
        "files_compared": report["files_compared"],
        "report": str(args.out) if args.out else None,
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
