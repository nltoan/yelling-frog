"""
Robots.txt Parser - Handles robots.txt parsing and directive checking
"""
import asyncio
from typing import Optional, List, Dict
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import aiohttp


class RobotsParser:
    """Parses and enforces robots.txt rules"""
    
    def __init__(self, user_agent: str = "WebCrawler/1.0"):
        self.user_agent = user_agent
        self.parser: Optional[RobotFileParser] = None
        self.robots_url: Optional[str] = None
        self.raw_content: Optional[str] = None
        self.respect_robots = True
        self.crawl_delay: Optional[float] = None
        self.sitemaps: List[str] = []
        
    async def fetch_robots(self, base_url: str) -> bool:
        """
        Fetch and parse robots.txt for the given base URL
        Returns True if successful, False otherwise
        """
        parsed = urlparse(base_url)
        self.robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.robots_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        self.raw_content = await response.text()
                        self._parse_robots()
                        return True
                    else:
                        # No robots.txt means allow all
                        self.raw_content = ""
                        return False
        except Exception as e:
            # If we can't fetch robots.txt, allow all by default
            self.raw_content = ""
            return False
    
    def _parse_robots(self):
        """Parse robots.txt content"""
        if not self.raw_content:
            return
        
        # Use standard library parser
        self.parser = RobotFileParser()
        self.parser.parse(self.raw_content.splitlines())
        
        # Extract crawl delay and sitemaps manually
        for line in self.raw_content.splitlines():
            line = line.strip()
            
            # Extract crawl delay
            if line.lower().startswith('crawl-delay:'):
                try:
                    delay = float(line.split(':', 1)[1].strip())
                    self.crawl_delay = delay
                except ValueError:
                    pass
            
            # Extract sitemaps
            if line.lower().startswith('sitemap:'):
                sitemap_url = line.split(':', 1)[1].strip()
                self.sitemaps.append(sitemap_url)
    
    def can_fetch(self, url: str) -> bool:
        """
        Check if URL can be fetched according to robots.txt
        Returns True if allowed or if not respecting robots
        """
        if not self.respect_robots:
            return True
        
        if self.parser is None:
            # No robots.txt means allow all
            return True
        
        return self.parser.can_fetch(self.user_agent, url)
    
    def get_crawl_delay(self) -> Optional[float]:
        """Get crawl delay specified in robots.txt"""
        return self.crawl_delay
    
    def get_sitemaps(self) -> List[str]:
        """Get sitemap URLs from robots.txt"""
        return self.sitemaps
    
    def get_directives(self) -> Dict:
        """Get parsed directives for analysis"""
        if not self.raw_content:
            return {}
        
        directives = {
            'user_agents': [],
            'disallowed': [],
            'allowed': [],
            'crawl_delay': self.crawl_delay,
            'sitemaps': self.sitemaps
        }
        
        current_ua = None
        
        for line in self.raw_content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'user-agent':
                    current_ua = value
                    if value not in directives['user_agents']:
                        directives['user_agents'].append(value)
                elif key == 'disallow' and value:
                    directives['disallowed'].append({
                        'user_agent': current_ua,
                        'path': value
                    })
                elif key == 'allow' and value:
                    directives['allowed'].append({
                        'user_agent': current_ua,
                        'path': value
                    })
        
        return directives
    
    def set_respect_robots(self, respect: bool):
        """Toggle robots.txt compliance"""
        self.respect_robots = respect
