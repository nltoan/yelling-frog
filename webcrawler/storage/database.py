"""
Database Layer
SQLite database operations for storing crawl data
"""
import sqlite3
import json
import threading
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import uuid
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from .models import (
    CrawledURL, ImageData, LinkData, HreflangData,
    CrawlSession, IssueReport, SQL_CREATE_TABLES
)
from ..utils.url_normalizer import normalize_url

DIRECTIVES_TEXT_SQL = (
    "LOWER("
    "COALESCE(meta_robots_1, '') || ' ' || "
    "COALESCE(meta_robots_2, '') || ' ' || "
    "COALESCE(x_robots_tag_1, '') || ' ' || "
    "COALESCE(x_robots_tag_2, '')"
    ")"
)
ISSUES_TEXT_SQL = "LOWER(COALESCE(issues, ''))"

FOLLOW_TOKEN_SQL = (
    f"({DIRECTIVES_TEXT_SQL} = 'follow' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE 'follow,%' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE 'follow %' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '%,follow,%' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '%,follow' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '% follow %' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '% follow,%' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '% follow')"
)

NONE_TOKEN_SQL = (
    f"({DIRECTIVES_TEXT_SQL} = 'none' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE 'none,%' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE 'none %' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '%,none,%' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '%,none' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '% none %' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '% none,%' OR "
    f"{DIRECTIVES_TEXT_SQL} LIKE '% none')"
)

PAGINATION_HAS_NEXT_SQL = "(COALESCE(rel_next_1, '') != '' OR COALESCE(http_rel_next_1, '') != '')"
PAGINATION_HAS_PREV_SQL = "(COALESCE(rel_prev_1, '') != '' OR COALESCE(http_rel_prev_1, '') != '')"
PAGINATION_HAS_ANY_SQL = f"({PAGINATION_HAS_NEXT_SQL} OR {PAGINATION_HAS_PREV_SQL})"


