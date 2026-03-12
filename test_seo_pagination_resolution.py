from webcrawler.extractors.seo import SEOExtractor


def test_seo_extractor_resolves_relative_pagination_and_alternates():
    html = """
    <html>
      <head>
        <link rel="next" href="/page/2" />
        <link rel="prev" href="/page/0" />
        <link rel="amphtml" href="/amp/page/1" />
        <link rel="alternate" media="only screen and (max-width: 640px)" href="/m/page/1" />
      </head>
      <body><h1>Pagination Test</h1></body>
    </html>
    """
    headers = {"Link": "</header-next>; rel=\"next\", </header-prev>; rel=\"prev\""}
    extractor = SEOExtractor()
    data = extractor.extract(html, "https://example.com/page/1", headers)

    assert data["rel_next_1"] == "https://example.com/page/2"
    assert data["rel_prev_1"] == "https://example.com/page/0"
    assert data["http_rel_next_1"] == "https://example.com/header-next"
    assert data["http_rel_prev_1"] == "https://example.com/header-prev"
    assert data["amphtml_link"] == "https://example.com/amp/page/1"
    assert data["mobile_alternate_link"] == "https://example.com/m/page/1"
