"""
Main Crawler - Core crawling engine that orchestrates all components
"""
import asyncio
import time
from typing import Optional, Dict, List, Set, Callable
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page

from .url_manager import URLManager
from .robots_parser import RobotsParser
from .sitemap_parser import SitemapParser
from .rate_limiter import RateLimiter


class CrawlState:
    """Represents the current state of a crawl"""
    IDLE = 'idle'
    RUNNING = 'running'
    PAUSED = 'paused'
    STOPPED = 'stopped'
    COMPLETED = 'completed'
    ERROR = 'error'


class PageResult:
    """Represents the result of crawling a single page"""
    
    def __init__(self, url: str):
        self.url = url
        self.status_code: Optional[int] = None
        self.content: Optional[str] = None
        self.html: Optional[str] = None
        self.headers: Dict = {}
        self.redirects: List[str] = []
        self.error: Optional[str] = None
        self.load_time: float = 0.0
        self.ttfb: float = 0.0  # Time to first byte
        self.timestamp: float = time.time()
        
        # Extracted data (will be populated by extractors)
        self.links: List[str] = []
        self.images: List[Dict] = []
        self.scripts: List[str] = []
        self.stylesheets: List[str] = []
        

class WebCrawler:
    """Main web crawler with Playwright support"""
    
    def __init__(
        self,
        start_url: str,
        max_depth: int = 10,
        max_urls: int = 10000,
        requests_per_second: float = 1.0,
        use_playwright: bool = False,
        user_agent: str = "WebCrawler/1.0",
        respect_robots: bool = True
    ):
        self.start_url = start_url
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.use_playwright = use_playwright
        self.user_agent = user_agent
        
        # Initialize components
        self.url_manager = URLManager(start_url, max_depth, max_urls)
        self.robots_parser = RobotsParser(user_agent)
        self.robots_parser.set_respect_robots(respect_robots)
        self.sitemap_parser = SitemapParser()
        self.rate_limiter = RateLimiter(requests_per_second)
        
        # Crawl state
        self.state = CrawlState.IDLE
        self.results: Dict[str, PageResult] = {}
        self.redirect_chains: Dict[str, List[str]] = {}
        
        # Playwright resources
        self.browser: Optional[Browser] = None
        self.playwright_context = None
        
        # Statistics
        self.stats = {
            'start_time': None,
            'end_time': None,
            'pages_crawled': 0,
            'pages_failed': 0,
            'total_bytes': 0
        }
        
        # Callbacks
        self.on_page_crawled: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
    async def initialize(self):
        """Initialize crawler (fetch robots.txt, setup Playwright if needed)"""
        # Fetch and parse robots.txt
        await self.robots_parser.fetch_robots(self.start_url)
        
        # Set crawl delay from robots.txt
        crawl_delay = self.robots_parser.get_crawl_delay()
        if crawl_delay:
            self.rate_limiter.set_crawl_delay(crawl_delay)
        
        # Parse sitemaps if found
        sitemap_urls = self.robots_parser.get_sitemaps()
        if sitemap_urls:
            await self.sitemap_parser.parse_all_sitemaps(sitemap_urls)
        
        # Initialize Playwright if needed
        if self.use_playwright:
            await self._init_playwright()
    
    async def _init_playwright(self):
        """Initialize Playwright browser"""
        self.playwright_context = await async_playwright().start()
        self.browser = await self.playwright_context.chromium.launch(headless=True)
    
    async def _close_playwright(self):
        """Close Playwright resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright_context:
            await self.playwright_context.stop()
    
    async def crawl(self):
        """Start the crawl process"""
        try:
            self.state = CrawlState.RUNNING
            self.stats['start_time'] = time.time()
            
            # Add start URL to queue
            await self.url_manager.add_url(self.start_url, depth=0)
            
            # Process queue
            while not self.url_manager.is_empty() and self.state == CrawlState.RUNNING:
                url = await self.url_manager.get_next_url()
                if url:
                    await self._crawl_url(url)
            
            # Mark as completed if not stopped
            if self.state == CrawlState.RUNNING:
                self.state = CrawlState.COMPLETED
            
            self.stats['end_time'] = time.time()
            
        except Exception as e:
            self.state = CrawlState.ERROR
            if self.on_error:
                await self.on_error(str(e))
            raise
        finally:
            await self.cleanup()
    
    async def _crawl_url(self, url: str):
        """Crawl a single URL"""
        # Check robots.txt
        if not self.robots_parser.can_fetch(url):
            return
        
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        # Crawl using appropriate method
        if self.use_playwright:
            result = await self._crawl_with_playwright(url)
        else:
            result = await self._crawl_with_aiohttp(url)
        
        # Store result
        self.results[url] = result
        
        # Update stats
        if result.error:
            self.stats['pages_failed'] += 1
        else:
            self.stats['pages_crawled'] += 1
            if result.html:
                self.stats['total_bytes'] += len(result.html)
        
        # Extract and queue links
        if result.html and not result.error:
            await self._extract_and_queue_links(url, result.html)
        
        # Call callback if set
        if self.on_page_crawled:
            await self.on_page_crawled(url, result)
    
    async def _crawl_with_aiohttp(self, url: str) -> PageResult:
        """Crawl URL using aiohttp"""
        result = PageResult(url)
        start_time = time.time()
        
        # Use browser-like headers to avoid bot detection
        headers = {
            'User-Agent': self.user_agent if 'Mozilla' in self.user_agent else 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    # Record TTFB
                    result.ttfb = time.time() - start_time
                    
                    result.status_code = response.status
                    result.headers = dict(response.headers)
                    
                    # Track redirects
                    if response.history:
                        result.redirects = [str(r.url) for r in response.history]
                        self.redirect_chains[url] = result.redirects
                    
                    # Get content
                    result.html = await response.text()
                    result.load_time = time.time() - start_time
                    
        except Exception as e:
            result.error = str(e)
            result.load_time = time.time() - start_time
        
        return result
    
    async def _crawl_with_playwright(self, url: str) -> PageResult:
        """Crawl URL using Playwright for JavaScript rendering"""
        result = PageResult(url)
        start_time = time.time()
        
        try:
            page = await self.browser.new_page()
            
            # Navigate to page
            response = await page.goto(url, wait_until='networkidle', timeout=30000)
            
            result.ttfb = time.time() - start_time
            result.status_code = response.status if response else None
            result.headers = dict(response.headers) if response else {}
            
            # Get rendered HTML
            result.html = await page.content()
            result.load_time = time.time() - start_time
            
            await page.close()
            
        except Exception as e:
            result.error = str(e)
            result.load_time = time.time() - start_time
        
        return result
    
    async def _extract_and_queue_links(self, source_url: str, html: str):
        """Extract links from HTML and add to queue"""
        soup = BeautifulSoup(html, 'lxml')
        
        # Get current URL depth
        current_depth = self.url_manager.get_url_metadata(source_url).get('depth', 0)
        
        # Extract all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(source_url, href)
            
            # Add to queue (URL manager will handle filtering)
            await self.url_manager.add_url(
                absolute_url,
                depth=current_depth + 1,
                source_url=source_url
            )
    
    async def pause(self):
        """Pause the crawl"""
        if self.state == CrawlState.RUNNING:
            self.state = CrawlState.PAUSED
    
    async def resume(self):
        """Resume a paused crawl"""
        if self.state == CrawlState.PAUSED:
            self.state = CrawlState.RUNNING
            await self.crawl()
    
    async def stop(self):
        """Stop the crawl"""
        self.state = CrawlState.STOPPED
        await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        if self.use_playwright:
            await self._close_playwright()
    
    def get_stats(self) -> Dict:
        """Get crawl statistics"""
        stats = self.stats.copy()
        stats['url_manager'] = self.url_manager.get_stats()
        stats['rate_limiter'] = self.rate_limiter.get_stats()
        stats['state'] = self.state
        
        if stats['start_time'] and stats['end_time']:
            stats['duration'] = stats['end_time'] - stats['start_time']
        elif stats['start_time']:
            stats['duration'] = time.time() - stats['start_time']
        
        return stats
    
    def get_results(self) -> Dict[str, PageResult]:
        """Get all crawl results"""
        return self.results
