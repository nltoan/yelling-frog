from webcrawler.processing.page_processor import PageProcessor
from webcrawler.storage.database import Database


def test_process_page_marks_javascript_only_issues(tmp_path):
    db = Database(str(tmp_path / "js_pipeline.db"))
    try:
        session = db.create_session(start_url="https://example.com")
        processor = PageProcessor(db, "https://example.com", session.session_id)

        raw_html = """
        <html><head></head><body><p>stub</p></body></html>
        """
        rendered_html = """
        <html>
          <head>
            <title>Rendered Title</title>
            <meta name="description" content="Rendered description only from JS">
            <link rel="canonical" href="/page">
          </head>
          <body>
            <h1>Rendered H1</h1>
            <a href="/page-2">Next page</a>
            <p>
              This rendered block contains enough words to exceed the javascript content threshold.
              It should be significantly longer than the raw HTML snapshot body text.
              extra words one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen
              sixteen seventeen eighteen nineteen twenty twentyone twentytwo twentythree twentyfour twentyfive
              twentysix twentyseven twentyeight twentynine thirty thirtyone thirtytwo thirtythree thirtyfour
              thirtyfive thirtysix thirtyseven thirtyeight thirtynine forty fortyone fortytwo fortythree fortyfour.
            </p>
          </body>
        </html>
        """

        row = processor.process_page(
            url="https://example.com/page",
            html=rendered_html,
            raw_html=raw_html,
            status_code=200,
            status_text="OK",
            headers={"content-type": "text/html; charset=utf-8"},
            response_time=0.1,
            ttfb=0.05,
            crawl_depth=0,
        )

        assert "javascript_only_titles" in row.issues
        assert "javascript_only_descriptions" in row.issues
        assert "javascript_only_h1" in row.issues
        assert "javascript_only_canonicals" in row.issues
        assert "javascript_links" in row.issues
        assert "javascript_content" in row.issues
    finally:
        db.close()
