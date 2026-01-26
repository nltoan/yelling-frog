"""
Resource Extractor
Extracts images, CSS, JavaScript, and other resources with full metadata
"""
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re


class ResourceExtractor:
    """Extract comprehensive resource data"""

    def __init__(self):
        pass

    def extract_images(self, html: str, current_url: str) -> List[Dict[str, Any]]:
        """
        Extract all images with metadata

        Returns list of dicts with:
        - image_url: Source URL
        - alt_text: Alt attribute
        - alt_text_length: Length of alt text
        - width: Width attribute (pixels)
        - height: Height attribute (pixels)
        - missing_alt: Boolean
        - missing_size_attributes: Boolean
        """
        soup = BeautifulSoup(html, 'lxml')
        images = []

        for img in soup.find_all('img'):
            src = img.get('src', '').strip()
            if not src:
                continue

            # Resolve relative URLs
            absolute_url = urljoin(current_url, src)

            # Extract alt text
            alt_text = img.get('alt')
            if alt_text is None:
                # Alt attribute completely missing
                alt_text = None
                missing_alt = True
                alt_length = 0
            else:
                # Alt attribute exists (may be empty string)
                alt_text = alt_text.strip()
                missing_alt = len(alt_text) == 0
                alt_length = len(alt_text)

            # Extract dimensions
            width = img.get('width')
            height = img.get('height')

            missing_size = not width or not height

            # Convert dimensions to int if possible
            try:
                width = int(width) if width else None
            except (ValueError, TypeError):
                width = None

            try:
                height = int(height) if height else None
            except (ValueError, TypeError):
                height = None

            image_data = {
                'image_url': absolute_url,
                'alt_text': alt_text,
                'alt_text_length': alt_length,
                'width': width,
                'height': height,
                'missing_alt': missing_alt,
                'missing_alt_attribute': alt_text is None,
                'missing_size_attributes': missing_size,
            }

            images.append(image_data)

        return images

    def extract_css_resources(self, html: str, current_url: str) -> List[Dict[str, Any]]:
        """
        Extract CSS stylesheet links

        Returns list of dicts with:
        - resource_url: CSS file URL
        - type: 'css'
        - media: Media attribute
        """
        soup = BeautifulSoup(html, 'lxml')
        css_resources = []

        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href', '').strip()
            if not href:
                continue

            absolute_url = urljoin(current_url, href)
            media = link.get('media', 'all')

            css_data = {
                'resource_url': absolute_url,
                'type': 'css',
                'media': media,
            }

            css_resources.append(css_data)

        return css_resources

    def extract_js_resources(self, html: str, current_url: str) -> List[Dict[str, Any]]:
        """
        Extract JavaScript resources

        Returns list of dicts with:
        - resource_url: JS file URL
        - type: 'javascript'
        - async: Boolean
        - defer: Boolean
        """
        soup = BeautifulSoup(html, 'lxml')
        js_resources = []

        for script in soup.find_all('script', src=True):
            src = script.get('src', '').strip()
            if not src:
                continue

            absolute_url = urljoin(current_url, src)

            js_data = {
                'resource_url': absolute_url,
                'type': 'javascript',
                'async': script.has_attr('async'),
                'defer': script.has_attr('defer'),
            }

            js_resources.append(js_data)

        return js_resources

    def analyze_image_issues(self, images: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize images by issues

        Returns dict with:
        - over_100kb: Images likely over 100KB (needs actual file size check)
        - missing_alt: Images with no alt text
        - missing_alt_attribute: Images with no alt attribute at all
        - alt_over_100_chars: Images with alt text over 100 characters
        - missing_size_attributes: Images without width/height
        """
        issues = {
            'missing_alt': [],
            'missing_alt_attribute': [],
            'alt_over_100_chars': [],
            'missing_size_attributes': [],
        }

        for img in images:
            if img['missing_alt']:
                issues['missing_alt'].append(img)

            if img['missing_alt_attribute']:
                issues['missing_alt_attribute'].append(img)

            if img['alt_text_length'] > 100:
                issues['alt_over_100_chars'].append(img)

            if img['missing_size_attributes']:
                issues['missing_size_attributes'].append(img)

        return issues

    def extract_all_resources(self, html: str, current_url: str) -> Dict[str, Any]:
        """
        Extract all resources in one pass

        Returns:
        - images: List of image data
        - css: List of CSS resources
        - js: List of JS resources
        - total_resources: Total count
        """
        images = self.extract_images(html, current_url)
        css = self.extract_css_resources(html, current_url)
        js = self.extract_js_resources(html, current_url)

        return {
            'images': images,
            'css_resources': css,
            'js_resources': js,
            'total_images': len(images),
            'total_css': len(css),
            'total_js': len(js),
            'total_resources': len(images) + len(css) + len(js),
        }

    def detect_render_blocking_resources(self, html: str, current_url: str) -> Dict[str, List[str]]:
        """
        Detect render-blocking CSS and JavaScript

        Returns:
        - render_blocking_css: List of CSS URLs without media queries
        - render_blocking_js: List of JS URLs without async/defer
        """
        soup = BeautifulSoup(html, 'lxml')

        render_blocking_css = []
        render_blocking_js = []

        # CSS without media queries (except 'all') is render-blocking
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href', '').strip()
            media = link.get('media', 'all')

            if href and media in ['all', 'screen', None]:
                absolute_url = urljoin(current_url, href)
                render_blocking_css.append(absolute_url)

        # JS without async or defer is render-blocking
        for script in soup.find_all('script', src=True):
            src = script.get('src', '').strip()

            if src and not (script.has_attr('async') or script.has_attr('defer')):
                absolute_url = urljoin(current_url, src)
                render_blocking_js.append(absolute_url)

        return {
            'render_blocking_css': render_blocking_css,
            'render_blocking_js': render_blocking_js,
        }

    def extract_favicon(self, html: str, current_url: str) -> Optional[str]:
        """Extract favicon URL"""
        soup = BeautifulSoup(html, 'lxml')

        # Look for icon link tags
        icon_link = soup.find('link', rel=re.compile(r'icon', re.I))
        if icon_link:
            href = icon_link.get('href', '').strip()
            if href:
                return urljoin(current_url, href)

        # Default favicon location
        parsed = urlparse(current_url)
        default_favicon = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
        return default_favicon

    def extract_video_resources(self, html: str, current_url: str) -> List[Dict[str, Any]]:
        """Extract video resources"""
        soup = BeautifulSoup(html, 'lxml')
        videos = []

        # Video tags
        for video in soup.find_all('video'):
            src = video.get('src')
            if src:
                absolute_url = urljoin(current_url, src)
                videos.append({
                    'video_url': absolute_url,
                    'type': 'video',
                    'poster': video.get('poster'),
                })

            # Source tags inside video
            for source in video.find_all('source'):
                src = source.get('src')
                if src:
                    absolute_url = urljoin(current_url, src)
                    videos.append({
                        'video_url': absolute_url,
                        'type': 'video',
                        'mime_type': source.get('type'),
                    })

        return videos

    def extract_audio_resources(self, html: str, current_url: str) -> List[Dict[str, Any]]:
        """Extract audio resources"""
        soup = BeautifulSoup(html, 'lxml')
        audio_files = []

        # Audio tags
        for audio in soup.find_all('audio'):
            src = audio.get('src')
            if src:
                absolute_url = urljoin(current_url, src)
                audio_files.append({
                    'audio_url': absolute_url,
                    'type': 'audio',
                })

            # Source tags inside audio
            for source in audio.find_all('source'):
                src = source.get('src')
                if src:
                    absolute_url = urljoin(current_url, src)
                    audio_files.append({
                        'audio_url': absolute_url,
                        'type': 'audio',
                        'mime_type': source.get('type'),
                    })

        return audio_files

    def extract_font_resources(self, html: str, current_url: str) -> List[str]:
        """Extract font resources"""
        soup = BeautifulSoup(html, 'lxml')
        fonts = []

        # Link tags with rel=preload or type=font
        for link in soup.find_all('link'):
            href = link.get('href', '').strip()
            as_attr = link.get('as', '')
            type_attr = link.get('type', '')

            if href and (as_attr == 'font' or 'font' in type_attr):
                absolute_url = urljoin(current_url, href)
                fonts.append(absolute_url)

        return fonts
