"""
URL Normalizer Utility
Centralized URL normalization for consistent URL matching throughout the crawler
"""
from urllib.parse import urlparse, urldefrag


def normalize_url(url: str) -> str:
    """
    Normalize URL for consistent matching:
    - Remove www. prefix
    - Remove trailing slash (except for root)
    - Lowercase the domain
    - Remove fragments
    - Ensure root URL consistency (empty path becomes /)
    
    This ensures www.example.com/page/ and example.com/page are treated as the same URL.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL string
    """
    if not url:
        return url
    
    # Remove fragment
    url, _ = urldefrag(url)
    
    parsed = urlparse(url)
    
    # Normalize domain (remove www., lowercase)
    domain = parsed.netloc.lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    
    # Normalize path
    path = parsed.path
    
    # Ensure root URL has trailing slash (empty path → /)
    if not path or path == '':
        path = '/'
    # Remove trailing slash from non-root paths
    elif path != '/' and path.endswith('/'):
        path = path.rstrip('/')
    
    # Rebuild URL without fragment
    normalized = f"{parsed.scheme}://{domain}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    
    return normalized


def normalize_domain(domain: str) -> str:
    """
    Normalize domain by removing www. prefix
    
    Args:
        domain: Domain to normalize
        
    Returns:
        Normalized domain string
    """
    if domain.startswith('www.'):
        return domain[4:]
    return domain
