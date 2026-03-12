from types import SimpleNamespace

import pytest

from webcrawler.api.main import build_directives_audit_report


class FakeDatabase:
    def __init__(self, rows, has_session=True):
        self._rows = rows
        self._has_session = has_session

    def get_session(self, _session_id):
        return object() if self._has_session else None

    def get_all_urls(self, _session_id):
        return self._rows


def make_row(url, canonical=None, status_code=200, indexability="Indexable"):
    return SimpleNamespace(
        url=url,
        content_type="text/html; charset=utf-8",
        canonical_link_element_1=canonical,
        meta_robots_1=None,
        meta_robots_2=None,
        x_robots_tag_1=None,
        x_robots_tag_2=None,
        meta_refresh_1=None,
        rel_next_1=None,
        rel_prev_1=None,
        http_rel_next_1=None,
        http_rel_prev_1=None,
        amphtml_link=None,
        mobile_alternate_link=None,
        status_code=status_code,
        indexability=indexability,
        indexability_status="Indexable",
    )


def test_directives_audit_detects_canonical_self_chain_and_loops():
    rows = [
        make_row("https://example.com/no-canonical"),
        make_row("https://example.com/self", canonical="https://example.com/self"),
        make_row("https://example.com/a", canonical="https://example.com/b"),
        make_row("https://example.com/b", canonical="https://example.com/c"),
        make_row("https://example.com/c", canonical="https://example.com/c"),
        make_row("https://example.com/d", canonical="https://example.com/e"),
        make_row("https://example.com/e", canonical="https://example.com/d"),
    ]

    report = build_directives_audit_report(FakeDatabase(rows), "session-1")
    summary = report["summary"]

    assert summary["total_html_pages"] == 7
    assert summary["missing_canonical"] == 1
    assert summary["self_referencing_canonical"] == 2
    assert summary["cross_canonical"] == 4
    assert summary["canonical_chains"] == 1
    assert summary["canonical_loops"] == 2

    by_url = {item["url"]: item for item in report["rows"]}
    chain_row = by_url["https://example.com/a"]
    assert chain_row["canonical_chain_hops"] == 2
    assert chain_row["canonical_chain_path"] == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]

    loop_row = by_url["https://example.com/d"]
    assert "Canonical loop" in loop_row["issues"]


def test_directives_audit_requires_existing_session():
    with pytest.raises(ValueError, match="Session not found"):
        build_directives_audit_report(FakeDatabase([], has_session=False), "missing")


def test_directives_audit_detects_non_indexable_and_non_200_canonical_targets():
    rows = [
        make_row("https://example.com/source-relative", canonical="/target-non-indexable"),
        make_row("https://example.com/target-non-indexable", canonical="https://example.com/target-non-indexable", status_code=200, indexability="Non-Indexable"),
        make_row("https://example.com/source-non200", canonical="https://example.com/target-non200"),
        make_row("https://example.com/target-non200", canonical="https://example.com/target-non200", status_code=404, indexability="Non-Indexable"),
    ]

    report = build_directives_audit_report(FakeDatabase(rows), "session-1")
    summary = report["summary"]

    assert summary["canonical_to_non_indexable"] == 2
    assert summary["canonical_to_non_200"] == 1

    by_url = {item["url"]: item for item in report["rows"]}
    relative_row = by_url["https://example.com/source-relative"]
    assert "Canonical trỏ đến URL non-indexable" in relative_row["issues"]
    assert relative_row["canonical_target_indexability"] == "Non-Indexable"

    non200_row = by_url["https://example.com/source-non200"]
    assert "Canonical trỏ đến URL non-indexable" in non200_row["issues"]
    assert "Canonical trỏ đến URL non-200" in non200_row["issues"]
    assert non200_row["canonical_target_status_code"] == 404
