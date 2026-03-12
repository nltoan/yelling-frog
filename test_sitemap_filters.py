from datetime import datetime

from webcrawler.storage.database import Database
from webcrawler.storage.models import CrawledURL


def _save_url(
    db: Database,
    session_id: str,
    path: str,
    status_code: int = 200,
    indexability: str = "Indexable",
    inlinks: int = 1,
):
    db.save_url(
        session_id,
        CrawledURL(
            url=f"https://example.com/{path}",
            content_type="text/html; charset=utf-8",
            status_code=status_code,
            indexability=indexability,
            inlinks=inlinks,
            crawled_at=datetime.now(),
        ),
    )


def test_sitemap_special_filters(tmp_path):
    db = Database(str(tmp_path / "sitemap_filters.db"))
    try:
        session = db.create_session(start_url="https://example.com")
        sid = session.session_id

        _save_url(db, sid, "in-ok", status_code=200, indexability="Indexable", inlinks=3)
        _save_url(db, sid, "in-404", status_code=404, indexability="Indexable", inlinks=2)
        _save_url(db, sid, "in-noindex", status_code=200, indexability="Non-Indexable", inlinks=2)
        _save_url(db, sid, "in-orphan", status_code=200, indexability="Indexable", inlinks=0)
        _save_url(db, sid, "not-in", status_code=200, indexability="Indexable", inlinks=1)

        db.save_sitemap_urls(
            sid,
            [
                "https://example.com/in-ok",
                "https://example.com/in-404",
                "https://example.com/in-noindex",
                "https://example.com/in-orphan",
            ],
        )

        assert {u.url for u in db.get_urls_by_filter(sid, "in_sitemap")} == {
            "https://example.com/in-ok",
            "https://example.com/in-404",
            "https://example.com/in-noindex",
            "https://example.com/in-orphan",
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "not_in_sitemap")} == {
            "https://example.com/not-in",
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "orphan_urls")} == {
            "https://example.com/in-orphan",
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "non_200_in_sitemap")} == {
            "https://example.com/in-404",
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "non_indexable_in_sitemap")} == {
            "https://example.com/in-noindex",
        }
    finally:
        db.close()
