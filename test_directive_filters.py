from datetime import datetime

from webcrawler.storage.database import Database
from webcrawler.storage.models import CrawledURL


def _save_url(
    db: Database,
    session_id: str,
    path: str,
    meta_robots_1=None,
    meta_robots_2=None,
    x_robots_tag_1=None,
    x_robots_tag_2=None,
):
    db.save_url(
        session_id,
        CrawledURL(
            url=f"https://example.com/{path}",
            content_type="text/html; charset=utf-8",
            status_code=200,
            meta_robots_1=meta_robots_1,
            meta_robots_2=meta_robots_2,
            x_robots_tag_1=x_robots_tag_1,
            x_robots_tag_2=x_robots_tag_2,
            crawled_at=datetime.now(),
        ),
    )


def test_database_directive_filters(tmp_path):
    db = Database(str(tmp_path / "directive_filters.db"))
    try:
        session = db.create_session(start_url="https://example.com")
        sid = session.session_id

        _save_url(db, sid, "noindex", meta_robots_1="noindex, follow")
        _save_url(db, sid, "nofollow", meta_robots_1="nofollow")
        _save_url(db, sid, "follow", meta_robots_1="follow")
        _save_url(db, sid, "none", meta_robots_1="none")
        _save_url(db, sid, "noarchive", x_robots_tag_1="noarchive")
        _save_url(db, sid, "nosnippet", meta_robots_1="nosnippet")
        _save_url(db, sid, "noimageindex", x_robots_tag_1="noimageindex")
        _save_url(db, sid, "max-snippet", meta_robots_1="max-snippet:50")
        _save_url(db, sid, "max-image", meta_robots_1="max-image-preview:large")
        _save_url(db, sid, "max-video", meta_robots_1="max-video-preview:30")
        _save_url(db, sid, "unavailable-after", meta_robots_1="unavailable_after: 25 Jun 2010 15:00:00 PST")
        _save_url(db, sid, "not-none", meta_robots_1="max-image-preview:none")

        assert {row.url for row in db.get_urls_by_filter(sid, "noindex", limit=100)} == {"https://example.com/noindex"}
        assert {row.url for row in db.get_urls_by_filter(sid, "nofollow", limit=100)} == {"https://example.com/nofollow"}
        assert {row.url for row in db.get_urls_by_filter(sid, "follow", limit=100)} == {
            "https://example.com/follow",
            "https://example.com/noindex",
        }
        assert {row.url for row in db.get_urls_by_filter(sid, "none", limit=100)} == {"https://example.com/none"}
        assert {row.url for row in db.get_urls_by_filter(sid, "noarchive", limit=100)} == {"https://example.com/noarchive"}
        assert {row.url for row in db.get_urls_by_filter(sid, "nosnippet", limit=100)} == {"https://example.com/nosnippet"}
        assert {row.url for row in db.get_urls_by_filter(sid, "noimageindex", limit=100)} == {"https://example.com/noimageindex"}
        assert {row.url for row in db.get_urls_by_filter(sid, "max_snippet", limit=100)} == {"https://example.com/max-snippet"}
        assert {row.url for row in db.get_urls_by_filter(sid, "max_image_preview", limit=100)} == {
            "https://example.com/max-image",
            "https://example.com/not-none",
        }
        assert {row.url for row in db.get_urls_by_filter(sid, "max_video_preview", limit=100)} == {"https://example.com/max-video"}
        assert {row.url for row in db.get_urls_by_filter(sid, "unavailable_after", limit=100)} == {
            "https://example.com/unavailable-after",
        }
    finally:
        db.close()
