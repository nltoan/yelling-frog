"""
FastAPI Main Application
RESTful API for controlling crawler and accessing data
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from collections import Counter, defaultdict
from datetime import datetime
from http import HTTPStatus
import asyncio
import os
import json
import csv
import io
import re
from html import escape
from functools import partial
from urllib.parse import urlparse, urljoin

from ..storage.database import Database
from ..storage.export import DataExporter
from ..storage.screaming_frog_exporter import ScreamingFrogExporter
from ..spider.crawler import WebCrawler, CrawlState
from ..spider.robots_parser import RobotsParser
from ..spider.sitemap_parser import SitemapParser
from ..processing.page_processor import PageProcessor
from ..analysis.duplicates import detect_duplicates_in_database
from ..analysis.orphans import detect_orphans_in_database
from ..analysis.redirects import detect_redirects_in_database
from ..extractors.structured_data import StructuredDataExtractor
from ..utils.url_normalizer import normalize_url

# Create FastAPI app
app = FastAPI(
    title="Web Crawler API",
    description="Screaming Frog SEO Spider Clone - Complete web crawler with SEO analysis",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_data_dir = os.environ.get("CRAWLER_DATA_DIR", os.path.join(_base_dir, "data"))
os.makedirs(_data_dir, exist_ok=True)
database = Database(os.path.join(_data_dir, "crawl_data.db"))
active_crawlers = {}  # session_id -> crawler instance
websocket_connections: Dict[str, List[WebSocket]] = {}  # session_id -> list of websockets

# On startup, mark any orphaned "running" sessions as stopped (from server restart)
def cleanup_orphaned_sessions():
    try:
        cursor = database.conn.cursor()
        cursor.execute(
            "UPDATE sessions SET status = 'stopped' WHERE status = 'running'"
        )
        database.conn.commit()
        count = cursor.rowcount
        if count > 0:
            print(f"Cleaned up {count} orphaned running sessions")
    except Exception as e:
        print(f"Failed to cleanup orphaned sessions: {e}")

cleanup_orphaned_sessions()


async def run_blocking(func, *args, **kwargs):
    """Run blocking sync work without stalling the event loop."""
    return await asyncio.to_thread(partial(func, *args, **kwargs))


async def filter_count(session_id: str, filter_name: str) -> int:
    """Return count for a filter without loading full matching rows."""
    result = await run_blocking(
        database.query_urls,
        session_id=session_id,
        limit=1,
        offset=0,
        filter_name=filter_name,
        search=None,
        sort_by='crawled_at',
        sort_order='desc',
    )
    return int(result.get("filtered_total", 0))


def _normalize_csv_value(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _flatten_report_rows(report_code: str, data: dict) -> List[Dict]:
    rows = data.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return [{k: _normalize_csv_value(v) for k, v in row.items()} for row in rows]

    if report_code == "hreflang":
        flat = []
        for page in data.get("pages", []):
            page_url = page.get("page_url")
            for entry in page.get("entries", []):
                flat.append({
                    "page_url": page_url,
                    "hreflang": entry.get("hreflang"),
                    "language": entry.get("language"),
                    "region": entry.get("region"),
                    "target_url": entry.get("url"),
                    "target_status_code": entry.get("target_status_code"),
                    "has_return_link": entry.get("has_return_link"),
                })
        if flat:
            return flat

    if report_code == "redirect_chains":
        flat = []
        chains = data.get("redirect_chains", {})
        if isinstance(chains, dict):
            for source_url, chain in chains.items():
                flat.append({
                    "source_url": source_url,
                    "chain_length": len(chain or []),
                    "chain": chain or [],
                })
        if flat:
            return [{k: _normalize_csv_value(v) for k, v in row.items()} for row in flat]

    if report_code == "redirect_loops":
        loops = data.get("redirect_loops", [])
        if isinstance(loops, list) and loops:
            return [
                {
                    "loop_length": len(loop or []),
                    "loop": _normalize_csv_value(loop or []),
                }
                for loop in loops
            ]

    if report_code == "duplicate_content":
        flat = []
        for url, info in (data.get("duplicate_info") or {}).items():
            flat.append({
                "url": url,
                "hash": info.get("hash"),
                "is_exact_duplicate": info.get("is_exact_duplicate"),
                "exact_duplicates_count": len(info.get("exact_duplicates") or []),
                "near_duplicates_count": len(info.get("near_duplicates") or []),
            })
        if flat:
            return [{k: _normalize_csv_value(v) for k, v in row.items()} for row in flat]

    if report_code == "orphan_pages":
        orphan_pages = data.get("orphan_pages", [])
        if isinstance(orphan_pages, list):
            return [{"url": url} for url in orphan_pages]

    if report_code == "sitemaps":
        rows_out = []
        for bucket in ["in_sitemap_only", "in_crawl_only", "in_both"]:
            for url in data.get(bucket, []):
                rows_out.append({"bucket": bucket, "url": url})
        if rows_out:
            return rows_out

    if report_code == "issues_report":
        flat = []
        issues_by_category = data.get("issues_by_category", {})
        for category, issues in issues_by_category.items():
            for issue in issues or []:
                flat.append({
                    "category": category,
                    "url": issue.get("url"),
                    "issue": issue.get("issue"),
                    "severity": issue.get("severity"),
                })
        if flat:
            return flat

    summary = data.get("summary")
    if isinstance(summary, dict) and summary:
        return [{k: _normalize_csv_value(v) for k, v in summary.items()}]

    return []


def status_text_from_code(status_code: Optional[int]) -> str:
    """Resolve human-readable status text from HTTP code."""
    if not status_code:
        return ""
    try:
        return HTTPStatus(int(status_code)).phrase
    except Exception:
        return str(status_code)


def _labelize_issue(issue_code: str) -> str:
    return issue_code.replace('_', ' ').strip().title()


def _top_url_rows(urls, metric: str, limit: int = 10, reverse: bool = True):
    ranked = [
        url_data for url_data in urls
        if getattr(url_data, metric, None) not in (None, "", 0)
    ]
    ranked.sort(key=lambda item: getattr(item, metric, 0) or 0, reverse=reverse)
    return [
        {
            "url": row.url,
            "title": row.title_1,
            "status_code": row.status_code,
            "value": getattr(row, metric, 0) or 0,
            "crawl_depth": row.crawl_depth,
            "inlinks": row.inlinks,
            "link_score": row.link_score,
        }
        for row in ranked[:limit]
    ]


def _build_tree_node(name: str):
    return {"name": name, "count": 0, "url": None, "children": {}}


SEO_CATEGORY_LABELS = {
    "on_page": "On-page",
    "technical": "Technical",
    "linking": "Linking",
    "content": "Content",
    "speed": "Speed",
    "schema": "Schema",
}

REPORT_DEFINITIONS = [
    {"code": "crawl_overview", "name": "Crawl Overview", "description": "Summary stats"},
    {"code": "internal_all", "name": "Internal All", "description": "Full internal URL data"},
    {"code": "external_all", "name": "External All", "description": "Full external URL data"},
    {"code": "response_codes", "name": "Response Codes", "description": "All URLs by status"},
    {"code": "redirect_chains", "name": "Redirect Chains", "description": "All redirect sequences"},
    {"code": "redirect_loops", "name": "Redirect Loops", "description": "Infinite redirects"},
    {"code": "canonicals", "name": "Canonicals", "description": "All canonical data"},
    {"code": "pagination", "name": "Pagination", "description": "Pagination audit"},
    {"code": "hreflang", "name": "Hreflang", "description": "International SEO audit"},
    {"code": "duplicate_content", "name": "Duplicate Content", "description": "Exact + near duplicates"},
    {"code": "insecure_content", "name": "Insecure Content", "description": "All security issues"},
    {"code": "structured_data", "name": "Structured Data", "description": "Schema validation"},
    {"code": "sitemaps", "name": "Sitemaps", "description": "Sitemap vs crawled URLs"},
    {"code": "orphan_pages", "name": "Orphan Pages", "description": "Pages with no internal links"},
    {"code": "link_score", "name": "Link Score", "description": "Internal PageRank distribution"},
    {"code": "issues_report", "name": "Issues Report", "description": "All errors/warnings/notices"},
]
REPORT_CODES = {item["code"] for item in REPORT_DEFINITIONS}

PRIORITY_SEGMENTS = {
    "all": {
        "label": "Tat ca",
        "description": "Toan bo URL dang co van de can theo doi.",
    },
    "quick_win": {
        "label": "Quick Win",
        "description": "Trang co the cai thien nhanh bang on-page va auto-fix.",
    },
    "traffic_recovery": {
        "label": "Traffic Recovery",
        "description": "Trang dang mat traffic do loi status, indexability hoac orphan.",
    },
    "cannibalization": {
        "label": "Cannibalization",
        "description": "Trang co dau hieu trung lap title, meta, heading hoac content.",
    },
    "content_thin": {
        "label": "Noi dung mong",
        "description": "Trang can bo sung heading, content depth hoac metadata.",
    },
    "technical_debt": {
        "label": "Technical Debt",
        "description": "Trang dang ton dong loi technical, speed, schema hoac linking.",
    },
}

AUDIT_PROFILES = {
    "blog": {
        "label": "Blog / Tin tuc",
        "description": "Uu tien title, meta, heading, content va schema cho bai viet.",
        "category_weights": {"on_page": 1.2, "technical": 0.9, "linking": 1.0, "content": 1.25, "speed": 1.0, "schema": 1.15},
    },
    "ecommerce": {
        "label": "E-commerce",
        "description": "Tang trong so cho technical, schema va internal linking.",
        "category_weights": {"on_page": 1.1, "technical": 1.2, "linking": 1.15, "content": 0.9, "speed": 1.1, "schema": 1.25},
    },
    "local": {
        "label": "Doanh nghiep dia phuong",
        "description": "Can bang on-page, technical va schema cho local SEO.",
        "category_weights": {"on_page": 1.1, "technical": 1.05, "linking": 0.9, "content": 0.95, "speed": 1.0, "schema": 1.3},
    },
    "docs": {
        "label": "Documentation",
        "description": "Uu tien heading hierarchy, internal linking va technical quality.",
        "category_weights": {"on_page": 1.1, "technical": 1.15, "linking": 1.2, "content": 1.05, "speed": 0.95, "schema": 0.9},
    },
    "custom": {
        "label": "Tuy chinh",
        "description": "Can bang tat ca nhom van de.",
        "category_weights": {"on_page": 1.0, "technical": 1.0, "linking": 1.0, "content": 1.0, "speed": 1.0, "schema": 1.0},
    },
}

AUDIT_MODES = {
    "safe": {
        "label": "An toan",
        "description": "Uu tien thay doi nhe, giam bot penalty va danh dau canh bao thay vi critical trong mot so truong hop.",
        "penalty_multiplier": 0.85,
        "priority_thresholds": {"critical": 42, "warning": 78},
    },
    "advanced": {
        "label": "Nang cao",
        "description": "Can bang giua on-page, technical va linking.",
        "penalty_multiplier": 1.0,
        "priority_thresholds": {"critical": 50, "warning": 82},
    },
    "comprehensive": {
        "label": "Toan dien",
        "description": "Danh gia nghiem hon va uu tien sua nhieu van de hon.",
        "penalty_multiplier": 1.15,
        "priority_thresholds": {"critical": 58, "warning": 86},
    },
}

SEVERITY_ORDER = {
    "critical": 3,
    "warning": 2,
    "info": 1,
    "pass": 0,
}

ISSUE_RULES = {
    "missing_title": {"label": "Trang thiếu title", "category": "on_page", "severity": "critical", "penalty": 12, "auto_fix": True},
    "duplicate_title": {"label": "Title bị trùng", "category": "on_page", "severity": "warning", "penalty": 6, "auto_fix": True},
    "title_over_60_chars": {"label": "Title quá dài", "category": "on_page", "severity": "warning", "penalty": 4, "auto_fix": True},
    "title_below_30_chars": {"label": "Title quá ngắn", "category": "on_page", "severity": "info", "penalty": 2, "auto_fix": True},
    "title_over_568_pixels": {"label": "Title vượt ngưỡng hiển thị", "category": "on_page", "severity": "info", "penalty": 2, "auto_fix": True},
    "multiple_titles": {"label": "Trang có nhiều title", "category": "on_page", "severity": "warning", "penalty": 4, "auto_fix": False},
    "missing_meta_description": {"label": "Thiếu meta description", "category": "on_page", "severity": "warning", "penalty": 8, "auto_fix": True},
    "duplicate_meta_description": {"label": "Meta description bị trùng", "category": "on_page", "severity": "warning", "penalty": 5, "auto_fix": True},
    "meta_description_over_155_chars": {"label": "Meta description quá dài", "category": "on_page", "severity": "info", "penalty": 3, "auto_fix": True},
    "meta_description_below_70_chars": {"label": "Meta description quá ngắn", "category": "on_page", "severity": "info", "penalty": 2, "auto_fix": True},
    "multiple_meta_descriptions": {"label": "Trang có nhiều meta description", "category": "on_page", "severity": "warning", "penalty": 4, "auto_fix": False},
    "missing_h1": {"label": "Trang thiếu thẻ H1", "category": "on_page", "severity": "critical", "penalty": 10, "auto_fix": True},
    "duplicate_h1": {"label": "H1 bị trùng", "category": "on_page", "severity": "warning", "penalty": 5, "auto_fix": True},
    "multiple_h1": {"label": "Trang có nhiều H1", "category": "on_page", "severity": "warning", "penalty": 6, "auto_fix": True},
    "h1_over_70_chars": {"label": "H1 quá dài", "category": "on_page", "severity": "info", "penalty": 2, "auto_fix": True},
    "missing_h2": {"label": "Trang thiếu H2", "category": "content", "severity": "info", "penalty": 2, "auto_fix": True},
    "non_sequential_headings": {"label": "Heading hierarchy chưa tuần tự", "category": "content", "severity": "warning", "penalty": 4, "auto_fix": True},
    "low_content": {"label": "Thin content", "category": "content", "severity": "warning", "penalty": 8, "auto_fix": False},
    "thin_content": {"label": "Thin content", "category": "content", "severity": "warning", "penalty": 8, "auto_fix": False},
    "low_text_ratio": {"label": "Tỷ lệ text thấp", "category": "content", "severity": "info", "penalty": 4, "auto_fix": False},
    "hard_to_read": {"label": "Nội dung khó đọc", "category": "content", "severity": "warning", "penalty": 4, "auto_fix": False},
    "long_sentences": {"label": "Câu văn quá dài", "category": "content", "severity": "info", "penalty": 3, "auto_fix": False},
    "redirection_3xx": {"label": "URL redirect", "category": "technical", "severity": "info", "penalty": 2, "auto_fix": False},
    "client_error_4xx": {"label": "Trang lỗi 4xx", "category": "technical", "severity": "critical", "penalty": 15, "auto_fix": False},
    "server_error_5xx": {"label": "Trang lỗi 5xx", "category": "technical", "severity": "critical", "penalty": 18, "auto_fix": False},
    "crawl_error": {"label": "URL crawl that bai", "category": "technical", "severity": "critical", "penalty": 18, "auto_fix": False},
    "http_urls": {"label": "Trang HTTP chưa an toàn", "category": "technical", "severity": "warning", "penalty": 5, "auto_fix": False},
    "http_url": {"label": "Trang HTTP chưa an toàn", "category": "technical", "severity": "warning", "penalty": 5, "auto_fix": False},
    "mixed_content": {"label": "HTTPS tải resource qua HTTP", "category": "technical", "severity": "critical", "penalty": 12, "auto_fix": False},
    "insecure_forms": {"label": "Form không an toàn", "category": "technical", "severity": "critical", "penalty": 12, "auto_fix": False},
    "missing_hsts": {"label": "Thiếu HSTS", "category": "technical", "severity": "info", "penalty": 2, "auto_fix": False},
    "unsafe_cross_origin_links": {"label": "Link mở tab mới thiếu noopener", "category": "technical", "severity": "warning", "penalty": 4, "auto_fix": False},
    "url_over_115_chars": {"label": "URL quá dài", "category": "technical", "severity": "info", "penalty": 2, "auto_fix": False},
    "long_url": {"label": "URL quá dài", "category": "technical", "severity": "info", "penalty": 2, "auto_fix": False},
    "url_with_parameters": {"label": "URL có parameters", "category": "technical", "severity": "info", "penalty": 1, "auto_fix": False},
    "has_parameters": {"label": "URL có parameters", "category": "technical", "severity": "info", "penalty": 1, "auto_fix": False},
    "url_with_underscores": {"label": "URL có dấu gạch dưới", "category": "technical", "severity": "info", "penalty": 1, "auto_fix": False},
    "has_underscores": {"label": "URL có dấu gạch dưới", "category": "technical", "severity": "info", "penalty": 1, "auto_fix": False},
    "url_with_uppercase": {"label": "URL có chữ hoa", "category": "technical", "severity": "info", "penalty": 1, "auto_fix": False},
    "has_uppercase": {"label": "URL có chữ hoa", "category": "technical", "severity": "info", "penalty": 1, "auto_fix": False},
    "url_with_non_ascii": {"label": "URL có ký tự non-ASCII", "category": "technical", "severity": "info", "penalty": 1, "auto_fix": False},
    "has_non_ascii": {"label": "URL có ký tự non-ASCII", "category": "technical", "severity": "info", "penalty": 1, "auto_fix": False},
    "deep_folder": {"label": "URL có cấu trúc thư mục quá sâu", "category": "technical", "severity": "info", "penalty": 2, "auto_fix": False},
    "noindex": {"label": "Trang bị noindex", "category": "technical", "severity": "info", "penalty": 3, "auto_fix": False},
    "missing_canonical": {"label": "Thiếu canonical", "category": "technical", "severity": "info", "penalty": 2, "auto_fix": True},
    "orphan_page": {"label": "Trang mồ côi", "category": "linking", "severity": "critical", "penalty": 12, "auto_fix": False},
    "low_internal_outlinks": {"label": "Trang có ít internal links outgoing", "category": "linking", "severity": "warning", "penalty": 4, "auto_fix": False},
    "deep_page": {"label": "Trang nằm quá sâu", "category": "linking", "severity": "warning", "penalty": 4, "auto_fix": False},
    "slow_page": {"label": "Trang phản hồi chậm", "category": "speed", "severity": "warning", "penalty": 5, "auto_fix": False},
    "slow_response": {"label": "Trang phản hồi chậm", "category": "speed", "severity": "warning", "penalty": 5, "auto_fix": False},
    "slow_ttfb": {"label": "TTFB chậm", "category": "speed", "severity": "warning", "penalty": 4, "auto_fix": False},
    "large_page": {"label": "Kích thước trang lớn", "category": "speed", "severity": "info", "penalty": 3, "auto_fix": False},
    "missing_structured_data": {"label": "Trang không có JSON-LD schema", "category": "schema", "severity": "warning", "penalty": 5, "auto_fix": True},
    "missing_og_title": {"label": "Thiếu Open Graph title", "category": "on_page", "severity": "info", "penalty": 2, "auto_fix": True},
    "missing_og_description": {"label": "Thiếu Open Graph description", "category": "on_page", "severity": "info", "penalty": 2, "auto_fix": True},
    "missing_og_image": {"label": "Thiếu Open Graph image", "category": "on_page", "severity": "warning", "penalty": 3, "auto_fix": True},
    "missing_twitter_card": {"label": "Thiếu Twitter card", "category": "on_page", "severity": "info", "penalty": 2, "auto_fix": True},
    "missing_twitter_title": {"label": "Thiếu Twitter title", "category": "on_page", "severity": "info", "penalty": 2, "auto_fix": True},
    "missing_twitter_description": {"label": "Thiếu Twitter description", "category": "on_page", "severity": "info", "penalty": 2, "auto_fix": True},
    "missing_twitter_image": {"label": "Thiếu Twitter image", "category": "on_page", "severity": "warning", "penalty": 3, "auto_fix": True},
}


def issue_label(issue_code: str) -> str:
    return ISSUE_RULES.get(issue_code, {}).get("label", _labelize_issue(issue_code))


def priority_label(priority: str) -> str:
    return {
        "critical": "cần sửa gấp",
        "warning": "cần theo dõi",
        "pass": "đạt yêu cầu",
    }.get(priority, priority)


def resolve_audit_config(profile: Optional[str] = None, mode: Optional[str] = None) -> Dict[str, object]:
    profile_key = profile if profile in AUDIT_PROFILES else "custom"
    mode_key = mode if mode in AUDIT_MODES else "advanced"
    return {
        "profile_key": profile_key,
        "profile": AUDIT_PROFILES[profile_key],
        "mode_key": mode_key,
        "mode": AUDIT_MODES[mode_key],
    }


def build_issue_record(issue_code: str, audit_config: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    rule = ISSUE_RULES.get(issue_code, {})
    config = audit_config or resolve_audit_config()
    category = rule.get("category", "technical")
    base_penalty = rule.get("penalty", 1)
    category_weight = config["profile"]["category_weights"].get(category, 1.0)
    penalty_multiplier = config["mode"]["penalty_multiplier"]
    penalty = max(1, round(base_penalty * category_weight * penalty_multiplier))
    return {
        "code": issue_code,
        "label": rule.get("label", _labelize_issue(issue_code)),
        "category": category,
        "category_label": SEO_CATEGORY_LABELS.get(category, "Technical"),
        "severity": rule.get("severity", "info"),
        "penalty": penalty,
        "base_penalty": base_penalty,
        "auto_fix": rule.get("auto_fix", False),
    }


def get_priority_segments(audit: Dict[str, object], url_data) -> List[str]:
    issue_codes = {issue["code"] for issue in audit["issues"]}
    issue_categories = {issue["category"] for issue in audit["issues"]}
    segments = []

    if audit["issues"]:
        segments.append("all")

    if (
        audit["priority"] != "pass"
        and audit["severity_counts"]["critical"] == 0
        and any(issue["auto_fix"] for issue in audit["issues"])
    ):
        segments.append("quick_win")

    if (
        (url_data.status_code or 0) >= 400
        or issue_codes.intersection({"client_error_4xx", "server_error_5xx", "noindex", "orphan_page", "redirection_3xx"})
    ):
        segments.append("traffic_recovery")

    if issue_codes.intersection({"duplicate_title", "duplicate_meta_description", "duplicate_h1"}):
        segments.append("cannibalization")

    if issue_codes.intersection({
        "low_content",
        "missing_h2",
        "missing_h1",
        "missing_meta_description",
        "meta_description_below_70_chars",
    }):
        segments.append("content_thin")

    if (
        issue_categories.intersection({"technical", "speed", "schema"})
        or issue_codes.intersection({"deep_page", "low_internal_outlinks", "missing_canonical"})
    ):
        segments.append("technical_debt")

    return list(dict.fromkeys(segments))


def build_page_audit(url_data, homepage_url: str, audit_config: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    config = audit_config or resolve_audit_config()
    normalized_home = normalize_url(homepage_url)
    issue_codes = set(url_data.issues or [])

    if (
        (url_data.inlinks or 0) == 0 and
        normalize_url(url_data.url) != normalized_home and
        (url_data.status_code or 0) < 400
    ):
        issue_codes.add("orphan_page")
    if (url_data.unique_outlinks or 0) < 3 and (url_data.status_code or 0) < 400:
        issue_codes.add("low_internal_outlinks")
    if (url_data.crawl_depth or 0) >= 4:
        issue_codes.add("deep_page")
    if (url_data.response_time or 0) >= 2:
        issue_codes.add("slow_page")
    if (url_data.size or 0) >= 1_500_000:
        issue_codes.add("large_page")
    if (
        "text/html" in (url_data.content_type or "") and
        not (url_data.has_json_ld or url_data.has_microdata or url_data.has_rdfa)
    ):
        issue_codes.add("missing_structured_data")

    issues = [build_issue_record(code, config) for code in issue_codes]
    issues.sort(key=lambda item: (-SEVERITY_ORDER[item["severity"]], -item["penalty"], item["label"]))

    severity_counts = {
        "critical": sum(1 for issue in issues if issue["severity"] == "critical"),
        "warning": sum(1 for issue in issues if issue["severity"] == "warning"),
        "info": sum(1 for issue in issues if issue["severity"] == "info"),
        "pass": 1 if not issues else 0,
    }

    category_penalties = {category: 0 for category in SEO_CATEGORY_LABELS}
    for issue in issues:
        category_penalties[issue["category"]] += issue["penalty"]
    category_scores = {
        category: max(0, 100 - penalty)
        for category, penalty in category_penalties.items()
    }

    total_penalty = sum(issue["penalty"] for issue in issues)
    seo_score = max(0, 100 - total_penalty)
    critical_threshold = config["mode"]["priority_thresholds"]["critical"]
    warning_threshold = config["mode"]["priority_thresholds"]["warning"]
    if severity_counts["critical"] > 0 or seo_score < critical_threshold:
        priority = "critical"
    elif severity_counts["warning"] > 0 or seo_score < warning_threshold:
        priority = "warning"
    else:
        priority = "pass"

    return {
        "seo_score": seo_score,
        "priority": priority,
        "severity_counts": severity_counts,
        "category_scores": category_scores,
        "issues": issues,
        "profile": config["profile_key"],
        "mode": config["mode_key"],
    }


def build_summary_report(
    db: Database,
    session_id: str,
    profile: Optional[str] = None,
    mode: Optional[str] = None
) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    audit_config = resolve_audit_config(profile, mode)
    urls = db.get_all_urls(session_id)
    links = db.get_links(session_id)
    orphans = detect_orphans_in_database(db, session_id)
    redirects = detect_redirects_in_database(db, session_id)
    page_audits = {row.url: build_page_audit(row, session.start_url, audit_config) for row in urls}

    total_urls = len(urls)
    indexable_count = sum(1 for row in urls if row.indexability == "Indexable")
    non_indexable_count = total_urls - indexable_count
    total_issues = sum(len(audit["issues"]) for audit in page_audits.values())
    pages_with_issues = sum(1 for audit in page_audits.values() if audit["issues"])
    overall_score = round(
        sum(audit["seo_score"] for audit in page_audits.values()) / max(len(page_audits), 1)
    ) if page_audits else 0

    status_buckets = {
        "2xx": sum(1 for row in urls if row.status_code and 200 <= row.status_code < 300),
        "3xx": sum(1 for row in urls if row.status_code and 300 <= row.status_code < 400),
        "4xx": sum(1 for row in urls if row.status_code and 400 <= row.status_code < 500),
        "5xx": sum(1 for row in urls if row.status_code and row.status_code >= 500),
    }
    content_types = Counter(
        (row.content_type or "unknown").split(";")[0].strip() or "unknown"
        for row in urls
    )
    issue_counts = Counter()
    severity_totals = Counter()
    priority_totals = Counter()
    segment_totals = Counter()
    category_score_totals = defaultdict(list)
    hash_groups = defaultdict(list)
    for row in urls:
        audit = page_audits[row.url]
        for issue in audit["issues"]:
            issue_counts[issue["code"]] += 1
            severity_totals[issue["severity"]] += 1
        priority_totals[audit["priority"]] += 1
        for segment in get_priority_segments(audit, row):
            if segment != "all":
                segment_totals[segment] += 1
        for category, score in audit["category_scores"].items():
            category_score_totals[category].append(score)
        if row.hash:
            hash_groups[row.hash].append(row.url)

    avg_response_time = round(
        sum((row.response_time or 0) for row in urls if row.response_time) /
        max(1, sum(1 for row in urls if row.response_time)),
        3
    ) if any(row.response_time for row in urls) else 0
    avg_word_count = int(
        sum((row.word_count or 0) for row in urls if row.word_count) /
        max(1, sum(1 for row in urls if row.word_count))
    ) if any(row.word_count for row in urls) else 0

    internal_links = sum(1 for link in links if link.is_internal)
    external_links = len(links) - internal_links
    duplicate_group_sizes = [len(group) for group in hash_groups.values() if len(group) > 1]
    duplicate_summary = {
        "duplicate_groups": len(duplicate_group_sizes),
        "duplicate_pages": sum(size - 1 for size in duplicate_group_sizes),
        "largest_duplicate_group": max(duplicate_group_sizes, default=0),
        "unique_pages": len(hash_groups),
    }
    top_issues = [
        {
            "code": code,
            "label": build_issue_record(code)["label"],
            "severity": build_issue_record(code)["severity"],
            "category": build_issue_record(code)["category"],
            "category_label": build_issue_record(code)["category_label"],
            "count": count,
            "share": round((count / max(total_urls, 1)) * 100, 1),
        }
        for code, count in issue_counts.most_common(10)
    ]

    thin_content_rows = sorted(
        [row for row in urls if row.word_count],
        key=lambda item: item.word_count
    )[:10]

    recommendations = []
    if status_buckets["4xx"] or status_buckets["5xx"]:
        recommendations.append({
            "priority": "high",
            "title": "Xu ly cac URL loi truoc",
            "detail": f"Phat hien {status_buckets['4xx']} trang 4xx va {status_buckets['5xx']} trang 5xx trong phien crawl.",
        })
    if issue_counts.get("missing_title"):
        recommendations.append({
            "priority": "high",
            "title": "Bo sung title cho cac trang dang thieu",
            "detail": f"Co {issue_counts['missing_title']} trang chua co the title.",
        })
    if issue_counts.get("missing_meta_description"):
        recommendations.append({
            "priority": "medium",
            "title": "Mo rong do phu meta description",
            "detail": f"Co {issue_counts['missing_meta_description']} trang chua co meta description.",
        })
    if orphans["statistics"]["orphan_pages"]:
        recommendations.append({
            "priority": "medium",
            "title": "Giam so luong trang mo coi",
            "detail": f"Co {orphans['statistics']['orphan_pages']} URL khong nhan duoc internal link tro den.",
        })
    if duplicate_summary["duplicate_groups"]:
        recommendations.append({
            "priority": "medium",
            "title": "Hop nhat cac cum noi dung trung lap",
            "detail": f"Phat hien {duplicate_summary['duplicate_groups']} cum duplicate can ra soat canonical hoac hop nhat noi dung.",
        })
    if avg_response_time > 2:
        recommendations.append({
            "priority": "medium",
            "title": "Ra soat cac trang phan hoi cham",
            "detail": f"Thoi gian phan hoi trung binh dang o muc {avg_response_time}s tren toan bo URL da crawl.",
        })

    return {
        "session": {
            "session_id": session.session_id,
            "start_url": session.start_url,
            "status": session.status,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        },
        "audit_config": {
            "profile": audit_config["profile_key"],
            "profile_label": audit_config["profile"]["label"],
            "mode": audit_config["mode_key"],
            "mode_label": audit_config["mode"]["label"],
        },
        "overview": {
            "total_urls": total_urls,
            "overall_score": overall_score,
            "indexable_count": indexable_count,
            "non_indexable_count": non_indexable_count,
            "total_issues": total_issues,
            "pages_with_issues": pages_with_issues,
            "avg_response_time": avg_response_time,
            "avg_word_count": avg_word_count,
            "internal_links": internal_links,
            "external_links": external_links,
        },
        "severity_totals": {
            "critical": severity_totals["critical"],
            "warning": severity_totals["warning"],
            "info": severity_totals["info"],
            "pass": sum(1 for audit in page_audits.values() if audit["severity_counts"]["pass"]),
        },
        "priority_totals": {
            "critical": priority_totals["critical"],
            "warning": priority_totals["warning"],
            "pass": priority_totals["pass"],
        },
        "segment_totals": [
            {
                "key": key,
                "label": meta["label"],
                "description": meta["description"],
                "count": segment_totals[key],
            }
            for key, meta in PRIORITY_SEGMENTS.items()
            if key != "all"
        ],
        "category_scores": [
            {
                "category": category,
                "label": SEO_CATEGORY_LABELS[category],
                "score": round(sum(scores) / max(len(scores), 1)),
            }
            for category, scores in category_score_totals.items()
        ],
        "status_buckets": status_buckets,
        "content_types": [
            {"type": content_type, "count": count}
            for content_type, count in content_types.most_common(8)
        ],
        "top_issues": top_issues,
        "top_pages": {
            "slowest": _top_url_rows(urls, "response_time"),
            "most_linked": _top_url_rows(urls, "inlinks"),
            "strongest": _top_url_rows(urls, "link_score"),
            "deepest": sorted([
                {
                    "url": row.url,
                    "title": row.title_1,
                    "status_code": row.status_code,
                    "value": row.crawl_depth or 0,
                    "crawl_depth": row.crawl_depth,
                    "inlinks": row.inlinks,
                    "link_score": row.link_score,
                }
                for row in urls
            ], key=lambda item: item["value"], reverse=True)[:10],
            "thin_content": [
                {
                    "url": row.url,
                    "title": row.title_1,
                    "status_code": row.status_code,
                    "value": row.word_count or 0,
                    "crawl_depth": row.crawl_depth,
                    "inlinks": row.inlinks,
                    "link_score": row.link_score,
                }
                for row in thin_content_rows
            ],
        },
        "priority_pages": sorted([
            {
                "url": row.url,
                "title": row.title_1,
                "status_code": row.status_code,
                "seo_score": page_audits[row.url]["seo_score"],
                "priority": page_audits[row.url]["priority"],
                "issues_count": len(page_audits[row.url]["issues"]),
                "top_issues": [issue["label"] for issue in page_audits[row.url]["issues"][:3]],
            }
            for row in urls
        ], key=lambda item: (item["seo_score"], -item["issues_count"]))[:20],
        "duplicates": duplicate_summary,
        "redirects": redirects["statistics"],
        "orphans": orphans["statistics"],
        "recommendations": recommendations[:6],
    }


def build_visualization_data(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    urls = db.get_all_urls(session_id)
    links = db.get_links(session_id)
    url_map = {normalize_url(row.url): row for row in urls}
    root_url = normalize_url(session.start_url)

    depth_columns = defaultdict(list)
    for row in urls:
        depth_columns[row.crawl_depth or 0].append({
            "url": row.url,
            "label": row.title_1 or urlparse(row.url).path or row.url,
            "status_code": row.status_code,
            "inlinks": row.inlinks,
            "link_score": round(row.link_score or 0, 1),
            "issues_count": len(row.issues or []),
        })

    for depth, rows in depth_columns.items():
        rows.sort(key=lambda item: (item["inlinks"], item["link_score"]), reverse=True)
        depth_columns[depth] = rows[:10]

    ranked_urls = sorted(
        urls,
        key=lambda row: ((row.inlinks or 0) * 2) + (row.link_score or 0),
        reverse=True
    )
    selected_urls = []
    selected_set = set()
    for row in ranked_urls:
        normalized = normalize_url(row.url)
        if normalized not in selected_set:
            selected_urls.append(row)
            selected_set.add(normalized)
        if len(selected_urls) >= 36:
            break
    if root_url in url_map and root_url not in selected_set:
        selected_urls.insert(0, url_map[root_url])
        selected_set.add(root_url)
        selected_urls = selected_urls[:36]

    graph_by_depth = defaultdict(list)
    for row in selected_urls:
        graph_by_depth[row.crawl_depth or 0].append(row)

    nodes = []
    for depth in sorted(graph_by_depth.keys()):
        bucket = sorted(
            graph_by_depth[depth],
            key=lambda item: (item.inlinks or 0, item.link_score or 0),
            reverse=True
        )
        for index, row in enumerate(bucket):
            normalized = normalize_url(row.url)
            nodes.append({
                "id": normalized,
                "url": row.url,
                "label": (row.title_1 or urlparse(row.url).path or row.url)[:36],
                "depth": depth,
                "status_code": row.status_code,
                "inlinks": row.inlinks,
                "link_score": round(row.link_score or 0, 1),
                "issues_count": len(row.issues or []),
                "x": 120 + (depth * 220),
                "y": 90 + (index * 88),
            })

    node_ids = {node["id"] for node in nodes}
    edges = []
    edge_keys = set()
    for link in links:
        if not link.is_internal:
            continue
        source = normalize_url(link.source_url)
        target = normalize_url(link.target_url)
        if source in node_ids and target in node_ids and source != target:
            edge_key = (source, target)
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)
            edges.append({"source": source, "target": target, "type": link.link_type})
        if len(edges) >= 120:
            break

    tree_root = _build_tree_node(urlparse(session.start_url).netloc or "root")
    for row in urls:
        parsed = urlparse(row.url)
        path_segments = [segment for segment in parsed.path.split("/") if segment]
        current = tree_root
        current["count"] += 1
        if not current["url"]:
            current["url"] = normalize_url(f"{parsed.scheme}://{parsed.netloc}/")
        if not path_segments:
            child_key = "(home)"
            if child_key not in current["children"]:
                current["children"][child_key] = _build_tree_node(child_key)
            current = current["children"][child_key]
            current["count"] += 1
            current["url"] = row.url
            continue

        for segment in path_segments[:4]:
            if segment not in current["children"]:
                current["children"][segment] = _build_tree_node(segment)
            current = current["children"][segment]
            current["count"] += 1
            current["url"] = row.url

    def serialize_tree(node):
        children = [
            serialize_tree(child)
            for child in sorted(
                node["children"].values(),
                key=lambda item: (-item["count"], item["name"])
            )[:12]
        ]
        return {
            "name": node["name"],
            "count": node["count"],
            "url": node["url"],
            "children": children,
        }

    return {
        "summary": {
            "total_urls": len(urls),
            "max_depth": max((row.crawl_depth or 0) for row in urls) if urls else 0,
            "graph_nodes": len(nodes),
            "graph_edges": len(edges),
            "internal_links": sum(1 for link in links if link.is_internal),
        },
        "depth_columns": [
            {"depth": depth, "count": len(rows), "pages": rows}
            for depth, rows in sorted(depth_columns.items(), key=lambda item: item[0])
        ],
        "graph": {
            "nodes": nodes,
            "edges": edges,
            "width": max((node["x"] for node in nodes), default=400) + 180,
            "height": max((node["y"] for node in nodes), default=240) + 120,
        },
        "tree": serialize_tree(tree_root),
    }


def build_priorities_report(
    db: Database,
    session_id: str,
    profile: Optional[str] = None,
    mode: Optional[str] = None,
    search: Optional[str] = None,
    priority: Optional[str] = None,
    severity: Optional[str] = None,
    segment: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    audit_config = resolve_audit_config(profile, mode)
    normalized_search = (search or "").strip().lower()
    matched_rows = []
    segment_counts = Counter()
    for url_data in db.get_all_urls(session_id):
        audit = build_page_audit(url_data, session.start_url, audit_config)
        if priority and audit["priority"] != priority:
            continue
        if severity and not any(issue["severity"] == severity for issue in audit["issues"]):
            continue
        if normalized_search:
            searchable = " ".join([
                url_data.url or "",
                url_data.title_1 or "",
                " ".join(issue["label"] for issue in audit["issues"]),
            ]).lower()
            if normalized_search not in searchable:
                continue
        segments = get_priority_segments(audit, url_data)
        for item in segments:
            segment_counts[item] += 1
        matched_rows.append({
            "url": url_data.url,
            "title": url_data.title_1,
            "status_code": url_data.status_code,
            "seo_score": audit["seo_score"],
            "priority": audit["priority"],
            "issues_count": len(audit["issues"]),
            "severity_counts": audit["severity_counts"],
            "top_issues": audit["issues"][:5],
            "response_time": url_data.response_time,
            "crawl_depth": url_data.crawl_depth,
            "inlinks": url_data.inlinks,
            "segments": segments,
        })

    rows = matched_rows
    if segment and segment != "all":
        rows = [row for row in matched_rows if segment in row["segments"]]

    rows.sort(key=lambda item: (item["seo_score"], -item["issues_count"], item["url"]))
    filtered_total = len(rows)
    page_rows = rows[offset:offset + limit]
    return {
        "audit_config": {
            "profile": audit_config["profile_key"],
            "profile_label": audit_config["profile"]["label"],
            "mode": audit_config["mode_key"],
            "mode_label": audit_config["mode"]["label"],
        },
        "total": filtered_total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(page_rows) < filtered_total,
        "selected_segment": segment or "all",
        "summary": {
            "critical": sum(1 for row in rows if row["priority"] == "critical"),
            "warning": sum(1 for row in rows if row["priority"] == "warning"),
            "pass": sum(1 for row in rows if row["priority"] == "pass"),
        },
        "segments": [
            {
                "key": key,
                "label": meta["label"],
                "description": meta["description"],
                "count": (len(matched_rows) if key == "all" else segment_counts[key]),
            }
            for key, meta in PRIORITY_SEGMENTS.items()
        ],
        "rows": page_rows,
    }


def build_audit_history(
    db: Database,
    session_id: str,
    profile: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    audit_config = resolve_audit_config(profile, mode)
    target_host = urlparse(session.start_url).netloc
    matching_sessions = [
        crawl_session
        for crawl_session in db.get_all_sessions(limit=50)
        if urlparse(crawl_session.start_url).netloc == target_host
    ]
    matching_sessions.sort(key=lambda crawl_session: crawl_session.started_at or datetime.min, reverse=True)
    matching_sessions = matching_sessions[:limit]

    history_rows = []
    for crawl_session in matching_sessions:
        urls = db.get_all_urls(crawl_session.session_id)
        audits = [build_page_audit(url_data, crawl_session.start_url, audit_config) for url_data in urls]
        overview_score = round(sum(audit["seo_score"] for audit in audits) / max(len(audits), 1)) if audits else 0
        total_issues = sum(len(audit["issues"]) for audit in audits)
        history_rows.append({
            "session_id": crawl_session.session_id,
            "start_url": crawl_session.start_url,
            "status": crawl_session.status,
            "started_at": crawl_session.started_at.isoformat() if crawl_session.started_at else None,
            "completed_at": crawl_session.completed_at.isoformat() if crawl_session.completed_at else None,
            "total_urls": crawl_session.total_urls,
            "crawled_urls": crawl_session.crawled_urls,
            "overview_score": overview_score,
            "total_issues": total_issues,
        })

    return {
        "audit_config": {
            "profile": audit_config["profile_key"],
            "mode": audit_config["mode_key"],
        },
        "host": target_host,
        "sessions": history_rows,
    }


def build_audit_compare(
    db: Database,
    session_id: str,
    compare_to_session_id: Optional[str] = None,
    profile: Optional[str] = None,
    mode: Optional[str] = None,
) -> Dict[str, object]:
    current_session = db.get_session(session_id)
    if not current_session:
        raise ValueError("Session not found")

    host = urlparse(current_session.start_url).netloc
    candidate_sessions = [
        crawl_session
        for crawl_session in db.get_all_sessions(limit=50)
        if urlparse(crawl_session.start_url).netloc == host
    ]
    candidate_sessions.sort(key=lambda crawl_session: crawl_session.started_at or datetime.min, reverse=True)

    baseline_session = None
    if compare_to_session_id:
        baseline_session = next((item for item in candidate_sessions if item.session_id == compare_to_session_id), None)
        if not baseline_session:
            raise ValueError("Baseline session not found")
    else:
        baseline_session = next((item for item in candidate_sessions if item.session_id != session_id), None)
        if not baseline_session:
            raise ValueError("No baseline session available for comparison")

    audit_config = resolve_audit_config(profile, mode)
    current_report = build_summary_report(db, session_id, profile, mode)
    baseline_report = build_summary_report(db, baseline_session.session_id, profile, mode)

    current_urls = {
        row.url: {
            "row": row,
            "audit": build_page_audit(row, current_session.start_url, audit_config),
        }
        for row in db.get_all_urls(session_id)
    }
    baseline_urls = {
        row.url: {
            "row": row,
            "audit": build_page_audit(row, baseline_session.start_url, audit_config),
        }
        for row in db.get_all_urls(baseline_session.session_id)
    }

    common_urls = set(current_urls).intersection(baseline_urls)
    improved_pages = []
    worsened_pages = []
    new_pages = []
    removed_pages = []

    for url in common_urls:
        current_audit = current_urls[url]["audit"]
        baseline_audit = baseline_urls[url]["audit"]
        score_delta = current_audit["seo_score"] - baseline_audit["seo_score"]
        issues_delta = len(current_audit["issues"]) - len(baseline_audit["issues"])
        row = {
            "url": url,
            "title": current_urls[url]["row"].title_1 or baseline_urls[url]["row"].title_1,
            "current_score": current_audit["seo_score"],
            "baseline_score": baseline_audit["seo_score"],
            "score_delta": score_delta,
            "current_issues": len(current_audit["issues"]),
            "baseline_issues": len(baseline_audit["issues"]),
            "issues_delta": issues_delta,
        }
        if score_delta > 0 or issues_delta < 0:
            improved_pages.append(row)
        elif score_delta < 0 or issues_delta > 0:
            worsened_pages.append(row)

    for url in sorted(set(current_urls) - set(baseline_urls)):
        audit = current_urls[url]["audit"]
        new_pages.append({
            "url": url,
            "title": current_urls[url]["row"].title_1,
            "current_score": audit["seo_score"],
            "current_issues": len(audit["issues"]),
        })

    for url in sorted(set(baseline_urls) - set(current_urls)):
        audit = baseline_urls[url]["audit"]
        removed_pages.append({
            "url": url,
            "title": baseline_urls[url]["row"].title_1,
            "baseline_score": audit["seo_score"],
            "baseline_issues": len(audit["issues"]),
        })

    improved_pages.sort(key=lambda item: (item["score_delta"], -item["issues_delta"], item["url"]), reverse=True)
    worsened_pages.sort(key=lambda item: (-item["score_delta"], item["issues_delta"], item["url"]))

    current_issue_counts = Counter(item["code"] for issue in current_urls.values() for item in issue["audit"]["issues"])
    baseline_issue_counts = Counter(item["code"] for issue in baseline_urls.values() for item in issue["audit"]["issues"])
    issue_deltas = []
    for issue_code in set(current_issue_counts).union(baseline_issue_counts):
        current_count = current_issue_counts.get(issue_code, 0)
        baseline_count = baseline_issue_counts.get(issue_code, 0)
        delta = current_count - baseline_count
        if delta == 0:
            continue
        issue_meta = build_issue_record(issue_code, audit_config)
        issue_deltas.append({
            "code": issue_code,
            "label": issue_meta["label"],
            "severity": issue_meta["severity"],
            "category": issue_meta["category"],
            "category_label": issue_meta["category_label"],
            "current_count": current_count,
            "baseline_count": baseline_count,
            "delta": delta,
        })
    issue_deltas.sort(key=lambda item: (-abs(item["delta"]), -SEVERITY_ORDER[item["severity"]], item["label"]))

    baseline_category_scores = {
        row["category"]: row["score"] for row in baseline_report["category_scores"]
    }
    category_deltas = []
    for row in current_report["category_scores"]:
        baseline_score = baseline_category_scores.get(row["category"], 0)
        category_deltas.append({
            "category": row["category"],
            "label": row["label"],
            "current_score": row["score"],
            "baseline_score": baseline_score,
            "delta": row["score"] - baseline_score,
        })

    return {
        "audit_config": {
            "profile": audit_config["profile_key"],
            "profile_label": audit_config["profile"]["label"],
            "mode": audit_config["mode_key"],
            "mode_label": audit_config["mode"]["label"],
        },
        "current": {
            "session_id": current_session.session_id,
            "start_url": current_session.start_url,
            "started_at": current_session.started_at.isoformat() if current_session.started_at else None,
        },
        "baseline": {
            "session_id": baseline_session.session_id,
            "start_url": baseline_session.start_url,
            "started_at": baseline_session.started_at.isoformat() if baseline_session.started_at else None,
        },
        "overview_delta": {
            "score_delta": current_report["overview"]["overall_score"] - baseline_report["overview"]["overall_score"],
            "total_issues_delta": current_report["overview"]["total_issues"] - baseline_report["overview"]["total_issues"],
            "pages_with_issues_delta": current_report["overview"]["pages_with_issues"] - baseline_report["overview"]["pages_with_issues"],
            "avg_response_delta": round(current_report["overview"]["avg_response_time"] - baseline_report["overview"]["avg_response_time"], 3),
            "urls_delta": current_report["overview"]["total_urls"] - baseline_report["overview"]["total_urls"],
        },
        "severity_delta": {
            key: current_report["severity_totals"].get(key, 0) - baseline_report["severity_totals"].get(key, 0)
            for key in ("critical", "warning", "info")
        },
        "category_deltas": category_deltas,
        "issue_deltas": issue_deltas[:20],
        "page_deltas": {
            "improved": improved_pages[:12],
            "worsened": worsened_pages[:12],
            "new_pages": new_pages[:12],
            "removed_pages": removed_pages[:12],
            "common_urls": len(common_urls),
        },
    }


def infer_target_keyword(url_data, stored_keyword: Optional[str] = None) -> str:
    if stored_keyword:
        return stored_keyword.strip()
    candidates = [url_data.h1_1, url_data.title_1]
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate.strip()[:80]
    path = urlparse(url_data.url).path.strip("/").split("/")
    if path and path[-1]:
        return path[-1].replace("-", " ").replace("_", " ")[:80]
    return ""


def build_page_insight(
    url_data,
    homepage_url: str,
    audit_config: Optional[Dict[str, object]] = None,
    target_keyword: Optional[str] = None
) -> Dict[str, object]:
    config = audit_config or resolve_audit_config()
    audit = build_page_audit(url_data, homepage_url, config)
    keyword = infer_target_keyword(url_data, target_keyword)
    normalized_keyword = keyword.lower().strip()
    title = (url_data.title_1 or "").strip()
    meta_description = (url_data.meta_description_1 or "").strip()
    h1 = (url_data.h1_1 or "").strip()
    strengths = []
    gaps = []
    sections_to_add = []
    keyword_opportunities = []

    if title and 30 <= (url_data.title_1_length or 0) <= 60:
        strengths.append("Title có độ dài ổn định, thuận lợi cho CTR và khả năng đọc hiểu.")
    if meta_description and 70 <= (url_data.meta_description_1_length or 0) <= 155:
        strengths.append("Meta description đang nằm trong khoảng hiển thị tốt trên kết quả tìm kiếm.")
    if h1:
        strengths.append("Trang đã có H1 rõ ràng để định nghĩa chủ đề chính.")
    if (url_data.word_count or 0) >= 700:
        strengths.append("Nội dung đủ dày để phát triển chiều sâu chủ đề.")
    if (url_data.response_time or 0) and (url_data.response_time or 0) < 1.2:
        strengths.append("Trang phản hồi nhanh, tốt cho trải nghiệm người dùng và crawl budget.")
    if (url_data.inlinks or 0) >= 10:
        strengths.append("Trang đang nhận được internal link tốt, hỗ trợ crawl và phân phối authority.")

    for issue in audit["issues"]:
        if issue["severity"] == "critical":
            gaps.append(f"{issue['label']} cần được ưu tiên xử lý trước.")
        elif issue["severity"] == "warning" and len(gaps) < 6:
            gaps.append(f"{issue['label']} đang làm giảm điểm audit của trang.")

    if "missing_h2" in [issue["code"] for issue in audit["issues"]]:
        sections_to_add.append("Thêm các H2 theo từng cụm nội dung chính để chia nhỏ bài viết và bao phủ entity liên quan.")
    if "low_content" in [issue["code"] for issue in audit["issues"]]:
        sections_to_add.append("Bổ sung phần FAQ, ví dụ thực tế hoặc checklist để tăng độ sâu nội dung.")
    if "missing_structured_data" in [issue["code"] for issue in audit["issues"]]:
        sections_to_add.append("Thêm JSON-LD phù hợp với loại nội dung hiện tại để tăng khả năng hiểu ngữ nghĩa.")
    if "low_internal_outlinks" in [issue["code"] for issue in audit["issues"]]:
        sections_to_add.append("Thêm internal link tới các trang cùng chủ đề và các trang chuyển đổi quan trọng.")

    if normalized_keyword:
        if normalized_keyword not in title.lower():
            keyword_opportunities.append("Từ khóa mục tiêu chưa xuất hiện trong title.")
        if normalized_keyword not in meta_description.lower():
            keyword_opportunities.append("Từ khóa mục tiêu chưa xuất hiện trong meta description.")
        if normalized_keyword not in h1.lower():
            keyword_opportunities.append("Từ khóa mục tiêu chưa xuất hiện trong H1.")
        if normalized_keyword.replace(" ", "-") not in url_data.url.lower():
            keyword_opportunities.append("Slug URL chưa phản ánh rõ từ khóa mục tiêu.")

    auto_fix_candidates = [issue["label"] for issue in audit["issues"] if issue["auto_fix"]][:6]
    summary = (
        f"Trang đạt {audit['seo_score']}/100 và đang ở nhóm {priority_label(audit['priority'])}. "
        f"Phát hiện {len(audit['issues'])} vấn đề, gồm {audit['severity_counts']['critical']} lỗi nghiêm trọng, "
        f"{audit['severity_counts']['warning']} cảnh báo và {audit['severity_counts']['info']} thông tin cần theo dõi."
    )

    return {
        "target_keyword": keyword,
        "summary": summary,
        "overview": {
            "seo_score": audit["seo_score"],
            "priority": audit["priority"],
            "severity_counts": audit["severity_counts"],
            "category_scores": audit["category_scores"],
        },
        "strengths": strengths[:5],
        "gaps": gaps[:6],
        "sections_to_add": sections_to_add[:5],
        "keyword_opportunities": keyword_opportunities[:6],
        "auto_fix_candidates": auto_fix_candidates,
        "issues": audit["issues"],
    }


def build_issue_catalog(
    db: Database,
    session_id: str,
    profile: Optional[str] = None,
    mode: Optional[str] = None,
) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    audit_config = resolve_audit_config(profile, mode)
    issue_map = {}
    for url_data in db.get_all_urls(session_id):
        audit = build_page_audit(url_data, session.start_url, audit_config)
        for issue in audit["issues"]:
            bucket = issue_map.setdefault(issue["code"], {
                "code": issue["code"],
                "label": issue["label"],
                "severity": issue["severity"],
                "category": issue["category"],
                "category_label": issue["category_label"],
                "auto_fix": issue["auto_fix"],
                "penalty": issue["penalty"],
                "count": 0,
                "affected_urls": [],
            })
            bucket["count"] += 1
            if len(bucket["affected_urls"]) < 25:
                bucket["affected_urls"].append({
                    "url": url_data.url,
                    "title": url_data.title_1,
                    "seo_score": audit["seo_score"],
                    "priority": audit["priority"],
                })

    issues = list(issue_map.values())
    for row in issues:
        row["impact_score"] = row["count"] * row["penalty"]
    issues.sort(key=lambda item: (-item["impact_score"], -SEVERITY_ORDER[item["severity"]], item["label"]))

    return {
        "summary": {
            "critical": sum(1 for row in issues if row["severity"] == "critical"),
            "warning": sum(1 for row in issues if row["severity"] == "warning"),
            "info": sum(1 for row in issues if row["severity"] == "info"),
            "total_issue_types": len(issues),
        },
        "issues": issues,
    }


def build_cannibalization_report(
    db: Database,
    session_id: str,
    profile: Optional[str] = None,
    mode: Optional[str] = None,
) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    audit_config = resolve_audit_config(profile, mode)
    urls = db.get_all_urls(session_id)
    page_audits = {row.url: build_page_audit(row, session.start_url, audit_config) for row in urls}

    groups = []

    def add_exact_groups(signal_key: str, signal_label: str, extractor):
        buckets = defaultdict(list)
        for row in urls:
            value = (extractor(row) or "").strip()
            if value:
                buckets[value].append(row)
        for value, bucket in buckets.items():
            if len(bucket) < 2:
                continue
            impact_score = len(bucket) * (8 if signal_key != "meta" else 6)
            groups.append({
                "type": "exact",
                "signal": signal_key,
                "signal_label": signal_label,
                "value": value,
                "group_size": len(bucket),
                "impact_score": impact_score,
                "severity": "warning" if signal_key == "meta" else "critical",
                "urls": [
                    {
                        "url": row.url,
                        "title": row.title_1,
                        "seo_score": page_audits[row.url]["seo_score"],
                        "priority": page_audits[row.url]["priority"],
                        "issues_count": len(page_audits[row.url]["issues"]),
                    }
                    for row in bucket[:12]
                ],
            })

    add_exact_groups("title", "Duplicate Titles", lambda row: row.title_1)
    add_exact_groups("meta", "Duplicate Meta Descriptions", lambda row: row.meta_description_1)
    add_exact_groups("h1", "Duplicate H1", lambda row: row.h1_1)

    seen_pairs = set()
    for row in urls:
        match_url = (row.closest_similarity_match or "").strip()
        raw_score = float(row.closest_similarity_score or 0)
        normalized_score = raw_score / 100 if raw_score > 1 else raw_score
        if not match_url or normalized_score < 0.82:
            continue
        normalized_pair = tuple(sorted([normalize_url(row.url), normalize_url(match_url)]))
        if normalized_pair in seen_pairs:
            continue
        seen_pairs.add(normalized_pair)
        target = db.get_url(session_id, match_url)
        bucket = [row]
        if target:
            bucket.append(target)
        groups.append({
            "type": "similarity",
            "signal": "content",
            "signal_label": "Near-Duplicate Content",
            "value": f"Similarity {round(normalized_score * 100, 1)}%",
            "group_size": len(bucket),
            "impact_score": round(normalized_score * len(bucket) * 10, 1),
            "severity": "warning",
            "urls": [
                {
                    "url": item.url,
                    "title": item.title_1,
                    "seo_score": page_audits.get(item.url, {}).get("seo_score"),
                    "priority": page_audits.get(item.url, {}).get("priority"),
                    "issues_count": len(page_audits.get(item.url, {}).get("issues", [])),
                }
                for item in bucket
            ],
        })

    groups.sort(key=lambda item: (-item["impact_score"], -item["group_size"], item["signal_label"], item["value"]))
    return {
        "summary": {
            "total_groups": len(groups),
            "title_groups": sum(1 for item in groups if item["signal"] == "title"),
            "meta_groups": sum(1 for item in groups if item["signal"] == "meta"),
            "h1_groups": sum(1 for item in groups if item["signal"] == "h1"),
            "content_groups": sum(1 for item in groups if item["signal"] == "content"),
        },
        "groups": groups,
    }


def build_fix_queue_report(
    db: Database,
    session_id: str,
    profile: Optional[str] = None,
    mode: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    audit_config = resolve_audit_config(profile, mode)
    items = db.get_fix_queue(session_id, status=status)
    rows = []
    status_totals = Counter()
    priority_totals = Counter()
    for item in items:
        url_data = db.get_url(session_id, item["url"])
        audit = build_page_audit(url_data, session.start_url, audit_config) if url_data else None
        status_totals[item["status"] or "queued"] += 1
        priority_totals[item.get("priority") or "warning"] += 1
        rows.append({
            **item,
            "seo_score": audit["seo_score"] if audit else None,
            "url_priority": audit["priority"] if audit else None,
            "issues_count": len(audit["issues"]) if audit else None,
            "title": url_data.title_1 if url_data else None,
        })

    return {
        "summary": {
            "queued": status_totals["queued"],
            "in_progress": status_totals["in_progress"],
            "done": status_totals["done"],
            "total": len(rows),
            "critical": priority_totals["critical"],
            "warning": priority_totals["warning"],
            "pass": priority_totals["pass"],
        },
        "items": rows,
    }


def build_social_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    rows = []
    summary = Counter()
    for row in db.get_all_urls(session_id):
        issues = []
        if not (row.og_title or "").strip():
            issues.append("missing_og_title")
            summary["missing_og_title"] += 1
        if not (row.og_description or "").strip():
            issues.append("missing_og_description")
            summary["missing_og_description"] += 1
        if not (row.og_image or "").strip():
            issues.append("missing_og_image")
            summary["missing_og_image"] += 1
        if not (row.twitter_card or "").strip():
            issues.append("missing_twitter_card")
            summary["missing_twitter_card"] += 1
        if not (row.twitter_title or "").strip():
            issues.append("missing_twitter_title")
            summary["missing_twitter_title"] += 1
        if not (row.twitter_description or "").strip():
            issues.append("missing_twitter_description")
            summary["missing_twitter_description"] += 1
        if not (row.twitter_image or "").strip():
            issues.append("missing_twitter_image")
            summary["missing_twitter_image"] += 1
        if issues:
            rows.append({
                "url": row.url,
                "title": row.title_1,
                "status_code": row.status_code,
                "og_title": row.og_title,
                "og_description": row.og_description,
                "og_image": row.og_image,
                "twitter_card": row.twitter_card,
                "twitter_title": row.twitter_title,
                "twitter_description": row.twitter_description,
                "twitter_image": row.twitter_image,
                "issues": issues,
            })
    return {
        "summary": {
            "total_urls": len(db.get_all_urls(session_id)),
            **summary,
        },
        "rows": rows,
    }


def build_schema_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    rows = []
    type_counter = Counter()
    summary = Counter()
    urls = db.get_all_urls(session_id)
    for row in urls:
        has_schema = bool(row.has_json_ld or row.has_microdata or row.has_rdfa)
        if has_schema:
            summary["with_schema"] += 1
        else:
            summary["missing_schema"] += 1
        summary["json_ld"] += 1 if row.has_json_ld else 0
        summary["validation_errors"] += 1 if (row.schema_validation_errors or 0) > 0 else 0
        summary["validation_warnings"] += 1 if (row.schema_validation_warnings or 0) > 0 else 0

        types = [item.strip() for item in (row.schema_types or "").split(",") if item.strip()]
        for schema_type in types:
            type_counter[schema_type] += 1

        if not has_schema or row.schema_validation_errors or row.schema_validation_warnings:
            rows.append({
                "url": row.url,
                "title": row.title_1,
                "status_code": row.status_code,
                "has_json_ld": bool(row.has_json_ld),
                "has_microdata": bool(row.has_microdata),
                "has_rdfa": bool(row.has_rdfa),
                "schema_types": types,
                "schema_validation_errors": row.schema_validation_errors or 0,
                "schema_validation_warnings": row.schema_validation_warnings or 0,
            })

    return {
        "summary": {
            "total_urls": len(urls),
            **summary,
        },
        "types": [{"type": key, "count": count} for key, count in type_counter.most_common(12)],
        "rows": rows,
    }


def build_link_opportunities_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    urls = db.get_all_urls(session_id)
    links = db.get_links(session_id)
    url_map = {row.url: row for row in urls}
    outgoing_map = defaultdict(set)
    for link in links:
        if link.is_internal:
            outgoing_map[normalize_url(link.source_url)].add(normalize_url(link.target_url))

    candidates = sorted(urls, key=lambda row: ((row.link_score or 0), (row.inlinks or 0)), reverse=True)
    opportunities = []
    for target in urls:
        if (target.inlinks or 0) > 5 and (target.outlinks or 0) >= 5 and (target.crawl_depth or 0) < 2:
            continue
        target_path = urlparse(target.url).path.strip("/").split("/")
        target_section = target_path[0] if target_path and target_path[0] else ""
        suggestions = []
        normalized_target = normalize_url(target.url)
        for source in candidates:
            normalized_source = normalize_url(source.url)
            if normalized_source == normalized_target:
                continue
            if normalized_target in outgoing_map.get(normalized_source, set()):
                continue
            source_path = urlparse(source.url).path.strip("/").split("/")
            source_section = source_path[0] if source_path and source_path[0] else ""
            relevance = 2 if target_section and target_section == source_section else 0
            relevance += 1 if (source.crawl_depth or 0) <= max((target.crawl_depth or 0) - 1, 0) else 0
            if relevance == 0:
                continue
            suggestions.append({
                "source_url": source.url,
                "source_title": source.title_1,
                "link_score": round(source.link_score or 0, 1),
                "inlinks": source.inlinks or 0,
                "relevance": relevance,
                "anchor_suggestion": (target.h1_1 or target.title_1 or urlparse(target.url).path.strip("/")).strip()[:80],
            })
            if len(suggestions) >= 3:
                break
        if suggestions:
            opportunities.append({
                "target_url": target.url,
                "target_title": target.title_1,
                "target_score": round(target.link_score or 0, 1),
                "target_inlinks": target.inlinks or 0,
                "target_outlinks": target.outlinks or 0,
                "crawl_depth": target.crawl_depth or 0,
                "suggestions": suggestions,
            })

    opportunities.sort(key=lambda item: (item["target_inlinks"], item["target_outlinks"], -item["target_score"], item["target_url"]))
    return {
        "summary": {
            "targets": len(opportunities),
            "low_inlinks": sum(1 for row in opportunities if row["target_inlinks"] <= 2),
            "low_outlinks": sum(1 for row in opportunities if row["target_outlinks"] < 3),
            "deep_pages": sum(1 for row in opportunities if row["crawl_depth"] >= 3),
        },
        "rows": opportunities[:50],
    }


def build_link_audit_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    urls = db.get_all_urls(session_id)
    links = [link for link in db.get_links(session_id) if (link.link_type or "href") == "href"]
    weak_anchors = {
        "", "click here", "here", "read more", "learn more", "more",
        "xem them", "xem thêm", "xem chi tiet", "xem chi tiết", "chi tiet",
        "chi tiết", "tại đây", "tai day", "xem ngay", "xem tiếp",
    }

    grouped_links = defaultdict(list)
    anchor_counter = Counter()
    for link in links:
        grouped_links[normalize_url(link.source_url)].append(link)
        anchor_text = (link.anchor_text or "").strip()
        if anchor_text:
            anchor_counter[anchor_text] += 1

    summary = Counter()
    rows = []

    for row in urls:
        row_links = grouped_links.get(normalize_url(row.url), [])
        internal_links = [link for link in row_links if link.is_internal]
        external_links = [link for link in row_links if not link.is_internal]
        nofollow_links = [link for link in row_links if link.is_nofollow]
        empty_anchor_links = [link for link in row_links if not (link.anchor_text or "").strip()]
        weak_anchor_links = [
            link for link in row_links
            if (link.anchor_text or "").strip().lower() in weak_anchors
        ]

        summary["total_links"] += len(row_links)
        summary["internal_links"] += len(internal_links)
        summary["external_links"] += len(external_links)
        summary["nofollow_links"] += len(nofollow_links)
        summary["empty_anchor_links"] += len(empty_anchor_links)
        summary["weak_anchor_links"] += len(weak_anchor_links)

        issues = []
        if row.indexability == "Indexable" and len(internal_links) < 3:
            issues.append("Ít internal link đầu ra")
            summary["pages_with_low_internal_links"] += 1
        if weak_anchor_links or empty_anchor_links:
            issues.append("Anchor text yếu hoặc trống")
            summary["pages_with_weak_anchor_issues"] += 1
        if len(external_links) >= 20:
            issues.append("Quá nhiều external links")
            summary["pages_with_high_external_links"] += 1
        if len(nofollow_links) >= 10:
            issues.append("Tỷ lệ nofollow cao")

        if not issues:
            continue

        top_anchors = Counter(
            (link.anchor_text or "").strip()
            for link in internal_links
            if (link.anchor_text or "").strip()
        ).most_common(5)

        rows.append({
            "url": row.url,
            "title": row.title_1,
            "status_code": row.status_code,
            "internal_links": len(internal_links),
            "external_links": len(external_links),
            "nofollow_links": len(nofollow_links),
            "empty_anchor_links": len(empty_anchor_links),
            "weak_anchor_links": len(weak_anchor_links),
            "crawl_depth": row.crawl_depth or 0,
            "inlinks": row.inlinks or 0,
            "link_score": round(row.link_score or 0, 1),
            "issues": issues,
            "top_anchors": [
                {"anchor": anchor, "count": count}
                for anchor, count in top_anchors
            ],
        })

    rows.sort(
        key=lambda item: (
            -len(item["issues"]),
            item["internal_links"],
            -item["external_links"],
            item["url"],
        )
    )

    return {
        "summary": {
            "total_pages": len(urls),
            "total_links": summary["total_links"],
            "internal_links": summary["internal_links"],
            "external_links": summary["external_links"],
            "nofollow_links": summary["nofollow_links"],
            "empty_anchor_links": summary["empty_anchor_links"],
            "weak_anchor_links": summary["weak_anchor_links"],
            "pages_with_low_internal_links": summary["pages_with_low_internal_links"],
            "pages_with_weak_anchor_issues": summary["pages_with_weak_anchor_issues"],
            "pages_with_high_external_links": summary["pages_with_high_external_links"],
        },
        "top_anchors": [
            {"anchor": anchor, "count": count}
            for anchor, count in anchor_counter.most_common(15)
        ],
        "rows": rows[:100],
    }


def build_directives_audit_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    urls = db.get_all_urls(session_id)
    html_rows = [row for row in urls if "text/html" in (row.content_type or "")]
    html_by_url = {normalize_url(row.url): row for row in html_rows}
    canonical_map = {}
    for row in html_rows:
        if row.canonical_link_element_1:
            canonical_map[normalize_url(row.url)] = normalize_url(
                urljoin(row.url, row.canonical_link_element_1)
            )

    def canonical_chain_info(start_url: str) -> Dict[str, object]:
        path = [start_url]
        visited = {start_url}
        current = start_url
        hops = 0

        while True:
            target = canonical_map.get(current)
            if not target or target == current:
                return {
                    "hops": hops,
                    "is_loop": False,
                    "path": path,
                }

            path.append(target)
            hops += 1

            if target in visited:
                return {
                    "hops": hops,
                    "is_loop": True,
                    "path": path,
                }

            visited.add(target)

            # Stop chain traversal once canonical points outside crawled HTML set.
            if target not in html_by_url:
                return {
                    "hops": hops,
                    "is_loop": False,
                    "path": path,
                }

            current = target

            if hops >= 50:
                return {
                    "hops": hops,
                    "is_loop": True,
                    "path": path,
                }

    summary = Counter()
    rows = []

    for row in html_rows:
        issues = []
        canonical = row.canonical_link_element_1
        normalized_current = normalize_url(row.url)
        normalized_canonical = normalize_url(urljoin(row.url, canonical)) if canonical else None
        canonical_chain = canonical_chain_info(normalized_current)

        if not canonical:
            issues.append("Thiếu canonical")
            summary["missing_canonical"] += 1
        elif normalized_canonical == normalized_current:
            issues.append("Canonical tự tham chiếu")
            summary["self_referencing_canonical"] += 1
        else:
            issues.append("Canonical trỏ sang URL khác")
            summary["cross_canonical"] += 1

        if canonical and canonical_chain["is_loop"]:
            issues.append("Canonical loop")
            summary["canonical_loops"] += 1
        elif canonical and canonical_chain["hops"] >= 2:
            issues.append(f"Canonical chain ({canonical_chain['hops']} hops)")
            summary["canonical_chains"] += 1

        target_row = html_by_url.get(normalized_canonical) if normalized_canonical else None
        if target_row and normalized_canonical != normalized_current:
            if (target_row.indexability or "").lower() != "indexable":
                issues.append("Canonical trỏ đến URL non-indexable")
                summary["canonical_to_non_indexable"] += 1
            target_status = target_row.status_code or 0
            if target_status and not (200 <= target_status < 300):
                issues.append("Canonical trỏ đến URL non-200")
                summary["canonical_to_non_200"] += 1

        meta_robots = ", ".join([
            item for item in [row.meta_robots_1, row.meta_robots_2] if item
        ])
        x_robots = ", ".join([
            item for item in [row.x_robots_tag_1, row.x_robots_tag_2] if item
        ])
        directives_text = f"{meta_robots} {x_robots}".lower()
        if "noindex" in directives_text:
            issues.append("Có chỉ thị noindex")
            summary["noindex"] += 1
        if "nofollow" in directives_text:
            issues.append("Có chỉ thị nofollow")
            summary["nofollow"] += 1
        if row.meta_refresh_1:
            issues.append("Có meta refresh")
            summary["meta_refresh"] += 1
        if row.rel_next_1 or row.rel_prev_1 or row.http_rel_next_1 or row.http_rel_prev_1:
            summary["pagination_hints"] += 1
        if row.amphtml_link:
            summary["amphtml"] += 1
        if row.mobile_alternate_link:
            summary["mobile_alternate"] += 1

        if not issues and not row.rel_next_1 and not row.rel_prev_1 and not row.http_rel_next_1 and not row.http_rel_prev_1:
            continue

        rows.append({
            "url": row.url,
            "status_code": row.status_code,
            "indexability": row.indexability,
            "indexability_status": row.indexability_status,
            "canonical": canonical,
            "canonical_chain_hops": canonical_chain["hops"],
            "canonical_chain_path": canonical_chain["path"] if canonical_chain["hops"] > 0 else [],
            "canonical_target_status_code": target_row.status_code if target_row else None,
            "canonical_target_indexability": target_row.indexability if target_row else None,
            "meta_robots": meta_robots or None,
            "x_robots_tag": x_robots or None,
            "meta_refresh": row.meta_refresh_1,
            "rel_next": row.rel_next_1 or row.http_rel_next_1,
            "rel_prev": row.rel_prev_1 or row.http_rel_prev_1,
            "amphtml": row.amphtml_link,
            "mobile_alternate": row.mobile_alternate_link,
            "issues": issues,
        })

    rows.sort(key=lambda item: (-len(item["issues"]), item["url"]))
    return {
        "summary": {
            "total_html_pages": len(html_rows),
            "missing_canonical": summary["missing_canonical"],
            "cross_canonical": summary["cross_canonical"],
            "self_referencing_canonical": summary["self_referencing_canonical"],
            "canonical_chains": summary["canonical_chains"],
            "canonical_loops": summary["canonical_loops"],
            "canonical_to_non_indexable": summary["canonical_to_non_indexable"],
            "canonical_to_non_200": summary["canonical_to_non_200"],
            "noindex": summary["noindex"],
            "nofollow": summary["nofollow"],
            "meta_refresh": summary["meta_refresh"],
            "pagination_hints": summary["pagination_hints"],
            "amphtml": summary["amphtml"],
            "mobile_alternate": summary["mobile_alternate"],
        },
        "rows": rows[:200],
    }


def build_image_audit_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    images = db.get_images(session_id)
    image_usage = defaultdict(set)
    summary = Counter()
    rows = []

    for image in images:
        image_usage[image.image_url].add(image.page_url)

    for image in images:
        issues = []
        if image.missing_alt or image.missing_alt_attribute:
            issues.append("Thiếu alt")
            summary["missing_alt"] += 1
        if image.missing_alt_attribute:
            issues.append("Thiếu hẳn thuộc tính alt")
            summary["missing_alt_attribute"] += 1
        if (image.alt_text_length or 0) > 100:
            issues.append("Alt text quá dài")
            summary["alt_over_100_chars"] += 1
        if image.missing_size_attributes:
            issues.append("Thiếu width/height")
            summary["missing_size"] += 1
        usage_count = len(image_usage.get(image.image_url, set()))
        if usage_count >= 5:
            summary["reused_images"] += 1

        if not issues and usage_count < 5:
            continue

        rows.append({
            "page_url": image.page_url,
            "image_url": image.image_url,
            "alt_text": image.alt_text,
            "alt_text_length": image.alt_text_length or 0,
            "width": image.width,
            "height": image.height,
            "used_on_pages": usage_count,
            "issues": issues,
        })

    rows.sort(key=lambda item: (-len(item["issues"]), -item["used_on_pages"], item["image_url"]))
    return {
        "summary": {
            "total_images": len(images),
            "missing_alt": summary["missing_alt"],
            "missing_alt_attribute": summary["missing_alt_attribute"],
            "alt_over_100_chars": summary["alt_over_100_chars"],
            "missing_size": summary["missing_size"],
            "reused_images": summary["reused_images"],
        },
        "rows": rows[:250],
    }


def build_content_quality_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    urls = db.get_all_urls(session_id)
    rows = []
    summary = Counter()
    readability_values = []
    for row in urls:
        if row.readability:
            readability_values.append(row.readability)
        issues = []
        if (row.word_count or 0) < 300:
            issues.append("thin_content")
            summary["thin_content"] += 1
        if (row.text_ratio or 0) < 15:
            issues.append("low_text_ratio")
            summary["low_text_ratio"] += 1
        if (row.readability or 0) > 0 and (row.readability or 0) < 35:
            issues.append("hard_to_read")
            summary["hard_to_read"] += 1
        if (row.avg_words_per_sentence or 0) > 22:
            issues.append("long_sentences")
            summary["long_sentences"] += 1
        if issues:
            rows.append({
                "url": row.url,
                "title": row.title_1,
                "status_code": row.status_code,
                "word_count": row.word_count or 0,
                "text_ratio": round(row.text_ratio or 0, 1),
                "readability": round(row.readability or 0, 1),
                "avg_words_per_sentence": round(row.avg_words_per_sentence or 0, 1),
                "issues": issues,
            })
    rows.sort(key=lambda item: (item["word_count"], item["text_ratio"], item["readability"]))
    return {
        "summary": {
            "total_urls": len(urls),
            "avg_readability": round(sum(readability_values) / max(len(readability_values), 1), 1) if readability_values else 0,
            **summary,
        },
        "rows": rows,
    }


def build_security_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    urls = db.get_all_urls(session_id)
    rows = []
    summary = Counter()
    for row in urls:
        issues = []
        if not row.is_https:
            issues.append("http_url")
            summary["http_url"] += 1
        if row.is_https and not row.hsts:
            issues.append("missing_hsts")
            summary["missing_hsts"] += 1
        if row.has_mixed_content:
            issues.append("mixed_content")
            summary["mixed_content"] += 1
        if row.has_insecure_forms:
            issues.append("insecure_forms")
            summary["insecure_forms"] += 1
        if (row.unsafe_cross_origin_links or 0) > 0:
            issues.append("unsafe_cross_origin_links")
            summary["unsafe_cross_origin_links"] += 1
        if issues:
            rows.append({
                "url": row.url,
                "title": row.title_1,
                "status_code": row.status_code,
                "is_https": bool(row.is_https),
                "hsts": bool(row.hsts),
                "csp": bool(row.csp),
                "x_frame_options": bool(row.x_frame_options),
                "referrer_policy": bool(row.referrer_policy),
                "unsafe_cross_origin_links": row.unsafe_cross_origin_links or 0,
                "issues": issues,
            })
    return {"summary": {"total_urls": len(urls), **summary}, "rows": rows}


def build_performance_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    urls = db.get_all_urls(session_id)
    rows = []
    response_values = [row.response_time for row in urls if row.response_time]
    ttfb_values = [row.ttfb for row in urls if row.ttfb]
    summary = Counter()
    for row in urls:
        issues = []
        if (row.response_time or 0) >= 2:
            issues.append("slow_response")
            summary["slow_response"] += 1
        if (row.ttfb or 0) >= 0.8:
            issues.append("slow_ttfb")
            summary["slow_ttfb"] += 1
        if (row.size or 0) >= 1_500_000:
            issues.append("large_page")
            summary["large_page"] += 1
        if issues:
            rows.append({
                "url": row.url,
                "title": row.title_1,
                "status_code": row.status_code,
                "response_time": round(row.response_time or 0, 3),
                "ttfb": round(row.ttfb or 0, 3),
                "size_kb": round((row.size or 0) / 1024, 1),
                "transferred_kb": round((row.transferred or 0) / 1024, 1),
                "issues": issues,
            })
    rows.sort(key=lambda item: (-item["response_time"], -item["ttfb"], -item["size_kb"]))
    return {
        "summary": {
            "total_urls": len(urls),
            "avg_response_time": round(sum(response_values) / max(len(response_values), 1), 3) if response_values else 0,
            "avg_ttfb": round(sum(ttfb_values) / max(len(ttfb_values), 1), 3) if ttfb_values else 0,
            **summary,
        },
        "rows": rows,
    }


def build_url_structure_report(db: Database, session_id: str) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    urls = db.get_all_urls(session_id)
    rows = []
    summary = Counter()
    for row in urls:
        issues = []
        if (row.url_length or 0) > 115:
            issues.append("long_url")
            summary["long_url"] += 1
        if row.has_parameters:
            issues.append("has_parameters")
            summary["has_parameters"] += 1
        if row.has_underscores:
            issues.append("has_underscores")
            summary["has_underscores"] += 1
        if row.has_uppercase:
            issues.append("has_uppercase")
            summary["has_uppercase"] += 1
        if row.has_non_ascii:
            issues.append("has_non_ascii")
            summary["has_non_ascii"] += 1
        if (row.folder_depth or 0) >= 4:
            issues.append("deep_folder")
            summary["deep_folder"] += 1
        if issues:
            rows.append({
                "url": row.url,
                "title": row.title_1,
                "status_code": row.status_code,
                "url_length": row.url_length or 0,
                "folder_depth": row.folder_depth or 0,
                "has_parameters": bool(row.has_parameters),
                "has_underscores": bool(row.has_underscores),
                "has_uppercase": bool(row.has_uppercase),
                "has_non_ascii": bool(row.has_non_ascii),
                "issues": issues,
            })
    rows.sort(key=lambda item: (-item["url_length"], -item["folder_depth"], item["url"]))
    return {"summary": {"total_urls": len(urls), **summary}, "rows": rows}


def bulk_populate_fix_queue(
    db: Database,
    session_id: str,
    source: str,
    limit: int = 10,
    profile: Optional[str] = None,
    mode: Optional[str] = None,
    segment: Optional[str] = None,
    issue_code: Optional[str] = None,
) -> Dict[str, object]:
    session = db.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    created = 0
    touched_urls = set()
    normalized_limit = max(1, min(limit, 100))

    if source == "priorities":
        priorities = build_priorities_report(
            db,
            session_id,
            profile=profile,
            mode=mode,
            priority="critical",
            segment=segment,
            limit=normalized_limit,
        )
        if not priorities["rows"]:
            priorities = build_priorities_report(
                db,
                session_id,
                profile=profile,
                mode=mode,
                priority="warning",
                segment=segment,
                limit=normalized_limit,
            )
        for row in priorities["rows"]:
            db.upsert_fix_queue_item(
                session_id,
                row["url"],
                None,
                "Priority page",
                row["priority"],
                "queued",
                ", ".join(issue["label"] for issue in row["top_issues"][:3]),
            )
            created += 1
            touched_urls.add(row["url"])
    elif source == "issues":
        issue_catalog = build_issue_catalog(db, session_id, profile, mode)
        selected_issues = issue_catalog["issues"]
        if issue_code:
            selected_issues = [row for row in selected_issues if row["code"] == issue_code]
        for issue in selected_issues[:normalized_limit]:
            for row in issue["affected_urls"][:10]:
                db.upsert_fix_queue_item(
                    session_id,
                    row["url"],
                    issue["code"],
                    issue["label"],
                    row["priority"],
                    "queued",
                    issue["category_label"],
                )
                created += 1
                touched_urls.add(row["url"])
    elif source == "cannibalization":
        report = build_cannibalization_report(db, session_id, profile, mode)
        for group in report["groups"][:normalized_limit]:
            for row in group["urls"][:10]:
                db.upsert_fix_queue_item(
                    session_id,
                    row["url"],
                    "cannibalization",
                    group["signal_label"],
                    row["priority"],
                    "queued",
                    group["value"],
                )
                created += 1
                touched_urls.add(row["url"])
    else:
        raise ValueError("Unsupported bulk queue source")

    return {
        "status": "queued",
        "source": source,
        "items_touched": created,
        "unique_urls": len(touched_urls),
    }


def render_audit_report_html(
    db: Database,
    session_id: str,
    profile: Optional[str] = None,
    mode: Optional[str] = None,
) -> str:
    report = build_summary_report(db, session_id, profile, mode)
    priorities = build_priorities_report(db, session_id, profile, mode, limit=20)
    issue_catalog = build_issue_catalog(db, session_id, profile, mode)

    issue_rows = "".join(
        f"""
        <tr>
            <td>{escape(str(row['label']))}</td>
            <td>{escape(str(row['severity']))}</td>
            <td>{escape(str(row['category_label']))}</td>
            <td>{row['count']}</td>
            <td>{row['impact_score']}</td>
        </tr>
        """
        for row in issue_catalog["issues"][:20]
    )
    priority_rows = "".join(
        f"""
        <tr>
            <td>{escape(str(row['url']))}</td>
            <td>{row['seo_score']}</td>
            <td>{escape(str(row['priority']))}</td>
            <td>{row['issues_count']}</td>
            <td>{escape(', '.join(issue['label'] for issue in row['top_issues'][:3]))}</td>
        </tr>
        """
        for row in priorities["rows"][:20]
    )
    recommendation_rows = "".join(
        f"<li><strong>{escape(str(item['title']))}</strong>: {escape(str(item['detail']))}</li>"
        for item in report["recommendations"]
    )

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Yelling Frog Audit Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 32px; color: #111827; }}
            h1, h2 {{ margin-bottom: 8px; }}
            .muted {{ color: #6b7280; }}
            .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 24px 0; }}
            .card {{ border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 16px 0 24px; }}
            th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px 8px; text-align: left; vertical-align: top; }}
            th {{ background: #f9fafb; }}
            ul {{ padding-left: 18px; }}
        </style>
    </head>
    <body>
        <h1>SEO Audit Report</h1>
        <div class="muted">Website: {escape(str(report['session']['start_url']))} | Profile: {escape(str(report['audit_config']['profile_label']))} | Mode: {escape(str(report['audit_config']['mode_label']))}</div>
        <div class="muted">Started: {report['session']['started_at']} | Completed: {report['session']['completed_at'] or '-'}</div>

        <div class="grid">
            <div class="card"><div class="muted">SEO Score</div><div style="font-size: 28px; font-weight: 700;">{report['overview']['overall_score']}/100</div></div>
            <div class="card"><div class="muted">URLs</div><div style="font-size: 28px; font-weight: 700;">{report['overview']['total_urls']}</div></div>
            <div class="card"><div class="muted">Total Issues</div><div style="font-size: 28px; font-weight: 700;">{report['overview']['total_issues']}</div></div>
            <div class="card"><div class="muted">Pages With Issues</div><div style="font-size: 28px; font-weight: 700;">{report['overview']['pages_with_issues']}</div></div>
        </div>

        <h2>Recommendations</h2>
        <ul>{recommendation_rows}</ul>

        <h2>Top Issue Types</h2>
        <table>
            <thead>
                <tr><th>Issue</th><th>Severity</th><th>Category</th><th>Affected URLs</th><th>Impact</th></tr>
            </thead>
            <tbody>{issue_rows}</tbody>
        </table>

        <h2>Priority Pages</h2>
        <table>
            <thead>
                <tr><th>URL</th><th>Score</th><th>Priority</th><th>Issue Count</th><th>Top Issues</th></tr>
            </thead>
            <tbody>{priority_rows}</tbody>
        </table>
    </body>
    </html>
    """


