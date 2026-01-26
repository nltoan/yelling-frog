"""
Database Layer
SQLite database operations for storing crawl data
"""
import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import uuid

from .models import (
    CrawledURL, ImageData, LinkData, HreflangData,
    CrawlSession, IssueReport, SQL_CREATE_TABLES
)


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
        self._connect()
        self._create_tables()

    def _connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Access columns by name

    def _create_tables(self):
        """Create all tables if they don't exist"""
        cursor = self.conn.cursor()
        cursor.executescript(SQL_CREATE_TABLES)
        self.conn.commit()

    def close(self):
        """Close database connection"""
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
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()

        if row:
            return CrawlSession.from_dict(dict(row))
        return None

    def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        total_urls: Optional[int] = None,
        crawled_urls: Optional[int] = None,
        failed_urls: Optional[int] = None
    ):
        """Update session statistics"""
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
        cursor = self.conn.cursor()

        query = "SELECT * FROM urls WHERE session_id = ? ORDER BY crawled_at DESC"
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        cursor.execute(query, (session_id,))
        rows = cursor.fetchall()

        return [CrawledURL.from_dict(dict(row)) for row in rows]

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
        cursor = self.conn.cursor()

        # Build filter query based on filter name
        filter_queries = {
            # Title filters
            'missing_title': "title_1 IS NULL OR title_1 = ''",
            'title_over_60_chars': "title_1_length > 60",
            'title_below_30_chars': "title_1_length < 30 AND title_1_length > 0",
            'title_over_568_pixels': "title_1_pixel_width > 568",
            'title_below_200_pixels': "title_1_pixel_width < 200 AND title_1_pixel_width > 0",
            'multiple_titles': "title_2 IS NOT NULL",

            # Meta description filters
            'missing_meta_description': "meta_description_1 IS NULL OR meta_description_1 = ''",
            'meta_description_over_155_chars': "meta_description_1_length > 155",
            'meta_description_below_70_chars': "meta_description_1_length < 70 AND meta_description_1_length > 0",
            'multiple_meta_descriptions': "meta_description_2 IS NOT NULL",

            # Heading filters
            'missing_h1': "h1_1 IS NULL OR h1_1 = ''",
            'h1_over_70_chars': "h1_len_1 > 70",
            'multiple_h1': "h1_2 IS NOT NULL",
            'missing_h2': "h2_1 IS NULL OR h2_1 = ''",

            # Content filters
            'low_content': "word_count < 200",
            'low_text_ratio': "text_ratio < 10",

            # Directive filters
            'noindex': "(meta_robots_1 LIKE '%noindex%' OR meta_robots_2 LIKE '%noindex%' OR x_robots_tag_1 LIKE '%noindex%' OR x_robots_tag_2 LIKE '%noindex%')",
            'nofollow': "(meta_robots_1 LIKE '%nofollow%' OR meta_robots_2 LIKE '%nofollow%')",

            # Canonical filters
            'contains_canonical': "canonical_link_element_1 IS NOT NULL",
            'missing_canonical': "canonical_link_element_1 IS NULL",

            # Status code filters
            'success_2xx': "status_code BETWEEN 200 AND 299",
            'redirection_3xx': "status_code BETWEEN 300 AND 399",
            'client_error_4xx': "status_code BETWEEN 400 AND 499",
            'server_error_5xx': "status_code BETWEEN 500 AND 599",

            # Security filters
            'http_urls': "is_https = 0",
            'https_urls': "is_https = 1",
            'mixed_content': "has_mixed_content = 1",
            'insecure_forms': "has_insecure_forms = 1",
            'missing_hsts': "is_https = 1 AND hsts = 0",

            # URL filters
            'url_over_115_chars': "url_length > 115",
            'url_with_parameters': "has_parameters = 1",
            'url_with_underscores': "has_underscores = 1",
            'url_with_uppercase': "has_uppercase = 1",
            'url_with_non_ascii': "has_non_ascii = 1",

            # Indexability
            'indexable': "indexability = 'Indexable'",
            'non_indexable': "indexability = 'Non-Indexable'",
        }

        where_clause = filter_queries.get(filter_name)
        if not where_clause:
            return []

        query = f"SELECT * FROM urls WHERE session_id = ? AND ({where_clause})"
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, (session_id,))
        rows = cursor.fetchall()

        return [CrawledURL.from_dict(dict(row)) for row in rows]

    def get_url_count(self, session_id: str) -> int:
        """Get total URL count for session"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM urls WHERE session_id = ?", (session_id,))
        return cursor.fetchone()[0]

    # ========== Image Storage ==========

    def save_image(self, session_id: str, image: ImageData):
        """Save image data"""
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
        cursor = self.conn.cursor()

        if page_url:
            cursor.execute(
                "SELECT * FROM images WHERE session_id = ? AND page_url = ?",
                (session_id, page_url)
            )
        else:
            cursor.execute("SELECT * FROM images WHERE session_id = ?", (session_id,))

        rows = cursor.fetchall()
        return [ImageData(**dict(row)) for row in rows]

    # ========== Link Storage ==========

    def save_link(self, session_id: str, link: LinkData):
        """Save link relationship"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO links (
                session_id, source_url, target_url, anchor_text,
                is_internal, is_nofollow, link_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, link.source_url, link.target_url, link.anchor_text,
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
        """Get links by source or target URL"""
        cursor = self.conn.cursor()

        if source_url:
            cursor.execute(
                "SELECT * FROM links WHERE session_id = ? AND source_url = ?",
                (session_id, source_url)
            )
        elif target_url:
            cursor.execute(
                "SELECT * FROM links WHERE session_id = ? AND target_url = ?",
                (session_id, target_url)
            )
        else:
            cursor.execute("SELECT * FROM links WHERE session_id = ?", (session_id,))

        rows = cursor.fetchall()
        return [LinkData(**dict(row)) for row in rows]

    # ========== Issue Storage ==========

    def save_issue(self, session_id: str, issue: IssueReport):
        """Save an issue/error/warning"""
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

    # ========== Statistics ==========

    def get_stats(self, session_id: str) -> Dict[str, Any]:
        """Get crawl statistics"""
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

        # Total URLs
        cursor.execute("SELECT COUNT(*) FROM urls WHERE session_id = ?", (session_id,))
        stats['total_urls'] = cursor.fetchone()[0]

        # Status code distribution
        cursor.execute("""
            SELECT status_code, COUNT(*) as count
            FROM urls
            WHERE session_id = ?
            GROUP BY status_code
        """, (session_id,))
        for row in cursor.fetchall():
            stats['status_codes'][row[0]] = row[1]

        # Indexability
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

        # Issues by type
        cursor.execute("""
            SELECT issue_type, COUNT(*) as count
            FROM issues
            WHERE session_id = ?
            GROUP BY issue_type
        """, (session_id,))
        for row in cursor.fetchall():
            stats['issues_by_type'][row[0]] = row[1]

        # Average response time
        cursor.execute("""
            SELECT AVG(response_time)
            FROM urls
            WHERE session_id = ? AND response_time > 0
        """, (session_id,))
        result = cursor.fetchone()[0]
        stats['avg_response_time'] = round(result, 3) if result else 0

        # Average word count
        cursor.execute("""
            SELECT AVG(word_count)
            FROM urls
            WHERE session_id = ? AND word_count > 0
        """, (session_id,))
        result = cursor.fetchone()[0]
        stats['avg_word_count'] = int(result) if result else 0

        return stats
