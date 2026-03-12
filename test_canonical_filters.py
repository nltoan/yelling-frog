from datetime import datetime

from webcrawler.storage.database import Database
from webcrawler.storage.models import CrawledURL


def _seed_session(db: Database) -> str:
    session = db.create_session(start_url="https://example.com")
    session_id = session.session_id

    rows = [
        {"url": "https://example.com/no-canonical", "canonical": None, "status_code": 200, "indexability": "Indexable"},
        {"url": "https://example.com/self", "canonical": "https://example.com/self", "status_code": 200, "indexability": "Indexable"},
        {"url": "https://example.com/a", "canonical": "https://example.com/b", "status_code": 200, "indexability": "Indexable"},
        {"url": "https://example.com/b", "canonical": "https://example.com/c", "status_code": 200, "indexability": "Indexable"},
        {"url": "https://example.com/c", "canonical": "https://example.com/c", "status_code": 200, "indexability": "Indexable"},
        {"url": "https://example.com/d", "canonical": "https://example.com/e", "status_code": 200, "indexability": "Indexable"},
        {"url": "https://example.com/e", "canonical": "https://example.com/d", "status_code": 200, "indexability": "Indexable"},
        # Relative canonical target should resolve to absolute URL.
        {"url": "https://example.com/rel-source", "canonical": "/rel-target", "status_code": 200, "indexability": "Indexable"},
        {"url": "https://example.com/rel-target", "canonical": "https://example.com/rel-target", "status_code": 200, "indexability": "Non-Indexable"},
        {"url": "https://example.com/non200-source", "canonical": "https://example.com/non200-target", "status_code": 200, "indexability": "Indexable"},
        {"url": "https://example.com/non200-target", "canonical": "https://example.com/non200-target", "status_code": 404, "indexability": "Non-Indexable"},
    ]

    for row in rows:
        db.save_url(
            session_id,
            CrawledURL(
                url=row["url"],
                content_type="text/html; charset=utf-8",
                canonical_link_element_1=row["canonical"],
                status_code=row["status_code"],
                indexability=row["indexability"],
                crawled_at=datetime.now(),
            ),
        )

    return session_id


def test_database_canonical_special_filters(tmp_path):
    db_path = tmp_path / "canonical_filters.db"
    db = Database(str(db_path))

    try:
        session_id = _seed_session(db)

        self_refs = {row.url for row in db.get_urls_by_filter(session_id, "self_referencing_canonical", limit=100)}
        canonicalised = {row.url for row in db.get_urls_by_filter(session_id, "canonicalised", limit=100)}
        chains = {row.url for row in db.get_urls_by_filter(session_id, "canonical_chain", limit=100)}
        loops = {row.url for row in db.get_urls_by_filter(session_id, "canonical_loop", limit=100)}
        canonical_to_non_indexable = {row.url for row in db.get_urls_by_filter(session_id, "canonical_to_non_indexable", limit=100)}
        canonical_to_non_200 = {row.url for row in db.get_urls_by_filter(session_id, "canonical_to_non_200", limit=100)}

        assert self_refs == {
            "https://example.com/self",
            "https://example.com/c",
            "https://example.com/rel-target",
            "https://example.com/non200-target",
        }
        assert canonicalised == {
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/d",
            "https://example.com/e",
            "https://example.com/rel-source",
            "https://example.com/non200-source",
        }
        assert chains == {"https://example.com/a"}
        assert loops == {
            "https://example.com/d",
            "https://example.com/e",
        }
        assert canonical_to_non_indexable == {
            "https://example.com/rel-source",
            "https://example.com/non200-source",
        }
        assert canonical_to_non_200 == {
            "https://example.com/non200-source",
        }
    finally:
        db.close()
