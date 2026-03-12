#!/usr/bin/env python3
"""
Local benchmark for validating 1000+ page crawl stability.

The script spins up a synthetic local website, runs the crawler against it,
and writes machine-readable results to benchmarks/results/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from webcrawler.spider.crawler import WebCrawler


def build_index_html(page_count: int) -> str:
    links = "\n".join(
        f'<li><a href="/page/{idx}">Page {idx}</a></li>'
        for idx in range(1, page_count + 1)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Synthetic Root</title>
</head>
<body>
  <h1>Synthetic Root</h1>
  <ul>
    {links}
  </ul>
</body>
</html>
"""


def build_page_html(page_id: int, page_count: int) -> str:
    next_href = f"/page/{page_id + 1}" if page_id < page_count else "/"
    prev_href = f"/page/{page_id - 1}" if page_id > 1 else "/"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Synthetic Page {page_id}</title>
  <link rel="canonical" href="/page/{page_id}">
</head>
<body>
  <h1>Page {page_id}</h1>
  <a href="/">Home</a>
  <a href="{next_href}">Next</a>
  <a href="{prev_href}">Prev</a>
</body>
</html>
"""


async def create_test_server(page_count: int) -> tuple[web.AppRunner, int]:
    app = web.Application()
    index_html = build_index_html(page_count)
    page_cache = {
        idx: build_page_html(idx, page_count)
        for idx in range(1, page_count + 1)
    }

    async def root_handler(_request: web.Request) -> web.Response:
        return web.Response(text=index_html, content_type="text/html")

    async def page_handler(request: web.Request) -> web.Response:
        page_id = int(request.match_info["page_id"])
        html = page_cache.get(page_id)
        if html is None:
            return web.Response(status=404, text="Not Found")
        return web.Response(text=html, content_type="text/html")

    async def robots_handler(_request: web.Request) -> web.Response:
        body = "User-agent: *\nAllow: /\n"
        return web.Response(text=body, content_type="text/plain")

    app.router.add_get("/", root_handler)
    app.router.add_get("/page/{page_id:\\d+}", page_handler)
    app.router.add_get("/robots.txt", robots_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=0)
    await site.start()

    sockets = site._server.sockets if site._server else []
    if not sockets:
        raise RuntimeError("Failed to start synthetic benchmark server")
    port = sockets[0].getsockname()[1]
    return runner, port


def serialize_stats(stats: dict) -> dict:
    return {
        "state": stats.get("state"),
        "pages_crawled": int(stats.get("pages_crawled", 0)),
        "pages_failed": int(stats.get("pages_failed", 0)),
        "total_bytes": int(stats.get("total_bytes", 0)),
        "duration_seconds": float(stats.get("duration", 0.0)),
        "url_manager": stats.get("url_manager", {}),
        "rate_limiter": stats.get("rate_limiter", {}),
    }


async def run_benchmark(page_count: int, requests_per_second: float) -> dict:
    runner, port = await create_test_server(page_count)
    start_url = f"http://127.0.0.1:{port}/"
    expected_min_pages = page_count + 1  # root + /page/1..N

    crawler = WebCrawler(
        start_url=start_url,
        max_depth=2,
        max_urls=page_count + 20,
        crawl_non_html=False,
        requests_per_second=requests_per_second,
        use_playwright=False,
        user_agent="WebCrawler/1.0 (Benchmark)",
        respect_robots=True,
    )

    try:
        await crawler.initialize()
        wall_start = time.perf_counter()
        await crawler.crawl()
        wall_duration = time.perf_counter() - wall_start
        stats = serialize_stats(crawler.get_stats())
    finally:
        await runner.cleanup()

    pages_crawled = stats["pages_crawled"]
    pages_failed = stats["pages_failed"]
    state = stats["state"]
    pages_per_second = pages_crawled / wall_duration if wall_duration > 0 else 0.0

    pass_checks = {
        "completed_state": state == "completed",
        "no_failed_pages": pages_failed == 0,
        "reached_expected_page_volume": pages_crawled >= expected_min_pages,
    }

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": {
            "name": "local_1000_plus_pages",
            "start_url": start_url,
            "page_count_generated": page_count,
            "expected_min_pages_crawled": expected_min_pages,
            "requests_per_second": requests_per_second,
        },
        "result": {
            "wall_duration_seconds": round(wall_duration, 4),
            "pages_per_second": round(pages_per_second, 2),
            "stats": stats,
        },
        "pass_checks": pass_checks,
        "passed": all(pass_checks.values()),
    }


def write_results(payload: dict) -> tuple[Path, Path]:
    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    latest_path = results_dir / "latest_1000_pages.json"
    history_path = results_dir / f"benchmark_1000_pages_{timestamp}.json"

    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    history_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return latest_path, history_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local 1000+ page crawl benchmark")
    parser.add_argument("--pages", type=int, default=1200, help="Number of synthetic pages to generate (default: 1200)")
    parser.add_argument("--rps", type=float, default=800.0, help="Crawler requests per second (default: 800)")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    payload = await run_benchmark(page_count=args.pages, requests_per_second=args.rps)
    latest_path, history_path = write_results(payload)

    print(json.dumps(payload, indent=2))
    print(f"\nSaved latest result to: {latest_path}")
    print(f"Saved historical result to: {history_path}")

    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
