from datetime import datetime

from webcrawler.storage.database import Database
from webcrawler.storage.models import CrawledURL


def _save_url(db: Database, session_id: str, path: str, **kwargs):
    db.save_url(
        session_id,
        CrawledURL(
            url=f"https://example.com/{path}",
            content_type="text/html; charset=utf-8",
            status_code=kwargs.pop("status_code", 200),
            crawled_at=datetime.now(),
            **kwargs,
        ),
    )


def test_amp_special_filters(tmp_path):
    db = Database(str(tmp_path / "amp_special_filters.db"))
    try:
        session = db.create_session(start_url="https://example.com")
        sid = session.session_id

        _save_url(db, sid, "page", amphtml_link="/amp/page")
        _save_url(db, sid, "amp/page", canonical_link_element_1="/page")

        _save_url(db, sid, "page-bad-amp", amphtml_link="/amp/bad")
        _save_url(db, sid, "amp/bad", status_code=404, canonical_link_element_1="/page-bad-amp")

        _save_url(db, sid, "page-orphan-amp", amphtml_link="/amp/orphan")
        _save_url(db, sid, "amp/orphan", canonical_link_element_1="/other-page")

        assert {u.url for u in db.get_urls_by_filter(sid, "valid_amp")} == {"https://example.com/page"}
        assert {u.url for u in db.get_urls_by_filter(sid, "non_200_amp_url")} == {"https://example.com/page-bad-amp"}
        assert {u.url for u in db.get_urls_by_filter(sid, "missing_non_amp_return")} == {"https://example.com/amp/orphan"}
    finally:
        db.close()


def test_hreflang_special_filters(tmp_path):
    db = Database(str(tmp_path / "hreflang_special_filters.db"))
    try:
        session = db.create_session(start_url="https://example.com")
        sid = session.session_id

        _save_url(
            db,
            sid,
            "h-good",
            hreflang_data=[
                {"hreflang": "en", "language": "en", "url": "https://example.com/h-good"},
                {"hreflang": "x-default", "language": "x", "url": "https://example.com/h-good"},
            ],
        )
        _save_url(
            db,
            sid,
            "h-inconsistent",
            hreflang_data=[
                {"hreflang": "en-us", "language": "fr", "url": "https://example.com/fr-us"},
                {"hreflang": "x-default", "language": "x", "url": "https://example.com/h-inconsistent"},
            ],
        )
        _save_url(
            db,
            sid,
            "h-invalid",
            hreflang_data=[
                {"hreflang": "zz-zz", "language": "zz", "url": "https://example.com/zz"},
                {"hreflang": "x-default", "language": "x", "url": "https://example.com/h-invalid"},
            ],
        )
        _save_url(
            db,
            sid,
            "h-multiple",
            hreflang_data=[
                {"hreflang": "en", "language": "en", "url": "https://example.com/en-a"},
                {"hreflang": "en", "language": "en", "url": "https://example.com/en-b"},
                {"hreflang": "x-default", "language": "x", "url": "https://example.com/h-multiple"},
            ],
        )
        _save_url(
            db,
            sid,
            "h-missing-self",
            hreflang_data=[
                {"hreflang": "en", "language": "en", "url": "https://example.com/en-only"},
                {"hreflang": "x-default", "language": "x", "url": "https://example.com/en-only"},
            ],
        )
        _save_url(
            db,
            sid,
            "h-not-canonical",
            canonical_link_element_1="/h-canonical",
            hreflang_data=[
                {"hreflang": "en", "language": "en", "url": "https://example.com/h-not-canonical"},
                {"hreflang": "x-default", "language": "x", "url": "https://example.com/h-not-canonical"},
            ],
        )
        _save_url(
            db,
            sid,
            "h-no-x-default",
            hreflang_data=[
                {"hreflang": "en", "language": "en", "url": "https://example.com/h-no-x-default"},
                {"hreflang": "fr", "language": "fr", "url": "https://example.com/fr-no-x"},
            ],
        )

        assert "https://example.com/h-inconsistent" in {u.url for u in db.get_urls_by_filter(sid, "inconsistent_language")}
        assert "https://example.com/h-invalid" in {u.url for u in db.get_urls_by_filter(sid, "invalid_hreflang_codes")}
        assert "https://example.com/h-multiple" in {u.url for u in db.get_urls_by_filter(sid, "multiple_hreflang_entries")}
        assert "https://example.com/h-missing-self" in {u.url for u in db.get_urls_by_filter(sid, "missing_self_reference")}
        assert "https://example.com/h-not-canonical" in {u.url for u in db.get_urls_by_filter(sid, "hreflang_not_using_canonical")}
        assert "https://example.com/h-no-x-default" in {u.url for u in db.get_urls_by_filter(sid, "missing_x_default")}
    finally:
        db.close()
