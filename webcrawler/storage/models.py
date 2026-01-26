"""
Database Models
Complete data models for all 55+ columns from Screaming Frog spec
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


@dataclass
class CrawledURL:
    """
    Complete data model for a crawled URL with ALL Screaming Frog columns
    """
    # Core URL Data
    url: str
    url_encoded: Optional[str] = None
    content_type: Optional[str] = None
    status_code: Optional[int] = None
    status_text: Optional[str] = None
    indexability: str = "Indexable"  # "Indexable" or "Non-Indexable"
    indexability_status: Optional[str] = None  # Reason if non-indexable
    hash: Optional[str] = None  # MD5 hash for duplicate detection

    # Page Title Data
    title_1: Optional[str] = None
    title_1_length: int = 0
    title_1_pixel_width: int = 0
    title_2: Optional[str] = None
    title_2_length: int = 0

    # Meta Description Data
    meta_description_1: Optional[str] = None
    meta_description_1_length: int = 0
    meta_description_1_pixel_width: int = 0
    meta_description_2: Optional[str] = None

    # Meta Keywords
    meta_keywords_1: Optional[str] = None
    meta_keywords_1_length: int = 0

    # Heading Data (H1-H6, 2 instances each)
    h1_1: Optional[str] = None
    h1_len_1: int = 0
    h1_2: Optional[str] = None
    h1_len_2: int = 0
    h2_1: Optional[str] = None
    h2_len_1: int = 0
    h2_2: Optional[str] = None
    h2_len_2: int = 0
    h3_1: Optional[str] = None
    h3_len_1: int = 0
    h3_2: Optional[str] = None
    h3_len_2: int = 0
    h4_1: Optional[str] = None
    h4_len_1: int = 0
    h4_2: Optional[str] = None
    h4_len_2: int = 0
    h5_1: Optional[str] = None
    h5_len_1: int = 0
    h5_2: Optional[str] = None
    h5_len_2: int = 0
    h6_1: Optional[str] = None
    h6_len_1: int = 0
    h6_2: Optional[str] = None
    h6_len_2: int = 0

    # Directives
    meta_robots_1: Optional[str] = None
    meta_robots_2: Optional[str] = None
    x_robots_tag_1: Optional[str] = None
    x_robots_tag_2: Optional[str] = None
    meta_refresh_1: Optional[str] = None

    # Canonical & Pagination
    canonical_link_element_1: Optional[str] = None
    canonical_link_element_2: Optional[str] = None
    rel_next_1: Optional[str] = None
    rel_prev_1: Optional[str] = None
    http_rel_next_1: Optional[str] = None
    http_rel_prev_1: Optional[str] = None

    # Size & Performance
    size: int = 0  # Bytes
    transferred: int = 0  # Actual bytes transferred
    response_time: float = 0.0  # Seconds
    ttfb: float = 0.0  # Time to first byte
    last_modified: Optional[str] = None

    # Content Analysis
    word_count: int = 0
    sentence_count: int = 0
    avg_words_per_sentence: float = 0.0
    text_ratio: float = 0.0  # Percentage
    readability: float = 0.0  # Flesch score
    readability_grade: Optional[str] = None  # "Hard", "Normal", etc.
    closest_similarity_match: Optional[str] = None  # URL of closest match
    closest_similarity_score: float = 0.0  # Percentage
    no_near_duplicates: int = 0  # Count
    language: Optional[str] = None
    spelling_errors: int = 0
    grammar_errors: int = 0

    # Link Metrics
    crawl_depth: int = 0  # Clicks from start
    folder_depth: int = 0  # URL path depth
    link_score: float = 0.0  # 0-100 PageRank-like score
    inlinks: int = 0  # Total inlinks
    unique_inlinks: int = 0  # Unique inlinks
    unique_js_inlinks: int = 0  # JS-discovered inlinks
    percentage_of_total: float = 0.0  # % of pages linking here
    outlinks: int = 0  # Total outlinks
    unique_outlinks: int = 0  # Unique outlinks
    unique_js_outlinks: int = 0  # JS-discovered outlinks
    external_outlinks: int = 0  # Total external
    unique_external_outlinks: int = 0  # Unique external
    unique_external_js_outlinks: int = 0  # JS-discovered external

    # Redirect Data
    redirect_uri: Optional[str] = None
    redirect_type: Optional[str] = None  # HTTP, Meta Refresh, JavaScript, HSTS
    http_version: str = "HTTP/1.1"
    
    # Additional link elements
    amphtml_link: Optional[str] = None  # AMP version link
    mobile_alternate_link: Optional[str] = None  # Mobile alternate link
    
    # Cookies
    cookies: Optional[str] = None
    
    # Semantic similarity
    closest_semantic_match: Optional[str] = None
    semantic_similarity_score: float = 0.0
    no_semantically_similar: int = 0
    semantic_relevance_score: float = 0.0

    # Security Headers
    hsts: bool = False
    hsts_value: Optional[str] = None
    csp: bool = False
    csp_value: Optional[str] = None
    x_content_type_options: bool = False
    x_frame_options: bool = False
    x_frame_options_value: Optional[str] = None
    referrer_policy: bool = False
    referrer_policy_value: Optional[str] = None

    # Open Graph
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: Optional[str] = None
    og_url: Optional[str] = None

    # Twitter Cards
    twitter_card: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    twitter_image: Optional[str] = None

    # Structured Data
    has_json_ld: bool = False
    has_microdata: bool = False
    has_rdfa: bool = False
    schema_types: Optional[str] = None  # Comma-separated
    schema_validation_errors: int = 0
    schema_validation_warnings: int = 0

    # Security Issues
    is_https: bool = False
    has_mixed_content: bool = False
    has_insecure_forms: bool = False
    unsafe_cross_origin_links: int = 0

    # URL Issues
    url_length: int = 0
    has_parameters: bool = False
    has_non_ascii: bool = False
    has_underscores: bool = False
    has_uppercase: bool = False

    # Technical
    charset: Optional[str] = None
    viewport: Optional[str] = None

    # Timestamps
    crawled_at: Optional[datetime] = None
    discovered_at: Optional[datetime] = None

    # Issue Flags (for quick filtering)
    issues: List[str] = field(default_factory=list)  # List of issue codes

    # Raw data storage (JSON fields)
    raw_headers: Optional[str] = None  # JSON string
    hreflang_data: Optional[str] = None  # JSON string
    structured_data: Optional[str] = None  # JSON string
    html_content: Optional[str] = None  # For duplicate detection

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, (list, dict)):
                data[key] = json.dumps(value)
            else:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawledURL':
        """Create instance from dictionary"""
        # Remove database-specific fields that aren't in the model
        data_copy = data.copy()
        data_copy.pop('id', None)  # Remove auto-increment ID
        data_copy.pop('session_id', None)  # Session ID is not part of the model

        # Parse datetime fields
        if 'crawled_at' in data_copy and isinstance(data_copy['crawled_at'], str):
            data_copy['crawled_at'] = datetime.fromisoformat(data_copy['crawled_at'])
        if 'discovered_at' in data_copy and isinstance(data_copy['discovered_at'], str):
            data_copy['discovered_at'] = datetime.fromisoformat(data_copy['discovered_at'])

        # Parse JSON fields
        if 'issues' in data_copy and isinstance(data_copy['issues'], str):
            data_copy['issues'] = json.loads(data_copy['issues']) if data_copy['issues'] else []

        return cls(**data_copy)


@dataclass
class ImageData:
    """Image resource data"""
    url: str
    page_url: str  # URL of page containing the image
    image_url: str  # Absolute URL of the image
    alt_text: Optional[str] = None
    alt_text_length: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None  # Bytes
    missing_alt: bool = False
    missing_alt_attribute: bool = False
    missing_size_attributes: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass
class LinkData:
    """Link relationship data"""
    source_url: str  # URL containing the link
    target_url: str  # URL being linked to
    anchor_text: Optional[str] = None
    is_internal: bool = True
    is_nofollow: bool = False
    link_type: str = "href"  # href, canonical, redirect, etc.

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass
class HreflangData:
    """Hreflang alternate language data"""
    page_url: str
    hreflang: str  # Language-region code
    language: str  # Language code
    region: Optional[str]  # Region code
    target_url: str
    source: str  # html or http_header
    has_return_link: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass
class CrawlSession:
    """Crawl session metadata"""
    session_id: str
    start_url: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"  # running, paused, completed, failed
    total_urls: int = 0
    crawled_urls: int = 0
    failed_urls: int = 0
    max_urls: int = 10000
    max_depth: Optional[int] = None
    respect_robots: bool = True
    user_agent: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = json.dumps(value)
            else:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlSession':
        if 'started_at' in data and isinstance(data['started_at'], str):
            data['started_at'] = datetime.fromisoformat(data['started_at'])
        if 'completed_at' in data and isinstance(data['completed_at'], str):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        if 'config' in data and isinstance(data['config'], str):
            data['config'] = json.loads(data['config'])
        return cls(**data)


@dataclass
class IssueReport:
    """Issue/error/warning data"""
    session_id: str
    url: str
    issue_type: str  # error, warning, notice
    issue_code: str  # missing_title, broken_link, etc.
    severity: int  # 1=low, 2=medium, 3=high, 4=critical
    message: str
    details: Optional[str] = None
    detected_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            else:
                data[key] = value
        return data


# SQL Schema Definitions
SQL_CREATE_TABLES = """
-- Main URLs table with all columns
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    url TEXT NOT NULL,
    url_encoded TEXT,
    content_type TEXT,
    status_code INTEGER,
    status_text TEXT,
    indexability TEXT DEFAULT 'Indexable',
    indexability_status TEXT,
    hash TEXT,

    -- Title data
    title_1 TEXT,
    title_1_length INTEGER DEFAULT 0,
    title_1_pixel_width INTEGER DEFAULT 0,
    title_2 TEXT,
    title_2_length INTEGER DEFAULT 0,

    -- Meta description
    meta_description_1 TEXT,
    meta_description_1_length INTEGER DEFAULT 0,
    meta_description_1_pixel_width INTEGER DEFAULT 0,
    meta_description_2 TEXT,

    -- Meta keywords
    meta_keywords_1 TEXT,
    meta_keywords_1_length INTEGER DEFAULT 0,

    -- Headings (H1-H6)
    h1_1 TEXT, h1_len_1 INTEGER DEFAULT 0,
    h1_2 TEXT, h1_len_2 INTEGER DEFAULT 0,
    h2_1 TEXT, h2_len_1 INTEGER DEFAULT 0,
    h2_2 TEXT, h2_len_2 INTEGER DEFAULT 0,
    h3_1 TEXT, h3_len_1 INTEGER DEFAULT 0,
    h3_2 TEXT, h3_len_2 INTEGER DEFAULT 0,
    h4_1 TEXT, h4_len_1 INTEGER DEFAULT 0,
    h4_2 TEXT, h4_len_2 INTEGER DEFAULT 0,
    h5_1 TEXT, h5_len_1 INTEGER DEFAULT 0,
    h5_2 TEXT, h5_len_2 INTEGER DEFAULT 0,
    h6_1 TEXT, h6_len_1 INTEGER DEFAULT 0,
    h6_2 TEXT, h6_len_2 INTEGER DEFAULT 0,

    -- Directives
    meta_robots_1 TEXT,
    meta_robots_2 TEXT,
    x_robots_tag_1 TEXT,
    x_robots_tag_2 TEXT,
    meta_refresh_1 TEXT,

    -- Canonical & Pagination
    canonical_link_element_1 TEXT,
    canonical_link_element_2 TEXT,
    rel_next_1 TEXT,
    rel_prev_1 TEXT,
    http_rel_next_1 TEXT,
    http_rel_prev_1 TEXT,

    -- Performance
    size INTEGER DEFAULT 0,
    transferred INTEGER DEFAULT 0,
    response_time REAL DEFAULT 0,
    ttfb REAL DEFAULT 0,
    last_modified TEXT,

    -- Content analysis
    word_count INTEGER DEFAULT 0,
    sentence_count INTEGER DEFAULT 0,
    avg_words_per_sentence REAL DEFAULT 0,
    text_ratio REAL DEFAULT 0,
    readability REAL DEFAULT 0,
    readability_grade TEXT,
    closest_similarity_match TEXT,
    closest_similarity_score REAL DEFAULT 0,
    no_near_duplicates INTEGER DEFAULT 0,
    language TEXT,
    spelling_errors INTEGER DEFAULT 0,
    grammar_errors INTEGER DEFAULT 0,

    -- Link metrics
    crawl_depth INTEGER DEFAULT 0,
    folder_depth INTEGER DEFAULT 0,
    link_score REAL DEFAULT 0,
    inlinks INTEGER DEFAULT 0,
    unique_inlinks INTEGER DEFAULT 0,
    unique_js_inlinks INTEGER DEFAULT 0,
    percentage_of_total REAL DEFAULT 0,
    outlinks INTEGER DEFAULT 0,
    unique_outlinks INTEGER DEFAULT 0,
    unique_js_outlinks INTEGER DEFAULT 0,
    external_outlinks INTEGER DEFAULT 0,
    unique_external_outlinks INTEGER DEFAULT 0,
    unique_external_js_outlinks INTEGER DEFAULT 0,

    -- Redirect data
    redirect_uri TEXT,
    redirect_type TEXT,
    http_version TEXT DEFAULT 'HTTP/1.1',
    
    -- Additional link elements
    amphtml_link TEXT,
    mobile_alternate_link TEXT,
    
    -- Cookies
    cookies TEXT,
    
    -- Semantic similarity
    closest_semantic_match TEXT,
    semantic_similarity_score REAL DEFAULT 0,
    no_semantically_similar INTEGER DEFAULT 0,
    semantic_relevance_score REAL DEFAULT 0,

    -- Security headers
    hsts INTEGER DEFAULT 0,
    hsts_value TEXT,
    csp INTEGER DEFAULT 0,
    csp_value TEXT,
    x_content_type_options INTEGER DEFAULT 0,
    x_frame_options INTEGER DEFAULT 0,
    x_frame_options_value TEXT,
    referrer_policy INTEGER DEFAULT 0,
    referrer_policy_value TEXT,

    -- Open Graph
    og_title TEXT,
    og_description TEXT,
    og_image TEXT,
    og_type TEXT,
    og_url TEXT,

    -- Twitter Cards
    twitter_card TEXT,
    twitter_title TEXT,
    twitter_description TEXT,
    twitter_image TEXT,

    -- Structured data
    has_json_ld INTEGER DEFAULT 0,
    has_microdata INTEGER DEFAULT 0,
    has_rdfa INTEGER DEFAULT 0,
    schema_types TEXT,
    schema_validation_errors INTEGER DEFAULT 0,
    schema_validation_warnings INTEGER DEFAULT 0,

    -- Security issues
    is_https INTEGER DEFAULT 0,
    has_mixed_content INTEGER DEFAULT 0,
    has_insecure_forms INTEGER DEFAULT 0,
    unsafe_cross_origin_links INTEGER DEFAULT 0,

    -- URL issues
    url_length INTEGER DEFAULT 0,
    has_parameters INTEGER DEFAULT 0,
    has_non_ascii INTEGER DEFAULT 0,
    has_underscores INTEGER DEFAULT 0,
    has_uppercase INTEGER DEFAULT 0,

    -- Technical
    charset TEXT,
    viewport TEXT,

    -- Timestamps
    crawled_at TEXT,
    discovered_at TEXT,

    -- Issue flags (JSON array)
    issues TEXT,

    -- Raw data (JSON)
    raw_headers TEXT,
    hreflang_data TEXT,
    structured_data TEXT,
    html_content TEXT,

    UNIQUE(session_id, url)
);

