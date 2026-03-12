#!/usr/bin/env python3
"""
Validate Screaming Frog spec parity for filters and reports.

This script regenerates parity matrices and exits non-zero if parity is incomplete.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILTER_SCRIPT = ROOT / "scripts" / "generate_filter_parity_matrix.py"
REPORT_SCRIPT = ROOT / "scripts" / "generate_report_parity_matrix.py"
FILTER_JSON = ROOT / "reports" / "filter_parity_matrix.json"
REPORT_JSON = ROOT / "reports" / "report_parity_matrix.json"


def run_script(path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Missing parity file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    run_script(FILTER_SCRIPT)
    run_script(REPORT_SCRIPT)

    filter_payload = load_json(FILTER_JSON)
    report_payload = load_json(REPORT_JSON)

    filter_counts = filter_payload.get("counts", {})
    report_counts = report_payload.get("counts", {})

    filter_spec = int(filter_counts.get("spec_filters", 0))
    filter_implemented = int(filter_counts.get("implemented", 0))
    filter_partial = int(filter_counts.get("partial", 0))
    filter_missing = int(filter_counts.get("missing", 0))

    report_spec = int(report_counts.get("spec_reports", 0))
    report_implemented = int(report_counts.get("implemented", 0))
    report_missing = int(report_counts.get("missing", 0))

    print(
        "Filter parity:",
        f"{filter_implemented}/{filter_spec}",
        f"(partial={filter_partial}, missing={filter_missing})",
    )
    print(
        "Report parity:",
        f"{report_implemented}/{report_spec}",
        f"(missing={report_missing})",
    )

    ok = (
        filter_spec > 0
        and report_spec > 0
        and filter_implemented == filter_spec
        and filter_partial == 0
        and filter_missing == 0
        and report_implemented == report_spec
        and report_missing == 0
    )
    if not ok:
        print("Spec parity validation failed.", file=sys.stderr)
        return 1

    print("Spec parity validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
