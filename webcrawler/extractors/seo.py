"""
SEO Data Extractor
Extracts all SEO-related data: titles, meta descriptions, headings, directives, canonicals, pagination
"""
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import re


class SEOExtractor:
    """Extract comprehensive SEO data from HTML content"""

    # Character width table based on Arial 16px (Google SERP/Screaming Frog standard)
    # Values calibrated against Screaming Frog reference output
    # Reference: "HEP is on the way!" (18 chars) = 164 pixels = ~9.1 px/char avg
    CHAR_WIDTHS = {
        # Narrow characters (4-6px)
        'i': 4, 'j': 6, 'l': 4, '|': 6, '!': 6, '.': 5, ',': 5, ':': 5, ';': 5,
        "'": 4, '`': 6, 'I': 6, '1': 10, 'f': 6, 't': 6, 'r': 7,
        
        # Normal lowercase (10-12px)
        'a': 10, 'b': 11, 'c': 10, 'd': 11, 'e': 10, 'g': 11, 'h': 11, 'k': 10, 'n': 11,
        'o': 11, 'p': 11, 'q': 11, 's': 10, 'u': 11, 'v': 10, 'x': 10, 'y': 10, 'z': 10,
        
        # Wide lowercase (15-17px)
        'm': 16, 'w': 15,
        
        # Uppercase letters (11-15px)
        'A': 13, 'B': 13, 'C': 14, 'D': 14, 'E': 12, 'F': 11, 'G': 15, 'H': 14, 'J': 10,
        'K': 13, 'L': 11, 'N': 14, 'O': 15, 'P': 12, 'Q': 15, 'R': 14, 'S': 12, 'T': 12,
        'U': 14, 'V': 13, 'X': 12, 'Y': 12, 'Z': 12,
        
        # Wide uppercase (16-18px)
        'M': 16, 'W': 18,
        
        # Numbers (10px average)
        '0': 10, '2': 10, '3': 10, '4': 10, '5': 10, '6': 10, '7': 10, '8': 10, '9': 10,
        
        # Special characters
        ' ': 5, '-': 7, '_': 10, '/': 6, '\\': 6, '(': 6, ')': 6, '[': 6, ']': 6,
        '{': 7, '}': 7, '<': 10, '>': 10, '+': 10, '=': 10, '*': 8, '&': 14, '@': 18,
        '#': 10, '$': 10, '%': 17, '^': 9, '~': 10, '?': 10, '"': 8,
        # Extended characters
        '–': 10, '—': 16, ''': 4, ''': 4, '"': 8, '"': 8, '…': 15, '•': 8,
    }
    DEFAULT_CHAR_WIDTH = 10  # fallback for unknown characters

    def __init__(self):
        pass

    def extract(self, html: str, url: str, response_headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Extract all SEO data from HTML

        Returns dict with all SEO columns:
        - Title data (Title 1, Title 1 Length, Title 1 Pixel Width, Title 2, etc.)
        - Meta Description data
        - Meta Keywords
        - Heading data (H1-H6, multiple instances)
        - Meta Robots directives
        - X-Robots-Tag from headers
        - Canonical links
        - Pagination (rel next/prev)
        - Meta Refresh
        - Language
        """
        soup = BeautifulSoup(html, 'lxml')
        response_headers = response_headers or {}

        data = {}

        # Extract title data
        data.update(self._extract_titles(soup))

        # Extract meta description data
        data.update(self._extract_meta_descriptions(soup))

        # Extract meta keywords
        data.update(self._extract_meta_keywords(soup))

        # Extract heading data (H1-H6)
        data.update(self._extract_headings(soup))

        # Extract directives (meta robots, X-Robots-Tag)
        data.update(self._extract_directives(soup, response_headers))

        # Extract canonical links
        data.update(self._extract_canonicals(soup, response_headers))

        # Extract pagination (rel next/prev)
        data.update(self._extract_pagination(soup, response_headers))

        # Extract meta refresh
        data.update(self._extract_meta_refresh(soup))

        # Extract language
        data.update(self._extract_language(soup))

        return data

    def _extract_titles(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract all title tags and calculate lengths"""
        titles = soup.find_all('title')

        result = {
            'title_1': None,
            'title_1_length': 0,
            'title_1_pixel_width': 0,
            'title_2': None,
            'title_2_length': 0,
        }

        if titles:
            # First title
            title_1_text = titles[0].get_text().strip()
            result['title_1'] = title_1_text
            result['title_1_length'] = len(title_1_text)
            result['title_1_pixel_width'] = self._calculate_pixel_width(title_1_text)

            # Second title if exists
            if len(titles) > 1:
                title_2_text = titles[1].get_text().strip()
                result['title_2'] = title_2_text
                result['title_2_length'] = len(title_2_text)

        return result

    def _extract_meta_descriptions(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract meta description tags"""
        descriptions = soup.find_all('meta', attrs={'name': re.compile(r'^description$', re.I)})

        result = {
            'meta_description_1': None,
            'meta_description_1_length': 0,
            'meta_description_1_pixel_width': 0,
            'meta_description_2': None,
        }

        if descriptions:
            # First description
            desc_1 = descriptions[0].get('content', '').strip()
            result['meta_description_1'] = desc_1
            result['meta_description_1_length'] = len(desc_1)
            result['meta_description_1_pixel_width'] = self._calculate_pixel_width(desc_1, is_description=True)

            # Second description if exists
            if len(descriptions) > 1:
                desc_2 = descriptions[1].get('content', '').strip()
                result['meta_description_2'] = desc_2

        return result

    def _extract_meta_keywords(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract meta keywords"""
        keywords = soup.find('meta', attrs={'name': re.compile(r'^keywords$', re.I)})

        result = {
            'meta_keywords_1': None,
            'meta_keywords_1_length': 0,
        }

        if keywords:
            kw_text = keywords.get('content', '').strip()
            result['meta_keywords_1'] = kw_text
            result['meta_keywords_1_length'] = len(kw_text)

        return result

    def _extract_headings(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract all heading tags H1-H6 with multiple instances"""
        result = {}

        # Extract headings for each level (H1-H6)
        for level in range(1, 7):
            tag = f'h{level}'
            headings = soup.find_all(tag)

            # Store up to 2 instances of each heading level
            for idx in range(min(2, len(headings))):
                heading_text = headings[idx].get_text().strip()
                result[f'h{level}_{idx + 1}'] = heading_text
                result[f'h{level}_len_{idx + 1}'] = len(heading_text)

            # Initialize empty if not found
            if len(headings) == 0:
                result[f'h{level}_1'] = None
                result[f'h{level}_len_1'] = 0

        return result

    def _extract_directives(self, soup: BeautifulSoup, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract meta robots and X-Robots-Tag directives

        Possible directives:
        - index, noindex
        - follow, nofollow
        - none (noindex + nofollow)
        - noarchive, nosnippet
        - max-snippet, max-image-preview, max-video-preview
        - noimageindex
        - unavailable_after
        """
        result = {
            'meta_robots_1': None,
            'meta_robots_2': None,
            'x_robots_tag_1': None,
            'x_robots_tag_2': None,
        }

        # Extract meta robots tags
        robots_tags = soup.find_all('meta', attrs={'name': re.compile(r'^robots$', re.I)})
        if robots_tags:
            result['meta_robots_1'] = robots_tags[0].get('content', '').strip()
            if len(robots_tags) > 1:
                result['meta_robots_2'] = robots_tags[1].get('content', '').strip()

        # Extract X-Robots-Tag from HTTP headers
        x_robots_headers = []
        for key, value in headers.items():
            if key.lower() == 'x-robots-tag':
                x_robots_headers.append(value)

        if x_robots_headers:
            result['x_robots_tag_1'] = x_robots_headers[0]
            if len(x_robots_headers) > 1:
                result['x_robots_tag_2'] = x_robots_headers[1]

        return result

    def _extract_canonicals(self, soup: BeautifulSoup, headers: Dict[str, str]) -> Dict[str, Any]:
        """Extract canonical link elements"""
        result = {
            'canonical_link_element_1': None,
            'canonical_link_element_2': None,
        }

        # Extract from HTML link tags
        canonical_links = soup.find_all('link', rel=re.compile(r'canonical', re.I))
        if canonical_links:
            result['canonical_link_element_1'] = canonical_links[0].get('href', '').strip()
            if len(canonical_links) > 1:
                result['canonical_link_element_2'] = canonical_links[1].get('href', '').strip()

        return result

    def _extract_pagination(self, soup: BeautifulSoup, headers: Dict[str, str]) -> Dict[str, Any]:
        """Extract rel=next and rel=prev pagination links"""
        result = {
            'rel_next_1': None,
            'rel_prev_1': None,
            'http_rel_next_1': None,
            'http_rel_prev_1': None,
        }

        # Extract from HTML link tags
        next_link = soup.find('link', rel=re.compile(r'next', re.I))
        if next_link:
            result['rel_next_1'] = next_link.get('href', '').strip()

        prev_link = soup.find('link', rel=re.compile(r'prev', re.I))
        if prev_link:
            result['rel_prev_1'] = prev_link.get('href', '').strip()

        # Extract from HTTP Link headers (if available)
        link_header = headers.get('link', '')
        if link_header:
            # Parse Link header: <url>; rel="next"
            next_match = re.search(r'<([^>]+)>;\s*rel=["\']?next["\']?', link_header, re.I)
            if next_match:
                result['http_rel_next_1'] = next_match.group(1)

            prev_match = re.search(r'<([^>]+)>;\s*rel=["\']?prev["\']?', link_header, re.I)
            if prev_match:
                result['http_rel_prev_1'] = prev_match.group(1)

        return result

    def _extract_meta_refresh(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract meta refresh directives"""
        result = {
            'meta_refresh_1': None,
        }

        meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'^refresh$', re.I)})
        if meta_refresh:
            result['meta_refresh_1'] = meta_refresh.get('content', '').strip()

        return result

    def _extract_language(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract HTML lang attribute"""
        result = {
            'language': None,
        }

        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            result['language'] = html_tag.get('lang').strip()

        return result

    def _calculate_pixel_width(self, text: str, is_description: bool = False) -> int:
        """
        Estimate pixel width for SERP display
        Based on Arial font character widths (matches Screaming Frog)
        
        Args:
            text: The text to measure
            is_description: If True, uses meta description scale (smaller font)
        """
        if not text:
            return 0

        width = 0
        for char in text:
            width += self.CHAR_WIDTHS.get(char, self.DEFAULT_CHAR_WIDTH)

        # Meta descriptions use smaller font (roughly 72% of title size in SERPs)
        if is_description:
            width = int(width * 0.72)
        
        return int(width)

    def analyze_title_issues(self, data: Dict[str, Any]) -> List[str]:
        """Identify title issues for filtering"""
        issues = []

        if not data.get('title_1'):
            issues.append('missing_title')
        elif data.get('title_1_length', 0) > 60:
            issues.append('title_over_60_chars')
        elif data.get('title_1_length', 0) < 30:
            issues.append('title_below_30_chars')

        if data.get('title_1_pixel_width', 0) > 568:
            issues.append('title_over_568_pixels')
        elif data.get('title_1_pixel_width', 0) < 200:
            issues.append('title_below_200_pixels')

        if data.get('title_2'):
            issues.append('multiple_titles')

        return issues

    def analyze_meta_description_issues(self, data: Dict[str, Any]) -> List[str]:
        """Identify meta description issues"""
        issues = []

        if not data.get('meta_description_1'):
            issues.append('missing_meta_description')
        elif data.get('meta_description_1_length', 0) > 155:
            issues.append('meta_description_over_155_chars')
        elif data.get('meta_description_1_length', 0) < 70:
            issues.append('meta_description_below_70_chars')

        if data.get('meta_description_1_pixel_width', 0) > 990:
            issues.append('meta_description_over_990_pixels')
        elif data.get('meta_description_1_pixel_width', 0) < 400:
            issues.append('meta_description_below_400_pixels')

        if data.get('meta_description_2'):
            issues.append('multiple_meta_descriptions')

        return issues

    def analyze_heading_issues(self, data: Dict[str, Any]) -> List[str]:
        """Identify heading issues"""
        issues = []

        if not data.get('h1_1'):
            issues.append('missing_h1')
        elif data.get('h1_len_1', 0) > 70:
            issues.append('h1_over_70_chars')

        if data.get('h1_2'):
            issues.append('multiple_h1')

        if not data.get('h2_1'):
            issues.append('missing_h2')

        # Check for non-sequential headings
        has_h1 = bool(data.get('h1_1'))
        has_h2 = bool(data.get('h2_1'))
        has_h3 = bool(data.get('h3_1'))
        has_h4 = bool(data.get('h4_1'))

        if has_h2 and not has_h1:
            issues.append('non_sequential_headings')
        if has_h3 and not has_h2:
            issues.append('non_sequential_headings')
        if has_h4 and not has_h3:
            issues.append('non_sequential_headings')

        return issues

    def get_indexability_status(self, data: Dict[str, Any]) -> tuple[str, Optional[str]]:
        """
        Determine if page is indexable and why

        Returns: (indexability, reason)
        - indexability: "Indexable" or "Non-Indexable"
        - reason: None if indexable, otherwise the reason (e.g., "noindex", "Redirected")
        """
        # Check status code - redirects are non-indexable
        status_code = data.get('status_code', 200)
        if status_code and 300 <= status_code < 400:
            return ('Non-Indexable', 'Redirected')
        
        # Check for client/server errors
        if status_code and status_code >= 400:
            if status_code < 500:
                return ('Non-Indexable', f'Client Error ({status_code})')
            else:
                return ('Non-Indexable', f'Server Error ({status_code})')
        
        # Check meta robots for noindex
        meta_robots_1 = (data.get('meta_robots_1') or '').lower()
        meta_robots_2 = (data.get('meta_robots_2') or '').lower()

        if 'noindex' in meta_robots_1 or 'noindex' in meta_robots_2:
            return ('Non-Indexable', 'noindex')

        if 'none' in meta_robots_1 or 'none' in meta_robots_2:
            return ('Non-Indexable', 'noindex (none)')

        # Check X-Robots-Tag
        x_robots_1 = (data.get('x_robots_tag_1') or '').lower()
        x_robots_2 = (data.get('x_robots_tag_2') or '').lower()

        if 'noindex' in x_robots_1 or 'noindex' in x_robots_2:
            return ('Non-Indexable', 'noindex (X-Robots-Tag)')

        # Check if canonicalised (canonical points to different URL)
        # This would need the actual URL to compare, so we'll mark it for later
        # canonical_1 = data.get('canonical_link_element_1')
        # if canonical_1 and canonical_1 != current_url:
        #     return ('Non-Indexable', 'canonicalised')

        return ('Indexable', None)
