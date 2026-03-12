from webcrawler.processing.page_processor import PageProcessor
from webcrawler.storage.database import Database


HTML_SAMPLE = """
<!doctype html>
<html>
  <head>
    <title>Header Case Regression Test</title>
    <meta name="description" content="Regression test for header case handling.">
  </head>
  <body>
    <h1>Header Case Handling</h1>
    <p>This page validates content extraction when response headers are title-cased.</p>
  </body>
</html>
"""


def test_page_processor_handles_title_cased_headers(tmp_path):
    db = Database(str(tmp_path / "header_case.db"))
    session = db.create_session(start_url="https://example.com", max_urls=10)
    processor = PageProcessor(db, "https://example.com", session.session_id)

    url_data = processor.process_page(
        url="https://example.com/header-case",
        html=HTML_SAMPLE,
        raw_html=HTML_SAMPLE,
        status_code=200,
        status_text="OK",
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(HTML_SAMPLE.encode("utf-8"))),
        },
        response_time=0.2,
        ttfb=0.05,
        crawl_depth=0,
    )

    assert url_data.content_type.lower().startswith("text/html")
    assert url_data.title_1 == "Header Case Regression Test"
    assert url_data.meta_description_1 == "Regression test for header case handling."
    assert url_data.h1_1 == "Header Case Handling"
    assert url_data.word_count > 0

    db.close()
