#!/usr/bin/env python3
"""
Generate an implementation parity matrix for SCREAMING_FROG_SPEC filters.

The matrix compares filter coverage across:
- DB filter engine (URL_FILTER_QUERIES + SPECIAL_URL_FILTERS)
- API filter listing (/filters endpoint)
- Frontend filter chips (urlTabFilters in frontend/index.html)
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
DB_PATH = ROOT / "webcrawler" / "storage" / "database.py"
API_PATH = ROOT / "webcrawler" / "api" / "main.py"
UI_PATH = ROOT / "frontend" / "index.html"
REPORTS_DIR = ROOT / "reports"
OUTPUT_MD = REPORTS_DIR / "filter_parity_matrix.md"
OUTPUT_JSON = REPORTS_DIR / "filter_parity_matrix.json"


@dataclass
class SpecFilter:
    category: str
    category_slug: str
    label: str
    label_slug: str
    description: str


@dataclass
class FilterParityRow:
    category: str
    spec_filter: str
    expected_code: Optional[str]
    db: bool
    api: bool
    ui: bool
    status: str
    note: str


CATEGORY_FILTER_ALIAS: Dict[str, Dict[str, str]] = {
    "response_codes": {
        "blocked_by_robots_txt": "blocked_by_robots_txt",
        "blocked_resource": "blocked_resource",
        "no_response": "crawl_error",
        "success_2xx": "success_2xx",
        "redirection_3xx": "redirection_3xx",
        "redirection_javascript": "redirection_javascript",
        "redirection_meta_refresh": "redirection_meta_refresh",
        "redirect_chain": "redirect_chain",
        "redirect_loop": "redirect_loop",
        "client_error_4xx": "client_error_4xx",
        "server_error_5xx": "server_error_5xx",
    },
    "page_titles": {
        "missing": "missing_title",
        "duplicate": "duplicate_title",
        "over_60_characters": "title_over_60_chars",
        "below_30_characters": "title_below_30_chars",
        "over_568_pixels": "title_over_568_pixels",
        "below_200_pixels": "title_below_200_pixels",
        "same_as_h1": "same_as_h1",
        "multiple": "multiple_titles",
    },
    "meta_description": {
        "missing": "missing_meta_description",
        "duplicate": "duplicate_meta_description",
        "over_155_characters": "meta_description_over_155_chars",
        "below_70_characters": "meta_description_below_70_chars",
        "over_990_pixels": "meta_description_over_990_pixels",
        "below_400_pixels": "meta_description_below_400_pixels",
        "multiple": "multiple_meta_descriptions",
    },
    "headings": {
        "missing_h1": "missing_h1",
        "duplicate_h1": "duplicate_h1",
        "over_70_characters_h1": "h1_over_70_chars",
        "multiple_h1": "multiple_h1",
        "missing_h2": "missing_h2",
        "non_sequential_headings": "non_sequential_headings",
    },
    "content": {
        "low_content": "low_content",
        "near_duplicates": "near_duplicates",
        "exact_duplicates": "exact_duplicates",
        "spelling_errors": "spelling_errors",
        "grammar_errors": "grammar_errors",
        "low_text_ratio": "low_text_ratio",
    },
    "directives": {
        "index": "indexable",
        "noindex": "noindex",
        "follow": "follow",
        "nofollow": "nofollow",
        "none": "none",
        "noarchive": "noarchive",
        "nosnippet": "nosnippet",
        "max_snippet": "max_snippet",
        "max_image_preview": "max_image_preview",
        "max_video_preview": "max_video_preview",
        "noimageindex": "noimageindex",
        "unavailable_after": "unavailable_after",
    },
    "canonicals": {
        "contains_canonical": "contains_canonical",
        "self_referencing": "self_referencing_canonical",
        "canonicalised": "canonicalised",
        "missing": "missing_canonical",
        "non_indexable_canonical": "canonical_to_non_indexable",
        "canonical_chain": "canonical_chain",
        "canonical_loop": "canonical_loop",
    },
    "pagination": {
        "contains_pagination": "contains_pagination",
        "first_page": "pagination_first_page",
        "paginated_2_page": "pagination_2_plus_page",
        "pagination_url_not_in_anchor": "pagination_url_not_in_anchor",
        "non_200_pagination_url": "non_200_pagination_url",
        "unlinked_pagination_url": "unlinked_pagination_url",
        "non_indexable": "non_indexable_pagination_url",
    },
    "hreflang": {
        "contains_hreflang": "contains_hreflang",
        "non_200_hreflang_url": "non_200_hreflang_url",
        "unlinked_hreflang_url": "unlinked_hreflang_url",
        "missing_return_links": "missing_return_links",
        "inconsistent_language": "inconsistent_language",
        "incorrect_language_region_codes": "invalid_hreflang_codes",
        "multiple_entries": "multiple_hreflang_entries",
        "missing_self_reference": "missing_self_reference",
        "not_using_canonical": "hreflang_not_using_canonical",
        "missing_x_default": "missing_x_default",
    },
    "images": {
        "over_100kb": "images_over_100kb",
        "missing_alt_text": "missing_alt_text",
        "missing_alt_attribute": "missing_alt_attribute",
        "alt_text_over_100_characters": "alt_text_over_100_chars",
        "missing_size_attributes": "missing_size_attributes",
    },
    "security": {
        "http_urls": "http_urls",
        "https_urls": "https_urls",
        "mixed_content": "mixed_content",
        "form_url_insecure": "insecure_forms",
        "form_on_http_url": "form_on_http_url",
        "unsafe_cross_origin_links": "unsafe_cross_origin_links",
        "protocol_relative_links": "protocol_relative_links",
        "missing_hsts_header": "missing_hsts",
        "missing_content_security_policy": "missing_csp",
        "missing_x_content_type_options": "missing_x_content_type_options",
        "missing_x_frame_options": "missing_x_frame_options",
        "missing_secure_referrer_policy": "missing_secure_referrer_policy",
        "bad_content_type": "bad_content_type",
    },
    "url": {
        "non_ascii_characters": "url_with_non_ascii",
        "underscores": "url_with_underscores",
        "uppercase": "url_with_uppercase",
        "parameters": "url_with_parameters",
        "over_115_characters": "url_over_115_chars",
        "duplicate": "duplicate_url",
        "broken_bookmarks": "broken_bookmarks",
    },
    "javascript": {
        "pages_with_javascript_links": "javascript_links",
        "pages_with_javascript_content": "javascript_content",
        "javascript_only_titles": "javascript_only_titles",
        "javascript_only_descriptions": "javascript_only_descriptions",
        "javascript_only_h1": "javascript_only_h1",
        "javascript_only_canonicals": "javascript_only_canonicals",
    },
    "structured_data": {
        "contains_structured_data": "contains_structured_data",
        "json_ld": "json_ld",
        "microdata": "microdata",
        "rdfa": "rdfa",
        "validation_errors": "validation_errors",
        "validation_warnings": "validation_warnings",
        "missing_fields": "schema_missing_fields",
    },
    "amp": {
        "valid_amp": "valid_amp",
        "amp_validation_errors": "amp_validation_errors",
        "amp_validation_warnings": "amp_validation_warnings",
        "non_200_amp_url": "non_200_amp_url",
        "missing_non_amp_return": "missing_non_amp_return",
    },
    "sitemaps": {
        "in_sitemap": "in_sitemap",
        "not_in_sitemap": "not_in_sitemap",
        "orphan_urls": "orphan_urls",
        "non_200_in_sitemap": "non_200_in_sitemap",
        "non_indexable_in_sitemap": "non_indexable_in_sitemap",
    },
}


GLOBAL_LABEL_ALIAS: Dict[str, str] = {
    "multiple": "multiple",
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def parse_spec_filters(text: str) -> List[SpecFilter]:
    rows: List[SpecFilter] = []
    in_filters = False
    current_category: Optional[str] = None
    current_category_slug: Optional[str] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## ") and "FILTERS (Issue Detection)" in line:
            in_filters = True
            continue

        if in_filters and line.startswith("## ") and "FILTERS (Issue Detection)" not in line:
            break

        if not in_filters:
            continue

        category_match = re.match(r"^###\s+(.+?)\s+Tab Filters(?:\s+\(.+?\))?\s*$", line)
        if category_match:
            current_category = category_match.group(1).strip()
            current_category_slug = slugify(current_category)
            continue

        bullet_match = re.match(r"^-\s+\*\*(.+?)\*\*\s*-\s*(.*)$", line)
        if bullet_match and current_category and current_category_slug:
            label = bullet_match.group(1).strip()
            description = bullet_match.group(2).strip()
            rows.append(
                SpecFilter(
                    category=current_category,
                    category_slug=current_category_slug,
                    label=label,
                    label_slug=slugify(label),
                    description=description,
                )
            )

    return rows


def extract_db_filter_codes(db_source: str) -> Set[str]:
    tree = ast.parse(db_source, filename=str(DB_PATH))
    codes: Set[str] = set()

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue

            if target.id == "URL_FILTER_QUERIES" and isinstance(node.value, ast.Dict):
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        codes.add(key.value)

            if target.id == "SPECIAL_URL_FILTERS" and isinstance(node.value, ast.Set):
                for item in node.value.elts:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        codes.add(item.value)

    return codes


def extract_api_filter_codes(api_source: str) -> Set[str]:
    tree = ast.parse(api_source, filename=str(API_PATH))
    lines = api_source.splitlines()

    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_available_filters":
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            chunk = "\n".join(lines[start:end])
            return set(re.findall(r'["\']code["\']\s*:\s*["\']([^"\']+)["\']', chunk))

    return set()


def _slice_brace_block(text: str, start_token: str) -> str:
    start_idx = text.find(start_token)
    if start_idx == -1:
        return ""

    brace_start = text.find("{", start_idx)
    if brace_start == -1:
        return ""

    depth = 0
    for idx in range(brace_start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start:idx + 1]

    return ""


def extract_ui_filter_codes(ui_source: str) -> Set[str]:
    block = _slice_brace_block(ui_source, "urlTabFilters:")
    if not block:
        return set()

    codes = set()
    for single, double in re.findall(r"code:\s*'([^']*)'|code:\s*\"([^\"]*)\"", block):
        code = (single or double).strip()
        if code:
            codes.add(code)
    return codes


def resolve_expected_code(
    spec_row: SpecFilter,
    all_known_codes: Set[str],
) -> Tuple[Optional[str], str]:
    category_map = CATEGORY_FILTER_ALIAS.get(spec_row.category_slug, {})
    if spec_row.label_slug in category_map:
        return category_map[spec_row.label_slug], "Matched by category alias"

    if spec_row.label_slug in all_known_codes:
        return spec_row.label_slug, "Matched by normalized label"

    if spec_row.label_slug in GLOBAL_LABEL_ALIAS:
        return GLOBAL_LABEL_ALIAS[spec_row.label_slug], "Matched by global alias"

    return None, "No mapping rule"


def classify_status(db: bool, api: bool, ui: bool) -> str:
    present = int(db) + int(api) + int(ui)
    if present == 3:
        return "implemented"
    if present > 0:
        return "partial"
    return "missing"


def render_markdown(
    rows: List[FilterParityRow],
    db_codes: Set[str],
    api_codes: Set[str],
    ui_codes: Set[str],
) -> str:
    total = len(rows)
    implemented = sum(1 for row in rows if row.status == "implemented")
    partial = sum(1 for row in rows if row.status == "partial")
    missing = sum(1 for row in rows if row.status == "missing")
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    lines: List[str] = []
    lines.append("# Filter Parity Matrix")
    lines.append("")
    lines.append(f"- Generated at (UTC): `{generated_at}`")
    lines.append(f"- Spec source: `{SPEC_PATH.name}`")
    lines.append(f"- DB filter codes found: `{len(db_codes)}`")
    lines.append(f"- API filter codes found: `{len(api_codes)}`")
    lines.append(f"- Frontend filter codes found: `{len(ui_codes)}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---:|")
    lines.append(f"| Total spec filters | {total} |")
    lines.append(f"| Implemented (DB+API+UI) | {implemented} |")
    lines.append(f"| Partial (at least one layer) | {partial} |")
    lines.append(f"| Missing (no layer) | {missing} |")
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    lines.append("| Category | Spec Filter | Expected Code | DB | API | UI | Status | Note |")
    lines.append("|---|---|---|:---:|:---:|:---:|---|---|")

    for row in rows:
        expected_code = row.expected_code or "-"
        lines.append(
            f"| {row.category} | {row.spec_filter} | `{expected_code}` | "
            f"{'Y' if row.db else 'N'} | {'Y' if row.api else 'N'} | {'Y' if row.ui else 'N'} | "
            f"{row.status} | {row.note} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    spec_source = SPEC_PATH.read_text(encoding="utf-8")
    db_source = DB_PATH.read_text(encoding="utf-8")
    api_source = API_PATH.read_text(encoding="utf-8")
    ui_source = UI_PATH.read_text(encoding="utf-8")

    spec_rows = parse_spec_filters(spec_source)
    db_codes = extract_db_filter_codes(db_source)
    api_codes = extract_api_filter_codes(api_source)
    ui_codes = extract_ui_filter_codes(ui_source)
    known_codes = db_codes | api_codes | ui_codes

    parity_rows: List[FilterParityRow] = []
    for spec_row in spec_rows:
        expected_code, mapping_note = resolve_expected_code(spec_row, known_codes)
        if expected_code:
            in_db = expected_code in db_codes
            in_api = expected_code in api_codes
            in_ui = expected_code in ui_codes
        else:
            in_db = False
            in_api = False
            in_ui = False

        status = classify_status(in_db, in_api, in_ui)
        parity_rows.append(
            FilterParityRow(
                category=spec_row.category,
                spec_filter=spec_row.label,
                expected_code=expected_code,
                db=in_db,
                api=in_api,
                ui=in_ui,
                status=status,
                note=mapping_note,
            )
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    markdown = render_markdown(parity_rows, db_codes, api_codes, ui_codes)
    OUTPUT_MD.write_text(markdown, encoding="utf-8")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sources": {
            "spec": str(SPEC_PATH),
            "database": str(DB_PATH),
            "api": str(API_PATH),
            "frontend": str(UI_PATH),
        },
        "counts": {
            "spec_filters": len(parity_rows),
            "implemented": sum(1 for row in parity_rows if row.status == "implemented"),
            "partial": sum(1 for row in parity_rows if row.status == "partial"),
            "missing": sum(1 for row in parity_rows if row.status == "missing"),
            "db_codes": len(db_codes),
            "api_codes": len(api_codes),
            "ui_codes": len(ui_codes),
        },
        "filters": [asdict(row) for row in parity_rows],
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Generated {OUTPUT_MD.relative_to(ROOT)}")
    print(f"Generated {OUTPUT_JSON.relative_to(ROOT)}")
    print(f"Spec filters: {payload['counts']['spec_filters']}")
    print(f"Implemented: {payload['counts']['implemented']}")
    print(f"Partial: {payload['counts']['partial']}")
    print(f"Missing: {payload['counts']['missing']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
