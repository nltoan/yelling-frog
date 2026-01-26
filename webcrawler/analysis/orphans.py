"""
Orphan Page Detection
Identifies pages with no internal inlinks (orphan pages)
"""
from typing import List, Dict, Set, Optional


class OrphanDetector:
    """Detects orphan pages (pages with no internal links pointing to them)"""

    def __init__(self):
        """Initialize orphan detector"""
        self.all_urls: Set[str] = set()
        self.urls_with_inlinks: Set[str] = set()
        self.inlink_count: Dict[str, int] = {}

    def add_url(self, url: str):
        """
        Register a URL as existing in the crawl

        Args:
            url: URL that was crawled
        """
        self.all_urls.add(url)
        if url not in self.inlink_count:
            self.inlink_count[url] = 0

    def add_link(self, source_url: str, target_url: str):
        """
        Register an internal link from source to target

        Args:
            source_url: URL containing the link
            target_url: URL being linked to
        """
        self.urls_with_inlinks.add(target_url)

        if target_url not in self.inlink_count:
            self.inlink_count[target_url] = 0
        self.inlink_count[target_url] += 1

    def get_orphan_pages(self, exclude_start_url: bool = True, start_url: Optional[str] = None) -> List[str]:
        """
        Get list of orphan pages

        Args:
            exclude_start_url: If True, don't consider the start URL as orphan
            start_url: The starting URL of the crawl

        Returns:
            List of orphan page URLs
        """
        orphans = self.all_urls - self.urls_with_inlinks

        if exclude_start_url and start_url:
            orphans.discard(start_url)

        return sorted(list(orphans))

    def get_inlink_count(self, url: str) -> int:
        """
        Get number of internal links pointing to a URL

        Args:
            url: URL to check

        Returns:
            Number of internal inlinks
        """
        return self.inlink_count.get(url, 0)

    def get_statistics(self, start_url: Optional[str] = None) -> Dict[str, any]:
        """
        Get orphan detection statistics

        Args:
            start_url: The starting URL of the crawl

        Returns:
            Dictionary with statistics
        """
        orphans = self.get_orphan_pages(exclude_start_url=True, start_url=start_url)

        return {
            'total_pages': len(self.all_urls),
            'pages_with_inlinks': len(self.urls_with_inlinks),
            'orphan_pages': len(orphans),
            'orphan_percentage': (len(orphans) / len(self.all_urls) * 100) if self.all_urls else 0
        }


def detect_orphans_in_database(database, session_id: str) -> Dict[str, any]:
    """
    Detect orphan pages for all URLs in a crawl session

    Args:
        database: Database instance
        session_id: Session ID to analyze

    Returns:
        Dictionary with orphan detection results
    """
    detector = OrphanDetector()

    # Get session to find start URL
    session = database.get_session(session_id)
    start_url = session.start_url if session else None

    # Get all URLs
    urls = database.get_all_urls(session_id)

    # Add all URLs to detector
    for url_data in urls:
        detector.add_url(url_data.url)

    # Get all links and build inlink graph
    links = database.get_links(session_id)

    for link in links:
        if link.is_internal:
            detector.add_link(link.source_url, link.target_url)

    # Get orphan pages
    orphan_pages = detector.get_orphan_pages(exclude_start_url=True, start_url=start_url)

    # Get statistics
    stats = detector.get_statistics(start_url=start_url)

    # Build detailed results
    results = {
        'orphan_pages': orphan_pages,
        'inlink_counts': {url: detector.get_inlink_count(url) for url in detector.all_urls},
        'statistics': stats
    }

    return results
