from webcrawler.extractors.seo import SEOExtractor


def test_seo_extractor_resolves_relative_canonical_to_absolute_url():
    html = """
    <html>
      <head>
        <link rel="canonical" href="/canonical-target" />
      </head>
      <body><h1>Test</h1></body>
    </html>
    """
    extractor = SEOExtractor()
    data = extractor.extract(html, "https://example.com/path/page")

    assert data["canonical_link_element_1"] == "https://example.com/canonical-target"
