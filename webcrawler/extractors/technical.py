"""
Technical Extractor
Extracts performance metrics, HTTP headers, security headers, and technical SEO data
"""
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import hashlib
import re


class TechnicalExtractor:
    """Extract technical SEO and performance data"""

    def __init__(self):
        pass

    def extract_performance_metrics(
        self,
        response_time: float,
        ttfb: float,
        size_bytes: int,
        transferred_bytes: int,
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Extract performance metrics

        Args:
            response_time: Total response time in seconds
            ttfb: Time to first byte in seconds
            size_bytes: Content size from Content-Length header
            transferred_bytes: Actual bytes transferred (may be compressed)
            headers: Response headers

        Returns:
            Dict with performance data
        """
        result = {
            'response_time': round(response_time, 3),
            'ttfb': round(ttfb, 3),
            'size': size_bytes,
            'transferred': transferred_bytes,
            'last_modified': headers.get('last-modified'),
            'content_encoding': headers.get('content-encoding'),
        }

        return result

    def extract_status_info(
        self,
        status_code: int,
        status_text: str,
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Extract HTTP status information

        Returns:
            - status_code: HTTP status code
            - status: Status text
            - http_version: HTTP/1.1 or HTTP/2
            - content_type: MIME type
        """
        result = {
            'status_code': status_code,
            'status': status_text,
            'http_version': headers.get('version', 'HTTP/1.1'),
            # Include full content-type with charset (like Screaming Frog does)
            'content_type': headers.get('content-type', '').strip(),
        }

        return result

    def extract_redirect_info(
        self,
        status_code: int,
        headers: Dict[str, str],
        html: str = None
    ) -> Dict[str, Any]:
        """
        Extract redirect information

        Returns:
            - redirect_uri: Target URL if redirecting
            - redirect_type: HTTP Redirect, Meta Refresh, JavaScript Redirect, HSTS Policy
        """
        result = {
            'redirect_uri': None,
            'redirect_type': None,
        }

        # HTTP redirects (3xx)
        if 300 <= status_code < 400:
            location = headers.get('location', headers.get('Location'))
            if location:
                result['redirect_uri'] = location
                result['redirect_type'] = 'HTTP Redirect'

        # HSTS header (forces HTTPS)
        if headers.get('strict-transport-security'):
            result['redirect_type'] = 'HSTS Policy'

        # Meta refresh redirect
        if html:
            soup = BeautifulSoup(html, 'lxml')
            meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'^refresh$', re.I)})
            if meta_refresh:
                content = meta_refresh.get('content', '')
                # Parse: 0;url=http://example.com
                match = re.search(r'url=(.+)', content, re.I)
                if match:
                    result['redirect_uri'] = match.group(1).strip()
                    result['redirect_type'] = 'Meta Refresh'

            # JavaScript redirect detection (simple patterns)
            scripts = soup.find_all('script')
            for script in scripts:
                script_text = script.get_text()
                if 'window.location' in script_text or 'location.href' in script_text or 'location.replace' in script_text:
                    result['redirect_type'] = 'JavaScript Redirect'
                    break

        return result

    def extract_security_headers(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract security headers

        Returns dict with:
        - hsts: Strict-Transport-Security present
        - hsts_value: HSTS header value
        - csp: Content-Security-Policy present
        - csp_value: CSP header value
        - x_content_type_options: X-Content-Type-Options present
        - x_frame_options: X-Frame-Options present
        - x_frame_options_value: Value (DENY, SAMEORIGIN)
        - referrer_policy: Referrer-Policy present
        - referrer_policy_value: Policy value
        """
        # Normalize header keys to lowercase
        headers_lower = {k.lower(): v for k, v in headers.items()}

        result = {
            'hsts': 'strict-transport-security' in headers_lower,
            'hsts_value': headers_lower.get('strict-transport-security'),
            'csp': 'content-security-policy' in headers_lower,
            'csp_value': headers_lower.get('content-security-policy'),
            'x_content_type_options': 'x-content-type-options' in headers_lower,
            'x_content_type_options_value': headers_lower.get('x-content-type-options'),
            'x_frame_options': 'x-frame-options' in headers_lower,
            'x_frame_options_value': headers_lower.get('x-frame-options'),
            'referrer_policy': 'referrer-policy' in headers_lower,
            'referrer_policy_value': headers_lower.get('referrer-policy'),
            'x_xss_protection': 'x-xss-protection' in headers_lower,
            'x_xss_protection_value': headers_lower.get('x-xss-protection'),
        }

        return result

    def detect_mixed_content(self, html: str, current_url: str) -> Dict[str, Any]:
        """
        Detect mixed content (HTTPS page loading HTTP resources)

        Returns:
            - is_https: Whether current page is HTTPS
            - mixed_content_images: List of HTTP image URLs on HTTPS page
            - mixed_content_scripts: List of HTTP script URLs
            - mixed_content_css: List of HTTP CSS URLs
            - has_mixed_content: Boolean
        """
        parsed_url = urlparse(current_url)
        is_https = parsed_url.scheme == 'https'

        mixed_content_images = []
        mixed_content_scripts = []
        mixed_content_css = []

        if is_https:
            soup = BeautifulSoup(html, 'lxml')

            # Check images
            for img in soup.find_all('img', src=True):
                src = img.get('src', '')
                if src.startswith('http://'):
                    mixed_content_images.append(src)

            # Check scripts
            for script in soup.find_all('script', src=True):
                src = script.get('src', '')
                if src.startswith('http://'):
                    mixed_content_scripts.append(src)

            # Check CSS
            for link in soup.find_all('link', rel='stylesheet', href=True):
                href = link.get('href', '')
                if href.startswith('http://'):
                    mixed_content_css.append(href)

        has_mixed_content = bool(mixed_content_images or mixed_content_scripts or mixed_content_css)

        return {
            'is_https': is_https,
            'mixed_content_images': mixed_content_images,
            'mixed_content_scripts': mixed_content_scripts,
            'mixed_content_css': mixed_content_css,
            'has_mixed_content': has_mixed_content,
        }

    def detect_insecure_forms(self, html: str, current_url: str) -> Dict[str, Any]:
        """
        Detect insecure forms

        Returns:
            - forms_on_http: Forms on HTTP page
            - forms_with_http_action: Forms with HTTP action URL
        """
        parsed_url = urlparse(current_url)
        is_http = parsed_url.scheme == 'http'

        soup = BeautifulSoup(html, 'lxml')
        forms = soup.find_all('form')

        forms_on_http = []
        forms_with_http_action = []

        for form in forms:
            action = form.get('action', '')

            if is_http:
                forms_on_http.append({
                    'action': action,
                    'method': form.get('method', 'get'),
                })

            if action.startswith('http://'):
                forms_with_http_action.append({
                    'action': action,
                    'method': form.get('method', 'get'),
                })

        return {
            'forms_on_http': forms_on_http,
            'forms_with_http_action': forms_with_http_action,
            'has_insecure_forms': bool(forms_on_http or forms_with_http_action),
        }

    def calculate_content_hash(self, html: str) -> str:
        """
        Calculate MD5 hash of page content for duplicate detection

        Returns:
            MD5 hash hex string
        """
        # Remove dynamic content that might change
        soup = BeautifulSoup(html, 'lxml')

        # Remove script and style tags
        for tag in soup.find_all(['script', 'style']):
            tag.decompose()

        # Get text content
        text_content = soup.get_text()

        # Normalize whitespace
        text_content = re.sub(r'\s+', ' ', text_content).strip()

        # Calculate hash
        hash_obj = hashlib.md5(text_content.encode('utf-8'))
        return hash_obj.hexdigest()

    def analyze_url_structure(self, url: str) -> Dict[str, Any]:
        """
        Analyze URL structure

        Returns:
            - url_length: Character count
            - has_parameters: Query parameters present
            - parameter_count: Number of parameters
            - has_non_ascii: Non-ASCII characters present
            - has_underscores: Underscores in path
            - has_uppercase: Uppercase letters
            - folder_depth: Number of folders in path
        """
        parsed = urlparse(url)

        path = parsed.path
        query = parsed.query

        # Parse parameters
        parameters = {}
        if query:
            for param in query.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    parameters[key] = value

        # Check for non-ASCII characters
        try:
            url.encode('ascii')
            has_non_ascii = False
        except UnicodeEncodeError:
            has_non_ascii = True

        # Check for underscores
        has_underscores = '_' in path

        # Check for uppercase
        has_uppercase = path != path.lower()

        # Calculate folder depth
        folder_depth = len([p for p in path.strip('/').split('/') if p])

        return {
            'url_length': len(url),
            'has_parameters': bool(query),
            'parameter_count': len(parameters),
            'has_non_ascii': has_non_ascii,
            'has_underscores': has_underscores,
            'has_uppercase': has_uppercase,
            'folder_depth': folder_depth,
            'scheme': parsed.scheme,
        }

    def detect_broken_anchors(self, html: str, current_url: str) -> List[str]:
        """
        Detect broken bookmark links (anchor links that don't exist on page)

        Returns:
            List of anchor IDs that don't exist
        """
        soup = BeautifulSoup(html, 'lxml')

        # Find all elements with IDs
        existing_ids = set()
        for element in soup.find_all(id=True):
            existing_ids.add(element.get('id'))

        # Find all elements with name attribute (old-style anchors)
        for element in soup.find_all(attrs={'name': True}):
            existing_ids.add(element.get('name'))

        # Find all anchor links pointing to this page
        broken_anchors = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '#' in href:
                # Check if it's a same-page anchor
                if href.startswith('#') or current_url in href:
                    anchor = href.split('#')[-1]
                    if anchor and anchor not in existing_ids:
                        broken_anchors.append(anchor)

        return broken_anchors

    def extract_charset(self, html: str, headers: Dict[str, str]) -> Optional[str]:
        """Extract character encoding"""
        # Check Content-Type header
        content_type = headers.get('content-type', '')
        charset_match = re.search(r'charset=([^\s;]+)', content_type, re.I)
        if charset_match:
            return charset_match.group(1)

        # Check meta charset tag
        soup = BeautifulSoup(html, 'lxml')
        meta_charset = soup.find('meta', charset=True)
        if meta_charset:
            return meta_charset.get('charset')

        # Check meta http-equiv tag
        meta_http_equiv = soup.find('meta', attrs={'http-equiv': re.compile(r'^content-type$', re.I)})
        if meta_http_equiv:
            content = meta_http_equiv.get('content', '')
            charset_match = re.search(r'charset=([^\s;]+)', content, re.I)
            if charset_match:
                return charset_match.group(1)

        return None

    def extract_viewport(self, html: str) -> Optional[str]:
        """Extract viewport meta tag"""
        soup = BeautifulSoup(html, 'lxml')
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        if viewport:
            return viewport.get('content')
        return None
