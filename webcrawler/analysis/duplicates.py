"""
Duplicate Content Detection
Identifies exact and near-duplicate pages using content hashing and similarity analysis
"""
import hashlib
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher


class DuplicateDetector:
    """Detects exact and near-duplicate content"""

    def __init__(self, similarity_threshold: float = 0.90):
        """
        Initialize duplicate detector

        Args:
            similarity_threshold: Minimum similarity ratio (0-1) to consider pages near-duplicates
        """
        self.similarity_threshold = similarity_threshold
        self.content_hashes: Dict[str, List[str]] = {}  # hash -> list of URLs
        self.content_cache: Dict[str, str] = {}  # url -> normalized content

    def normalize_content(self, html_content: str) -> str:
        """
        Normalize HTML content for comparison

        Removes dynamic elements like timestamps, session IDs, etc.

        Args:
            html_content: Raw HTML content

        Returns:
            Normalized content string
        """
        # Remove common dynamic elements
        import re

        content = html_content.lower()

        # Remove comments
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

        # Remove script and style tags
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)

        # Remove common dynamic attributes
        content = re.sub(r'data-timestamp="[^"]*"', '', content)
        content = re.sub(r'data-session="[^"]*"', '', content)
        content = re.sub(r'csrf[-_]token["\']?\s*[:=]\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)

        # Normalize whitespace
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()

        return content

    def calculate_hash(self, content: str) -> str:
        """
        Calculate MD5 hash of content

        Args:
            content: Content to hash

        Returns:
            MD5 hash string
        """
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def add_page(self, url: str, html_content: str) -> Tuple[str, bool]:
        """
        Add a page for duplicate detection

        Args:
            url: Page URL
            html_content: Page HTML content

        Returns:
            Tuple of (content_hash, is_exact_duplicate)
        """
        # Normalize and hash content
        normalized = self.normalize_content(html_content)
        content_hash = self.calculate_hash(normalized)

        # Store normalized content for similarity comparison
        self.content_cache[url] = normalized

        # Check if exact duplicate
        is_duplicate = content_hash in self.content_hashes

        # Add to hash map
        if content_hash not in self.content_hashes:
            self.content_hashes[content_hash] = []
        self.content_hashes[content_hash].append(url)

        return content_hash, is_duplicate

    def get_exact_duplicates(self, url: str, content_hash: str) -> List[str]:
        """
        Get all URLs that are exact duplicates of the given URL

        Args:
            url: URL to check
            content_hash: Content hash of the URL

        Returns:
            List of duplicate URLs (excluding the given URL)
        """
        if content_hash not in self.content_hashes:
            return []

        duplicates = [u for u in self.content_hashes[content_hash] if u != url]
        return duplicates

    def calculate_similarity(self, content1: str, content2: str) -> float:
        """
        Calculate similarity ratio between two content strings

        Args:
            content1: First content string
            content2: Second content string

        Returns:
            Similarity ratio (0-1)
        """
        return SequenceMatcher(None, content1, content2).ratio()

    def find_near_duplicates(self, url: str, max_comparisons: int = 100) -> List[Tuple[str, float]]:
        """
        Find near-duplicate pages for a given URL

        Args:
            url: URL to check for near-duplicates
            max_comparisons: Maximum number of pages to compare (for performance)

        Returns:
            List of (url, similarity_ratio) tuples for near-duplicates
        """
        if url not in self.content_cache:
            return []

        target_content = self.content_cache[url]
        near_duplicates = []

        # Compare with other pages (limit comparisons for performance)
        comparison_count = 0
        for other_url, other_content in self.content_cache.items():
            if other_url == url:
                continue

            if comparison_count >= max_comparisons:
                break

            # Quick length check to skip very different pages
            len_ratio = min(len(target_content), len(other_content)) / max(len(target_content), len(other_content))
            if len_ratio < 0.5:
                continue

            similarity = self.calculate_similarity(target_content, other_content)

            if similarity >= self.similarity_threshold:
                near_duplicates.append((other_url, similarity))
                comparison_count += 1

        # Sort by similarity (highest first)
        near_duplicates.sort(key=lambda x: x[1], reverse=True)

        return near_duplicates

    def get_duplicate_groups(self) -> List[List[str]]:
        """
        Get all groups of exact duplicate URLs

        Returns:
            List of URL groups, where each group contains exact duplicates
        """
        groups = []
        for urls in self.content_hashes.values():
            if len(urls) > 1:
                groups.append(urls)

        return groups

    def get_statistics(self) -> Dict[str, any]:
        """
        Get duplicate detection statistics

        Returns:
            Dictionary with statistics
        """
        total_pages = len(self.content_cache)
        unique_hashes = len(self.content_hashes)
        duplicate_groups = self.get_duplicate_groups()

        duplicate_pages = sum(len(group) - 1 for group in duplicate_groups)

        return {
            'total_pages': total_pages,
            'unique_pages': unique_hashes,
            'duplicate_pages': duplicate_pages,
            'duplicate_groups': len(duplicate_groups),
            'largest_duplicate_group': max((len(g) for g in duplicate_groups), default=0)
        }


def detect_duplicates_in_database(database, session_id: str) -> Dict[str, any]:
    """
    Detect duplicates for all URLs in a crawl session

    Args:
        database: Database instance
        session_id: Session ID to analyze

    Returns:
        Dictionary with duplicate detection results
    """
    detector = DuplicateDetector()

    # Get all URLs from database
    urls = database.get_all_urls(session_id)

    # Process each URL
    duplicate_info = {}
    for url_data in urls:
        if not url_data.html_content:
            continue

        content_hash, is_duplicate = detector.add_page(url_data.url, url_data.html_content)

        duplicate_info[url_data.url] = {
            'hash': content_hash,
            'is_exact_duplicate': is_duplicate,
            'exact_duplicates': [],
            'near_duplicates': []
        }

    # Find exact duplicates
    for url, info in duplicate_info.items():
        if info['is_exact_duplicate']:
            info['exact_duplicates'] = detector.get_exact_duplicates(url, info['hash'])

    # Find near duplicates (only for pages without exact duplicates to save time)
    for url, info in duplicate_info.items():
        if not info['exact_duplicates']:
            near_dups = detector.find_near_duplicates(url, max_comparisons=50)
            info['near_duplicates'] = [{'url': u, 'similarity': s} for u, s in near_dups]

    stats = detector.get_statistics()

    return {
        'duplicate_info': duplicate_info,
        'statistics': stats
    }
