#!/usr/bin/env python3
"""
Generate parity matrix for "REPORTS TO GENERATE" in SCREAMING_FROG_SPEC.md.
Compares spec report list vs API REPORT_DEFINITIONS.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "SCREAMING_FROG_SPEC.md"
API_PATH = ROOT / "webcrawler" / "api" / "main.py"
REPORTS_DIR = ROOT / "reports"
OUTPUT_MD = REPORTS_DIR / "report_parity_matrix.md"
OUTPUT_JSON = REPORTS_DIR / "report_parity_matrix.json"


@dataclass
class SpecReport:
    order: int
    title: str
    title_slug: str
    description: str


@dataclass
class ReportParityRow:
    spec_report: str
    expected_code: Optional[str]
    api: bool
    status: str
    note: str


TITLE_ALIAS: Dict[str, str] = {
    "crawl_overview": "crawl_overview",
    "internal_all": "internal_all",
    "external_all": "external_all",
    "response_codes": "response_codes",
    "redirect_chains": "redirect_chains",
    "redirect_loops": "redirect_loops",
    "canonicals": "canonicals",
    "pagination": "pagination",
    "hreflang": "hreflang",
    "duplicate_content": "duplicate_content",
    "insecure_content": "insecure_content",
    "structured_data": "structured_data",
    "sitemaps": "sitemaps",
    "orphan_pages": "orphan_pages",
    "link_score": "link_score",
    "issues_report": "issues_report",
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def parse_spec_reports(text: str) -> List[SpecReport]:
    rows: List[SpecReport] = []
    in_section = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## ") and "REPORTS TO GENERATE" in line:
            in_section = True
            continue

        if in_section and line.startswith("## ") and "REPORTS TO GENERATE" not in line:
            break

        if not in_section:
            continue

        match = re.match(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*-\s*(.*)$", line)
        if not match:
            continue

        order = int(match.group(1))
        title = match.group(2).strip()
        description = match.group(3).strip()
        rows.append(
            SpecReport(
                order=order,
                title=title,
                title_slug=slugify(title),
                description=description,
            )
        )

    return rows


def extract_api_report_codes(api_source: str) -> Set[str]:
    tree = ast.parse(api_source, filename=str(API_PATH))
    codes: Set[str] = set()

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "REPORT_DEFINITIONS" for target in node.targets):
            continue
        if not isinstance(node.value, ast.List):
            continue
        for element in node.value.elts:
            if not isinstance(element, ast.Dict):
                continue
            item = {}
            for key_node, value_node in zip(element.keys, element.values):
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    key = key_node.value
                    if isinstance(value_node, ast.Constant):
                        item[key] = value_node.value
            code = item.get("code")
            if isinstance(code, str):
                codes.add(code)

    return codes


def resolve_expected_code(spec_row: SpecReport, api_codes: Set[str]) -> Tuple[Optional[str], str]:
    if spec_row.title_slug in TITLE_ALIAS:
        return TITLE_ALIAS[spec_row.title_slug], "Matched by report alias"
    if spec_row.title_slug in api_codes:
        return spec_row.title_slug, "Matched by normalized title"
    return None, "No mapping rule"


def main() -> int:
    spec_source = SPEC_PATH.read_text(encoding="utf-8")
    api_source = API_PATH.read_text(encoding="utf-8")

    spec_rows = parse_spec_reports(spec_source)
    api_codes = extract_api_report_codes(api_source)

    rows: List[ReportParityRow] = []
    for spec_row in spec_rows:
        expected_code, note = resolve_expected_code(spec_row, api_codes)
        in_api = bool(expected_code and expected_code in api_codes)
        rows.append(
            ReportParityRow(
                spec_report=spec_row.title,
                expected_code=expected_code,
                api=in_api,
                status="implemented" if in_api else "missing",
                note=note,
            )
        )

    implemented = sum(1 for row in rows if row.status == "implemented")
    missing = sum(1 for row in rows if row.status == "missing")
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    md_lines = [
        "# Report Parity Matrix",
        "",
        f"- Generated at (UTC): `{generated_at}`",
        f"- Spec reports: `{len(rows)}`",
        f"- API report definitions: `{len(api_codes)}`",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Spec reports | {len(rows)} |",
        f"| Implemented | {implemented} |",
        f"| Missing | {missing} |",
        "",
        "## Matrix",
        "",
        "| Spec Report | Expected Code | API | Status | Note |",
        "|---|---|:---:|---|---|",
    ]
    for row in rows:
        md_lines.append(
            f"| {row.spec_report} | `{row.expected_code or '-'}` | {'Y' if row.api else 'N'} | {row.status} | {row.note} |"
        )
    OUTPUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    payload = {
        "generated_at_utc": generated_at,
        "sources": {
            "spec": str(SPEC_PATH),
            "api": str(API_PATH),
        },
        "counts": {
            "spec_reports": len(rows),
            "implemented": implemented,
            "missing": missing,
            "api_report_codes": len(api_codes),
        },
        "reports": [asdict(row) for row in rows],
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Generated {OUTPUT_MD.relative_to(ROOT)}")
    print(f"Generated {OUTPUT_JSON.relative_to(ROOT)}")
    print(f"Spec reports: {len(rows)}")
    print(f"Implemented: {implemented}")
    print(f"Missing: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
