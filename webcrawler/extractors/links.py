"""
Link Extractor
Extracts and analyzes all internal and external links, anchor text, and link metrics
"""
from typing import Dict, List, Set, Tuple, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

from ..utils.url_normalizer import normalize_url as util_normalize_url, normalize_domain


class LinkExtractor:
    """Extract comprehensive link data from HTML content"""

    def __init__(self, base_url: str):
        """
        Args:
            base_url: The base URL of the site being crawled
        """
        self.base_url = base_url
        self.base_domain = normalize_domain(urlparse(base_url).netloc)
    
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain by removing www. prefix for consistent matching"""
        return normalize_domain(domain)

    def extract(self, html: str, current_url: str) -> Dict[str, Any]:
        """
        Extract all link data

        Returns dict with:
        - internal_links: List of internal link URLs (normalized)
        - external_links: List of external link URLs
        - anchor_texts: Dict mapping URLs to anchor texts
        - outlinks: Count of internal outlinks
        - unique_outlinks: Count of unique internal outlinks
        - external_outlinks: Count of external outlinks
        - unique_external_outlinks: Count of unique external outlinks
        """
        soup = BeautifulSoup(html, 'lxml')

        internal_links = []
        external_links = []
        anchor_texts = {}  # URL -> [anchor texts]

        # Find all anchor tags
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:') or href.startswith('tel:'):
                continue

            # Resolve relative URLs
            absolute_url = urljoin(current_url, href)
            parsed_url = urlparse(absolute_url)

            # Get anchor text
            anchor_text = link.get_text().strip()

            # Determine if internal or external (handles www/non-www)
            url_domain = self._normalize_domain(parsed_url.netloc)
            if url_domain == self.base_domain or parsed_url.netloc == '':
                # Normalize internal links for consistent storage and lookup
                normalized_url = util_normalize_url(absolute_url)
                internal_links.append(normalized_url)
                if normalized_url not in anchor_texts:
                    anchor_texts[normalized_url] = []
                anchor_texts[normalized_url].append(anchor_text)
            else:
                external_links.append(absolute_url)
                if absolute_url not in anchor_texts:
                    anchor_texts[absolute_url] = []
                anchor_texts[absolute_url].append(anchor_text)

        # Calculate metrics using normalized URLs
        unique_internal = set(internal_links)
        unique_external = set(external_links)

        result = {
            'internal_links': internal_links,
            'external_links': external_links,
            'anchor_texts': anchor_texts,
            'outlinks': len(internal_links),
            'unique_outlinks': len(unique_internal),
            'external_outlinks': len(external_links),
            'unique_external_outlinks': len(unique_external),
        }

        return result

    def extract_all_href_links(self, html: str, current_url: str) -> List[str]:
        """
        Extract all href links (for crawling purposes)

        Returns list of absolute URLs
        """
        soup = BeautifulSoup(html, 'lxml')
        links = []

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:') or href.startswith('tel:'):
                continue

            # Resolve relative URLs
            absolute_url = urljoin(current_url, href)
            links.append(absolute_url)

        return links

    def is_internal(self, url: str) -> bool:
        """Check if URL is internal to the base domain (handles www/non-www)"""
        parsed = urlparse(url)
        url_domain = normalize_domain(parsed.netloc)
        return url_domain == self.base_domain or parsed.netloc == ''

    def extract_nofollow_links(self, html: str, current_url: str) -> List[str]:
        """Extract links with rel=nofollow"""
        soup = BeautifulSoup(html, 'lxml')
        nofollow_links = []

        for link in soup.find_all('a', href=True):
            rel = link.get('rel', [])
            if 'nofollow' in rel:
                href = link.get('href', '').strip()
                if href and not href.startswith('#'):
                    absolute_url = urljoin(current_url, href)
                    nofollow_links.append(absolute_url)

        return nofollow_links

    def extract_unsafe_cross_origin_links(self, html: str, current_url: str) -> List[str]:
        """
        Extract links with target="_blank" but missing rel="noopener"
        These are security vulnerabilities
        """
        soup = BeautifulSoup(html, 'lxml')
        unsafe_links = []

        for link in soup.find_all('a', href=True, target='_blank'):
            rel = link.get('rel', [])
            if isinstance(rel, str):
                rel = [rel]

            if 'noopener' not in rel and 'noreferrer' not in rel:
                href = link.get('href', '').strip()
                if href:
                    absolute_url = urljoin(current_url, href)
                    unsafe_links.append(absolute_url)

        return unsafe_links

    def extract_protocol_relative_links(self, html: str) -> List[str]:
        """Extract protocol-relative links (//example.com)"""
        soup = BeautifulSoup(html, 'lxml')
        protocol_relative = []

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if href.startswith('//'):
                protocol_relative.append(href)

        return protocol_relative

    def calculate_crawl_depth(self, url: str, start_url: str) -> int:
        """
        Calculate crawl depth (clicks from start page)
        This needs to be calculated during crawling, not from HTML
        """
        # This will be calculated by the crawler
        return 0

    def calculate_folder_depth(self, url: str) -> int:
        """Calculate folder depth from URL path"""
        parsed = urlparse(url)
        path = parsed.path.strip('/')

        if not path:
            return 0

        return len(path.split('/'))

    def extract_image_links(self, html: str, current_url: str) -> List[str]:
        """Extract all image src URLs"""
        soup = BeautifulSoup(html, 'lxml')
        image_links = []

        for img in soup.find_all('img', src=True):
            src = img.get('src', '').strip()
            if src:
                absolute_url = urljoin(current_url, src)
                image_links.append(absolute_url)

        return image_links

    def extract_css_links(self, html: str, current_url: str) -> List[str]:
        """Extract all CSS stylesheet links"""
        soup = BeautifulSoup(html, 'lxml')
        css_links = []

        for link in soup.find_all('link', rel='stylesheet', href=True):
            href = link.get('href', '').strip()
            if href:
                absolute_url = urljoin(current_url, href)
                css_links.append(absolute_url)

        return css_links

    def extract_js_links(self, html: str, current_url: str) -> List[str]:
        """Extract all JavaScript script links"""
        soup = BeautifulSoup(html, 'lxml')
        js_links = []

        for script in soup.find_all('script', src=True):
            src = script.get('src', '').strip()
            if src:
                absolute_url = urljoin(current_url, src)
                js_links.append(absolute_url)

        return js_links


class LinkMetricsCalculator:
    """
    Calculate link metrics across the entire site
    This needs to run after crawling is complete
    """

    def __init__(self):
        self.url_inlinks = {}  # normalized URL -> list of normalized URLs linking to it
        self.url_data = {}  # normalized URL -> page data
        self.original_urls = {}  # normalized URL -> original URL (for lookup)

    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Normalize URL for consistent matching.
        Uses the centralized normalizer from utils.
        """
        return util_normalize_url(url)

    def add_page(self, url: str, outlinks: List[str]):
        """Add a page and its outlinks"""
        norm_url = self.normalize_url(url)
        self.original_urls[norm_url] = url
        
        # Normalize outlinks
        norm_outlinks = [self.normalize_url(link) for link in outlinks]
        self.url_data[norm_url] = {'outlinks': norm_outlinks}

        # Track inlinks using normalized URLs
        for norm_outlink in norm_outlinks:
            if norm_outlink not in self.url_inlinks:
                self.url_inlinks[norm_outlink] = []
            self.url_inlinks[norm_outlink].append(norm_url)

    def calculate_inlinks(self, url: str) -> Dict[str, int]:
        """Calculate inlink metrics for a URL"""
        norm_url = self.normalize_url(url)
        inlinks = self.url_inlinks.get(norm_url, [])
        unique_inlinks = set(inlinks)

        total_pages = len(self.url_data)
        percentage = (len(unique_inlinks) / total_pages * 100) if total_pages > 0 else 0

        return {
            'inlinks': len(inlinks),
            'unique_inlinks': len(unique_inlinks),
            'percentage_of_total': round(percentage, 3),
        }

    def calculate_link_score(self, iterations: int = 20, damping: float = 0.85) -> Dict[str, float]:
        """
        Calculate PageRank-like link score (0-100)

        Args:
            iterations: Number of PageRank iterations
            damping: Damping factor (default 0.85)

        Returns:
            Dict mapping original URL -> link score (0-100)
        """
        if not self.url_data:
            return {}

        # Initialize scores (using normalized URLs internally)
        num_pages = len(self.url_data)
        scores = {url: 1.0 / num_pages for url in self.url_data}

        # Run PageRank algorithm
        for _ in range(iterations):
            new_scores = {}

            for norm_url in self.url_data:
                # Base score from random surfer
                rank = (1 - damping) / num_pages

                # Add contributions from inlinks
                inlinks = self.url_inlinks.get(norm_url, [])
                for inlink in inlinks:
                    outlinks = self.url_data.get(inlink, {}).get('outlinks', [])
                    if outlinks:
                        rank += damping * (scores.get(inlink, 0) / len(outlinks))

                new_scores[norm_url] = rank

            scores = new_scores

        # Normalize to 0-100 scale
        max_score = max(scores.values()) if scores else 1
        
        # Return scores keyed by original URLs
        normalized_scores = {}
        for norm_url, score in scores.items():
            original_url = self.original_urls.get(norm_url, norm_url)
            normalized_scores[original_url] = round(score / max_score * 100, 2)

        return normalized_scores
    
    def get_link_score(self, url: str, scores: Dict[str, float]) -> float:
        """Get link score for a URL, handling normalization"""
        # Try direct lookup first
        if url in scores:
            return scores[url]
        # Try normalized lookup
        norm_url = self.normalize_url(url)
        for orig_url, score in scores.items():
            if self.normalize_url(orig_url) == norm_url:
                return score
        return 0.0

    def find_orphan_pages(self, all_urls: Set[str]) -> List[str]:
        """
        Find orphan pages (pages with no internal links pointing to them)

        Args:
            all_urls: Set of all crawled URLs

        Returns:
            List of orphan page URLs
        """
        orphans = []

        for url in all_urls:
            norm_url = self.normalize_url(url)
            if norm_url not in self.url_inlinks or len(self.url_inlinks[norm_url]) == 0:
                orphans.append(url)

        return orphans
