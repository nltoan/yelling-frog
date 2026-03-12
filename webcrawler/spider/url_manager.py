"""
URL Manager - Handles URL queue, deduplication, and priority
"""
import asyncio
from typing import Set, Optional, Dict, List
from urllib.parse import urlparse, urljoin
from collections import deque
import re

from ..utils.url_normalizer import normalize_url as util_normalize_url, normalize_domain


class URLManager:
    """Manages URL queue with deduplication and priority"""
    ALLOWED_SCHEMES = {'http', 'https'}
    BLOCKED_EXTENSIONS = {
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.svg', '.ico', '.bmp', '.tif', '.tiff',
        # Video/audio
        '.mp4', '.webm', '.mov', '.avi', '.mkv', '.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a',
        # Docs/archives/executables
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.7z', '.tar', '.gz',
        '.exe', '.dmg', '.pkg', '.apk', '.iso',
        # Fonts / feeds / data
        '.woff', '.woff2', '.ttf', '.otf', '.eot', '.rss', '.xml', '.json', '.txt',
        # Frontend static assets
        '.css', '.js', '.mjs', '.map',
    }
    
    def __init__(
        self,
        base_url: str,
        max_depth: int = 10,
        max_urls: int = 10000,
        crawl_non_html: bool = False
    ):
        self.base_url = base_url
        self.base_domain = self._normalize_domain(urlparse(base_url).netloc)
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.crawl_non_html = crawl_non_html
        
        # URL tracking
        self.seen_urls: Set[str] = set()
        self.queued_urls: Set[str] = set()
        self.crawled_urls: Set[str] = set()
        
        # Priority queue (using deque for simplicity, can upgrade to heapq)
        self.queue: deque = deque()
        
        # URL metadata
        self.url_metadata: Dict[str, Dict] = {}
        
        # Include/exclude patterns
        self.include_patterns: List[re.Pattern] = []
        self.exclude_patterns: List[re.Pattern] = []
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain by removing www. prefix for consistent matching"""
        return normalize_domain(domain)
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments, www prefix, and trailing slashes"""
        return util_normalize_url(url)
    
    def is_internal(self, url: str) -> bool:
        """Check if URL belongs to the base domain (handles www/non-www)"""
        parsed = urlparse(url)
        if parsed.scheme and parsed.scheme not in self.ALLOWED_SCHEMES:
            return False
        url_domain = normalize_domain(parsed.netloc)
        return url_domain == self.base_domain
    
    def should_crawl(self, url: str) -> bool:
        """Determine if URL should be crawled based on patterns"""
        if not self.crawl_non_html and self._has_blocked_extension(url):
            return False

        # Check exclude patterns first
        for pattern in self.exclude_patterns:
            if pattern.search(url):
                return False
        
        # If include patterns exist, URL must match at least one
        if self.include_patterns:
            return any(pattern.search(url) for pattern in self.include_patterns)
        
        return True

    @classmethod
    def _has_blocked_extension(cls, url: str) -> bool:
        """Return True for obvious non-HTML resource URLs."""
        parsed = urlparse(url)
        path = (parsed.path or '').lower()
        for ext in cls.BLOCKED_EXTENSIONS:
            if path.endswith(ext):
                return True
        return False
    
    async def add_url(self, url: str, depth: int = 0, source_url: Optional[str] = None) -> bool:
        """
        Add URL to queue if not seen and meets criteria
        Returns True if added, False otherwise
        """
        async with self._lock:
            parsed_input = urlparse(url)

            # Resolve relative URLs against the crawl start URL
            if not parsed_input.scheme:
                url = urljoin(self.base_url, url)
                parsed_input = urlparse(url)

            # Skip unsupported schemes early (mailto:, javascript:, data:, etc.)
            if parsed_input.scheme.lower() not in self.ALLOWED_SCHEMES:
                return False

            # Normalize URL
            url = self.normalize_url(url)
            
            # Skip if already seen
            if url in self.seen_urls:
                return False
            
            # Skip if not internal
            if not self.is_internal(url):
                return False
            
            # Skip if exceeds depth
            if depth > self.max_depth:
                return False
            
            # Skip if max URLs reached
            if len(self.seen_urls) >= self.max_urls:
                return False
            
            # Check include/exclude patterns
            if not self.should_crawl(url):
                return False
            
            # Add to tracking sets
            self.seen_urls.add(url)
            self.queued_urls.add(url)
            
            # Add to queue
            self.queue.append(url)
            
            # Store metadata
            self.url_metadata[url] = {
                'depth': depth,
                'source_url': source_url,
                'discovered_at': asyncio.get_event_loop().time()
            }
            
            return True
    
    async def get_next_url(self) -> Optional[str]:
        """Get next URL from queue"""
        async with self._lock:
            if not self.queue:
                return None
            
            url = self.queue.popleft()
            self.queued_urls.remove(url)
            self.crawled_urls.add(url)
            
            return url
    
    async def mark_crawled(self, url: str):
        """Mark URL as crawled"""
        async with self._lock:
            self.crawled_urls.add(url)
            if url in self.queued_urls:
                self.queued_urls.remove(url)
    
    def add_include_pattern(self, pattern: str):
        """Add regex pattern for URLs to include"""
        self.include_patterns.append(re.compile(pattern))
    
    def add_exclude_pattern(self, pattern: str):
        """Add regex pattern for URLs to exclude"""
        self.exclude_patterns.append(re.compile(pattern))
    
    def get_stats(self) -> Dict:
        """Get current URL statistics"""
        return {
            'total_seen': len(self.seen_urls),
            'queued': len(self.queued_urls),
            'crawled': len(self.crawled_urls),
            'queue_size': len(self.queue)
        }
    
    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self.queue) == 0
    
    def get_url_metadata(self, url: str) -> Optional[Dict]:
        """Get metadata for a specific URL"""
        return self.url_metadata.get(url)
