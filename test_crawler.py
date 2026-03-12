"""
Test script for the modular crawler
"""
import asyncio
import pytest
from webcrawler.spider import WebCrawler, CrawlState


@pytest.mark.asyncio
async def test_basic_crawl():
    """Test basic crawling functionality"""
    print("🕷️  Testing WebCrawler modular components...")
    print("="*60)
    
    # Create crawler instance
    crawler = WebCrawler(
        start_url='https://example.com',
        max_depth=2,
        max_urls=10,
        requests_per_second=2.0,
        use_playwright=False,
        respect_robots=True
    )
    
    # Set up callback to show progress
    async def on_page_crawled(url, result):
        status = f"✅ {result.status_code}" if result.status_code else f"❌ ERROR"
        print(f"{status} | {url[:80]}...")
        if result.error:
            print(f"    Error: {result.error}")
    
    crawler.on_page_crawled = on_page_crawled
    
    # Initialize crawler (fetch robots.txt, etc.)
    print("\n📋 Initializing crawler...")
    await crawler.initialize()
    
    print(f"   Robots.txt fetched: {crawler.robots_parser.robots_url}")
    print(f"   Crawl delay: {crawler.robots_parser.get_crawl_delay()}")
    print(f"   Sitemaps found: {len(crawler.robots_parser.get_sitemaps())}")
    
    # Start crawl
    print("\n🚀 Starting crawl...")
    await crawler.crawl()
    
    # Print statistics
    print("\n📊 Crawl Statistics:")
    print("="*60)
    stats = crawler.get_stats()
    print(f"   State: {stats['state']}")
    print(f"   Pages crawled: {stats['pages_crawled']}")
    print(f"   Pages failed: {stats['pages_failed']}")
    print(f"   Total bytes: {stats['total_bytes']:,}")
    print(f"   Duration: {stats.get('duration', 0):.2f}s")
    
    url_stats = stats['url_manager']
    print(f"\n   URLs seen: {url_stats['total_seen']}")
    print(f"   URLs crawled: {url_stats['crawled']}")
    print(f"   URLs queued: {url_stats['queued']}")
    
    rate_stats = stats['rate_limiter']
    print(f"\n   Total requests: {rate_stats['total_requests']}")
    print(f"   Total wait time: {rate_stats['total_wait_time']:.2f}s")
    print(f"   Requests/sec: {rate_stats['requests_per_second']}")
    
    print("\n✅ Test completed!")
    return crawler


if __name__ == "__main__":
    asyncio.run(test_basic_crawl())
