"""
FastAPI Main Application
RESTful API for controlling crawler and accessing data
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
from pydantic import BaseModel
from datetime import datetime
import asyncio
import os
import json

from ..storage.database import Database
from ..storage.export import DataExporter
from ..spider.crawler import WebCrawler
from ..processing.page_processor import PageProcessor
from ..analysis.duplicates import detect_duplicates_in_database
from ..analysis.orphans import detect_orphans_in_database
from ..analysis.redirects import detect_redirects_in_database

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
database = Database("/app/data/crawl_data.db")
active_crawlers = {}  # session_id -> crawler instance
websocket_connections: Dict[str, List[WebSocket]] = {}  # session_id -> list of websockets


# ========== Request/Response Models ==========

class CrawlStartRequest(BaseModel):
    start_url: str
    max_urls: int = 10000
    max_depth: Optional[int] = None
    requests_per_second: float = 1.0
    respect_robots: bool = True
    user_agent: str = "WebCrawler/1.0"


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
    # Create session
    session = database.create_session(
        start_url=request.start_url,
        max_urls=request.max_urls,
        max_depth=request.max_depth,
        respect_robots=request.respect_robots,
        user_agent=request.user_agent
    )

    # Create crawler
    crawler = WebCrawler(
        start_url=request.start_url,
        max_depth=request.max_depth or 10,
        max_urls=request.max_urls,
        requests_per_second=request.requests_per_second,
        use_playwright=False,  # TODO: Make configurable
        user_agent=request.user_agent,
        respect_robots=request.respect_robots
    )

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

        # Create page processor
        processor = PageProcessor(database, crawler.start_url, session_id)

        # Set up callback to process each page
        async def on_page_crawled(url: str, page_result):
            if page_result.html and not page_result.error:
                # Process page through all extractors
                processor.process_page(
                    url=url,
                    html=page_result.html,
                    status_code=page_result.status_code,
                    status_text="OK",  # TODO: Get actual status text
                    headers=page_result.headers,
                    response_time=page_result.load_time,
                    ttfb=page_result.ttfb,
                    crawl_depth=crawler.url_manager.get_url_metadata(url).get('depth', 0)
                )

            # Update session stats
            stats = crawler.get_stats()
            database.update_session(
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
                "total_urls": stats['url_manager']['total_urls'],
                "failed_urls": stats['pages_failed']
            })

        crawler.on_page_crawled = on_page_crawled

        # Start crawling
        await crawler.crawl()

        # Post-process: Calculate link metrics
        processor.post_process_link_metrics()

        # Mark as completed
        database.update_session(session_id, status="completed")

        # Broadcast completion
        await broadcast_to_websockets(session_id, {
            "type": "completed",
            "message": "Crawl completed successfully"
        })

    except Exception as e:
        database.update_session(session_id, status="failed")
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
    session = database.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Calculate progress
    progress = 0.0
    if session.total_urls > 0:
        progress = (session.crawled_urls / session.max_urls) * 100
        progress = min(progress, 100.0)

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
    database.update_session(session_id, status="paused")

    return {"status": "paused"}


@app.post("/crawl/{session_id}/resume")
async def resume_crawl(session_id: str):
    """Resume a paused crawl"""
    crawler = active_crawlers.get(session_id)

    if not crawler:
        raise HTTPException(status_code=404, detail="Active crawler not found")

    await crawler.resume()
    database.update_session(session_id, status="running")

    return {"status": "running"}


@app.post("/crawl/{session_id}/stop")
async def stop_crawl(session_id: str):
    """Stop a crawl"""
    crawler = active_crawlers.get(session_id)

    if not crawler:
        raise HTTPException(status_code=404, detail="Active crawler not found")

    await crawler.stop()
    database.update_session(session_id, status="stopped")
    active_crawlers.pop(session_id, None)

    return {"status": "stopped"}


# ========== Data Access Endpoints ==========

@app.get("/data/{session_id}/urls")
async def get_urls(
    session_id: str,
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    filter: Optional[str] = None
):
    """
    Get URLs for a session

    Args:
        session_id: Crawl session ID
        limit: Number of URLs to return
        offset: Offset for pagination
        filter: Optional filter name (e.g., 'missing_title')
    """
    if filter:
        urls = database.get_urls_by_filter(session_id, filter, limit=limit)
    else:
        urls = database.get_all_urls(session_id, limit=limit, offset=offset)

    # Convert to response format
    response_urls = []
    for url_data in urls:
        response_urls.append({
            "url": url_data.url,
            "status_code": url_data.status_code,
            "title": url_data.title_1,
            "meta_description": url_data.meta_description_1,
            "h1": url_data.h1_1,
            "word_count": url_data.word_count,
            "indexability": url_data.indexability,
            "issues": url_data.issues or []
        })

    total_count = database.get_url_count(session_id)

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "urls": response_urls
    }


@app.get("/data/{session_id}/url")
async def get_single_url(session_id: str, url: str):
    """Get detailed data for a specific URL"""
    url_data = database.get_url(session_id, url)

    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")

    return url_data.to_dict()


@app.get("/data/{session_id}/stats", response_model=StatsResponse)
async def get_stats(session_id: str):
    """Get crawl statistics"""
    stats = database.get_stats(session_id)

    return StatsResponse(**stats)


@app.get("/data/{session_id}/images")
async def get_images(session_id: str):
    """Get all images for a session"""
    images = database.get_images(session_id)

    return {
        "total": len(images),
        "images": [img.to_dict() for img in images]
    }


@app.get("/data/{session_id}/links")
async def get_links(
    session_id: str,
    internal_only: bool = False,
    external_only: bool = False
):
    """Get all links for a session"""
    links = database.get_links(session_id)

    # Filter if needed
    if internal_only:
        links = [link for link in links if link.is_internal]
    elif external_only:
        links = [link for link in links if not link.is_internal]

    return {
        "total": len(links),
        "links": [link.to_dict() for link in links]
    }


# ========== Analysis Endpoints ==========

@app.get("/analysis/{session_id}/duplicates")
async def get_duplicates(session_id: str):
    """
    Analyze and return duplicate content information

    Returns exact duplicates and near-duplicates
    """
    try:
        results = detect_duplicates_in_database(database, session_id)
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
        results = detect_orphans_in_database(database, session_id)
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
        results = detect_redirects_in_database(database, session_id)
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
            ("title_over_60_chars", "titles", "Title over 60 characters"),
            ("title_below_30_chars", "titles", "Title below 30 characters"),
            ("missing_meta_description", "meta_descriptions", "Missing meta description"),
            ("meta_description_over_155_chars", "meta_descriptions", "Meta description over 155 characters"),
            ("missing_h1", "headings", "Missing H1 tag"),
            ("multiple_h1", "headings", "Multiple H1 tags"),
            ("low_content", "content", "Low content (< 200 words)"),
            ("redirection_3xx", "redirects", "Redirect found"),
            ("client_error_4xx", "redirects", "Client error (4xx)"),
            ("server_error_5xx", "redirects", "Server error (5xx)"),
            ("http_urls", "security", "Insecure HTTP URL"),
            ("mixed_content", "security", "Mixed content detected"),
            ("missing_hsts", "security", "Missing HSTS header"),
        ]

        for filter_code, category, message in filters_to_check:
            urls = database.get_urls_by_filter(session_id, filter_code, limit=100)
            for url_data in urls:
                issues[category].append({
                    "url": url_data.url,
                    "issue": message,
                    "severity": "warning"
                })

        # Add duplicate issues
        try:
            dup_results = detect_duplicates_in_database(database, session_id)
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
            orphan_results = detect_orphans_in_database(database, session_id)
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


# ========== Export Endpoints ==========

@app.get("/export/{session_id}/csv")
async def export_csv(
    session_id: str,
    filter: Optional[str] = None
):
    """Export data to CSV"""
    exporter = DataExporter(database)

    output_path = f"/tmp/export_{session_id}.csv"

    count = exporter.export_to_csv(session_id, output_path, filter_name=filter)

    if count == 0:
        raise HTTPException(status_code=404, detail="No data to export")

    return FileResponse(
        output_path,
        media_type="text/csv",
        filename=f"crawl_{session_id}.csv"
    )


@app.get("/export/{session_id}/json")
async def export_json(
    session_id: str,
    filter: Optional[str] = None
):
    """Export data to JSON"""
    exporter = DataExporter(database)

    output_path = f"/tmp/export_{session_id}.json"

    count = exporter.export_to_json(session_id, output_path, filter_name=filter)

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
        count = exporter.export_to_excel(session_id, output_path)

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


# ========== Filter List Endpoint ==========

@app.get("/filters")
async def get_available_filters():
    """Get list of available filters"""
    return {
        "filters": [
            {"code": "missing_title", "name": "Missing Titles", "category": "titles"},
            {"code": "title_over_60_chars", "name": "Titles Over 60 Characters", "category": "titles"},
            {"code": "title_below_30_chars", "name": "Titles Below 30 Characters", "category": "titles"},
            {"code": "multiple_titles", "name": "Multiple Titles", "category": "titles"},

            {"code": "missing_meta_description", "name": "Missing Meta Descriptions", "category": "meta"},
            {"code": "meta_description_over_155_chars", "name": "Meta Descriptions Over 155 Characters", "category": "meta"},
            {"code": "meta_description_below_70_chars", "name": "Meta Descriptions Below 70 Characters", "category": "meta"},

            {"code": "missing_h1", "name": "Missing H1", "category": "headings"},
            {"code": "multiple_h1", "name": "Multiple H1", "category": "headings"},
            {"code": "h1_over_70_chars", "name": "H1 Over 70 Characters", "category": "headings"},

            {"code": "low_content", "name": "Low Content (< 200 words)", "category": "content"},
            {"code": "low_text_ratio", "name": "Low Text Ratio", "category": "content"},

            {"code": "missing_canonical", "name": "Missing Canonical", "category": "canonicals"},

            {"code": "success_2xx", "name": "Success (2xx)", "category": "status_codes"},
            {"code": "redirection_3xx", "name": "Redirects (3xx)", "category": "status_codes"},
            {"code": "client_error_4xx", "name": "Client Errors (4xx)", "category": "status_codes"},
            {"code": "server_error_5xx", "name": "Server Errors (5xx)", "category": "status_codes"},

            {"code": "http_urls", "name": "HTTP URLs", "category": "security"},
            {"code": "https_urls", "name": "HTTPS URLs", "category": "security"},
            {"code": "mixed_content", "name": "Mixed Content", "category": "security"},
            {"code": "insecure_forms", "name": "Insecure Forms", "category": "security"},
            {"code": "missing_hsts", "name": "Missing HSTS Header", "category": "security"},

            {"code": "url_over_115_chars", "name": "URLs Over 115 Characters", "category": "url_issues"},
            {"code": "url_with_parameters", "name": "URLs with Parameters", "category": "url_issues"},
            {"code": "url_with_underscores", "name": "URLs with Underscores", "category": "url_issues"},
            {"code": "url_with_uppercase", "name": "URLs with Uppercase", "category": "url_issues"},

            {"code": "indexable", "name": "Indexable Pages", "category": "indexability"},
            {"code": "non_indexable", "name": "Non-Indexable Pages", "category": "indexability"},
            {"code": "noindex", "name": "Noindex Pages", "category": "indexability"},
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
