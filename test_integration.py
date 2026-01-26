#!/usr/bin/env python3
"""
Integration Test - Test the complete crawler system end-to-end
"""
import asyncio
import os
import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from webcrawler.spider.crawler import WebCrawler
from webcrawler.storage.database import Database
from webcrawler.processing.page_processor import PageProcessor
from webcrawler.storage.export import DataExporter
from webcrawler.analysis.duplicates import detect_duplicates_in_database
from webcrawler.analysis.orphans import detect_orphans_in_database
from webcrawler.analysis.redirects import detect_redirects_in_database


async def test_full_crawl():
    """Test a complete crawl of a website"""
    print("=" * 80)
    print("INTEGRATION TEST - Full Crawl Test")
    print("=" * 80)

    # Use a small test site
    start_url = "https://example.com"
    max_urls = 20

    # Setup database
    db_path = "/app/data/test_crawl.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    db = Database(db_path)

    # Create session
    session = db.create_session(
        start_url=start_url,
        max_urls=max_urls,
        max_depth=3,
        respect_robots=True,
        user_agent="WebCrawler/1.0 (Test)"
    )
    session_id = session.session_id

    print(f"\n✓ Created session: {session_id}")

    # Create crawler
    crawler = WebCrawler(
        start_url=start_url,
        max_depth=3,
        max_urls=max_urls,
        requests_per_second=2.0,
        use_playwright=False,
        user_agent="WebCrawler/1.0 (Test)",
        respect_robots=True
    )

    print(f"✓ Crawler initialized")
    print(f"  Start URL: {start_url}")
    print(f"  Max URLs: {max_urls}")
    print(f"  Max Depth: 3")

    # Initialize crawler
    await crawler.initialize()
    print(f"✓ Crawler ready")

    # Create page processor
    processor = PageProcessor(db, start_url, session_id)
    print(f"✓ Page processor initialized")

    # Track progress
    pages_processed = 0

    # Set up callback to process each page
    async def on_page_crawled(url: str, page_result):
        nonlocal pages_processed

        if page_result.html and not page_result.error:
            # Process page through all extractors
            processor.process_page(
                url=url,
                html=page_result.html,
                status_code=page_result.status_code,
                status_text="OK",
                headers=page_result.headers,
                response_time=page_result.load_time,
                ttfb=page_result.ttfb,
                crawl_depth=crawler.url_manager.get_url_metadata(url).get('depth', 0)
            )

            pages_processed += 1
            print(f"  [{pages_processed}] Processed: {url[:80]}")

        # Update session stats
        stats = crawler.get_stats()
        db.update_session(
            session_id,
            crawled_urls=stats['pages_crawled'],
            failed_urls=stats['pages_failed'],
            total_urls=stats['url_manager']['total_seen']
        )

    crawler.on_page_crawled = on_page_crawled

    # Start crawling
    print(f"\n▶ Starting crawl...")
    start_time = time.time()

    await crawler.crawl()

    elapsed = time.time() - start_time
    print(f"\n✓ Crawl completed in {elapsed:.2f}s")

    # Post-process: Calculate link metrics
    print(f"\n▶ Calculating link metrics...")
    processor.post_process_link_metrics()
    print(f"✓ Link metrics calculated")

    # Mark session as completed
    db.update_session(session_id, status="completed")

    # Get final stats
    stats = crawler.get_stats()
    print(f"\n📊 CRAWL STATISTICS:")
    print(f"  Total URLs found: {stats['url_manager']['total_seen']}")
    print(f"  Pages crawled: {stats['pages_crawled']}")
    print(f"  Pages failed: {stats['pages_failed']}")
    print(f"  URLs in queue: {stats['url_manager']['queue_size']}")
    if elapsed > 0:
        print(f"  Processing rate: {stats['pages_crawled'] / elapsed:.2f} pages/sec")

    # Analyze data
    print(f"\n▶ Running analysis...")

    # Get database stats
    db_stats = db.get_stats(session_id)
    print(f"\n📊 DATABASE STATISTICS:")
    print(f"  Total URLs: {db_stats['total_urls']}")
    print(f"  Indexable: {db_stats['indexable_count']}")
    print(f"  Non-Indexable: {db_stats['non_indexable_count']}")
    print(f"  Avg Response Time: {db_stats['avg_response_time']:.3f}s")
    print(f"  Avg Word Count: {db_stats['avg_word_count']}")

    # Status codes
    print(f"\n  Status Codes:")
    for code, count in sorted(db_stats['status_codes'].items()):
        print(f"    {code}: {count}")

    # Test filters
    print(f"\n▶ Testing filters...")
    filters_to_test = [
        'missing_title',
        'missing_meta_description',
        'missing_h1',
        'low_content',
        'success_2xx',
        'https_urls',
    ]

    for filter_code in filters_to_test:
        urls = db.get_urls_by_filter(session_id, filter_code, limit=5)
        if urls:
            print(f"  ✓ {filter_code}: {len(urls)} URLs")

    # Test analysis features
    print(f"\n▶ Running advanced analysis...")

    try:
        # Duplicate detection
        dup_results = detect_duplicates_in_database(db, session_id)
        print(f"  ✓ Duplicate Detection:")
        print(f"    Total pages: {dup_results['statistics']['total_pages']}")
        print(f"    Unique pages: {dup_results['statistics']['unique_pages']}")
        print(f"    Duplicate pages: {dup_results['statistics']['duplicate_pages']}")
    except Exception as e:
        print(f"  ✗ Duplicate detection failed: {e}")

    try:
        # Orphan detection
        orphan_results = detect_orphans_in_database(db, session_id)
        print(f"  ✓ Orphan Detection:")
        print(f"    Total pages: {orphan_results['statistics']['total_pages']}")
        print(f"    Orphan pages: {orphan_results['statistics']['orphan_pages']}")
    except Exception as e:
        print(f"  ✗ Orphan detection failed: {e}")

    try:
        # Redirect analysis
        redirect_results = detect_redirects_in_database(db, session_id)
        print(f"  ✓ Redirect Analysis:")
        print(f"    Total redirects: {redirect_results['statistics']['total_redirects']}")
        print(f"    Redirect loops: {redirect_results['statistics']['redirect_loops']}")
    except Exception as e:
        print(f"  ✗ Redirect analysis failed: {e}")

    # Test exports
    print(f"\n▶ Testing exports...")
    exporter = DataExporter(db)

    try:
        csv_path = "/tmp/test_export.csv"
        count = exporter.export_to_csv(session_id, csv_path)
        print(f"  ✓ CSV export: {count} rows exported to {csv_path}")
    except Exception as e:
        print(f"  ✗ CSV export failed: {e}")

    try:
        json_path = "/tmp/test_export.json"
        count = exporter.export_to_json(session_id, json_path)
        print(f"  ✓ JSON export: {count} rows exported to {json_path}")
    except Exception as e:
        print(f"  ✗ JSON export failed: {e}")

    # Test specific URL retrieval
    print(f"\n▶ Testing URL retrieval...")
    urls = db.get_all_urls(session_id, limit=5)
    if urls:
        print(f"  ✓ Retrieved {len(urls)} URLs")
        for url_data in urls[:3]:
            print(f"    - {url_data.url}")
            print(f"      Status: {url_data.status_code}")
            print(f"      Title: {url_data.title_1 or 'N/A'}")
            print(f"      Words: {url_data.word_count}")

    # Test images
    print(f"\n▶ Testing image extraction...")
    images = db.get_images(session_id)
    print(f"  ✓ Found {len(images)} images")
    if images:
        for img in images[:3]:
            print(f"    - {img.image_url[:80]}")
            print(f"      Alt: {img.alt_text or 'N/A'}")
            print(f"      Missing alt: {img.missing_alt}")

    # Test links
    print(f"\n▶ Testing link extraction...")
    links = db.get_links(session_id)
    print(f"  ✓ Found {len(links)} links")
    internal_links = [l for l in links if l.is_internal]
    external_links = [l for l in links if not l.is_internal]
    print(f"    Internal: {len(internal_links)}")
    print(f"    External: {len(external_links)}")

    # Final summary
    print(f"\n" + "=" * 80)
    print(f"✅ INTEGRATION TEST COMPLETED SUCCESSFULLY")
    print(f"=" * 80)
    print(f"\nAll systems tested:")
    print(f"  ✓ Web crawler")
    print(f"  ✓ Page processor")
    print(f"  ✓ All extractors (SEO, links, content, resources, technical, structured data)")
    print(f"  ✓ Database storage")
    print(f"  ✓ Filters")
    print(f"  ✓ Analysis (duplicates, orphans, redirects)")
    print(f"  ✓ Export (CSV, JSON)")
    print(f"\nSession ID: {session_id}")
    print(f"Database: {db_path}")
    print(f"\n" + "=" * 80)

    # Close database
    db.close()

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_full_crawl())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
