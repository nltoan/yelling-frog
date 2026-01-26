#!/usr/bin/env python3
"""
Test all extractors with sample HTML
"""
import sys
import os
sys.path.insert(0, '/app')

from webcrawler.extractors.seo import SEOExtractor
from webcrawler.extractors.links import LinkExtractor
from webcrawler.extractors.resources import ResourceExtractor
from webcrawler.extractors.technical import TechnicalExtractor
from webcrawler.extractors.structured_data import StructuredDataExtractor
from webcrawler.extractors.content import ContentAnalyzer
from webcrawler.storage.database import Database
from webcrawler.processing.page_processor import PageProcessor

# Sample HTML for testing
SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="This is a test page for the web crawler with a meta description.">
    <meta name="keywords" content="web crawler, SEO, testing">
    <meta name="robots" content="index, follow">
    <title>Test Page - Web Crawler Testing</title>
    <link rel="canonical" href="https://example.com/test-page">
    <link rel="stylesheet" href="/styles.css">

    <!-- Open Graph -->
    <meta property="og:title" content="Test Page OG Title">
    <meta property="og:description" content="Test OG Description">
    <meta property="og:image" content="https://example.com/image.jpg">
    <meta property="og:type" content="website">

    <!-- Twitter Cards -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Test Twitter Title">

    <!-- Structured Data -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Test Article",
        "author": {
            "@type": "Person",
            "name": "John Doe"
        }
    }
    </script>
</head>
<body>
    <header>
        <h1>Main Heading - Test Page</h1>
        <nav>
            <a href="/about">About</a>
            <a href="/contact">Contact</a>
        </nav>
    </header>

    <main>
        <article>
            <h2>First Subheading</h2>
            <p>This is a test paragraph with enough content to analyze. The web crawler should extract
            all SEO-related data from this page including titles, meta descriptions, headings, and
            structured data. This paragraph contains multiple sentences to test readability scoring.</p>

            <h2>Second Subheading</h2>
            <p>Another paragraph with more content. Search engine optimization is important for website
            visibility. The crawler analyzes word count, text ratio, and content quality metrics.</p>

            <h3>Third Level Heading</h3>
            <p>Additional content to reach a reasonable word count for testing purposes. The content
            analyzer should calculate Flesch reading ease scores and detect potential issues.</p>

            <img src="/images/test1.jpg" alt="Test image 1" width="800" height="600">
            <img src="/images/test2.jpg" alt="Another test image">
            <img src="/images/test3.jpg">

            <a href="https://external-site.com" target="_blank">External Link</a>
            <a href="/internal-page">Internal Link</a>
        </article>
    </main>

    <footer>
        <p>Footer content</p>
    </footer>

    <script src="/app.js"></script>