# ========== Request/Response Models ==========

class CrawlStartRequest(BaseModel):
    start_url: str
    max_urls: int = 10000
    max_depth: Optional[int] = None
    crawl_non_html: bool = False
    requests_per_second: float = 1.0
    respect_robots: bool = True
    user_agent: str = "WebCrawler/1.0"
    use_playwright: bool = True
    include_patterns: List[str] = Field(default_factory=list)
    exclude_patterns: List[str] = Field(default_factory=list)


class CrawlStatusResponse(BaseModel):
    session_id: str
    status: str
    start_url: str
    total_urls: int
    crawled_urls: int
    failed_urls: int
    progress_percentage: float
    started_at: str
    duration_seconds: Optional[float] = None


class URLDataResponse(BaseModel):
    url: str
    status_code: Optional[int]
    title: Optional[str]
    meta_description: Optional[str]
    h1: Optional[str]
    word_count: int
    indexability: str
    issues: List[str]


class StatsResponse(BaseModel):
    total_urls: int
    status_codes: dict
    indexable_count: int
    non_indexable_count: int
    avg_response_time: float
    avg_word_count: int
    issues_by_type: dict


class TargetKeywordRequest(BaseModel):
    url: str
    target_keyword: str


class FixQueueCreateRequest(BaseModel):
    url: str
    issue_code: Optional[str] = None
    issue_label: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None


class FixQueueUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[str] = None


class FixQueueBulkRequest(BaseModel):
    source: str
    limit: int = 10
    segment: Optional[str] = None
    issue_code: Optional[str] = None


# ========== Health Check ==========

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Web Crawler API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/sessions")
async def list_sessions(limit: int = Query(20, ge=1, le=100)):
    """List all crawl sessions (history)"""
    sessions = await run_blocking(database.get_all_sessions, limit=limit)
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "start_url": s.start_url,
                "status": s.status,
                "crawled_urls": s.crawled_urls,
                "total_urls": s.total_urls,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None
            }
            for s in sessions
        ]
    }


# ========== Crawl Control Endpoints ==========

@app.post("/crawl/start", response_model=CrawlStatusResponse)
async def start_crawl(request: CrawlStartRequest, background_tasks: BackgroundTasks):
    """
    Start a new crawl

    Args:
        request: Crawl configuration

    Returns:
        Crawl status with session ID
    """
    include_patterns = [
        pattern.strip()
        for pattern in (request.include_patterns or [])
        if pattern and pattern.strip()
    ]
    exclude_patterns = [
        pattern.strip()
        for pattern in (request.exclude_patterns or [])
        if pattern and pattern.strip()
    ]

    # Validate regex patterns before creating session/crawler
    try:
        for pattern in include_patterns:
            re.compile(pattern)
        for pattern in exclude_patterns:
            re.compile(pattern)
    except re.error as exc:
        raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {exc}")

    # Create session
    session = await run_blocking(
        database.create_session,
        start_url=request.start_url,
        max_urls=request.max_urls,
        max_depth=request.max_depth,
        respect_robots=request.respect_robots,
        user_agent=request.user_agent,
        config={
            "crawl_non_html": request.crawl_non_html,
            "use_playwright": request.use_playwright,
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
        }
    )

    # Create crawler
    crawler = WebCrawler(
        start_url=request.start_url,
        max_depth=request.max_depth or 10,
        max_urls=request.max_urls,
        crawl_non_html=request.crawl_non_html,
        requests_per_second=request.requests_per_second,
        use_playwright=request.use_playwright,
        user_agent=request.user_agent,
        respect_robots=request.respect_robots
    )

    for pattern in include_patterns:
        crawler.url_manager.add_include_pattern(pattern)
    for pattern in exclude_patterns:
        crawler.url_manager.add_exclude_pattern(pattern)

    # Store crawler instance
    active_crawlers[session.session_id] = crawler

    # Start crawl in background
    background_tasks.add_task(run_crawl, session.session_id, crawler)

    return CrawlStatusResponse(
        session_id=session.session_id,
        status=session.status,
        start_url=session.start_url,
        total_urls=0,
        crawled_urls=0,
        failed_urls=0,
        progress_percentage=0.0,
        started_at=session.started_at.isoformat()
    )


