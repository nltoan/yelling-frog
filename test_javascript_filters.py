from datetime import datetime

from webcrawler.storage.database import Database
from webcrawler.storage.models import CrawledURL


def _save_url(db: Database, session_id: str, path: str, issues):
    db.save_url(
        session_id,
        CrawledURL(
            url=f"https://example.com/{path}",
            content_type="text/html; charset=utf-8",
            status_code=200,
            issues=issues,
            crawled_at=datetime.now(),
        ),
    )


def test_javascript_issue_filters(tmp_path):
    db = Database(str(tmp_path / "javascript_filters.db"))
    try:
        session = db.create_session(start_url="https://example.com")
        sid = session.session_id

        _save_url(db, sid, "js-links", ["javascript_links"])
        _save_url(db, sid, "js-content", ["javascript_content"])
        _save_url(db, sid, "js-title", ["javascript_only_titles"])
        _save_url(db, sid, "js-desc", ["javascript_only_descriptions"])
        _save_url(db, sid, "js-h1", ["javascript_only_h1"])
        _save_url(db, sid, "js-canonical", ["javascript_only_canonicals"])

        assert {u.url for u in db.get_urls_by_filter(sid, "javascript_links")} == {"https://example.com/js-links"}
        assert {u.url for u in db.get_urls_by_filter(sid, "javascript_content")} == {"https://example.com/js-content"}
        assert {u.url for u in db.get_urls_by_filter(sid, "javascript_only_titles")} == {"https://example.com/js-title"}
        assert {u.url for u in db.get_urls_by_filter(sid, "javascript_only_descriptions")} == {"https://example.com/js-desc"}
        assert {u.url for u in db.get_urls_by_filter(sid, "javascript_only_h1")} == {"https://example.com/js-h1"}
        assert {u.url for u in db.get_urls_by_filter(sid, "javascript_only_canonicals")} == {
            "https://example.com/js-canonical"
        }
    finally:
        db.close()
