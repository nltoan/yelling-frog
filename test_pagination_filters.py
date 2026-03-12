from datetime import datetime

from webcrawler.storage.database import Database
from webcrawler.storage.models import CrawledURL


def _save_page(
    db: Database,
    session_id: str,
    url: str,
    status_code: int = 200,
    indexability: str = "Indexable",
    rel_next_1=None,
    rel_prev_1=None,
    http_rel_next_1=None,
    http_rel_prev_1=None,
    inlinks: int = 0,
    html_content: str = "",
):
    db.save_url(
        session_id,
        CrawledURL(
            url=url,
            content_type="text/html; charset=utf-8",
            status_code=status_code,
            indexability=indexability,
            rel_next_1=rel_next_1,
            rel_prev_1=rel_prev_1,
            http_rel_next_1=http_rel_next_1,
            http_rel_prev_1=http_rel_prev_1,
            inlinks=inlinks,
            html_content=html_content,
            crawled_at=datetime.now(),
        ),
    )


def test_pagination_filters(tmp_path):
    db = Database(str(tmp_path / "pagination_filters.db"))
    try:
        session = db.create_session(start_url="https://example.com/page1")
        sid = session.session_id

        _save_page(
            db,
            sid,
            "https://example.com/page1",
            rel_next_1="/page2",
            inlinks=1,
            html_content='<a href="/page2">Next</a>',
        )
        _save_page(
            db,
            sid,
            "https://example.com/page2",
            rel_next_1="/page3",
            rel_prev_1="/page1",
            inlinks=3,
            html_content='<a href="/page1">Prev</a>',
        )
        _save_page(
            db,
            sid,
            "https://example.com/page3",
            status_code=404,
            indexability="Non-Indexable",
            rel_prev_1="/page2",
            inlinks=2,
            html_content='<a href="/page2">Prev</a>',
        )
        _save_page(
            db,
            sid,
            "https://example.com/page4",
            http_rel_next_1="/page5",
            inlinks=1,
            html_content='<a href="/other">Other</a>',
        )
        _save_page(db, sid, "https://example.com/page5", inlinks=0)

        assert {row.url for row in db.get_urls_by_filter(sid, "contains_pagination", limit=100)} == {
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
            "https://example.com/page4",
        }
        assert {row.url for row in db.get_urls_by_filter(sid, "pagination_first_page", limit=100)} == {
            "https://example.com/page1",
            "https://example.com/page4",
        }
        assert {row.url for row in db.get_urls_by_filter(sid, "pagination_2_plus_page", limit=100)} == {
            "https://example.com/page2",
            "https://example.com/page3",
        }
        assert {row.url for row in db.get_urls_by_filter(sid, "non_200_pagination_url", limit=100)} == {
            "https://example.com/page2",
        }
        assert {row.url for row in db.get_urls_by_filter(sid, "non_indexable_pagination_url", limit=100)} == {
            "https://example.com/page2",
        }
        assert {row.url for row in db.get_urls_by_filter(sid, "pagination_url_not_in_anchor", limit=100)} == {
            "https://example.com/page2",
            "https://example.com/page4",
        }
        assert {row.url for row in db.get_urls_by_filter(sid, "unlinked_pagination_url", limit=100)} == {
            "https://example.com/page4",
        }
    finally:
        db.close()
