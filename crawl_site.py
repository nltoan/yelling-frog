#!/usr/bin/env python3
"""
Crawl a website and generate SEO report
Based on the working integration test architecture
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/app')

from webcrawler.spider.crawler import WebCrawler
from webcrawler.storage.database import Database
from webcrawler.processing.page_processor import PageProcessor
from webcrawler.storage.export import DataExporter


async def crawl_site(url: str, max_pages: int = 50):
    """Crawl a website and generate report"""
    print(f"\n{'='*70}")
    print(f"🕷️  WEB CRAWLER - Screaming Frog Clone")
    print(f"{'='*70}")
    print(f"URL: {url}")
    print(f"Max Pages: {max_pages}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    # Setup database
    db_path = "/app/data/crawl_results.db"
    db = Database(db_path)
    
    # Create session
    session = db.create_session(
        start_url=url,
        max_urls=max_pages,
        max_depth=5,
        respect_robots=True,
        user_agent="WebCrawler/1.0"
    )
    session_id = session.session_id
    print(f"Session ID: {session_id}")
    
    # Create crawler
    crawler = WebCrawler(
        start_url=url,
        max_depth=5,
        max_urls=max_pages,
        requests_per_second=2.0,
        use_playwright=True,  # Use real browser rendering
        user_agent="WebCrawler/1.0",
        respect_robots=True
    )
    
    # Initialize crawler
    await crawler.initialize()
    print("Crawler initialized with Playwright\n")
    
    # Create page processor (handles all extraction)
    processor = PageProcessor(db, url, session_id)
    
    # Track progress
    pages_processed = [0]
    
    # Set up callback to process each page
    async def on_page_crawled(crawled_url: str, page_result):
        if page_result.html and not page_result.error:
            # Process page through all extractors
            processor.process_page(
                url=crawled_url,
                html=page_result.html,
                status_code=page_result.status_code,
                status_text="OK",
                headers=page_result.headers,
                response_time=page_result.load_time,
                ttfb=page_result.ttfb,
                crawl_depth=crawler.url_manager.get_url_metadata(crawled_url).get('depth', 0)
            )
            pages_processed[0] += 1
            
            print(f"[{pages_processed[0]:3d}/{max_pages}] {page_result.status_code or '???'} | {crawled_url[:60]}...")
        elif page_result.error:
            print(f"[ERR] {crawled_url[:60]} - {page_result.error}")
    
    crawler.on_page_crawled = on_page_crawled
    
    # Run the crawl
    print("Starting crawl...\n")
    await crawler.crawl()
    
    # Get final stats
    stats = crawler.get_stats()
    
    print(f"\n{'='*70}")
    print(f"✅ CRAWL COMPLETE")
    print(f"{'='*70}")
    print(f"Pages Crawled: {stats.get('pages_crawled', 0)}")
    print(f"Pages Failed: {stats.get('pages_failed', 0)}")
    print(f"Duration: {stats.get('end_time', 0) - stats.get('start_time', 0):.1f}s")
    
    # Get all crawled URLs for analysis
    urls = db.get_all_urls(session_id)
    
    if urls:
        # Status code breakdown
        status_counts = {}
        for u in urls:
            status = getattr(u, 'status_code', 0) or 0
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"\nStatus Codes:")
        for status, count in sorted(status_counts.items()):
            emoji = "✓" if status == 200 else "⚠" if status in [301, 302] else "✗"
            print(f"  {emoji} {status}: {count}")
        
        # SEO Issues
        missing_title = sum(1 for u in urls if not getattr(u, 'title_1', None))
        missing_desc = sum(1 for u in urls if not getattr(u, 'meta_description_1', None))
        missing_h1 = sum(1 for u in urls if not getattr(u, 'h1_1', None))
        
        titles = [getattr(u, 'title_1', None) for u in urls if getattr(u, 'title_1', None)]
        dup_titles = len(titles) - len(set(titles))
        
        descs = [getattr(u, 'meta_description_1', None) for u in urls if getattr(u, 'meta_description_1', None)]
        dup_descs = len(descs) - len(set(descs))
        
        print(f"\n📊 SEO Issues:")
        print(f"  Missing Titles: {missing_title}")
        print(f"  Missing Meta Descriptions: {missing_desc}")
        print(f"  Missing H1: {missing_h1}")
        print(f"  Duplicate Titles: {dup_titles}")
        print(f"  Duplicate Descriptions: {dup_descs}")
        
        # Sample data
        print(f"\n📄 Sample Pages:")
        for u in urls[:5]:
            url_str = getattr(u, 'url', 'Unknown')[:60]
            status = getattr(u, 'status_code', '?')
            title = (getattr(u, 'title_1', None) or 'None')[:50]
            h1 = (getattr(u, 'h1_1', None) or 'None')[:50]
            words = getattr(u, 'word_count', 0) or 0
            print(f"\n  [{status}] {url_str}")
            print(f"      Title: {title}")
            print(f"      H1: {h1}")
            print(f"      Words: {words}")
    
    # Export results
    exporter = DataExporter(db)
    csv_path = f"/app/data/crawl_{session_id[:8]}.csv"
    json_path = f"/app/data/crawl_{session_id[:8]}.json"
    
    try:
        exporter.export_csv(session_id, csv_path)
        exporter.export_json(session_id, json_path)
        print(f"\n📁 Exports:")
        print(f"  CSV: {csv_path}")
        print(f"  JSON: {json_path}")
    except Exception as e:
        print(f"\nExport error: {e}")
    
    # Update session
    db.update_session_status(session_id, "completed", len(urls))
    
    print(f"\n{'='*70}")
    print(f"Database: {db_path}")
    print(f"{'='*70}\n")
    
    db.close()
    await crawler.cleanup()
    
    return session_id


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    asyncio.run(crawl_site(url, max_pages))
