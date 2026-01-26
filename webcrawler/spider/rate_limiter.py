"""
Rate Limiter - Controls crawl speed to be polite to servers
"""
import asyncio
import time
from typing import Optional


class RateLimiter:
    """Controls request rate to avoid overwhelming servers"""
    
    def __init__(self, requests_per_second: float = 1.0, respect_crawl_delay: bool = True):
        """
        Initialize rate limiter
        
        Args:
            requests_per_second: Number of requests allowed per second
            respect_crawl_delay: Whether to respect Crawl-delay from robots.txt
        """
        self.requests_per_second = requests_per_second
        self.min_delay = 1.0 / requests_per_second if requests_per_second > 0 else 0
        self.respect_crawl_delay = respect_crawl_delay
        
        self.last_request_time = 0.0
        self.crawl_delay: Optional[float] = None
        self._lock = asyncio.Lock()
        
        # Statistics
        self.total_requests = 0
        self.total_wait_time = 0.0
    
    def set_crawl_delay(self, delay: Optional[float]):
        """Set crawl delay from robots.txt"""
        self.crawl_delay = delay
    
    def get_effective_delay(self) -> float:
        """Get the effective delay to use"""
        delays = [self.min_delay]
        
        if self.respect_crawl_delay and self.crawl_delay is not None:
            delays.append(self.crawl_delay)
        
        return max(delays)
    
    async def acquire(self):
        """
        Wait until next request is allowed
        Call this before making each request
        """
        async with self._lock:
            current_time = time.time()
            effective_delay = self.get_effective_delay()
            
            # Calculate time since last request
            time_since_last = current_time - self.last_request_time
            
            # Calculate how long we need to wait
            wait_time = effective_delay - time_since_last
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                self.total_wait_time += wait_time
            
            # Update last request time
            self.last_request_time = time.time()
            self.total_requests += 1
    
    def set_rate(self, requests_per_second: float):
        """Update requests per second"""
        self.requests_per_second = requests_per_second
        self.min_delay = 1.0 / requests_per_second if requests_per_second > 0 else 0
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            'total_requests': self.total_requests,
            'total_wait_time': self.total_wait_time,
            'requests_per_second': self.requests_per_second,
            'effective_delay': self.get_effective_delay(),
            'crawl_delay': self.crawl_delay,
            'avg_wait_per_request': self.total_wait_time / self.total_requests if self.total_requests > 0 else 0
        }
    
    def reset_stats(self):
        """Reset statistics counters"""
        self.total_requests = 0
        self.total_wait_time = 0.0