</body>
</html>
"""


def test_seo_extractor():
    """Test SEO extractor"""
    print("\n=== Testing SEO Extractor ===")
    extractor = SEOExtractor()

    data = extractor.extract(SAMPLE_HTML, "https://example.com/test-page", {})

    print(f"✓ Title: {data.get('title_1')} (Length: {data.get('title_1_length')})")
    print(f"✓ Meta Description: {data.get('meta_description_1')[:50]}... (Length: {data.get('meta_description_1_length')})")
    print(f"✓ H1: {data.get('h1_1')}")
    print(f"✓ H2-1: {data.get('h2_1')}")
    print(f"✓ H2-2: {data.get('h2_2')}")
    print(f"✓ Meta Robots: {data.get('meta_robots_1')}")
    print(f"✓ Canonical: {data.get('canonical_link_element_1')}")
    print(f"✓ Language: {data.get('language')}")

    # Test issue detection
    issues = extractor.analyze_title_issues(data)
    print(f"✓ Title Issues: {issues}")

    indexability, reason = extractor.get_indexability_status(data)
    print(f"✓ Indexability: {indexability} ({reason})")


def test_link_extractor():
    """Test link extractor"""
    print("\n=== Testing Link Extractor ===")
    extractor = LinkExtractor("https://example.com")

    data = extractor.extract(SAMPLE_HTML, "https://example.com/test-page")

    print(f"✓ Internal Links: {data['outlinks']}")
    print(f"✓ Unique Internal Links: {data['unique_outlinks']}")
    print(f"✓ External Links: {data['external_outlinks']}")
    print(f"✓ Unique External Links: {data['unique_external_outlinks']}")
    print(f"✓ Sample Internal Link: {data['internal_links'][0] if data['internal_links'] else 'None'}")
    print(f"✓ Sample External Link: {data['external_links'][0] if data['external_links'] else 'None'}")


def test_resource_extractor():
    """Test resource extractor"""
    print("\n=== Testing Resource Extractor ===")
    extractor = ResourceExtractor()

    images = extractor.extract_images(SAMPLE_HTML, "https://example.com/test-page")

    print(f"✓ Total Images: {len(images)}")
    for idx, img in enumerate(images, 1):
        print(f"  Image {idx}:")
        print(f"    - URL: {img['image_url']}")
        print(f"    - Alt: {img['alt_text']}")
        print(f"    - Missing Alt: {img['missing_alt']}")
        print(f"    - Has Dimensions: {not img['missing_size_attributes']}")


def test_technical_extractor():
    """Test technical extractor"""
    print("\n=== Testing Technical Extractor ===")
    extractor = TechnicalExtractor()

    headers = {
        'content-type': 'text/html; charset=utf-8',
        'content-length': '5000',
        'strict-transport-security': 'max-age=31536000',
    }

    # Performance metrics
    perf = extractor.extract_performance_metrics(0.250, 0.120, 5000, 4800, headers)
    print(f"✓ Response Time: {perf['response_time']}s")
    print(f"✓ TTFB: {perf['ttfb']}s")
    print(f"✓ Size: {perf['size']} bytes")

    # Security headers
    security = extractor.extract_security_headers(headers)
    print(f"✓ HSTS: {security['hsts']}")
    print(f"✓ CSP: {security['csp']}")

    # URL analysis
    url_analysis = extractor.analyze_url_structure("https://example.com/test-page?param=value")
    print(f"✓ URL Length: {url_analysis['url_length']}")
    print(f"✓ Has Parameters: {url_analysis['has_parameters']}")
    print(f"✓ Folder Depth: {url_analysis['folder_depth']}")

    # Content hash
    hash_val = extractor.calculate_content_hash(SAMPLE_HTML)
    print(f"✓ Content Hash: {hash_val[:16]}...")


def test_structured_data_extractor():
    """Test structured data extractor"""
    print("\n=== Testing Structured Data Extractor ===")
    extractor = StructuredDataExtractor()

    data = extractor.extract_all(SAMPLE_HTML)

    print(f"✓ Has Structured Data: {data['has_structured_data']}")
    print(f"✓ JSON-LD Items: {len(data['json_ld'])}")
    print(f"✓ Schema Types: {data['schema_types']}")

    if data['json_ld']:
        print(f"✓ First JSON-LD Type: {data['json_ld'][0].get('@type')}")

    # Open Graph
    og_data = extractor.extract_open_graph(SAMPLE_HTML)
    print(f"✓ OG Title: {og_data.get('og:title')}")
    print(f"✓ OG Description: {og_data.get('og:description')}")

    # Twitter Cards
    twitter_data = extractor.extract_twitter_cards(SAMPLE_HTML)
    print(f"✓ Twitter Card: {twitter_data.get('twitter:card')}")
    print(f"✓ Twitter Title: {twitter_data.get('twitter:title')}")


def test_content_analyzer():
    """Test content analyzer"""
    print("\n=== Testing Content Analyzer ===")
    analyzer = ContentAnalyzer()

    data = analyzer.extract_content_metrics(SAMPLE_HTML, "https://example.com/test-page")

    print(f"✓ Word Count: {data['word_count']}")
    print(f"✓ Text Ratio: {data['text_ratio']}%")
    print(f"✓ Readability: {data['readability']} (Flesch score)")
    print(f"✓ Hash: {data['hash'][:16]}...")

    # Test keyword extraction
    keywords = analyzer.extract_top_keywords(data['text_content'], top_n=5)
    print(f"✓ Top Keywords: {[kw['keyword'] for kw in keywords[:5]]}")


def test_database():
    """Test database operations"""
    print("\n=== Testing Database ===")

    db = Database("test_crawl.db")

    # Create session
    session = db.create_session(
        start_url="https://example.com",
        max_urls=1000,
        respect_robots=True
    )
    print(f"✓ Created Session: {session.session_id}")

    # Get stats (should be empty)
    stats = db.get_stats(session.session_id)
    print(f"✓ Initial Stats: {stats['total_urls']} URLs")

    db.close()
    print(f"✓ Database closed")

    # Clean up
    import os
    if os.path.exists("test_crawl.db"):
        os.remove("test_crawl.db")
        print(f"✓ Test database removed")


def test_page_processor():
    """Test complete page processor"""
    print("\n=== Testing Page Processor (Full Integration) ===")

    db = Database("test_processor.db")

    # Create session
    session = db.create_session(
        start_url="https://example.com",
        max_urls=1000
    )

    # Create processor
    processor = PageProcessor(db, "https://example.com", session.session_id)

    # Process sample page
    url_data = processor.process_page(
        url="https://example.com/test-page",
        html=SAMPLE_HTML,
        status_code=200,
        status_text="OK",
        headers={
            'content-type': 'text/html; charset=utf-8',
            'content-length': str(len(SAMPLE_HTML)),
        },
        response_time=0.250,
        ttfb=0.120,
        crawl_depth=1
    )

    print(f"✓ Processed URL: {url_data.url}")
    print(f"✓ Status Code: {url_data.status_code}")
    print(f"✓ Title: {url_data.title_1}")
    print(f"✓ Word Count: {url_data.word_count}")
    print(f"✓ Issues Found: {len(url_data.issues)}")
    print(f"✓ Issues: {', '.join(url_data.issues[:5])}")

    # Get from database
    retrieved = db.get_url(session.session_id, url_data.url)
    print(f"✓ Retrieved from DB: {retrieved.url}")
    print(f"✓ Title from DB: {retrieved.title_1}")

    db.close()

    # Clean up
    import os
    if os.path.exists("test_processor.db"):
        os.remove("test_processor.db")
        print(f"✓ Test database removed")


def main():
    """Run all tests"""
    print("=" * 60)
    print("TESTING ALL EXTRACTORS")
    print("=" * 60)

    try:
        test_seo_extractor()
        test_link_extractor()
        test_resource_extractor()
        test_technical_extractor()
        test_structured_data_extractor()
        test_content_analyzer()
        test_database()
        test_page_processor()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