URL_FILTER_QUERIES = {
    # Title filters
    'missing_title': "title_1 IS NULL OR title_1 = ''",
    'title_over_60_chars': "title_1_length > 60",
    'title_below_30_chars': "title_1_length < 30 AND title_1_length > 0",
    'title_over_568_pixels': "title_1_pixel_width > 568",
    'title_below_200_pixels': "title_1_pixel_width < 200 AND title_1_pixel_width > 0",
    'same_as_h1': (
        "title_1 IS NOT NULL AND title_1 != '' AND "
        "h1_1 IS NOT NULL AND h1_1 != '' AND "
        "LOWER(TRIM(title_1)) = LOWER(TRIM(h1_1))"
    ),
    'multiple_titles': "title_2 IS NOT NULL",
    'duplicate_title': """
        title_1 IS NOT NULL AND title_1 != '' AND EXISTS (
            SELECT 1 FROM urls AS dup
            WHERE dup.session_id = urls.session_id
              AND dup.url != urls.url
              AND dup.title_1 = urls.title_1
        )
    """,

    # Meta description filters
    'missing_meta_description': "meta_description_1 IS NULL OR meta_description_1 = ''",
    'meta_description_over_155_chars': "meta_description_1_length > 155",
    'meta_description_below_70_chars': "meta_description_1_length < 70 AND meta_description_1_length > 0",
    'meta_description_over_990_pixels': "meta_description_1_pixel_width > 990",
    'meta_description_below_400_pixels': "meta_description_1_pixel_width < 400 AND meta_description_1_pixel_width > 0",
    'multiple_meta_descriptions': "meta_description_2 IS NOT NULL",
    'duplicate_meta_description': """
        meta_description_1 IS NOT NULL AND meta_description_1 != '' AND EXISTS (
            SELECT 1 FROM urls AS dup
            WHERE dup.session_id = urls.session_id
              AND dup.url != urls.url
              AND dup.meta_description_1 = urls.meta_description_1
        )
    """,

    # Heading filters
    'missing_h1': "h1_1 IS NULL OR h1_1 = ''",
    'h1_over_70_chars': "h1_len_1 > 70",
    'multiple_h1': "h1_2 IS NOT NULL",
    'missing_h2': "h2_1 IS NULL OR h2_1 = ''",
    'non_sequential_headings': f"{ISSUES_TEXT_SQL} LIKE '%non_sequential_headings%'",
    'duplicate_h1': """
        h1_1 IS NOT NULL AND h1_1 != '' AND EXISTS (
            SELECT 1 FROM urls AS dup
            WHERE dup.session_id = urls.session_id
              AND dup.url != urls.url
              AND dup.h1_1 = urls.h1_1
        )
    """,

    # Content filters
    'low_content': "word_count < 200",
    'low_text_ratio': "text_ratio < 10",
    'near_duplicates': "no_near_duplicates > 0",
    'exact_duplicates': """
        hash IS NOT NULL AND hash != '' AND EXISTS (
            SELECT 1 FROM urls AS dup
            WHERE dup.session_id = urls.session_id
              AND dup.url != urls.url
              AND dup.hash = urls.hash
        )
    """,
    'spelling_errors': "spelling_errors > 0",
    'grammar_errors': "grammar_errors > 0",

    # Directive filters
    'noindex': f"{DIRECTIVES_TEXT_SQL} LIKE '%noindex%'",
    'nofollow': f"{DIRECTIVES_TEXT_SQL} LIKE '%nofollow%'",
    'follow': f"{FOLLOW_TOKEN_SQL} AND {DIRECTIVES_TEXT_SQL} NOT LIKE '%nofollow%'",
    'none': f"{NONE_TOKEN_SQL}",
    'noarchive': f"{DIRECTIVES_TEXT_SQL} LIKE '%noarchive%'",
    'nosnippet': f"{DIRECTIVES_TEXT_SQL} LIKE '%nosnippet%'",
    'noimageindex': f"{DIRECTIVES_TEXT_SQL} LIKE '%noimageindex%'",
    'max_snippet': f"{DIRECTIVES_TEXT_SQL} LIKE '%max-snippet:%'",
    'max_image_preview': f"{DIRECTIVES_TEXT_SQL} LIKE '%max-image-preview:%'",
    'max_video_preview': f"{DIRECTIVES_TEXT_SQL} LIKE '%max-video-preview:%'",
    'unavailable_after': f"{DIRECTIVES_TEXT_SQL} LIKE '%unavailable_after:%' OR {DIRECTIVES_TEXT_SQL} LIKE '%unavailable-after:%'",

    # Canonical filters
    'contains_canonical': "canonical_link_element_1 IS NOT NULL",
    'missing_canonical': "canonical_link_element_1 IS NULL",

    # Pagination filters
    'contains_pagination': PAGINATION_HAS_ANY_SQL,
    'pagination_first_page': f"({PAGINATION_HAS_NEXT_SQL} AND NOT {PAGINATION_HAS_PREV_SQL})",
    'pagination_2_plus_page': PAGINATION_HAS_PREV_SQL,

    # Status code filters
    'blocked_by_robots_txt': "LOWER(COALESCE(indexability_status, '')) LIKE '%robots%'",
    'blocked_resource': f"{ISSUES_TEXT_SQL} LIKE '%blocked_resource%'",
    'success_2xx': "status_code BETWEEN 200 AND 299",
    'redirection_3xx': "status_code BETWEEN 300 AND 399",
    'redirection_javascript': "LOWER(COALESCE(redirect_type, '')) = 'javascript redirect'",
    'redirection_meta_refresh': "LOWER(COALESCE(redirect_type, '')) = 'meta refresh'",
    'redirect_chain': f"{ISSUES_TEXT_SQL} LIKE '%redirect_chain%'",
    'redirect_loop': f"{ISSUES_TEXT_SQL} LIKE '%redirect_loop%'",
    'client_error_4xx': "status_code BETWEEN 400 AND 499",
    'server_error_5xx': "status_code BETWEEN 500 AND 599",
    'crawl_error': "status_code IS NULL OR status_code = 0",

    # Security filters
    'http_urls': "is_https = 0",
    'https_urls': "is_https = 1",
    'mixed_content': "has_mixed_content = 1",
    'insecure_forms': "has_insecure_forms = 1",
    'form_on_http_url': "is_https = 0 AND has_insecure_forms = 1",
    'unsafe_cross_origin_links': "unsafe_cross_origin_links > 0",
    'protocol_relative_links': (
        "LOWER(COALESCE(html_content, '')) LIKE '%href=\"//%' OR "
        "LOWER(COALESCE(html_content, '')) LIKE '%src=\"//%' OR "
        "LOWER(COALESCE(html_content, '')) LIKE \"%href='//%\" OR "
        "LOWER(COALESCE(html_content, '')) LIKE \"%src='//%\""
    ),
    'missing_hsts': "is_https = 1 AND hsts = 0",
    'missing_csp': "is_https = 1 AND csp = 0",
    'missing_x_content_type_options': "x_content_type_options = 0",
    'missing_x_frame_options': "x_frame_options = 0",
    'missing_secure_referrer_policy': (
        "is_https = 1 AND ("
        "referrer_policy = 0 OR "
        "LOWER(COALESCE(referrer_policy_value, '')) IN ('', 'unsafe-url', 'no-referrer-when-downgrade')"
        ")"
    ),
    'bad_content_type': f"{ISSUES_TEXT_SQL} LIKE '%bad_content_type%'",

    # URL filters
    'url_over_115_chars': "url_length > 115",
    'url_with_parameters': "has_parameters = 1",
    'url_with_underscores': "has_underscores = 1",
    'url_with_uppercase': "has_uppercase = 1",
    'url_with_non_ascii': "has_non_ascii = 1",
    'duplicate_url': """
        hash IS NOT NULL AND hash != '' AND EXISTS (
            SELECT 1 FROM urls AS dup
            WHERE dup.session_id = urls.session_id
              AND dup.url != urls.url
              AND dup.hash = urls.hash
        )
    """,
    'broken_bookmarks': f"{ISSUES_TEXT_SQL} LIKE '%broken_bookmarks%'",
    'javascript_links': f"{ISSUES_TEXT_SQL} LIKE '%javascript_links%'",
    'javascript_content': f"{ISSUES_TEXT_SQL} LIKE '%javascript_content%'",
    'javascript_only_titles': f"{ISSUES_TEXT_SQL} LIKE '%javascript_only_titles%'",
    'javascript_only_descriptions': f"{ISSUES_TEXT_SQL} LIKE '%javascript_only_descriptions%'",
    'javascript_only_h1': f"{ISSUES_TEXT_SQL} LIKE '%javascript_only_h1%'",
    'javascript_only_canonicals': f"{ISSUES_TEXT_SQL} LIKE '%javascript_only_canonicals%'",

    # Structured data filters
    'contains_structured_data': "(has_json_ld = 1 OR has_microdata = 1 OR has_rdfa = 1)",
    'json_ld': "has_json_ld = 1",
    'microdata': "has_microdata = 1",
    'rdfa': "has_rdfa = 1",
    'validation_errors': "schema_validation_errors > 0",
    'validation_warnings': "schema_validation_warnings > 0",
    'schema_missing_fields': "schema_validation_errors > 0",

    # Image filters
    'images_over_100kb': """
        EXISTS (
            SELECT 1 FROM images AS img
            WHERE img.session_id = urls.session_id
              AND img.page_url = urls.url
              AND COALESCE(img.file_size, 0) > 102400
        )
    """,
    'missing_alt_text': """
        EXISTS (
            SELECT 1 FROM images AS img
            WHERE img.session_id = urls.session_id
              AND img.page_url = urls.url
              AND img.missing_alt = 1
        )
    """,
    'missing_alt_attribute': """
        EXISTS (
            SELECT 1 FROM images AS img
            WHERE img.session_id = urls.session_id
              AND img.page_url = urls.url
              AND img.missing_alt_attribute = 1
        )
    """,
    'alt_text_over_100_chars': """
        EXISTS (
            SELECT 1 FROM images AS img
            WHERE img.session_id = urls.session_id
              AND img.page_url = urls.url
              AND COALESCE(img.alt_text_length, 0) > 100
        )
    """,
    'missing_size_attributes': """
        EXISTS (
            SELECT 1 FROM images AS img
            WHERE img.session_id = urls.session_id
              AND img.page_url = urls.url
              AND img.missing_size_attributes = 1
        )
    """,

    # Hreflang filters
    'contains_hreflang': """
        EXISTS (
            SELECT 1 FROM hreflang AS h
            WHERE h.session_id = urls.session_id
              AND h.page_url = urls.url
        )
    """,
    'missing_return_links': """
        EXISTS (
            SELECT 1 FROM hreflang AS h
            WHERE h.session_id = urls.session_id
              AND h.page_url = urls.url
              AND h.has_return_link = 0
        )
    """,
    'unlinked_hreflang_url': """
        EXISTS (
            SELECT 1 FROM hreflang AS h
            WHERE h.session_id = urls.session_id
              AND h.page_url = urls.url
              AND h.has_return_link = 0
        )
    """,
    'non_200_hreflang_url': """
        EXISTS (
            SELECT 1 FROM hreflang AS h
            JOIN urls AS target ON target.session_id = h.session_id AND target.url = h.target_url
            WHERE h.session_id = urls.session_id
              AND h.page_url = urls.url
              AND (target.status_code < 200 OR target.status_code >= 300)
        )
    """,
    'amp_validation_errors': f"{ISSUES_TEXT_SQL} LIKE '%amp_validation_errors%'",
    'amp_validation_warnings': f"{ISSUES_TEXT_SQL} LIKE '%amp_validation_warnings%'",

    # Indexability
    'indexable': "indexability = 'Indexable'",
    'non_indexable': "indexability = 'Non-Indexable'",
}

