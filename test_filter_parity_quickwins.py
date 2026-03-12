from datetime import datetime

from webcrawler.storage.database import Database
from webcrawler.storage.models import CrawledURL, HreflangData, ImageData


def _url(path: str) -> str:
    return f"https://example.com/{path}"


def _save_url(db: Database, session_id: str, path: str, **kwargs):
    db.save_url(
        session_id,
        CrawledURL(
            url=_url(path),
            content_type="text/html; charset=utf-8",
            status_code=kwargs.pop("status_code", 200),
            crawled_at=datetime.now(),
            **kwargs,
        ),
    )


def test_quickwin_filters_titles_content_security(tmp_path):
    db = Database(str(tmp_path / "quickwin_filters.db"))
    try:
        session = db.create_session(start_url="https://example.com")
        sid = session.session_id

        _save_url(db, sid, "same-title-h1", title_1="Homepage", h1_1="homepage")
        _save_url(db, sid, "meta-wide", meta_description_1_pixel_width=1024)
        _save_url(db, sid, "meta-narrow", meta_description_1_pixel_width=350)
        _save_url(db, sid, "near-dup", no_near_duplicates=2)
        _save_url(db, sid, "exact-1", hash="hash-a")
        _save_url(db, sid, "exact-2", hash="hash-a")
        _save_url(db, sid, "spelling", spelling_errors=3)
        _save_url(db, sid, "grammar", grammar_errors=2)
        _save_url(db, sid, "non-seq", issues=["non_sequential_headings"])
        _save_url(db, sid, "unsafe-links", unsafe_cross_origin_links=2)
        _save_url(
            db,
            sid,
            "secure-ok",
            is_https=True,
            csp=True,
            x_content_type_options=True,
            x_frame_options=True,
            referrer_policy=True,
            referrer_policy_value="strict-origin-when-cross-origin",
        )
        _save_url(db, sid, "missing-sec", is_https=True, csp=False, x_content_type_options=False, x_frame_options=False, referrer_policy=False)
        _save_url(db, sid, "unsafe-referrer", is_https=True, csp=True, referrer_policy=True, referrer_policy_value="unsafe-url")

        assert {u.url for u in db.get_urls_by_filter(sid, "same_as_h1")} == {_url("same-title-h1")}
        assert {u.url for u in db.get_urls_by_filter(sid, "meta_description_over_990_pixels")} == {_url("meta-wide")}
        assert {u.url for u in db.get_urls_by_filter(sid, "meta_description_below_400_pixels")} == {_url("meta-narrow")}
        assert {u.url for u in db.get_urls_by_filter(sid, "near_duplicates")} == {_url("near-dup")}
        assert {u.url for u in db.get_urls_by_filter(sid, "exact_duplicates")} == {_url("exact-1"), _url("exact-2")}
        assert {u.url for u in db.get_urls_by_filter(sid, "duplicate_url")} == {_url("exact-1"), _url("exact-2")}
        assert {u.url for u in db.get_urls_by_filter(sid, "spelling_errors")} == {_url("spelling")}
        assert {u.url for u in db.get_urls_by_filter(sid, "grammar_errors")} == {_url("grammar")}
        assert {u.url for u in db.get_urls_by_filter(sid, "non_sequential_headings")} == {_url("non-seq")}
        assert {u.url for u in db.get_urls_by_filter(sid, "unsafe_cross_origin_links")} == {_url("unsafe-links")}
        assert {u.url for u in db.get_urls_by_filter(sid, "missing_csp")} == {_url("missing-sec")}
        assert {u.url for u in db.get_urls_by_filter(sid, "missing_x_content_type_options")} == {
            _url("same-title-h1"),
            _url("meta-wide"),
            _url("meta-narrow"),
            _url("near-dup"),
            _url("exact-1"),
            _url("exact-2"),
            _url("spelling"),
            _url("grammar"),
            _url("non-seq"),
            _url("unsafe-links"),
            _url("missing-sec"),
            _url("unsafe-referrer"),
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "missing_x_frame_options")} == {
            _url("same-title-h1"),
            _url("meta-wide"),
            _url("meta-narrow"),
            _url("near-dup"),
            _url("exact-1"),
            _url("exact-2"),
            _url("spelling"),
            _url("grammar"),
            _url("non-seq"),
            _url("unsafe-links"),
            _url("missing-sec"),
            _url("unsafe-referrer"),
        }
        assert {u.url for u in db.get_urls_by_filter(sid, "missing_secure_referrer_policy")} == {
            _url("missing-sec"),
            _url("unsafe-referrer"),
        }
    finally:
        db.close()


def test_quickwin_filters_images_and_hreflang(tmp_path):
    db = Database(str(tmp_path / "quickwin_media_hreflang.db"))
    try:
        session = db.create_session(start_url="https://example.com")
        sid = session.session_id

        _save_url(db, sid, "page-with-image")
        _save_url(db, sid, "page-with-hreflang")
        _save_url(db, sid, "fr-page", status_code=404)

        db.save_image(
            sid,
            ImageData(
                url="https://cdn.example.com/img.jpg",
                page_url=_url("page-with-image"),
                image_url="https://cdn.example.com/img.jpg",
                alt_text="a" * 120,
                alt_text_length=120,
                width=0,
                height=0,
                file_size=150_000,
                missing_alt=True,
                missing_alt_attribute=True,
                missing_size_attributes=True,
            ),
        )

        db.save_hreflang(
            sid,
            HreflangData(
                page_url=_url("page-with-hreflang"),
                hreflang="fr-fr",
                language="fr",
                region="fr",
                target_url=_url("fr-page"),
                source="html",
                has_return_link=False,
            ),
        )

        assert {u.url for u in db.get_urls_by_filter(sid, "images_over_100kb")} == {_url("page-with-image")}
        assert {u.url for u in db.get_urls_by_filter(sid, "missing_alt_text")} == {_url("page-with-image")}
        assert {u.url for u in db.get_urls_by_filter(sid, "missing_alt_attribute")} == {_url("page-with-image")}
        assert {u.url for u in db.get_urls_by_filter(sid, "alt_text_over_100_chars")} == {_url("page-with-image")}
        assert {u.url for u in db.get_urls_by_filter(sid, "missing_size_attributes")} == {_url("page-with-image")}

        assert {u.url for u in db.get_urls_by_filter(sid, "contains_hreflang")} == {_url("page-with-hreflang")}
        assert {u.url for u in db.get_urls_by_filter(sid, "missing_return_links")} == {_url("page-with-hreflang")}
        assert {u.url for u in db.get_urls_by_filter(sid, "unlinked_hreflang_url")} == {_url("page-with-hreflang")}
        assert {u.url for u in db.get_urls_by_filter(sid, "non_200_hreflang_url")} == {_url("page-with-hreflang")}
    finally:
        db.close()