CREATE INDEX IF NOT EXISTS idx_urls_session ON urls(session_id);
CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status_code);
CREATE INDEX IF NOT EXISTS idx_urls_hash ON urls(hash);
CREATE INDEX IF NOT EXISTS idx_urls_indexability ON urls(indexability);

-- Images table
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    image_url TEXT NOT NULL,
    alt_text TEXT,
    alt_text_length INTEGER DEFAULT 0,
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    missing_alt INTEGER DEFAULT 0,
    missing_alt_attribute INTEGER DEFAULT 0,
    missing_size_attributes INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_images_session ON images(session_id);
CREATE INDEX IF NOT EXISTS idx_images_page ON images(page_url);

-- Links table
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    anchor_text TEXT,
    is_internal INTEGER DEFAULT 1,
    is_nofollow INTEGER DEFAULT 0,
    link_type TEXT DEFAULT 'href'
);

CREATE INDEX IF NOT EXISTS idx_links_session ON links(session_id);
CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url);

-- Hreflang table
CREATE TABLE IF NOT EXISTS hreflang (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    hreflang TEXT NOT NULL,
    language TEXT,
    region TEXT,
    target_url TEXT NOT NULL,
    source TEXT,
    has_return_link INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_hreflang_session ON hreflang(session_id);
CREATE INDEX IF NOT EXISTS idx_hreflang_page ON hreflang(page_url);

-- Crawl sessions table
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    start_url TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    total_urls INTEGER DEFAULT 0,
    crawled_urls INTEGER DEFAULT 0,
    failed_urls INTEGER DEFAULT 0,
    max_urls INTEGER DEFAULT 10000,
    max_depth INTEGER,
    respect_robots INTEGER DEFAULT 1,
    user_agent TEXT,
    config TEXT
);

-- Issues table
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    url TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    issue_code TEXT NOT NULL,
    severity INTEGER DEFAULT 2,
    message TEXT NOT NULL,
    details TEXT,
    detected_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_issues_session ON issues(session_id);
CREATE INDEX IF NOT EXISTS idx_issues_type ON issues(issue_type);
CREATE INDEX IF NOT EXISTS idx_issues_code ON issues(issue_code);
"""