async def broadcast_to_websockets(session_id: str, message: dict):
    """Broadcast message to all connected WebSockets for a session"""
    if session_id in websocket_connections:
        dead_connections = []
        for ws in websocket_connections[session_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)

        # Remove dead connections
        for ws in dead_connections:
            websocket_connections[session_id].remove(ws)


async def run_crawl(session_id: str, crawler: WebCrawler):
    """
    Run crawl in background

    Args:
        session_id: Crawl session ID
        crawler: Crawler instance
    """
    try:
        # Initialize crawler
        await crawler.initialize()
        await run_blocking(
            database.save_sitemap_urls,
            session_id,
            crawler.sitemap_parser.get_urls(),
        )

        # Create page processor
        processor = PageProcessor(database, crawler.start_url, session_id)

        # Set up callback to process each page
        async def on_page_crawled(url: str, page_result):
            depth = (crawler.url_manager.get_url_metadata(url) or {}).get('depth', 0)
            headers = dict(page_result.headers or {})
            if page_result.error:
                headers['x-crawl-error'] = page_result.error
            if page_result.redirects:
                headers['x-redirect-chain'] = json.dumps(page_result.redirects)

            resolved_status_text = (
                page_result.status_text
                or status_text_from_code(page_result.status_code)
                or ("Request Error" if page_result.error else "Unknown")
            )

            # Persist every crawled URL (including failures) so technical audits are complete.
            await asyncio.to_thread(
                processor.process_page,
                url=url,
                html=page_result.html or "",
                raw_html=page_result.raw_html,
                status_code=page_result.status_code,
                status_text=resolved_status_text,
                headers=headers,
                response_time=page_result.load_time,
                ttfb=page_result.ttfb,
                crawl_depth=depth
            )

            # Update session stats
            stats = crawler.get_stats()
            await run_blocking(
                database.update_session,
                session_id,
                crawled_urls=stats['pages_crawled'],
                failed_urls=stats['pages_failed'],
                total_urls=stats['url_manager']['total_seen']
            )

            # Broadcast progress via WebSocket
            await broadcast_to_websockets(session_id, {
                "type": "progress",
                "url": url,
                "status_code": page_result.status_code if page_result.status_code else None,
                "crawled_urls": stats['pages_crawled'],
                "total_urls": stats['url_manager']['total_seen'],
                "failed_urls": stats['pages_failed']
            })

        crawler.on_page_crawled = on_page_crawled

        # Start crawling
        await crawler.crawl()

        # Post-process: Calculate link metrics
        await run_blocking(processor.post_process_link_metrics)
        if crawler.state == CrawlState.STOPPED:
            final_status = "stopped"
            completion_message = "Crawl stopped by user"
        elif crawler.state == CrawlState.ERROR:
            final_status = "failed"
            completion_message = "Crawl failed"
        else:
            final_status = "completed"
            completion_message = "Crawl completed successfully"

        await run_blocking(database.update_session, session_id, status=final_status)

        # Broadcast completion state
        await broadcast_to_websockets(session_id, {
            "type": final_status,
            "message": completion_message
        })

    except Exception as e:
        await run_blocking(database.update_session, session_id, status="failed")
        print(f"Crawl failed: {e}")
        import traceback
        traceback.print_exc()

        # Broadcast error
        await broadcast_to_websockets(session_id, {
            "type": "error",
            "message": str(e)
        })

    finally:
        # Remove from active crawlers
        active_crawlers.pop(session_id, None)


