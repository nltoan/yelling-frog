"""
Link Extractor
Extracts and analyzes all internal and external links, anchor text, and link metrics
"""
from typing import Dict, List, Set, Tuple, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re


class LinkExtractor:
    """Extract comprehensive link data from HTML content"""

    def __init__(self, base_url: str):
        """
        Args:
            base_url: The base URL of the site being crawled
        """
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc

    def extract(self, html: str, current_url: str) -> Dict[str, Any]:
        """
        Extract all link data

        Returns dict with:
        - internal_links: List of internal link URLs
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

            # Determine if internal or external
            if parsed_url.netloc == self.base_domain or parsed_url.netloc == '':
                internal_links.append(absolute_url)
                if absolute_url not in anchor_texts:
                    anchor_texts[absolute_url] = []
                anchor_texts[absolute_url].append(anchor_text)
            else:
                external_links.append(absolute_url)
                if absolute_url not in anchor_texts:
                    anchor_texts[absolute_url] = []
                anchor_texts[absolute_url].append(anchor_text)

        # Calculate metrics
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
        """Check if URL is internal to the base domain"""
        parsed = urlparse(url)
        return parsed.netloc == self.base_domain or parsed.netloc == ''

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
        self.url_inlinks = {}  # URL -> list of URLs linking to it
        self.url_data = {}  # URL -> page data

    def add_page(self, url: str, outlinks: List[str]):
        """Add a page and its outlinks"""
        self.url_data[url] = {'outlinks': outlinks}

        # Track inlinks
        for outlink in outlinks:
            if outlink not in self.url_inlinks:
                self.url_inlinks[outlink] = []
            self.url_inlinks[outlink].append(url)

    def calculate_inlinks(self, url: str) -> Dict[str, int]:
        """Calculate inlink metrics for a URL"""
        inlinks = self.url_inlinks.get(url, [])
        unique_inlinks = set(inlinks)

        total_pages = len(self.url_data)
        percentage = (len(unique_inlinks) / total_pages * 100) if total_pages > 0 else 0

        return {
            'inlinks': len(inlinks),
            'unique_inlinks': len(unique_inlinks),
            'percentage_of_total': round(percentage, 2),
        }

    def calculate_link_score(self, iterations: int = 20, damping: float = 0.85) -> Dict[str, float]:
        """
        Calculate PageRank-like link score (0-100)

        Args:
            iterations: Number of PageRank iterations
            damping: Damping factor (default 0.85)

        Returns:
            Dict mapping URL -> link score (0-100)
        """
        if not self.url_data:
            return {}

        # Initialize scores
        num_pages = len(self.url_data)
        scores = {url: 1.0 / num_pages for url in self.url_data}

        # Run PageRank algorithm
        for _ in range(iterations):
            new_scores = {}

            for url in self.url_data:
                # Base score from random surfer
                rank = (1 - damping) / num_pages

                # Add contributions from inlinks
                inlinks = self.url_inlinks.get(url, [])
                for inlink in inlinks:
                    outlinks = self.url_data.get(inlink, {}).get('outlinks', [])
                    if outlinks:
                        rank += damping * (scores.get(inlink, 0) / len(outlinks))

                new_scores[url] = rank

            scores = new_scores

        # Normalize to 0-100 scale
        max_score = max(scores.values()) if scores else 1
        normalized_scores = {url: (score / max_score * 100) for url, score in scores.items()}

        return normalized_scores

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
            if url not in self.url_inlinks or len(self.url_inlinks[url]) == 0:
                orphans.append(url)

        return orphans
