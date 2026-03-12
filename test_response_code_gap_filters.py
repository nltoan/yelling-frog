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


def test_response_and_security_gap_filters(tmp_path):
    db = Database(str(tmp_path / "response_gap_filters.db"))
    try:
        session = db.create_session(start_url="https://example.com")
        sid = session.session_id

        _save_url(db, sid, "robots-blocked", indexability_status="Blocked by robots.txt")
        _save_url(db, sid, "blocked-resource", issues=["blocked_resource"])
        _save_url(db, sid, "js-redirect", redirect_type="JavaScript Redirect")
        _save_url(db, sid, "meta-redirect", redirect_type="Meta Refresh")
        _save_url(db, sid, "chain", issues=["redirect_chain"])
        _save_url(db, sid, "loop", issues=["redirect_loop"])
        _save_url(db, sid, "protocol-relative", html_content='<script src="//cdn.example.com/a.js"></script>')

        assert {u.url for u in db.get_urls_by_filter(sid, "blocked_by_robots_txt")} == {
            "https://example.com/robots-blocked"
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "blocked_resource")} == {
            "https://example.com/blocked-resource"
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "redirection_javascript")} == {
            "https://example.com/js-redirect"
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "redirection_meta_refresh")} == {
            "https://example.com/meta-redirect"
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "redirect_chain")} == {
            "https://example.com/chain"
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "redirect_loop")} == {
            "https://example.com/loop"
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "protocol_relative_links")} == {
            "https://example.com/protocol-relative"
        }
    finally:
        db.close()