SPECIAL_URL_FILTERS = {
    'self_referencing_canonical',
    'canonicalised',
    'canonical_chain',
    'canonical_loop',
    'canonical_to_non_indexable',
    'canonical_to_non_200',
    'non_200_pagination_url',
    'non_indexable_pagination_url',
    'pagination_url_not_in_anchor',
    'unlinked_pagination_url',
    'inconsistent_language',
    'invalid_hreflang_codes',
    'multiple_hreflang_entries',
    'missing_self_reference',
    'hreflang_not_using_canonical',
    'missing_x_default',
    'valid_amp',
    'non_200_amp_url',
    'missing_non_amp_return',
    'in_sitemap',
    'not_in_sitemap',
    'orphan_urls',
    'non_200_in_sitemap',
    'non_indexable_in_sitemap',
}

SITEMAP_SPECIAL_FILTERS = {
    'in_sitemap',
    'not_in_sitemap',
    'orphan_urls',
    'non_200_in_sitemap',
    'non_indexable_in_sitemap',
}


URL_SORT_COLUMNS = {
    'url': 'url',
    'status_code': 'status_code',
    'title': 'title_1',
    'title_length': 'title_1_length',
    'h1': 'h1_1',
    'h1_length': 'h1_len_1',
    'word_count': 'word_count',
    'indexability': 'indexability',
    'meta_description_length': 'meta_description_1_length',
    'response_time': 'response_time',
    'crawl_depth': 'crawl_depth',
    'inlinks': 'inlinks',
    'link_score': 'link_score',
    'crawled_at': 'crawled_at',
}