@app.get("/crawl/{session_id}/status", response_model=CrawlStatusResponse)
async def get_crawl_status(session_id: str):
    """Get crawl status"""
    session = await run_blocking(database.get_session, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Calculate progress
    progress = 0.0
    if session.status == "completed":
        progress = 100.0
    elif session.total_urls > 0:
        progress = (session.crawled_urls / max(session.total_urls, 1)) * 100
        progress = min(progress, 99.0)

    # Calculate duration
    duration = None
    if session.started_at:
        end_time = session.completed_at or datetime.now()
        duration = (end_time - session.started_at).total_seconds()

    return CrawlStatusResponse(
        session_id=session.session_id,
        status=session.status,
        start_url=session.start_url,
        total_urls=session.total_urls,
        crawled_urls=session.crawled_urls,
        failed_urls=session.failed_urls,
        progress_percentage=round(progress, 2),
        started_at=session.started_at.isoformat(),
        duration_seconds=duration
    )


@app.post("/crawl/{session_id}/pause")
async def pause_crawl(session_id: str):
    """Pause an active crawl"""
    crawler = active_crawlers.get(session_id)

    if not crawler:
        raise HTTPException(status_code=404, detail="Active crawler not found")

    await crawler.pause()
    await run_blocking(database.update_session, session_id, status="paused")
    await broadcast_to_websockets(session_id, {"type": "status", "status": "paused"})

    return {"status": "paused"}


@app.post("/crawl/{session_id}/resume")
async def resume_crawl(session_id: str):
    """Resume a paused crawl"""
    crawler = active_crawlers.get(session_id)

    if not crawler:
        raise HTTPException(status_code=404, detail="Active crawler not found")

    await crawler.resume()
    await run_blocking(database.update_session, session_id, status="running")
    await broadcast_to_websockets(session_id, {"type": "status", "status": "running"})

    return {"status": "running"}


@app.post("/crawl/{session_id}/stop")
async def stop_crawl(session_id: str):
    """Stop a crawl"""
    crawler = active_crawlers.get(session_id)

    if not crawler:
        raise HTTPException(status_code=404, detail="Active crawler not found")

    await crawler.stop()
    await run_blocking(database.update_session, session_id, status="stopped")
    await broadcast_to_websockets(session_id, {"type": "status", "status": "stopped"})
    active_crawlers.pop(session_id, None)

    return {"status": "stopped"}


# ========== Data Access Endpoints ==========

@app.get("/data/{session_id}/urls")
async def get_urls(
    session_id: str,
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    filter: Optional[str] = None,
    search: Optional[str] = Query(None, max_length=200),
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    sort_by: str = Query("crawled_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$")
):
    """
    Get URLs for a session

    Args:
        session_id: Crawl session ID
        limit: Number of URLs to return
        offset: Offset for pagination
        filter: Optional filter name (e.g., 'missing_title')
    """
    query_result = await run_blocking(
        database.query_urls,
        session_id=session_id,
        limit=limit,
        offset=offset,
        filter_name=filter,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )
    urls = query_result["urls"]
    session = await run_blocking(database.get_session, session_id)
    homepage_url = session.start_url if session else ""
    audit_config = resolve_audit_config(profile, mode)

    # Convert to response format
    response_urls = []
    for url_data in urls:
        audit = build_page_audit(url_data, homepage_url, audit_config)
        response_urls.append({
            "url": url_data.url,
            "status_code": url_data.status_code,
            "title": url_data.title_1,
            "title_length": url_data.title_1_length,
            "title_pixel_width": url_data.title_1_pixel_width,
            "meta_description": url_data.meta_description_1,
            "meta_description_length": url_data.meta_description_1_length,
            "meta_description_pixel_width": url_data.meta_description_1_pixel_width,
            "h1": url_data.h1_1,
            "h1_length": url_data.h1_len_1,
            "h2": url_data.h2_1,
            "h2_length": url_data.h2_len_1,
            "word_count": url_data.word_count,
            "indexability": url_data.indexability,
            "indexability_status": url_data.indexability_status,
            "issues": [issue["code"] for issue in audit["issues"]],
            "issues_count": len(audit["issues"]),
            "response_time": url_data.response_time,
            "crawl_depth": url_data.crawl_depth,
            "inlinks": url_data.inlinks,
            "link_score": url_data.link_score,
            "content_type": url_data.content_type,
            "canonical": url_data.canonical_link_element_1,
            "meta_robots": url_data.meta_robots_1,
            "x_robots_tag": url_data.x_robots_tag_1,
            "seo_score": audit["seo_score"] if audit else None,
            "priority": audit["priority"] if audit else None,
            "severity_counts": audit["severity_counts"] if audit else None,
        })

    return {
        "total": query_result["total"],
        "filtered_total": query_result["filtered_total"],
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(response_urls) < query_result["filtered_total"],
        "sort_by": sort_by,
        "sort_order": sort_order,
        "search": (search or "").strip(),
        "filter": filter,
        "profile": audit_config["profile_key"],
        "mode": audit_config["mode_key"],
        "urls": response_urls
    }


@app.get("/data/{session_id}/url")
async def get_single_url(
    session_id: str,
    url: str,
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Get detailed data for a specific URL"""
    url_data = await run_blocking(database.get_url, session_id, url)
    session = await run_blocking(database.get_session, session_id)
    note = await run_blocking(database.get_page_audit_note, session_id, url)

    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")

    detailed_data = {}
    for key, value in url_data.__dict__.items():
        if isinstance(value, datetime):
            detailed_data[key] = value.isoformat()
        else:
            detailed_data[key] = value

    audit = build_page_audit(url_data, session.start_url if session else "", resolve_audit_config(profile, mode))
    detailed_data["seo_score"] = audit["seo_score"]
    detailed_data["priority"] = audit["priority"]
    detailed_data["severity_counts"] = audit["severity_counts"]
    detailed_data["category_scores"] = audit["category_scores"]
    detailed_data["audit_issues"] = audit["issues"]
    detailed_data["target_keyword"] = note.get("target_keyword") if note else None

    return detailed_data


@app.get("/data/{session_id}/stats", response_model=StatsResponse)
async def get_stats(session_id: str):
    """Get crawl statistics"""
    stats = await run_blocking(database.get_stats, session_id)

    return StatsResponse(**stats)


@app.get("/data/{session_id}/images")
async def get_images(
    session_id: str,
    missing_alt_only: bool = False,
    missing_size_only: bool = False,
):
    """Get all images for a session"""
    images = await run_blocking(database.get_images, session_id)

    if missing_alt_only:
        images = [img for img in images if img.missing_alt or img.missing_alt_attribute]
    if missing_size_only:
        images = [img for img in images if img.missing_size_attributes]

    total_images = len(images)
    missing_alt_count = sum(1 for img in images if img.missing_alt or img.missing_alt_attribute)
    missing_size_count = sum(1 for img in images if img.missing_size_attributes)

    return {
        "total": total_images,
        "summary": {
            "missing_alt": missing_alt_count,
            "missing_size": missing_size_count,
        },
        "images": [img.to_dict() for img in images]
    }


@app.get("/data/{session_id}/links")
async def get_links(
    session_id: str,
    internal_only: bool = False,
    external_only: bool = False,
    nofollow_only: bool = False,
):
    """Get all links for a session"""
    links = await run_blocking(database.get_links, session_id)

    # Filter if needed
    if internal_only:
        links = [link for link in links if link.is_internal]
    elif external_only:
        links = [link for link in links if not link.is_internal]

    if nofollow_only:
        links = [link for link in links if link.is_nofollow]

    summary = {
        "internal": sum(1 for link in links if link.is_internal),
        "external": sum(1 for link in links if not link.is_internal),
        "nofollow": sum(1 for link in links if link.is_nofollow),
    }

    return {
        "total": len(links),
        "summary": summary,
        "links": [link.to_dict() for link in links]
    }


@app.get("/data/{session_id}/hreflang")
async def get_hreflang(session_id: str):
    """Get hreflang data with page-level issue analysis."""
    hreflang_rows = await run_blocking(database.get_hreflang, session_id)
    urls = await run_blocking(database.get_all_urls, session_id)
    status_map = {normalize_url(url_data.url): url_data.status_code for url_data in urls}
    hreflang_extractor = StructuredDataExtractor()

    grouped: Dict[str, List[dict]] = {}
    for row in hreflang_rows:
        grouped.setdefault(row.page_url, []).append({
            "hreflang": row.hreflang,
            "language": row.language,
            "region": row.region,
            "url": row.target_url,
            "source": row.source,
        })

    total_missing_return_links = 0
    total_non_200 = 0
    total_invalid_codes = 0
    total_missing_x_default = 0
    pages = []

    for page_url, entries in grouped.items():
        normalized_page = normalize_url(page_url)
        normalized_entries = []
        enriched_entries = []

        for entry in entries:
            normalized_target = normalize_url(entry["url"])
            normalized_entries.append({
                **entry,
                "url": normalized_target,
            })
            target_entries = grouped.get(normalized_target, [])
            has_return_link = any(normalize_url(target_entry["url"]) == normalized_page for target_entry in target_entries)
            enriched_entries.append({
                **entry,
                "target_status_code": status_map.get(normalized_target),
                "has_return_link": has_return_link,
            })

        issues = hreflang_extractor.analyze_hreflang_issues(
            normalized_entries,
            status_map
        )
        issues["missing_return_links"] = [
            entry for entry in enriched_entries if not entry["has_return_link"]
        ]

        total_missing_return_links += len(issues["missing_return_links"])
        total_non_200 += len(issues["non_200_urls"])
        total_invalid_codes += len(issues["invalid_codes"])
        total_missing_x_default += 1 if issues["missing_x_default"] else 0

        pages.append({
            "page_url": page_url,
            "entries": enriched_entries,
            "issues": issues,
        })

    return {
        "total_pages": len(grouped),
        "total_entries": len(hreflang_rows),
        "summary": {
            "missing_return_links": total_missing_return_links,
            "non_200_urls": total_non_200,
            "invalid_codes": total_invalid_codes,
            "pages_missing_x_default": total_missing_x_default,
        },
        "pages": pages,
    }


# ========== Analysis Endpoints ==========

@app.get("/analysis/{session_id}/report")
async def get_summary_report(
    session_id: str,
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Get an executive crawl report with prioritized findings."""
    try:
        return await run_blocking(build_summary_report, database, session_id, profile, mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(exc)}")


@app.get("/analysis/{session_id}/priorities")
async def get_priorities(
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, max_length=200),
    priority: Optional[str] = Query(None, pattern="^(critical|warning|pass)$"),
    severity: Optional[str] = Query(None, pattern="^(critical|warning|info)$"),
    segment: Optional[str] = Query(None, pattern="^(all|quick_win|traffic_recovery|cannibalization|content_thin|technical_debt)$"),
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Get pages ranked by SEO priority for fixing."""
    try:
        return await run_blocking(
            build_priorities_report,
            database,
            session_id,
            profile,
            mode,
            search,
            priority,
            severity,
            segment,
            limit,
            offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Priority analysis failed: {str(exc)}")


@app.get("/analysis/{session_id}/history")
async def get_audit_history(
    session_id: str,
    limit: int = Query(10, ge=1, le=20),
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Get recent audit history for the same host."""
    try:
        return await run_blocking(build_audit_history, database, session_id, profile, mode, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audit history failed: {str(exc)}")


@app.get("/analysis/{session_id}/compare")
async def compare_audits(
    session_id: str,
    baseline_session_id: Optional[str] = Query(None),
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Compare one audit session with another session on the same host."""
    try:
        return await run_blocking(build_audit_compare, database, session_id, baseline_session_id, profile, mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audit comparison failed: {str(exc)}")


@app.get("/analysis/config")
async def get_audit_config_options():
    """Get available audit profiles and application modes."""
    return {
        "profiles": [
            {"key": key, **value}
            for key, value in AUDIT_PROFILES.items()
        ],
        "modes": [
            {"key": key, **value}
            for key, value in AUDIT_MODES.items()
        ],
        "priority_segments": [
            {"key": key, **value}
            for key, value in PRIORITY_SEGMENTS.items()
        ],
        "issue_labels": {
            code: issue_label(code)
            for code in ISSUE_RULES
        },
    }


@app.get("/analysis/{session_id}/page-insight")
async def get_page_insight(
    session_id: str,
    url: str,
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Get heuristic page-level insight panel data."""
    url_data = await run_blocking(database.get_url, session_id, url)
    session = await run_blocking(database.get_session, session_id)
    stored_note = await run_blocking(database.get_page_audit_note, session_id, url)

    if not url_data or not session:
        raise HTTPException(status_code=404, detail="Page not found")

    insight = build_page_insight(
        url_data,
        session.start_url,
        resolve_audit_config(profile, mode),
        stored_note.get("target_keyword") if stored_note else None,
    )
    await run_blocking(
        database.upsert_page_audit_note,
        session_id,
        url,
        stored_note.get("target_keyword") if stored_note else None,
        insight["summary"],
        insight,
    )
    return insight


@app.get("/analysis/{session_id}/issue-catalog")
async def get_issue_catalog(
    session_id: str,
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Get aggregated issue catalog ranked by impact."""
    try:
        return await run_blocking(build_issue_catalog, database, session_id, profile, mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Issue catalog failed: {str(exc)}")


@app.get("/analysis/{session_id}/cannibalization")
async def get_cannibalization(
    session_id: str,
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Get duplicate/cannibalization clusters across titles, meta, headings, and similar content."""
    try:
        return await run_blocking(build_cannibalization_report, database, session_id, profile, mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cannibalization analysis failed: {str(exc)}")


@app.get("/analysis/{session_id}/social")
async def get_social_report(session_id: str):
    """Get Open Graph and Twitter card coverage issues."""
    try:
        return await run_blocking(build_social_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Social report failed: {str(exc)}")


@app.get("/analysis/{session_id}/schema")
async def get_schema_report(session_id: str):
    """Get schema coverage and validation issues."""
    try:
        return await run_blocking(build_schema_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Schema report failed: {str(exc)}")


@app.get("/analysis/{session_id}/content-quality")
async def get_content_quality_report(session_id: str):
    """Get content quality issues based on word count, readability, and text ratio."""
    try:
        return await run_blocking(build_content_quality_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Content quality report failed: {str(exc)}")


@app.get("/analysis/{session_id}/security")
async def get_security_report(session_id: str):
    """Get technical security issues by URL."""
    try:
        return await run_blocking(build_security_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Security report failed: {str(exc)}")


@app.get("/analysis/{session_id}/performance")
async def get_performance_report(session_id: str):
    """Get page performance issues by URL."""
    try:
        return await run_blocking(build_performance_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Performance report failed: {str(exc)}")


@app.get("/analysis/{session_id}/url-structure")
async def get_url_structure_report(session_id: str):
    """Get URL structure issues by URL."""
    try:
        return await run_blocking(build_url_structure_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"URL structure report failed: {str(exc)}")


@app.get("/analysis/{session_id}/directives-audit")
async def get_directives_audit_report(session_id: str):
    """Get directives/canonical/pagination issues by URL."""
    try:
        return await run_blocking(build_directives_audit_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Directives audit report failed: {str(exc)}")


@app.get("/analysis/{session_id}/image-audit")
async def get_image_audit_report(session_id: str):
    """Get image SEO issues by image instance."""
    try:
        return await run_blocking(build_image_audit_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image audit report failed: {str(exc)}")


@app.get("/analysis/{session_id}/link-opportunities")
async def get_link_opportunities(session_id: str):
    """Get internal link opportunity suggestions."""
    try:
        return await run_blocking(build_link_opportunities_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Link opportunity report failed: {str(exc)}")


@app.get("/analysis/{session_id}/link-audit")
async def get_link_audit(session_id: str):
    """Get internal/external link quality issues by page."""
    try:
        return await run_blocking(build_link_audit_report, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Link audit report failed: {str(exc)}")


@app.get("/analysis/{session_id}/sitemaps")
async def get_sitemap_report(session_id: str):
    """Fetch robots.txt sitemaps on demand and compare them with crawled URLs."""
    session = await run_blocking(database.get_session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    robots = RobotsParser()
    await robots.fetch_robots(session.start_url)
    sitemap_urls = robots.get_sitemaps()
    if not sitemap_urls:
        parsed = urlparse(session.start_url)
        sitemap_urls = [f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"]

    parser = SitemapParser()
    await parser.parse_all_sitemaps(sitemap_urls)
    await run_blocking(database.save_sitemap_urls, session_id, parser.get_urls())
    crawled_urls = {
        normalize_url(row.url)
        for row in await run_blocking(database.get_all_urls, session_id)
    }
    comparison = parser.compare_with_crawled(crawled_urls)
    return {
        "robots_url": robots.robots_url,
        "sitemaps": sitemap_urls,
        "summary": {
            "sitemap_count": comparison["sitemap_count"],
            "crawled_count": comparison["crawled_count"],
            "match_percentage": round(comparison["match_percentage"], 1),
            "sitemap_only": len(comparison["in_sitemap_only"]),
            "crawl_only": len(comparison["in_crawl_only"]),
        },
        "in_sitemap_only": comparison["in_sitemap_only"][:100],
        "in_crawl_only": comparison["in_crawl_only"][:100],
        "in_both": comparison["in_both"][:100],
    }


@app.get("/analysis/{session_id}/fix-queue")
async def get_fix_queue(
    session_id: str,
    status: Optional[str] = Query(None, pattern="^(queued|in_progress|done)$"),
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Get the manual fix queue for the session."""
    try:
        return await run_blocking(build_fix_queue_report, database, session_id, profile, mode, status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fix queue loading failed: {str(exc)}")


@app.post("/analysis/{session_id}/fix-queue")
async def create_fix_queue_item(session_id: str, request: FixQueueCreateRequest):
    """Add or update a fix queue item for a page or specific issue."""
    issue_label = request.issue_label
    if request.issue_code and not issue_label:
        issue_label = build_issue_record(request.issue_code).get("label")
    item = await run_blocking(
        database.upsert_fix_queue_item,
        session_id,
        request.url,
        request.issue_code,
        issue_label,
        request.priority,
        "queued",
        request.notes,
    )
    return {"status": "saved", "item": item}


@app.post("/analysis/{session_id}/fix-queue/bulk")
async def bulk_create_fix_queue_items(
    session_id: str,
    request: FixQueueBulkRequest,
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Bulk-add queue items from priorities, issue catalog, or cannibalization clusters."""
    try:
        return await run_blocking(
            bulk_populate_fix_queue,
            database,
            session_id,
            request.source,
            request.limit,
            profile,
            mode,
            request.segment,
            request.issue_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bulk queue creation failed: {str(exc)}")


@app.patch("/analysis/{session_id}/fix-queue/{item_id}")
async def update_fix_queue_item(session_id: str, item_id: int, request: FixQueueUpdateRequest):
    """Update queue item state."""
    item = await run_blocking(
        database.update_fix_queue_item,
        item_id,
        request.status,
        request.notes,
        request.priority,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return {"status": "updated", "item": item}


@app.delete("/analysis/{session_id}/fix-queue/{item_id}")
async def delete_fix_queue_item(session_id: str, item_id: int):
    """Delete a queue item."""
    await run_blocking(database.delete_fix_queue_item, item_id)
    return {"status": "deleted"}


@app.post("/analysis/{session_id}/page-insight/keyword")
async def save_target_keyword(session_id: str, request: TargetKeywordRequest):
    """Persist a target keyword for a page to drive insight suggestions."""
    await run_blocking(
        database.upsert_page_audit_note,
        session_id,
        request.url,
        request.target_keyword.strip(),
        None,
        None,
    )
    return {"status": "saved"}


@app.get("/analysis/{session_id}/visualizations")
async def get_visualizations(session_id: str):
    """Get structured crawl data for tree and graph visualizations."""
    try:
        return await run_blocking(build_visualization_data, database, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Visualization generation failed: {str(exc)}")


@app.get("/analysis/{session_id}/duplicates")
async def get_duplicates(session_id: str):
    """
    Analyze and return duplicate content information

    Returns exact duplicates and near-duplicates
    """
    try:
        results = await run_blocking(detect_duplicates_in_database, database, session_id)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Duplicate analysis failed: {str(e)}")


@app.get("/analysis/{session_id}/orphans")
async def get_orphans(session_id: str):
    """
    Detect and return orphan pages (pages with no internal links)

    Returns list of orphan pages and statistics
    """
    try:
        results = await run_blocking(detect_orphans_in_database, database, session_id)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orphan detection failed: {str(e)}")


@app.get("/analysis/{session_id}/redirects")
async def get_redirects(session_id: str):
    """
    Analyze redirects and detect chains and loops

    Returns redirect chains, loops, and statistics
    """
    try:
        results = await run_blocking(detect_redirects_in_database, database, session_id)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redirect analysis failed: {str(e)}")


@app.get("/analysis/{session_id}/issues")
async def get_issues(session_id: str):
    """
    Get comprehensive issue report for a session

    Returns all detected issues organized by category
    """
    try:
        # Collect issues from various sources
        issues = {
            "titles": [],
            "meta_descriptions": [],
            "headings": [],
            "content": [],
            "redirects": [],
            "security": [],
            "duplicates": [],
            "orphans": []
        }

        # Get URLs with issues
        filters_to_check = [
            ("missing_title", "titles", "Missing title tag"),
            ("duplicate_title", "titles", "Duplicate title"),
            ("title_over_60_chars", "titles", "Title over 60 characters"),
            ("title_below_30_chars", "titles", "Title below 30 characters"),
            ("missing_meta_description", "meta_descriptions", "Missing meta description"),
            ("duplicate_meta_description", "meta_descriptions", "Duplicate meta description"),
            ("meta_description_over_155_chars", "meta_descriptions", "Meta description over 155 characters"),
            ("missing_h1", "headings", "Missing H1 tag"),
            ("duplicate_h1", "headings", "Duplicate H1"),
            ("multiple_h1", "headings", "Multiple H1 tags"),
            ("low_content", "content", "Low content (< 200 words)"),
            ("redirection_3xx", "redirects", "Redirect found"),
            ("client_error_4xx", "redirects", "Client error (4xx)"),
            ("server_error_5xx", "redirects", "Server error (5xx)"),
            ("crawl_error", "redirects", "Crawl request failed"),
            ("http_urls", "security", "Insecure HTTP URL"),
            ("mixed_content", "security", "Mixed content detected"),
            ("missing_hsts", "security", "Missing HSTS header"),
        ]

        for filter_code, category, message in filters_to_check:
            urls = await run_blocking(database.get_urls_by_filter, session_id, filter_code, 100)
            for url_data in urls:
                issues[category].append({
                    "url": url_data.url,
                    "issue": message,
                    "severity": "warning"
                })

        # Add duplicate issues
        try:
            dup_results = await run_blocking(detect_duplicates_in_database, database, session_id)
            for url, info in dup_results['duplicate_info'].items():
                if info['exact_duplicates']:
                    issues["duplicates"].append({
                        "url": url,
                        "issue": f"Exact duplicate of {len(info['exact_duplicates'])} other page(s)",
                        "severity": "error"
                    })
                elif info['near_duplicates']:
                    issues["duplicates"].append({
                        "url": url,
                        "issue": f"Near-duplicate of {len(info['near_duplicates'])} other page(s)",
                        "severity": "warning"
                    })
        except Exception:
            pass

        # Add orphan issues
        try:
            orphan_results = await run_blocking(detect_orphans_in_database, database, session_id)
            for orphan_url in orphan_results['orphan_pages'][:100]:
                issues["orphans"].append({
                    "url": orphan_url,
                    "issue": "Orphan page (no internal links)",
                    "severity": "warning"
                })
        except Exception:
            pass

        # Calculate summary
        total_issues = sum(len(v) for v in issues.values())

        return {
            "total_issues": total_issues,
            "issues_by_category": issues,
            "summary": {
                "titles": len(issues["titles"]),
                "meta_descriptions": len(issues["meta_descriptions"]),
                "headings": len(issues["headings"]),
                "content": len(issues["content"]),
                "redirects": len(issues["redirects"]),
                "security": len(issues["security"]),
                "duplicates": len(issues["duplicates"]),
                "orphans": len(issues["orphans"])
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Issue analysis failed: {str(e)}")


# ========== Named Reports ==========

@app.get("/reports/{session_id}")
async def list_reports(session_id: str):
    """List Screaming Frog-style named reports available for a crawl session."""
    session = await run_blocking(database.get_session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "total_reports": len(REPORT_DEFINITIONS),
        "reports": REPORT_DEFINITIONS,
    }


@app.get("/reports/{session_id}/{report_code}")
async def get_named_report(
    session_id: str,
    report_code: str,
    limit: int = Query(1000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
):
    """Get a named Screaming Frog-style report."""
    if report_code not in REPORT_CODES:
        raise HTTPException(status_code=404, detail=f"Unknown report code: {report_code}")

    session = await run_blocking(database.get_session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if report_code == "crawl_overview":
        data = await get_summary_report(session_id)
    elif report_code == "internal_all":
        rows = await run_blocking(database.get_all_urls, session_id, limit, offset)
        total = await run_blocking(database.get_url_count, session_id)
        data = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "rows": [row.to_dict() for row in rows],
        }
    elif report_code == "external_all":
        links = await run_blocking(database.get_links, session_id)
        external = [link for link in links if not link.is_internal]
        data = {
            "total": len(external),
            "rows": [link.to_dict() for link in external[offset:offset + limit]],
        }
    elif report_code == "response_codes":
        rows = await run_blocking(database.get_all_urls, session_id)
        buckets = {
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        }
        for row in rows:
            status_code = row.status_code or 0
            if 200 <= status_code < 300:
                buckets["2xx"] += 1
            elif 300 <= status_code < 400:
                buckets["3xx"] += 1
            elif 400 <= status_code < 500:
                buckets["4xx"] += 1
            elif 500 <= status_code < 600:
                buckets["5xx"] += 1
            else:
                buckets["other"] += 1
        data = {
            "summary": buckets,
            "rows": [
                {
                    "url": row.url,
                    "status_code": row.status_code,
                    "status_text": row.status_text,
                }
                for row in rows[offset:offset + limit]
            ],
        }
    elif report_code == "redirect_chains":
        redirect_data = await get_redirects(session_id)
        data = {
            "total_chains": len(redirect_data.get("redirect_chains", {})),
            "redirect_chains": redirect_data.get("redirect_chains", {}),
            "stats": redirect_data.get("stats", {}),
        }
    elif report_code == "redirect_loops":
        redirect_data = await get_redirects(session_id)
        data = {
            "total_loops": len(redirect_data.get("redirect_loops", [])),
            "redirect_loops": redirect_data.get("redirect_loops", []),
            "stats": redirect_data.get("stats", {}),
        }
    elif report_code == "canonicals":
        rows = await run_blocking(database.get_all_urls, session_id)
        canonical_rows = [
            {
                "url": row.url,
                "canonical": row.canonical_link_element_1,
                "indexability": row.indexability,
                "status_code": row.status_code,
            }
            for row in rows
            if row.canonical_link_element_1
        ]
        data = {
            "summary": {
                "contains_canonical": await filter_count(session_id, "contains_canonical"),
                "missing_canonical": await filter_count(session_id, "missing_canonical"),
                "canonical_chain": await filter_count(session_id, "canonical_chain"),
                "canonical_loop": await filter_count(session_id, "canonical_loop"),
            },
            "rows": canonical_rows[offset:offset + limit],
        }
    elif report_code == "pagination":
        rows = await run_blocking(database.get_all_urls, session_id)
        pagination_rows = [
            {
                "url": row.url,
                "rel_next_1": row.rel_next_1,
                "rel_prev_1": row.rel_prev_1,
                "http_rel_next_1": row.http_rel_next_1,
                "http_rel_prev_1": row.http_rel_prev_1,
            }
            for row in rows
            if row.rel_next_1 or row.rel_prev_1 or row.http_rel_next_1 or row.http_rel_prev_1
        ]
        data = {
            "summary": {
                "contains_pagination": await filter_count(session_id, "contains_pagination"),
                "pagination_first_page": await filter_count(session_id, "pagination_first_page"),
                "pagination_2_plus_page": await filter_count(session_id, "pagination_2_plus_page"),
            },
            "rows": pagination_rows[offset:offset + limit],
        }
    elif report_code == "hreflang":
        data = await get_hreflang(session_id)
    elif report_code == "duplicate_content":
        data = await get_duplicates(session_id)
    elif report_code == "insecure_content":
        data = await get_security_report(session_id)
    elif report_code == "structured_data":
        data = await get_schema_report(session_id)
    elif report_code == "sitemaps":
        data = await get_sitemap_report(session_id)
    elif report_code == "orphan_pages":
        data = await get_orphans(session_id)
    elif report_code == "link_score":
        rows = await run_blocking(database.get_all_urls, session_id)
        ranked = sorted(rows, key=lambda row: (row.link_score or 0), reverse=True)
        data = {
            "total": len(ranked),
            "rows": [
                {
                    "url": row.url,
                    "link_score": row.link_score,
                    "inlinks": row.inlinks,
                    "unique_inlinks": row.unique_inlinks,
                    "outlinks": row.outlinks,
                }
                for row in ranked[offset:offset + limit]
            ],
        }
    else:
        data = await get_issues(session_id)

    report_meta = next(item for item in REPORT_DEFINITIONS if item["code"] == report_code)
    return {
        "report": report_meta,
        "session_id": session_id,
        "data": data,
    }


@app.get("/reports/{session_id}/{report_code}/csv")
async def export_named_report_csv(
    session_id: str,
    report_code: str,
    limit: int = Query(50000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
):
    """Export a named report as CSV."""
    payload = await get_named_report(session_id, report_code, limit=limit, offset=offset)
    report_meta = payload["report"]
    data = payload["data"]
    rows = _flatten_report_rows(report_code, data)
    if not rows:
        raise HTTPException(status_code=404, detail="No rows available for CSV export")

    fieldnames = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _normalize_csv_value(row.get(key)) for key in fieldnames})

    filename = f"{report_meta['code']}_{session_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/reports/{session_id}/{report_code}/json")
async def export_named_report_json(
    session_id: str,
    report_code: str,
    limit: int = Query(50000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
):
    """Export a named report as JSON."""
    payload = await get_named_report(session_id, report_code, limit=limit, offset=offset)
    report_meta = payload["report"]

    content = json.dumps(payload["data"], ensure_ascii=False, indent=2)
    filename = f"{report_meta['code']}_{session_id}.json"
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/reports/{session_id}/{report_code}/xlsx")
async def export_named_report_xlsx(
    session_id: str,
    report_code: str,
    limit: int = Query(50000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
):
    """Export a named report as XLSX."""
    payload = await get_named_report(session_id, report_code, limit=limit, offset=offset)
    report_meta = payload["report"]
    rows = _flatten_report_rows(report_code, payload["data"])
    if not rows:
        raise HTTPException(status_code=404, detail="No rows available for XLSX export")

    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="XLSX export requires openpyxl. Install with: pip install openpyxl",
        )

    fieldnames = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = report_meta["code"][:31]
    worksheet.append(fieldnames)
    for row in rows:
        worksheet.append([_normalize_csv_value(row.get(key)) for key in fieldnames])

    buffer = io.BytesIO()
    workbook.save(buffer)
    filename = f"{report_meta['code']}_{session_id}.xlsx"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ========== Export Endpoints ==========

@app.get("/export/{session_id}/csv")
async def export_csv(
    session_id: str,
    filter: Optional[str] = None,
    format: Optional[str] = "screaming_frog"
):
    """Export data to CSV (Screaming Frog format by default)"""
    output_path = f"/tmp/export_{session_id}.csv"
    
    if format == "screaming_frog":
        # Use Screaming Frog exporter (exact 72-column format)
        exporter = ScreamingFrogExporter(database)
        count = await run_blocking(exporter.export_csv, session_id, output_path)
    else:
        # Use basic exporter
        exporter = DataExporter(database)
        count = await run_blocking(exporter.export_to_csv, session_id, output_path, filter_name=filter)

    if count == 0:
        raise HTTPException(status_code=404, detail="No data to export")

    return FileResponse(
        output_path,
        media_type="text/csv",
        filename=f"crawl_{session_id}_screaming_frog.csv"
    )


@app.get("/export/{session_id}/json")
async def export_json(
    session_id: str,
    filter: Optional[str] = None
):
    """Export data to JSON"""
    exporter = DataExporter(database)

    output_path = f"/tmp/export_{session_id}.json"

    count = await run_blocking(exporter.export_to_json, session_id, output_path, filter_name=filter)

    if count == 0:
        raise HTTPException(status_code=404, detail="No data to export")

    return FileResponse(
        output_path,
        media_type="application/json",
        filename=f"crawl_{session_id}.json"
    )


@app.get("/export/{session_id}/excel")
async def export_excel(session_id: str):
    """Export data to Excel"""
    exporter = DataExporter(database)

    output_path = f"/tmp/export_{session_id}.xlsx"

    try:
        count = await run_blocking(exporter.export_to_excel, session_id, output_path)

        if count == 0:
            raise HTTPException(status_code=404, detail="No data to export")

        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"crawl_{session_id}.xlsx"
        )
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Excel export requires openpyxl. Install with: pip install openpyxl"
        )


@app.get("/export/{session_id}/audit-report")
async def export_audit_report(
    session_id: str,
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Export a printable HTML audit report."""
    output_path = f"/tmp/audit_report_{session_id}.html"
    html = await run_blocking(render_audit_report_html, database, session_id, profile, mode)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(html)
    return FileResponse(
        output_path,
        media_type="text/html",
        filename=f"audit_report_{session_id}.html"
    )


@app.get("/export/{session_id}/audit-report.pdf")
async def export_audit_report_pdf(
    session_id: str,
    profile: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
):
    """Export a printable PDF audit report."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise HTTPException(status_code=501, detail="PDF export requires Playwright to be installed") from exc

    output_path = f"/tmp/audit_report_{session_id}.pdf"
    html = await run_blocking(render_audit_report_html, database, session_id, profile, mode)

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html, wait_until="load")
            await page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "16mm", "right": "12mm", "bottom": "16mm", "left": "12mm"},
            )
            await browser.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF report export failed: {str(exc)}")

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"audit_report_{session_id}.pdf"
    )


# ========== Filter List Endpoint ==========

@app.get("/filters")
async def get_available_filters():
    """Get list of available filters"""
    return {
        "filters": [
            {"code": "missing_title", "name": "Thiếu title", "category": "titles"},
            {"code": "duplicate_title", "name": "Title bị trùng", "category": "titles"},
            {"code": "title_over_60_chars", "name": "Title quá 60 ký tự", "category": "titles"},
            {"code": "title_below_30_chars", "name": "Title dưới 30 ký tự", "category": "titles"},
            {"code": "title_over_568_pixels", "name": "Title quá 568px", "category": "titles"},
            {"code": "title_below_200_pixels", "name": "Title dưới 200px", "category": "titles"},
            {"code": "same_as_h1", "name": "Title trùng H1", "category": "titles"},
            {"code": "multiple_titles", "name": "Có nhiều title", "category": "titles"},

            {"code": "missing_meta_description", "name": "Thiếu meta description", "category": "meta"},
            {"code": "duplicate_meta_description", "name": "Meta description bị trùng", "category": "meta"},
            {"code": "meta_description_over_155_chars", "name": "Meta description quá 155 ký tự", "category": "meta"},
            {"code": "meta_description_below_70_chars", "name": "Meta description dưới 70 ký tự", "category": "meta"},
            {"code": "meta_description_over_990_pixels", "name": "Meta description quá 990px", "category": "meta"},
            {"code": "meta_description_below_400_pixels", "name": "Meta description dưới 400px", "category": "meta"},
            {"code": "multiple_meta_descriptions", "name": "Có nhiều meta description", "category": "meta"},

            {"code": "missing_h1", "name": "Thiếu H1", "category": "headings"},
            {"code": "duplicate_h1", "name": "H1 bị trùng", "category": "headings"},
            {"code": "multiple_h1", "name": "Có nhiều H1", "category": "headings"},
            {"code": "h1_over_70_chars", "name": "H1 quá 70 ký tự", "category": "headings"},
            {"code": "missing_h2", "name": "Thiếu H2", "category": "headings"},
            {"code": "non_sequential_headings", "name": "Heading không tuần tự", "category": "headings"},

            {"code": "low_content", "name": "Nội dung mỏng (< 200 từ)", "category": "content"},
            {"code": "low_text_ratio", "name": "Tỷ lệ text thấp", "category": "content"},
            {"code": "near_duplicates", "name": "Near duplicates", "category": "content"},
            {"code": "exact_duplicates", "name": "Exact duplicates", "category": "content"},
            {"code": "spelling_errors", "name": "Spelling errors", "category": "content"},
            {"code": "grammar_errors", "name": "Grammar errors", "category": "content"},

            {"code": "noindex", "name": "Noindex", "category": "directives"},
            {"code": "nofollow", "name": "Nofollow", "category": "directives"},
            {"code": "follow", "name": "Follow (explicit)", "category": "directives"},
            {"code": "none", "name": "None (noindex,nofollow)", "category": "directives"},
            {"code": "noarchive", "name": "Noarchive", "category": "directives"},
            {"code": "nosnippet", "name": "Nosnippet", "category": "directives"},
            {"code": "noimageindex", "name": "Noimageindex", "category": "directives"},
            {"code": "max_snippet", "name": "Max-snippet", "category": "directives"},
            {"code": "max_image_preview", "name": "Max-image-preview", "category": "directives"},
            {"code": "max_video_preview", "name": "Max-video-preview", "category": "directives"},
            {"code": "unavailable_after", "name": "Unavailable_after", "category": "directives"},

            {"code": "contains_canonical", "name": "Có canonical", "category": "canonicals"},
            {"code": "missing_canonical", "name": "Thiếu canonical", "category": "canonicals"},
            {"code": "self_referencing_canonical", "name": "Canonical tự tham chiếu", "category": "canonicals"},
            {"code": "canonicalised", "name": "Canonical trỏ URL khác", "category": "canonicals"},
            {"code": "canonical_chain", "name": "Canonical chain", "category": "canonicals"},
            {"code": "canonical_loop", "name": "Canonical loop", "category": "canonicals"},
            {"code": "canonical_to_non_indexable", "name": "Canonical trỏ URL non-indexable", "category": "canonicals"},
            {"code": "canonical_to_non_200", "name": "Canonical trỏ URL non-200", "category": "canonicals"},

            {"code": "contains_pagination", "name": "Có pagination", "category": "pagination"},
            {"code": "pagination_first_page", "name": "Pagination first page", "category": "pagination"},
            {"code": "pagination_2_plus_page", "name": "Pagination 2+ page", "category": "pagination"},
            {"code": "pagination_url_not_in_anchor", "name": "Pagination URL không có trong anchor", "category": "pagination"},
            {"code": "non_200_pagination_url", "name": "Pagination URL non-200", "category": "pagination"},
            {"code": "unlinked_pagination_url", "name": "Pagination URL unlinked", "category": "pagination"},
            {"code": "non_indexable_pagination_url", "name": "Pagination URL non-indexable", "category": "pagination"},

            {"code": "blocked_by_robots_txt", "name": "Blocked by robots.txt", "category": "status_codes"},
            {"code": "blocked_resource", "name": "Blocked resource", "category": "status_codes"},
            {"code": "success_2xx", "name": "URL thành công (2xx)", "category": "status_codes"},
            {"code": "redirection_3xx", "name": "URL chuyển hướng (3xx)", "category": "status_codes"},
            {"code": "redirection_javascript", "name": "Redirect JavaScript", "category": "status_codes"},
            {"code": "redirection_meta_refresh", "name": "Redirect Meta Refresh", "category": "status_codes"},
            {"code": "redirect_chain", "name": "Redirect chain", "category": "status_codes"},
            {"code": "redirect_loop", "name": "Redirect loop", "category": "status_codes"},
            {"code": "client_error_4xx", "name": "Lỗi client (4xx)", "category": "status_codes"},
            {"code": "server_error_5xx", "name": "Lỗi server (5xx)", "category": "status_codes"},
            {"code": "crawl_error", "name": "Không có phản hồi crawl", "category": "status_codes"},

            {"code": "http_urls", "name": "URL HTTP", "category": "security"},
            {"code": "https_urls", "name": "URL HTTPS", "category": "security"},
            {"code": "mixed_content", "name": "Mixed content", "category": "security"},
            {"code": "insecure_forms", "name": "Form không an toàn", "category": "security"},
            {"code": "missing_hsts", "name": "Thiếu HSTS header", "category": "security"},
            {"code": "form_on_http_url", "name": "Form trên HTTP URL", "category": "security"},
            {"code": "unsafe_cross_origin_links", "name": "Unsafe cross-origin links", "category": "security"},
            {"code": "missing_csp", "name": "Thiếu CSP header", "category": "security"},
            {"code": "missing_x_content_type_options", "name": "Thiếu X-Content-Type-Options", "category": "security"},
            {"code": "missing_x_frame_options", "name": "Thiếu X-Frame-Options", "category": "security"},
            {"code": "missing_secure_referrer_policy", "name": "Thiếu secure Referrer-Policy", "category": "security"},
            {"code": "protocol_relative_links", "name": "Protocol-relative links", "category": "security"},
            {"code": "bad_content_type", "name": "Bad content type", "category": "security"},

            {"code": "url_over_115_chars", "name": "URL quá 115 ký tự", "category": "url_issues"},
            {"code": "url_with_parameters", "name": "URL có tham số", "category": "url_issues"},
            {"code": "url_with_underscores", "name": "URL có dấu gạch dưới", "category": "url_issues"},
            {"code": "url_with_uppercase", "name": "URL có chữ hoa", "category": "url_issues"},
            {"code": "url_with_non_ascii", "name": "URL có ký tự non-ASCII", "category": "url_issues"},
            {"code": "duplicate_url", "name": "URL trùng nội dung", "category": "url_issues"},
            {"code": "broken_bookmarks", "name": "Broken bookmarks", "category": "url_issues"},

            {"code": "javascript_links", "name": "JavaScript links", "category": "javascript"},
            {"code": "javascript_content", "name": "JavaScript content", "category": "javascript"},
            {"code": "javascript_only_titles", "name": "JavaScript-only titles", "category": "javascript"},
            {"code": "javascript_only_descriptions", "name": "JavaScript-only descriptions", "category": "javascript"},
            {"code": "javascript_only_h1", "name": "JavaScript-only H1", "category": "javascript"},
            {"code": "javascript_only_canonicals", "name": "JavaScript-only canonicals", "category": "javascript"},

            {"code": "contains_structured_data", "name": "Contains structured data", "category": "structured_data"},
            {"code": "json_ld", "name": "JSON-LD", "category": "structured_data"},
            {"code": "microdata", "name": "Microdata", "category": "structured_data"},
            {"code": "rdfa", "name": "RDFa", "category": "structured_data"},
            {"code": "validation_errors", "name": "Schema validation errors", "category": "structured_data"},
            {"code": "validation_warnings", "name": "Schema validation warnings", "category": "structured_data"},
            {"code": "schema_missing_fields", "name": "Schema missing fields", "category": "structured_data"},

            {"code": "valid_amp", "name": "Valid AMP", "category": "amp"},
            {"code": "amp_validation_errors", "name": "AMP validation errors", "category": "amp"},
            {"code": "amp_validation_warnings", "name": "AMP validation warnings", "category": "amp"},
            {"code": "non_200_amp_url", "name": "Non-200 AMP URL", "category": "amp"},
            {"code": "missing_non_amp_return", "name": "Missing non-AMP return", "category": "amp"},

            {"code": "images_over_100kb", "name": "Images over 100KB", "category": "images"},
            {"code": "missing_alt_text", "name": "Missing alt text", "category": "images"},
            {"code": "missing_alt_attribute", "name": "Missing alt attribute", "category": "images"},
            {"code": "alt_text_over_100_chars", "name": "Alt text over 100 chars", "category": "images"},
            {"code": "missing_size_attributes", "name": "Missing image size attributes", "category": "images"},

            {"code": "contains_hreflang", "name": "Contains hreflang", "category": "hreflang"},
            {"code": "non_200_hreflang_url", "name": "Non-200 hreflang URL", "category": "hreflang"},
            {"code": "unlinked_hreflang_url", "name": "Unlinked hreflang URL", "category": "hreflang"},
            {"code": "missing_return_links", "name": "Missing return links", "category": "hreflang"},
            {"code": "inconsistent_language", "name": "Inconsistent language", "category": "hreflang"},
            {"code": "invalid_hreflang_codes", "name": "Invalid hreflang codes", "category": "hreflang"},
            {"code": "multiple_hreflang_entries", "name": "Multiple hreflang entries", "category": "hreflang"},
            {"code": "missing_self_reference", "name": "Missing self reference", "category": "hreflang"},
            {"code": "hreflang_not_using_canonical", "name": "Hreflang not using canonical", "category": "hreflang"},
            {"code": "missing_x_default", "name": "Missing x-default", "category": "hreflang"},

            {"code": "in_sitemap", "name": "In sitemap", "category": "sitemaps"},
            {"code": "not_in_sitemap", "name": "Not in sitemap", "category": "sitemaps"},
            {"code": "orphan_urls", "name": "Orphan sitemap URLs", "category": "sitemaps"},
            {"code": "non_200_in_sitemap", "name": "Non-200 in sitemap", "category": "sitemaps"},
            {"code": "non_indexable_in_sitemap", "name": "Non-indexable in sitemap", "category": "sitemaps"},

            {"code": "indexable", "name": "Trang indexable", "category": "indexability"},
            {"code": "non_indexable", "name": "Trang non-indexable", "category": "indexability"},
        ]
    }


# ========== WebSocket Endpoint ==========

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time crawl updates

    Clients connect to /ws/{session_id} to receive real-time progress updates
    """
    await websocket.accept()

    # Add to connections list
    if session_id not in websocket_connections:
        websocket_connections[session_id] = []
    websocket_connections[session_id].append(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "WebSocket connected successfully"
        })

        # Keep connection alive and listen for client messages
        while True:
            try:
                # Receive messages (mostly just for keepalive)
                data = await websocket.receive_text()

                # Optional: handle client commands
                if data == "ping":
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                break

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Remove from connections
        if session_id in websocket_connections:
            if websocket in websocket_connections[session_id]:
                websocket_connections[session_id].remove(websocket)
            if not websocket_connections[session_id]:
                del websocket_connections[session_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
