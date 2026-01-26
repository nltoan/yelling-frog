"""
Page Processor
Orchestrates all extractors to process a crawled page and extract ALL data
"""
from typing import Dict, Any, Optional
from datetime import datetime
from urllib.parse import quote, urlparse
import time

from ..extractors.seo import SEOExtractor
from ..extractors.links import LinkExtractor, LinkMetricsCalculator
from ..extractors.resources import ResourceExtractor
from ..extractors.technical import TechnicalExtractor
from ..extractors.structured_data import StructuredDataExtractor
from ..extractors.content import ContentAnalyzer
from ..storage.models import CrawledURL, ImageData, LinkData
from ..storage.database import Database


class PageProcessor:
    """
    Process crawled pages through all extractors and store complete data
    """

    def __init__(self, database: Database, base_url: str, session_id: str):
        """
        Args:
            database: Database instance for storage
            base_url: Base URL of the site being crawled
            session_id: Current crawl session ID
        """
        self.db = database
        self.base_url = base_url
        self.session_id = session_id

        # Initialize all extractors
        self.seo_extractor = SEOExtractor()
        self.link_extractor = LinkExtractor(base_url)
        self.resource_extractor = ResourceExtractor()
        self.technical_extractor = TechnicalExtractor()
        self.structured_extractor = StructuredDataExtractor()
        self.content_analyzer = ContentAnalyzer()

        # Link metrics calculator (for post-processing)
        self.link_metrics = LinkMetricsCalculator()

    def process_page(
        self,
        url: str,
        html: str,
        status_code: int,
        status_text: str,
        headers: Dict[str, str],
        response_time: float,
        ttfb: float,
        crawl_depth: int = 0
    ) -> CrawledURL:
        """
        Process a single page through all extractors

        Args:
            url: Page URL
            html: HTML content
            status_code: HTTP status code
            status_text: HTTP status text
            headers: Response headers
            response_time: Total response time in seconds
            ttfb: Time to first byte
            crawl_depth: Depth from start URL

        Returns:
            CrawledURL object with all extracted data
        """
        start_time = time.time()

        # Create URL data object
        url_data = CrawledURL(
            url=url,
            crawled_at=datetime.now(),
            crawl_depth=crawl_depth
        )

        # ========== Core URL Data ==========
        url_data.url_encoded = quote(url, safe=':/?#[]@!$&\'()*+,;=')
        url_data.status_code = status_code
        url_data.status_text = status_text

        # ========== Technical Data ==========
        # Performance metrics
        perf_data = self.technical_extractor.extract_performance_metrics(
            response_time=response_time,
            ttfb=ttfb,
            size_bytes=int(headers.get('content-length', 0)),
            transferred_bytes=len(html.encode('utf-8')) if html else 0,
            headers=headers
        )
        url_data.response_time = perf_data['response_time']
        url_data.ttfb = perf_data['ttfb']
        url_data.size = perf_data['size']
        url_data.transferred = perf_data['transferred']
        url_data.last_modified = perf_data.get('last_modified')

        # Status info
        status_info = self.technical_extractor.extract_status_info(
            status_code, status_text, headers
        )
        url_data.content_type = status_info['content_type']
        url_data.http_version = status_info.get('http_version', 'HTTP/1.1')

        # Redirect info
        redirect_info = self.technical_extractor.extract_redirect_info(
            status_code, headers, html
        )
        url_data.redirect_uri = redirect_info.get('redirect_uri')
        url_data.redirect_type = redirect_info.get('redirect_type')

        # Security headers
        security_headers = self.technical_extractor.extract_security_headers(headers)
        url_data.hsts = security_headers['hsts']
        url_data.hsts_value = security_headers.get('hsts_value')
        url_data.csp = security_headers['csp']
        url_data.csp_value = security_headers.get('csp_value')
        url_data.x_content_type_options = security_headers['x_content_type_options']
        url_data.x_frame_options = security_headers['x_frame_options']
        url_data.x_frame_options_value = security_headers.get('x_frame_options_value')
        url_data.referrer_policy = security_headers['referrer_policy']
        url_data.referrer_policy_value = security_headers.get('referrer_policy_value')

        # URL structure analysis
        url_structure = self.technical_extractor.analyze_url_structure(url)
        url_data.url_length = url_structure['url_length']
        url_data.has_parameters = url_structure['has_parameters']
        url_data.has_non_ascii = url_structure['has_non_ascii']
        url_data.has_underscores = url_structure['has_underscores']
        url_data.has_uppercase = url_structure['has_uppercase']
        url_data.folder_depth = url_structure['folder_depth']
        url_data.is_https = url_structure['scheme'] == 'https'

        # Content hash
        url_data.hash = self.technical_extractor.calculate_content_hash(html)

        # Charset and viewport
        url_data.charset = self.technical_extractor.extract_charset(html, headers)
        url_data.viewport = self.technical_extractor.extract_viewport(html)

        # Store HTML content for duplicate detection (limit to first 100KB to save space)
        if html and 'text/html' in url_data.content_type:
            url_data.html_content = html[:100000] if len(html) > 100000 else html

        # Only process HTML content
        if html and 'text/html' in url_data.content_type:
            # ========== SEO Data ==========
            seo_data = self.seo_extractor.extract(html, url, headers)

            # Titles
            url_data.title_1 = seo_data.get('title_1')
            url_data.title_1_length = seo_data.get('title_1_length', 0)
            url_data.title_1_pixel_width = seo_data.get('title_1_pixel_width', 0)
            url_data.title_2 = seo_data.get('title_2')
            url_data.title_2_length = seo_data.get('title_2_length', 0)

            # Meta descriptions
            url_data.meta_description_1 = seo_data.get('meta_description_1')
            url_data.meta_description_1_length = seo_data.get('meta_description_1_length', 0)
            url_data.meta_description_1_pixel_width = seo_data.get('meta_description_1_pixel_width', 0)
            url_data.meta_description_2 = seo_data.get('meta_description_2')

            # Meta keywords
            url_data.meta_keywords_1 = seo_data.get('meta_keywords_1')
            url_data.meta_keywords_1_length = seo_data.get('meta_keywords_1_length', 0)

            # Headings (H1-H6)
            for level in range(1, 7):
                for idx in range(1, 3):
                    setattr(url_data, f'h{level}_{idx}', seo_data.get(f'h{level}_{idx}'))
                    setattr(url_data, f'h{level}_len_{idx}', seo_data.get(f'h{level}_len_{idx}', 0))

            # Directives
            url_data.meta_robots_1 = seo_data.get('meta_robots_1')
            url_data.meta_robots_2 = seo_data.get('meta_robots_2')
            url_data.x_robots_tag_1 = seo_data.get('x_robots_tag_1')
            url_data.x_robots_tag_2 = seo_data.get('x_robots_tag_2')
            url_data.meta_refresh_1 = seo_data.get('meta_refresh_1')

            # Canonicals
            url_data.canonical_link_element_1 = seo_data.get('canonical_link_element_1')
            url_data.canonical_link_element_2 = seo_data.get('canonical_link_element_2')

            # Pagination
            url_data.rel_next_1 = seo_data.get('rel_next_1')
            url_data.rel_prev_1 = seo_data.get('rel_prev_1')
            url_data.http_rel_next_1 = seo_data.get('http_rel_next_1')
            url_data.http_rel_prev_1 = seo_data.get('http_rel_prev_1')

            # Language
            url_data.language = seo_data.get('language')

            # ========== Content Analysis ==========
            content_data = self.content_analyzer.extract_content_metrics(html, url)
            url_data.word_count = content_data['word_count']
            url_data.text_ratio = content_data['text_ratio']
            url_data.readability = content_data['readability']
            url_data.hash = content_data['hash']

            # ========== Link Extraction ==========
            link_data = self.link_extractor.extract(html, url)
            url_data.outlinks = link_data['outlinks']
            url_data.unique_outlinks = link_data['unique_outlinks']
            url_data.external_outlinks = link_data['external_outlinks']
            url_data.unique_external_outlinks = link_data['unique_external_outlinks']

            # Store link relationships
            self._store_links(url, link_data)

            # ========== Resource Extraction ==========
            # Images
            images = self.resource_extractor.extract_images(html, url)
            self._store_images(url, images)

            # ========== Structured Data ==========
            structured = self.structured_extractor.extract_all(html)
            url_data.has_json_ld = bool(structured['json_ld'])
            url_data.has_microdata = bool(structured['microdata'])
            url_data.has_rdfa = bool(structured['rdfa'])
            url_data.schema_types = ', '.join(structured['schema_types']) if structured['schema_types'] else None

            # Validate structured data
            validation = self.structured_extractor.validate_schema_org(structured)
            url_data.schema_validation_errors = len(validation['errors'])
            url_data.schema_validation_warnings = len(validation['warnings'])

            # Open Graph
            og_data = self.structured_extractor.extract_open_graph(html)
            url_data.og_title = og_data.get('og:title')
            url_data.og_description = og_data.get('og:description')
            url_data.og_image = og_data.get('og:image')
            url_data.og_type = og_data.get('og:type')
            url_data.og_url = og_data.get('og:url')

            # Twitter Cards
            twitter_data = self.structured_extractor.extract_twitter_cards(html)
            url_data.twitter_card = twitter_data.get('twitter:card')
            url_data.twitter_title = twitter_data.get('twitter:title')
            url_data.twitter_description = twitter_data.get('twitter:description')
            url_data.twitter_image = twitter_data.get('twitter:image')

            # ========== Security Issues ==========
            mixed_content = self.technical_extractor.detect_mixed_content(html, url)
            url_data.has_mixed_content = mixed_content['has_mixed_content']

            insecure_forms = self.technical_extractor.detect_insecure_forms(html, url)
            url_data.has_insecure_forms = insecure_forms['has_insecure_forms']

            unsafe_links = self.link_extractor.extract_unsafe_cross_origin_links(html, url)
            url_data.unsafe_cross_origin_links = len(unsafe_links)

        # ========== Indexability ==========
        indexability, reason = self.seo_extractor.get_indexability_status(url_data.__dict__)
        url_data.indexability = indexability
        url_data.indexability_status = reason

        # ========== Issue Detection ==========
        url_data.issues = self._detect_issues(url_data)

        # Save to database
        self.db.save_url(self.session_id, url_data)

        processing_time = time.time() - start_time
        print(f"Processed {url} in {processing_time:.2f}s - {len(url_data.issues)} issues found")

        return url_data

    def _store_links(self, source_url: str, link_data: Dict[str, Any]):
        """Store link relationships in database"""
        # Store internal links
        for target_url in link_data['internal_links']:
            anchor_texts = link_data['anchor_texts'].get(target_url, [])
            anchor_text = ', '.join(anchor_texts[:3]) if anchor_texts else None

            link = LinkData(
                source_url=source_url,
                target_url=target_url,
                anchor_text=anchor_text,
                is_internal=True,
                link_type='href'
            )
            self.db.save_link(self.session_id, link)

        # Store external links
        for target_url in link_data['external_links']:
            anchor_texts = link_data['anchor_texts'].get(target_url, [])
            anchor_text = ', '.join(anchor_texts[:3]) if anchor_texts else None

            link = LinkData(
                source_url=source_url,
                target_url=target_url,
                anchor_text=anchor_text,
                is_internal=False,
                link_type='href'
            )
            self.db.save_link(self.session_id, link)

    def _store_images(self, page_url: str, images: list):
        """Store image data in database"""
        for img in images:
            image_data = ImageData(
                url=page_url,  # For compatibility
                page_url=page_url,
                image_url=img['image_url'],
                alt_text=img['alt_text'],
                alt_text_length=img['alt_text_length'],
                width=img['width'],
                height=img['height'],
                missing_alt=img['missing_alt'],
                missing_alt_attribute=img['missing_alt_attribute'],
                missing_size_attributes=img['missing_size_attributes']
            )
            self.db.save_image(self.session_id, image_data)

    def _detect_issues(self, url_data: CrawledURL) -> list:
        """
        Detect all issues for a URL

        Returns list of issue codes that can be used for filtering
        """
        issues = []

        # Title issues
        if not url_data.title_1:
            issues.append('missing_title')
        elif url_data.title_1_length > 60:
            issues.append('title_over_60_chars')
        elif url_data.title_1_length < 30:
            issues.append('title_below_30_chars')

        if url_data.title_1_pixel_width > 568:
            issues.append('title_over_568_pixels')

        if url_data.title_2:
            issues.append('multiple_titles')

        # Meta description issues
        if not url_data.meta_description_1:
            issues.append('missing_meta_description')
        elif url_data.meta_description_1_length > 155:
            issues.append('meta_description_over_155_chars')
        elif url_data.meta_description_1_length < 70:
            issues.append('meta_description_below_70_chars')

        if url_data.meta_description_2:
            issues.append('multiple_meta_descriptions')

        # Heading issues
        if not url_data.h1_1:
            issues.append('missing_h1')
        elif url_data.h1_len_1 > 70:
            issues.append('h1_over_70_chars')

        if url_data.h1_2:
            issues.append('multiple_h1')

        if not url_data.h2_1:
            issues.append('missing_h2')

        # Content issues
        if url_data.word_count < 200:
            issues.append('low_content')

        if url_data.text_ratio < 10:
            issues.append('low_text_ratio')

        # Canonical issues
        if not url_data.canonical_link_element_1:
            issues.append('missing_canonical')

        # Security issues
        if not url_data.is_https:
            issues.append('http_url')

        if url_data.has_mixed_content:
            issues.append('mixed_content')

        if url_data.has_insecure_forms:
            issues.append('insecure_forms')

        if url_data.is_https and not url_data.hsts:
            issues.append('missing_hsts')

        # URL issues
        if url_data.url_length > 115:
            issues.append('url_over_115_chars')

        if url_data.has_underscores:
            issues.append('url_with_underscores')

        if url_data.has_uppercase:
            issues.append('url_with_uppercase')

        # Status code issues
        if url_data.status_code >= 400:
            issues.append('error_status')

        if url_data.status_code in [301, 302, 307, 308]:
            issues.append('redirect')

        # Indexability issues
        if url_data.indexability == 'Non-Indexable':
            issues.append('non_indexable')

        return issues

    def post_process_link_metrics(self):
        """
        Calculate link metrics after crawl is complete
        This includes inlinks, link scores, and orphan detection
        """
        print("Calculating link metrics...")

        # Get all URLs from this session
        all_urls = self.db.get_all_urls(self.session_id)

        # Build link graph
        for url_data in all_urls:
            # Get outlinks for this URL
            links = self.db.get_links(self.session_id, source_url=url_data.url)
            outlink_urls = [link.target_url for link in links if link.is_internal]

            self.link_metrics.add_page(url_data.url, outlink_urls)

        # Calculate link scores (PageRank-like)
        link_scores = self.link_metrics.calculate_link_score()

        # Update each URL with link metrics
        for url_data in all_urls:
            # Calculate inlinks
            inlink_data = self.link_metrics.calculate_inlinks(url_data.url)
            url_data.inlinks = inlink_data['inlinks']
            url_data.unique_inlinks = inlink_data['unique_inlinks']
            url_data.percentage_of_total = inlink_data['percentage_of_total']

            # Set link score
            url_data.link_score = round(link_scores.get(url_data.url, 0), 2)

            # Save updated data
            self.db.save_url(self.session_id, url_data)

        # Find orphan pages
        all_url_set = {url.url for url in all_urls}
        orphans = self.link_metrics.find_orphan_pages(all_url_set)

        print(f"Link metrics calculated: {len(orphans)} orphan pages found")

        return {
            'total_pages': len(all_urls),
            'orphan_pages': len(orphans),
            'orphan_urls': orphans
        }