class Database:
    """SQLite database interface for crawler data"""

    def __init__(self, db_path: str = "crawl_data.db"):
        """
        Initialize database connection

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._lock = threading.RLock()
        self._connect()
        self._create_tables()

    def _connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Access columns by name

    def _create_tables(self):
        """Create all tables if they don't exist"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.executescript(SQL_CREATE_TABLES)
            self.conn.commit()

    def close(self):
        """Close database connection"""
        with self._lock:
            if self.conn:
                self.conn.close()

    # ========== Session Management ==========

    def create_session(
        self,
        start_url: str,
        max_urls: int = 10000,
        max_depth: Optional[int] = None,
        respect_robots: bool = True,
        user_agent: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> CrawlSession:
        """Create a new crawl session"""
        with self._lock:
            session_id = str(uuid.uuid4())
            session = CrawlSession(
                session_id=session_id,
                start_url=start_url,
                started_at=datetime.now(),
                max_urls=max_urls,
                max_depth=max_depth,
                respect_robots=respect_robots,
                user_agent=user_agent,
                config=config
            )

            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (
                    session_id, start_url, started_at, status,
                    max_urls, max_depth, respect_robots, user_agent, config
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                session.start_url,
                session.started_at.isoformat(),
                session.status,
                session.max_urls,
                session.max_depth,
                1 if session.respect_robots else 0,
                session.user_agent,
                json.dumps(session.config) if session.config else None
            ))
            self.conn.commit()

            return session

    def get_session(self, session_id: str) -> Optional[CrawlSession]:
        """Get session by ID"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()

            if row:
                return CrawlSession.from_dict(dict(row))
            return None

    def get_all_sessions(self, limit: int = 20) -> List[CrawlSession]:
        """Get all sessions ordered by most recent"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [CrawlSession.from_dict(dict(row)) for row in rows]

    def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        total_urls: Optional[int] = None,
        crawled_urls: Optional[int] = None,
        failed_urls: Optional[int] = None
    ):
        """Update session statistics"""
        with self._lock:
            updates = []
            values = []

            if status:
                updates.append("status = ?")
                values.append(status)
                if status == "completed":
                    updates.append("completed_at = ?")
                    values.append(datetime.now().isoformat())

            if total_urls is not None:
                updates.append("total_urls = ?")
                values.append(total_urls)

            if crawled_urls is not None:
                updates.append("crawled_urls = ?")
                values.append(crawled_urls)

            if failed_urls is not None:
                updates.append("failed_urls = ?")
                values.append(failed_urls)

            if updates:
                values.append(session_id)
                query = f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?"
                cursor = self.conn.cursor()
                cursor.execute(query, values)
                self.conn.commit()

    # ========== URL Storage ==========

    def save_url(self, session_id: str, url_data: CrawledURL):
        """Save or update URL data"""
        with self._lock:
            cursor = self.conn.cursor()

            # Convert boolean fields to integers for SQLite
            data_dict = url_data.to_dict()
            data_dict['session_id'] = session_id

            # Convert booleans
            bool_fields = [
                'hsts', 'csp', 'x_content_type_options', 'x_frame_options',
                'referrer_policy', 'has_json_ld', 'has_microdata', 'has_rdfa',
                'is_https', 'has_mixed_content', 'has_insecure_forms',
                'has_parameters', 'has_non_ascii', 'has_underscores', 'has_uppercase'
            ]
            for field in bool_fields:
                if field in data_dict and isinstance(data_dict[field], bool):
                    data_dict[field] = 1 if data_dict[field] else 0

            # Build INSERT OR REPLACE query
            columns = list(data_dict.keys())
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join(columns)

            query = f"""
                INSERT OR REPLACE INTO urls ({column_names})
                VALUES ({placeholders})
            """

            values = [data_dict.get(col) for col in columns]

            cursor.execute(query, values)
            self.conn.commit()

    def get_url(self, session_id: str, url: str) -> Optional[CrawledURL]:
        """Get URL data by URL"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM urls WHERE session_id = ? AND url = ?",
                (session_id, url)
            )
            row = cursor.fetchone()

            if row:
                return CrawledURL.from_dict(dict(row))
            return None

    def get_all_urls(
        self,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[CrawledURL]:
        """Get all URLs for a session"""
        with self._lock:
            cursor = self.conn.cursor()

            query = "SELECT * FROM urls WHERE session_id = ? ORDER BY crawled_at DESC"
            if limit:
                query += f" LIMIT {limit} OFFSET {offset}"

            cursor.execute(query, (session_id,))
            rows = cursor.fetchall()

            return [CrawledURL.from_dict(dict(row)) for row in rows]

    def query_urls(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        filter_name: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = 'crawled_at',
        sort_order: str = 'desc'
    ) -> Dict[str, Any]:
        """Query URLs with filtering, search, sorting, and pagination metadata."""
        with self._lock:
            normalized_search = (search or '').strip().lower()
            if filter_name in SPECIAL_URL_FILTERS:
                urls = self.get_all_urls(session_id)
                sitemap_urls = None
                if filter_name in SITEMAP_SPECIAL_FILTERS:
                    sitemap_urls = self.get_sitemap_urls(session_id)
                filtered_urls = self._apply_special_filter(urls, filter_name, sitemap_urls=sitemap_urls)

                if normalized_search:
                    filtered_urls = [
                        row for row in filtered_urls
                        if self._row_matches_search(row, normalized_search)
                    ]

                filtered_urls = self._sort_rows_in_memory(filtered_urls, sort_by, sort_order)
                paged_urls = filtered_urls[offset:offset + limit]

                return {
                    'urls': paged_urls,
                    'total': self.get_url_count(session_id),
                    'filtered_total': len(filtered_urls),
                }

            cursor = self.conn.cursor()

            where_clauses = ["session_id = ?"]
            params: List[Any] = [session_id]

            if filter_name:
                filter_clause = URL_FILTER_QUERIES.get(filter_name)
                if not filter_clause:
                    return {
                        'urls': [],
                        'total': self.get_url_count(session_id),
                        'filtered_total': 0,
                    }
                where_clauses.append(f"({filter_clause})")

            if normalized_search:
                search_like = f"%{normalized_search}%"
                where_clauses.append(
                    "(url LIKE ? OR title_1 LIKE ? OR h1_1 LIKE ? OR meta_description_1 LIKE ?)"
                )
                params.extend([search_like] * 4)

            where_sql = " AND ".join(where_clauses)
            count_query = f"SELECT COUNT(*) FROM urls WHERE {where_sql}"
            cursor.execute(count_query, params)
            filtered_total = cursor.fetchone()[0]

            sort_column = URL_SORT_COLUMNS.get(sort_by, 'crawled_at')
            normalized_order = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

            query = f"""
                SELECT * FROM urls
                WHERE {where_sql}
                ORDER BY
                    CASE WHEN {sort_column} IS NULL THEN 1 ELSE 0 END ASC,
                    {sort_column} {normalized_order},
                    url ASC
                LIMIT ? OFFSET ?
            """
            query_params = [*params, limit, offset]
            cursor.execute(query, query_params)
            rows = cursor.fetchall()

            return {
                'urls': [CrawledURL.from_dict(dict(row)) for row in rows],
                'total': self.get_url_count(session_id),
                'filtered_total': filtered_total,
            }

    @staticmethod
    def _row_matches_search(row: CrawledURL, normalized_search: str) -> bool:
        haystacks = [
            row.url or "",
            row.title_1 or "",
            row.h1_1 or "",
            row.meta_description_1 or "",
        ]
        return any(normalized_search in text.lower() for text in haystacks)

    @staticmethod
    def _sort_rows_in_memory(
        rows: List[CrawledURL],
        sort_by: str,
        sort_order: str,
    ) -> List[CrawledURL]:
        sort_column = URL_SORT_COLUMNS.get(sort_by, 'crawled_at')
        reverse = sort_order.lower() == 'desc'

        with_value = [row for row in rows if getattr(row, sort_column, None) is not None]
        without_value = [row for row in rows if getattr(row, sort_column, None) is None]

        # Keep URL ascending as stable tiebreaker, then apply requested ordering.
        with_value.sort(key=lambda row: row.url or "")
        with_value.sort(key=lambda row: getattr(row, sort_column), reverse=reverse)

        without_value.sort(key=lambda row: row.url or "")
        return [*with_value, *without_value]

    @staticmethod
    def _canonical_chain_info(
        start_url: str,
        canonical_map: Dict[str, str],
        urls_by_normalized: Dict[str, CrawledURL],
    ) -> Dict[str, Any]:
        path = [start_url]
        visited = {start_url}
        current = start_url
        hops = 0

        while True:
            target = canonical_map.get(current)
            if not target or target == current:
                return {"hops": hops, "is_loop": False, "path": path}

            path.append(target)
            hops += 1

            if target in visited:
                return {"hops": hops, "is_loop": True, "path": path}

            visited.add(target)

            if target not in urls_by_normalized:
                return {"hops": hops, "is_loop": False, "path": path}

            current = target
            if hops >= 50:
                return {"hops": hops, "is_loop": True, "path": path}

    @staticmethod
    def _pagination_targets(row: CrawledURL) -> List[str]:
        targets: List[str] = []
        for raw_target in [row.rel_next_1, row.rel_prev_1, row.http_rel_next_1, row.http_rel_prev_1]:
            candidate = (raw_target or "").strip()
            if not candidate:
                continue
            targets.append(normalize_url(urljoin(row.url, candidate)))
        return targets

    @staticmethod
    def _anchor_targets(row: CrawledURL) -> set[str]:
        html = row.html_content or ""
        if not html:
            return set()

        soup = BeautifulSoup(html, 'lxml')
        targets: set[str] = set()
        for tag in soup.find_all(['a', 'area'], href=True):
            href = (tag.get('href') or '').strip()
            if not href or href.startswith('#'):
                continue
            targets.add(normalize_url(urljoin(row.url, href)))
        return targets

    @staticmethod
    def _hreflang_entries(row: CrawledURL) -> List[Dict[str, str]]:
        raw = row.hreflang_data
        if not raw:
            return []

        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return []

        if not isinstance(parsed, list):
            return []

        entries: List[Dict[str, str]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            hreflang = (item.get("hreflang") or "").strip().lower()
            target_url = (item.get("url") or item.get("target_url") or "").strip()
            if not hreflang or not target_url:
                continue
            language = (item.get("language") or hreflang.split("-")[0]).strip().lower()
            entries.append({
                "hreflang": hreflang,
                "language": language,
                "target": normalize_url(urljoin(row.url, target_url)),
            })
        return entries

    @classmethod
    def _apply_special_filter(
        cls,
        rows: List[CrawledURL],
        filter_name: str,
        sitemap_urls: Optional[set[str]] = None,
    ) -> List[CrawledURL]:
        urls_by_normalized: Dict[str, CrawledURL] = {}
        canonical_map: Dict[str, str] = {}
        amp_sources_by_target: Dict[str, set[str]] = {}

        for row in rows:
            normalized_url = normalize_url(row.url)
            urls_by_normalized[normalized_url] = row
            canonical = (row.canonical_link_element_1 or "").strip()
            if canonical:
                canonical_map[normalized_url] = normalize_url(urljoin(row.url, canonical))
            amp_link = (row.amphtml_link or "").strip()
            if amp_link:
                normalized_amp_target = normalize_url(urljoin(row.url, amp_link))
                amp_sources_by_target.setdefault(normalized_amp_target, set()).add(normalized_url)

        filtered: List[CrawledURL] = []
        for row in rows:
            normalized_url = normalize_url(row.url)

            if filter_name in SITEMAP_SPECIAL_FILTERS:
                sitemap_set = sitemap_urls or set()
                in_sitemap = normalized_url in sitemap_set
                status_code = row.status_code or 0
                is_non_200 = not (200 <= status_code < 300)
                is_non_indexable = (row.indexability or "").lower() != "indexable"
                is_orphan = (row.inlinks or 0) == 0

                include_row = (
                    (filter_name == 'in_sitemap' and in_sitemap) or
                    (filter_name == 'not_in_sitemap' and not in_sitemap) or
                    (filter_name == 'orphan_urls' and in_sitemap and is_orphan) or
                    (filter_name == 'non_200_in_sitemap' and in_sitemap and is_non_200) or
                    (filter_name == 'non_indexable_in_sitemap' and in_sitemap and is_non_indexable)
                )
                if include_row:
                    filtered.append(row)
                continue

            if filter_name in {
                'inconsistent_language',
                'invalid_hreflang_codes',
                'multiple_hreflang_entries',
                'missing_self_reference',
                'hreflang_not_using_canonical',
                'missing_x_default',
            }:
                entries = cls._hreflang_entries(row)
                if not entries:
                    continue

                include_row = False
                if filter_name == 'missing_x_default':
                    include_row = not any(entry["hreflang"] == "x-default" for entry in entries)
                elif filter_name == 'missing_self_reference':
                    include_row = not any(entry["target"] == normalized_url for entry in entries)
                elif filter_name == 'multiple_hreflang_entries':
                    seen_codes: set[str] = set()
                    include_row = False
                    for entry in entries:
                        code = entry["hreflang"]
                        if code in seen_codes:
                            include_row = True
                            break
                        seen_codes.add(code)
                elif filter_name == 'invalid_hreflang_codes':
                    valid_languages = {
                        'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'zh', 'ko', 'ar', 'nl', 'pl', 'tr', 'x'
                    }
                    include_row = any(entry["language"] not in valid_languages for entry in entries)
                elif filter_name == 'inconsistent_language':
                    seen_codes: Dict[str, str] = {}
                    for entry in entries:
                        code = entry["hreflang"]
                        lang_from_code = code.split("-")[0]
                        if code == "x-default":
                            continue
                        if entry["language"] != lang_from_code:
                            include_row = True
                            break
                        if code in seen_codes and seen_codes[code] != entry["target"]:
                            include_row = True
                            break
                        seen_codes[code] = entry["target"]
                elif filter_name == 'hreflang_not_using_canonical':
                    canonical_target = canonical_map.get(normalized_url)
                    include_row = bool(canonical_target and canonical_target != normalized_url)

                if include_row:
                    filtered.append(row)
                continue

            if filter_name in {'valid_amp', 'non_200_amp_url', 'missing_non_amp_return'}:
                include_row = False
                if filter_name in {'valid_amp', 'non_200_amp_url'}:
                    amp_link = (row.amphtml_link or "").strip()
                    if amp_link:
                        amp_target = normalize_url(urljoin(row.url, amp_link))
                        amp_row = urls_by_normalized.get(amp_target)
                        if amp_row:
                            amp_status = amp_row.status_code or 0
                            amp_canonical = (amp_row.canonical_link_element_1 or "").strip()
                            amp_canonical_target = normalize_url(urljoin(amp_row.url, amp_canonical)) if amp_canonical else ""
                            if filter_name == 'non_200_amp_url':
                                include_row = bool(amp_status and not (200 <= amp_status < 300))
                            else:
                                include_row = bool(
                                    200 <= amp_status < 300 and
                                    amp_canonical_target == normalized_url
                                )
                else:
                    source_candidates = amp_sources_by_target.get(normalized_url, set())
                    if source_candidates:
                        canonical_target = canonical_map.get(normalized_url)
                        include_row = canonical_target not in source_candidates

                if include_row:
                    filtered.append(row)
                continue

            if filter_name in {
                'non_200_pagination_url',
                'non_indexable_pagination_url',
                'pagination_url_not_in_anchor',
                'unlinked_pagination_url',
            }:
                pagination_targets = cls._pagination_targets(row)
                if not pagination_targets:
                    continue

                include_row = False
                if filter_name == 'pagination_url_not_in_anchor':
                    anchor_targets = cls._anchor_targets(row)
                    for target_url in pagination_targets:
                        if target_url not in anchor_targets:
                            include_row = True
                            break
                else:
                    for target_url in pagination_targets:
                        target_row = urls_by_normalized.get(target_url)
                        if not target_row:
                            continue
                        if filter_name == 'non_200_pagination_url':
                            status_code = target_row.status_code or 0
                            if status_code and not (200 <= status_code < 300):
                                include_row = True
                                break
                        elif filter_name == 'non_indexable_pagination_url':
                            if (target_row.indexability or "").lower() != "indexable":
                                include_row = True
                                break
                        elif filter_name == 'unlinked_pagination_url':
                            if (target_row.inlinks or 0) == 0:
                                include_row = True
                                break

                if include_row:
                    filtered.append(row)
                continue

            canonical = (row.canonical_link_element_1 or "").strip()
            if not canonical:
                continue

            normalized_canonical = normalize_url(urljoin(row.url, canonical))

            if filter_name == 'self_referencing_canonical':
                if normalized_canonical == normalized_url:
                    filtered.append(row)
                continue

            if filter_name == 'canonicalised':
                if normalized_canonical != normalized_url:
                    filtered.append(row)
                continue

            if filter_name in {'canonical_to_non_indexable', 'canonical_to_non_200'}:
                if normalized_canonical == normalized_url:
                    continue
                target_row = urls_by_normalized.get(normalized_canonical)
                if not target_row:
                    continue
                if filter_name == 'canonical_to_non_indexable':
                    if (target_row.indexability or "").lower() != "indexable":
                        filtered.append(row)
                else:
                    target_status = target_row.status_code or 0
                    if target_status and not (200 <= target_status < 300):
                        filtered.append(row)
                continue

            chain_info = cls._canonical_chain_info(
                normalized_url,
                canonical_map,
                urls_by_normalized,
            )
            if filter_name == 'canonical_chain':
                if chain_info["hops"] >= 2 and not chain_info["is_loop"]:
                    filtered.append(row)
            elif filter_name == 'canonical_loop':
                if chain_info["is_loop"]:
                    filtered.append(row)

        return filtered

    def get_urls_by_filter(
        self,
        session_id: str,
        filter_name: str,
        limit: Optional[int] = None
    ) -> List[CrawledURL]:
        """
        Get URLs matching a specific filter

        Filter names match Screaming Frog filters (e.g., 'missing_title', 'noindex', etc.)
        """
        result = self.query_urls(
            session_id=session_id,
            limit=limit or 10000,
            offset=0,
            filter_name=filter_name,
        )
        return result['urls']

    def get_url_count(self, session_id: str) -> int:
        """Get total URL count for session"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM urls WHERE session_id = ?", (session_id,))
            return cursor.fetchone()[0]

    # ========== Image Storage ==========

    def save_image(self, session_id: str, image: ImageData):
        """Save image data"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO images (
                    session_id, page_url, image_url, alt_text, alt_text_length,
                    width, height, file_size, missing_alt, missing_alt_attribute,
                    missing_size_attributes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, image.page_url, image.image_url, image.alt_text,
                image.alt_text_length, image.width, image.height, image.file_size,
                1 if image.missing_alt else 0,
                1 if image.missing_alt_attribute else 0,
                1 if image.missing_size_attributes else 0
            ))
            self.conn.commit()

    def get_images(self, session_id: str, page_url: Optional[str] = None) -> List[ImageData]:
        """Get images for a session or specific page"""
        with self._lock:
            cursor = self.conn.cursor()

            if page_url:
                cursor.execute(
                    "SELECT * FROM images WHERE session_id = ? AND page_url = ?",
                    (session_id, page_url)
                )
            else:
                cursor.execute("SELECT * FROM images WHERE session_id = ?", (session_id,))

            rows = cursor.fetchall()
            result = []
            for row in rows:
                row_dict = dict(row)
                row_dict.pop('id', None)
                row_dict.pop('session_id', None)
                row_dict['url'] = row_dict.get('image_url')
                result.append(ImageData(**row_dict))
            return result

    # ========== Link Storage ==========

    def save_link(self, session_id: str, link: LinkData):
        """Save link relationship with normalized URLs for consistent matching"""
        with self._lock:
            cursor = self.conn.cursor()
            normalized_source = normalize_url(link.source_url)
            normalized_target = normalize_url(link.target_url)
            cursor.execute("""
                INSERT INTO links (
                    session_id, source_url, target_url, anchor_text,
                    is_internal, is_nofollow, link_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, normalized_source, normalized_target, link.anchor_text,
                1 if link.is_internal else 0,
                1 if link.is_nofollow else 0,
                link.link_type
            ))
            self.conn.commit()

    def get_links(
        self,
        session_id: str,
        source_url: Optional[str] = None,
        target_url: Optional[str] = None
    ) -> List[LinkData]:
        """Get links by source or target URL (uses normalized URL for lookup)"""
        with self._lock:
            cursor = self.conn.cursor()

            if source_url:
                normalized_source = normalize_url(source_url)
                cursor.execute(
                    "SELECT * FROM links WHERE session_id = ? AND source_url = ?",
                    (session_id, normalized_source)
                )
            elif target_url:
                normalized_target = normalize_url(target_url)
                cursor.execute(
                    "SELECT * FROM links WHERE session_id = ? AND target_url = ?",
                    (session_id, normalized_target)
                )
            else:
                cursor.execute("SELECT * FROM links WHERE session_id = ?", (session_id,))

            rows = cursor.fetchall()
            result = []
            for row in rows:
                row_dict = dict(row)
                row_dict.pop('id', None)
                row_dict.pop('session_id', None)
                result.append(LinkData(**row_dict))
            return result

    # ========== Hreflang Storage ==========

    def save_hreflang(self, session_id: str, hreflang: HreflangData):
        """Save hreflang alternate language relationship."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO hreflang (
                    session_id, page_url, hreflang, language, region,
                    target_url, source, has_return_link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                hreflang.page_url,
                hreflang.hreflang,
                hreflang.language,
                hreflang.region,
                hreflang.target_url,
                hreflang.source,
                1 if hreflang.has_return_link else 0
            ))
            self.conn.commit()

    def get_hreflang(self, session_id: str, page_url: Optional[str] = None) -> List[HreflangData]:
        """Get hreflang rows for a session or a specific page."""
        with self._lock:
            cursor = self.conn.cursor()

            if page_url:
                cursor.execute(
                    "SELECT * FROM hreflang WHERE session_id = ? AND page_url = ? ORDER BY page_url, hreflang",
                    (session_id, page_url)
                )
            else:
                cursor.execute(
                    "SELECT * FROM hreflang WHERE session_id = ? ORDER BY page_url, hreflang",
                    (session_id,)
                )

            rows = cursor.fetchall()
            result = []
            for row in rows:
                row_dict = dict(row)
                row_dict.pop('id', None)
                row_dict.pop('session_id', None)
                row_dict['has_return_link'] = bool(row_dict.get('has_return_link'))
                result.append(HreflangData(**row_dict))
            return result

    # ========== Sitemap URL Storage ==========

    def save_sitemap_urls(self, session_id: str, urls: List[str]):
        """Persist discovered sitemap URLs for a crawl session."""
        if not urls:
            return

        normalized_urls = {normalize_url(url) for url in urls if url}
        if not normalized_urls:
            return

        with self._lock:
            cursor = self.conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO sitemap_urls (session_id, url) VALUES (?, ?)",
                [(session_id, url) for url in sorted(normalized_urls)],
            )
            self.conn.commit()

    def get_sitemap_urls(self, session_id: str) -> set[str]:
        """Get normalized sitemap URLs for a crawl session."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT url FROM sitemap_urls WHERE session_id = ?", (session_id,))
            rows = cursor.fetchall()
            return {row["url"] for row in rows}

    # ========== Issue Storage ==========

    def save_issue(self, session_id: str, issue: IssueReport):
        """Save an issue/error/warning"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO issues (
                    session_id, url, issue_type, issue_code, severity,
                    message, details, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, issue.url, issue.issue_type, issue.issue_code,
                issue.severity, issue.message, issue.details,
                issue.detected_at.isoformat() if issue.detected_at else datetime.now().isoformat()
            ))
            self.conn.commit()

    def get_issues(
        self,
        session_id: str,
        issue_type: Optional[str] = None,
        url: Optional[str] = None
    ) -> List[IssueReport]:
        """Get issues for a session"""
        with self._lock:
            cursor = self.conn.cursor()

            query = "SELECT * FROM issues WHERE session_id = ?"
            params = [session_id]

            if issue_type:
                query += " AND issue_type = ?"
                params.append(issue_type)

            if url:
                query += " AND url = ?"
                params.append(url)

            query += " ORDER BY severity DESC, detected_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [IssueReport(**dict(row)) for row in rows]

    # ========== Page Audit Notes ==========

    def upsert_page_audit_note(
        self,
        session_id: str,
        url: str,
        target_keyword: Optional[str] = None,
        ai_summary: Optional[str] = None,
        ai_data: Optional[Dict[str, Any]] = None
    ):
        """Create or update stored page-level audit notes / insights."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO page_audit_notes (
                    session_id, url, target_keyword, ai_summary, ai_data, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, url) DO UPDATE SET
                    target_keyword = COALESCE(excluded.target_keyword, page_audit_notes.target_keyword),
                    ai_summary = COALESCE(excluded.ai_summary, page_audit_notes.ai_summary),
                    ai_data = COALESCE(excluded.ai_data, page_audit_notes.ai_data),
                    updated_at = excluded.updated_at
            """, (
                session_id,
                url,
                target_keyword,
                ai_summary,
                json.dumps(ai_data) if ai_data is not None else None,
                datetime.now().isoformat()
            ))
            self.conn.commit()

    def get_page_audit_note(self, session_id: str, url: str) -> Optional[Dict[str, Any]]:
        """Get stored notes / cached insights for a page."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM page_audit_notes WHERE session_id = ? AND url = ?",
                (session_id, url)
            )
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data.pop('id', None)
            if data.get('ai_data'):
                data['ai_data'] = json.loads(data['ai_data'])
            return data

    # ========== Fix Queue ==========

    def upsert_fix_queue_item(
        self,
        session_id: str,
        url: str,
        issue_code: Optional[str] = None,
        issue_label: Optional[str] = None,
        priority: Optional[str] = None,
        status: str = "queued",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a fix queue item for a URL / issue."""
        with self._lock:
            cursor = self.conn.cursor()
            normalized_issue_code = issue_code.strip() if issue_code else ""
            cursor.execute("""
                INSERT INTO fix_queue (
                    session_id, url, issue_code, issue_label, priority, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, url, issue_code) DO UPDATE SET
                    issue_label = COALESCE(excluded.issue_label, fix_queue.issue_label),
                    priority = COALESCE(excluded.priority, fix_queue.priority),
                    status = COALESCE(excluded.status, fix_queue.status),
                    notes = COALESCE(excluded.notes, fix_queue.notes),
                    updated_at = excluded.updated_at
            """, (
                session_id,
                url,
                normalized_issue_code,
                issue_label,
                priority,
                status,
                notes,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ))
            self.conn.commit()

            cursor.execute("""
                SELECT * FROM fix_queue
                WHERE session_id = ? AND url = ? AND issue_code = ?
            """, (session_id, url, normalized_issue_code))
            row = cursor.fetchone()
            return dict(row) if row else {}

    def get_fix_queue(
        self,
        session_id: str,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """List queue items for a session."""
        with self._lock:
            cursor = self.conn.cursor()
            query = "SELECT * FROM fix_queue WHERE session_id = ?"
            params: List[Any] = [session_id]
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY CASE status WHEN 'done' THEN 2 WHEN 'in_progress' THEN 0 ELSE 1 END, priority DESC, updated_at DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_fix_queue_item(
        self,
        item_id: int,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update queue item fields."""
        with self._lock:
            updates = []
            values: List[Any] = []
            if status is not None:
                updates.append("status = ?")
                values.append(status)
            if notes is not None:
                updates.append("notes = ?")
                values.append(notes)
            if priority is not None:
                updates.append("priority = ?")
                values.append(priority)
            if not updates:
                return None
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(item_id)
            cursor = self.conn.cursor()
            cursor.execute(f"UPDATE fix_queue SET {', '.join(updates)} WHERE id = ?", values)
            self.conn.commit()
            cursor.execute("SELECT * FROM fix_queue WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_fix_queue_item(self, item_id: int) -> None:
        """Delete a queue item."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM fix_queue WHERE id = ?", (item_id,))
            self.conn.commit()

    # ========== Statistics ==========

    def get_stats(self, session_id: str) -> Dict[str, Any]:
        """Get crawl statistics"""
        with self._lock:
            cursor = self.conn.cursor()

            stats = {
                'total_urls': 0,
                'status_codes': {},
                'indexable_count': 0,
                'non_indexable_count': 0,
                'issues_by_type': {},
                'avg_response_time': 0,
                'avg_word_count': 0,
            }

            cursor.execute("SELECT COUNT(*) FROM urls WHERE session_id = ?", (session_id,))
            stats['total_urls'] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT status_code, COUNT(*) as count
                FROM urls
                WHERE session_id = ?
                GROUP BY status_code
            """, (session_id,))
            for row in cursor.fetchall():
                stats['status_codes'][row[0]] = row[1]

            cursor.execute("""
                SELECT indexability, COUNT(*) as count
                FROM urls
                WHERE session_id = ?
                GROUP BY indexability
            """, (session_id,))
            for row in cursor.fetchall():
                if row[0] == 'Indexable':
                    stats['indexable_count'] = row[1]
                else:
                    stats['non_indexable_count'] = row[1]

            cursor.execute("""
                SELECT issue_type, COUNT(*) as count
                FROM issues
                WHERE session_id = ?
                GROUP BY issue_type
            """, (session_id,))
            for row in cursor.fetchall():
                stats['issues_by_type'][row[0]] = row[1]

            cursor.execute("""
                SELECT AVG(response_time)
                FROM urls
                WHERE session_id = ? AND response_time > 0
            """, (session_id,))
            result = cursor.fetchone()[0]
            stats['avg_response_time'] = round(result, 3) if result else 0

            cursor.execute("""
                SELECT AVG(word_count)
                FROM urls
                WHERE session_id = ? AND word_count > 0
            """, (session_id,))
            result = cursor.fetchone()[0]
            stats['avg_word_count'] = int(result) if result else 0

            return stats
