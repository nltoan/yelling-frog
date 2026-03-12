"""
Page Processor
Orchestrates all extractors to process a crawled page and extract ALL data
"""
from typing import Dict, Any, Optional
from datetime import datetime
from urllib.parse import quote, urlparse, urljoin
import json
import time

from ..extractors.seo import SEOExtractor
from ..extractors.links import LinkExtractor, LinkMetricsCalculator
from ..extractors.resources import ResourceExtractor
from ..extractors.technical import TechnicalExtractor
from ..extractors.structured_data import StructuredDataExtractor
from ..extractors.content import ContentAnalyzer
from ..storage.models import CrawledURL, ImageData, LinkData, HreflangData
from ..storage.database import Database
from ..utils.url_normalizer import normalize_url
from ..analysis.duplicates import DuplicateDetector


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
        raw_html: Optional[str],
        status_code: Optional[int],
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
            raw_html: Pre-render HTML snapshot (if available, e.g. Playwright response body)
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

        # Normalize URL for consistent storage and lookup
        normalized_url = normalize_url(url)
        
        # Normalize header names once to ensure case-insensitive downstream processing.
        normalized_headers = {}
        if headers:
            try:
                header_items = headers.items()
            except AttributeError:
                header_items = dict(headers).items()
            normalized_headers = {str(k).lower(): v for k, v in header_items}
        headers = normalized_headers

        # Create URL data object with normalized URL
        url_data = CrawledURL(
            url=normalized_url,
            crawled_at=datetime.now(),
            crawl_depth=crawl_depth
        )

        # ========== Core URL Data ==========
        url_data.url_encoded = quote(url, safe=':/?#[]@!$&\'()*+,;=')
        url_data.status_code = status_code
        url_data.status_text = status_text
        url_data.raw_headers = json.dumps(headers or {})

        # ========== Technical Data ==========
        # Performance metrics
        # Calculate actual HTML size for both size and transferred
        html_size = len(html.encode('utf-8')) if html else 0
        # Use Content-Length if available, otherwise use actual HTML size
        size_bytes = int(headers.get('content-length', 0)) or html_size
        perf_data = self.technical_extractor.extract_performance_metrics(
            response_time=response_time,
            ttfb=ttfb,
            size_bytes=size_bytes,
            transferred_bytes=html_size,
            headers=headers
        )
        url_data.response_time = perf_data['response_time']
        url_data.ttfb = perf_data['ttfb']
        url_data.size = perf_data['size']
        url_data.transferred = perf_data['transferred']
        url_data.last_modified = perf_data.get('last_modified')

        # Status info
        status_info = self.technical_extractor.extract_status_info(
            status_code or 0, status_text, headers
        )
        url_data.content_type = status_info['content_type']
        url_data.http_version = status_info.get('http_version', 'HTTP/1.1')

        # Redirect info
        redirect_info = self.technical_extractor.extract_redirect_info(
            status_code or 0, headers, html
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
            url_data.canonical_link_element_1 = self._normalize_link_target(seo_data.get('canonical_link_element_1'), url)
            url_data.canonical_link_element_2 = self._normalize_link_target(seo_data.get('canonical_link_element_2'), url)

            # Pagination
            url_data.rel_next_1 = self._normalize_link_target(seo_data.get('rel_next_1'), url)
            url_data.rel_prev_1 = self._normalize_link_target(seo_data.get('rel_prev_1'), url)
            url_data.http_rel_next_1 = self._normalize_link_target(seo_data.get('http_rel_next_1'), url)
            url_data.http_rel_prev_1 = self._normalize_link_target(seo_data.get('http_rel_prev_1'), url)
            url_data.amphtml_link = self._normalize_link_target(seo_data.get('amphtml_link'), url)
            url_data.mobile_alternate_link = self._normalize_link_target(seo_data.get('mobile_alternate_link'), url)

            # Language
            url_data.language = seo_data.get('language')

            # ========== Content Analysis ==========
            content_data = self.content_analyzer.extract_content_metrics(html, url)
            url_data.word_count = content_data['word_count']
            url_data.sentence_count = content_data.get('sentence_count', 0)
            url_data.avg_words_per_sentence = content_data.get('avg_words_per_sentence', 0)
            url_data.text_ratio = content_data['text_ratio']
            url_data.readability = content_data['readability']
            url_data.readability_grade = content_data.get('readability_grade', '')
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
            url_data.structured_data = structured

            # Validate structured data
            validation = self.structured_extractor.validate_schema_org(structured)
            url_data.schema_validation_errors = len(validation['errors'])
            url_data.schema_validation_warnings = len(validation['warnings'])

            # Open Graph
            og_data = self.structured_extractor.extract_open_graph(html)
            url_data.og_title = og_data.get('og:title')
            url_data.og_description = og_data.get('og:description')
            url_data.og_image = self._normalize_link_target(og_data.get('og:image'), url)
            url_data.og_type = og_data.get('og:type')
            url_data.og_url = self._normalize_link_target(og_data.get('og:url'), url)

            # Twitter Cards
            twitter_data = self.structured_extractor.extract_twitter_cards(html)
            url_data.twitter_card = twitter_data.get('twitter:card')
            url_data.twitter_title = twitter_data.get('twitter:title')
            url_data.twitter_description = twitter_data.get('twitter:description')
            url_data.twitter_image = self._normalize_link_target(twitter_data.get('twitter:image'), url)

            # Hreflang
            hreflang_data = self.structured_extractor.extract_hreflang(html, headers)
            if hreflang_data:
                hreflang_data = [
                    {**item, 'url': self._normalize_link_target(item.get('url'), url)}
                    for item in hreflang_data
                    if self._normalize_link_target(item.get('url'), url)
                ]
                url_data.hreflang_data = hreflang_data
                self._store_hreflang(url_data.url, hreflang_data)

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
        issues = self._detect_issues(url_data)
        issues.extend(self._detect_javascript_only_issues(url, html, raw_html, headers, url_data))
        url_data.issues = list(dict.fromkeys(issues))

        # Save to database
        self.db.save_url(self.session_id, url_data)

        processing_time = time.time() - start_time
        print(f"Processed {url} in {processing_time:.2f}s - {len(url_data.issues)} issues found")

        return url_data

    def _store_links(self, source_url: str, link_data: Dict[str, Any]):
        """Store link relationships in database with normalized URLs"""
        # Normalize source URL for consistent storage
        normalized_source = normalize_url(source_url)

        for link_row in link_data.get('link_rows', []):
            link = LinkData(
                source_url=normalized_source,
                target_url=link_row['target_url'],
                anchor_text=link_row.get('anchor_text'),
                is_internal=bool(link_row.get('is_internal')),
                is_nofollow=bool(link_row.get('is_nofollow')),
                link_type=link_row.get('link_type', 'href'),
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

    def _store_hreflang(self, page_url: str, hreflang_rows: list):
        """Store hreflang relationships in database."""
        for item in hreflang_rows:
            hreflang_data = HreflangData(
                page_url=page_url,
                hreflang=item['hreflang'],
                language=item['language'],
                region=item.get('region'),
                target_url=item['url'],
                source=item['source'],
                has_return_link=False
            )
            self.db.save_hreflang(self.session_id, hreflang_data)

    def _detect_javascript_only_issues(
        self,
        url: str,
        rendered_html: str,
        raw_html: Optional[str],
        headers: Dict[str, str],
        url_data: CrawledURL,
    ) -> list:
        """
        Detect data that appears only after JS execution by comparing raw vs rendered HTML.
        """
        if not rendered_html or not raw_html or raw_html == rendered_html:
            return []
        if 'text/html' not in (url_data.content_type or ''):
            return []

        issues = []

        raw_seo = self.seo_extractor.extract(raw_html, url, headers)
        raw_title = (raw_seo.get('title_1') or '').strip()
        raw_meta = (raw_seo.get('meta_description_1') or '').strip()
        raw_h1 = (raw_seo.get('h1_1') or '').strip()
        raw_canonical = (raw_seo.get('canonical_link_element_1') or '').strip()

        if not raw_title and (url_data.title_1 or '').strip():
            issues.append('javascript_only_titles')
        if not raw_meta and (url_data.meta_description_1 or '').strip():
            issues.append('javascript_only_descriptions')
        if not raw_h1 and (url_data.h1_1 or '').strip():
            issues.append('javascript_only_h1')
        if not raw_canonical and (url_data.canonical_link_element_1 or '').strip():
            issues.append('javascript_only_canonicals')

        raw_links = self.link_extractor.extract(raw_html, url)
        raw_unique_outlinks = raw_links.get('unique_outlinks', 0) or 0
        rendered_unique_outlinks = (url_data.unique_outlinks or 0)
        if rendered_unique_outlinks > raw_unique_outlinks:
            issues.append('javascript_links')

        raw_content = self.content_analyzer.extract_content_metrics(raw_html, url)
        raw_word_count = raw_content.get('word_count', 0) or 0
        rendered_word_count = (url_data.word_count or 0)
        if rendered_word_count >= raw_word_count + 30:
            issues.append('javascript_content')

        return issues

    def _detect_issues(self, url_data: CrawledURL) -> list:
        """
        Detect all issues for a URL

        Returns list of issue codes that can be used for filtering
        """
        issues = []
        is_html = 'text/html' in (url_data.content_type or '')

        if is_html:
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

            if (
                (url_data.h2_1 and not url_data.h1_1) or
                (url_data.h3_1 and not url_data.h2_1) or
                (url_data.h4_1 and not url_data.h3_1)
            ):
                issues.append('non_sequential_headings')

            # Content issues
            if url_data.word_count < 200:
                issues.append('low_content')

            if url_data.text_ratio < 10:
                issues.append('low_text_ratio')

            if (url_data.readability or 0) < 50:
                issues.append('hard_to_read')

            if (url_data.avg_words_per_sentence or 0) > 24:
                issues.append('long_sentences')

            # Canonical issues
            if not url_data.canonical_link_element_1:
                issues.append('missing_canonical')

            # Social metadata issues
            if not url_data.og_title:
                issues.append('missing_og_title')
            if not url_data.og_description:
                issues.append('missing_og_description')
            if not url_data.og_image:
                issues.append('missing_og_image')
            if not url_data.twitter_card:
                issues.append('missing_twitter_card')
            if not url_data.twitter_title:
                issues.append('missing_twitter_title')
            if not url_data.twitter_description:
                issues.append('missing_twitter_description')
            if not url_data.twitter_image:
                issues.append('missing_twitter_image')

            # Security issues tied to HTML rendering
            if url_data.has_mixed_content:
                issues.append('mixed_content')

            if url_data.has_insecure_forms:
                issues.append('insecure_forms')

            if (url_data.unsafe_cross_origin_links or 0) > 0:
                issues.append('unsafe_cross_origin_links')

        if not url_data.is_https:
            issues.append('http_urls')

        if url_data.is_https and not url_data.hsts:
            issues.append('missing_hsts')

        # URL issues
        if url_data.url_length > 115:
            issues.append('url_over_115_chars')

        if url_data.has_parameters:
            issues.append('url_with_parameters')

        if url_data.has_underscores:
            issues.append('url_with_underscores')

        if url_data.has_uppercase:
            issues.append('url_with_uppercase')

        if url_data.has_non_ascii:
            issues.append('url_with_non_ascii')

        # Status code issues
        redirect_type = (url_data.redirect_type or '').strip().lower()
        if redirect_type == 'javascript redirect':
            issues.append('redirection_javascript')
        elif redirect_type == 'meta refresh':
            issues.append('redirection_meta_refresh')

        raw_headers = {}
        if isinstance(url_data.raw_headers, str) and url_data.raw_headers:
            try:
                raw_headers = json.loads(url_data.raw_headers)
            except Exception:
                raw_headers = {}

        redirect_chain_raw = raw_headers.get('x-redirect-chain')
        if redirect_chain_raw:
            try:
                redirect_chain = json.loads(redirect_chain_raw) if isinstance(redirect_chain_raw, str) else redirect_chain_raw
            except Exception:
                redirect_chain = []

            if isinstance(redirect_chain, list) and len(redirect_chain) >= 2:
                issues.append('redirect_chain')
                normalized_chain = [normalize_url(str(item)) for item in redirect_chain if item]
                normalized_chain.append(normalize_url(url_data.url))
                if len(set(normalized_chain)) < len(normalized_chain):
                    issues.append('redirect_loop')

        if 300 <= (url_data.status_code or 0) < 400:
            issues.append('redirection_3xx')
        elif 400 <= (url_data.status_code or 0) < 500:
            issues.append('client_error_4xx')
        elif (url_data.status_code or 0) >= 500:
            issues.append('server_error_5xx')

        if (url_data.ttfb or 0) >= 1:
            issues.append('slow_ttfb')

        if (url_data.status_code or 0) == 0 and (url_data.status_text or '').strip():
            issues.append('crawl_error')

        # Indexability issues
        if url_data.indexability == 'Non-Indexable' and (url_data.indexability_status or '').lower().startswith('noindex'):
            issues.append('noindex')

        return list(dict.fromkeys(issues))

    def _normalize_link_target(self, candidate_url: Optional[str], source_url: str) -> Optional[str]:
        """Resolve relative targets and normalize internal URLs consistently."""
        if not candidate_url:
            return None

        resolved = urljoin(source_url, candidate_url.strip())
        if self.link_extractor.is_internal(resolved):
            return normalize_url(resolved)
        return resolved

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
            outlink_urls = [link.target_url for link in links if link.is_internal and link.link_type == 'href']

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

            # Set link score (use helper method that handles URL normalization)
            url_data.link_score = self.link_metrics.get_link_score(url_data.url, link_scores)

            # Save updated data
            self.db.save_url(self.session_id, url_data)

        # Find orphan pages
        all_url_set = {url.url for url in all_urls}
        orphans = self.link_metrics.find_orphan_pages(all_url_set)

        print(f"Link metrics calculated: {len(orphans)} orphan pages found")
        
        # Find near duplicates based on content hash
        self._calculate_near_duplicates(all_urls)

        return {
            'total_pages': len(all_urls),
            'orphan_pages': len(orphans),
            'orphan_urls': orphans
        }
    
    def _calculate_near_duplicates(self, all_urls):
        """Calculate exact and near duplicate information using similarity analysis."""
        detector = DuplicateDetector()
        comparable_urls = []
        detector_hashes = {}

        for url_data in all_urls:
            if url_data.html_content and url_data.content_type and 'text/html' in url_data.content_type:
                detector_hash, _ = detector.add_page(url_data.url, url_data.html_content)
                detector_hashes[url_data.url] = detector_hash
                comparable_urls.append(url_data)

        duplicates_found = 0
        max_comparisons = max(len(comparable_urls), 50)

        for url_data in comparable_urls:
            exact_duplicates = detector.get_exact_duplicates(url_data.url, detector_hashes[url_data.url])
            near_duplicates = detector.find_near_duplicates(url_data.url, max_comparisons=max_comparisons)
            non_exact_near_duplicates = [
                (match_url, score) for match_url, score in near_duplicates
                if match_url not in exact_duplicates
            ]

            if exact_duplicates:
                url_data.closest_similarity_match = exact_duplicates[0]
                url_data.closest_similarity_score = 100.0
                duplicates_found += len(exact_duplicates)
            elif non_exact_near_duplicates:
                best_match, best_score = non_exact_near_duplicates[0]
                url_data.closest_similarity_match = best_match
                url_data.closest_similarity_score = round(best_score * 100, 1)
                duplicates_found += len(non_exact_near_duplicates)
            else:
                url_data.closest_similarity_match = None
                url_data.closest_similarity_score = 0.0

            url_data.no_near_duplicates = len(non_exact_near_duplicates)
            self.db.save_url(self.session_id, url_data)

        if duplicates_found > 0:
            print(f"Duplicate analysis updated for {len(comparable_urls)} pages")
