# WebCrawler PRD - Screaming Frog Clone
## Complete Product Requirements Document

---

## 🎯 Vision
Build an exact feature-complete clone of Screaming Frog SEO Spider with a web-based UI. No stone left unturned.

## ⚠️ CRITICAL RULES
1. **ALL code execution MUST happen inside Docker container `webcrawler-dev`**
2. Test with: `docker exec webcrawler-dev python /app/script.py`
3. NEVER run code directly on the host machine
4. Test each component before moving to the next
5. Update progress in this document as you complete items

---

## 📋 User Stories

### Epic 1: Core Spider Engine
**US-1.1** As a user, I can enter a URL and crawl the entire website up to a configurable page limit (default 10,000 pages)

**US-1.2** As a user, the spider respects robots.txt directives and can optionally ignore them

**US-1.3** As a user, I can configure crawl rate (requests per second) to be polite to servers

**US-1.4** As a user, the spider follows redirects and tracks redirect chains

**US-1.5** As a user, I can pause, resume, and stop crawls

**US-1.6** As a user, the spider handles JavaScript-rendered pages (Playwright)

### Epic 2: On-Page SEO Analysis
**US-2.1** Extract and analyze page titles (length, duplicates, missing)

**US-2.2** Extract meta descriptions (length, duplicates, missing)

**US-2.3** Extract all heading tags (H1-H6) with counts and content

**US-2.4** Extract meta robots directives (index, follow, noindex, nofollow)

**US-2.5** Extract canonical URLs and identify conflicts

**US-2.6** Extract hreflang tags for international SEO

**US-2.7** Extract Open Graph and Twitter Card meta tags

**US-2.8** Extract structured data (JSON-LD, microdata, RDFa)

### Epic 3: Technical SEO Analysis
**US-3.1** Track HTTP status codes for all URLs (200, 301, 302, 404, 500, etc.)

**US-3.2** Measure page load time and TTFB (Time To First Byte)

**US-3.3** Analyze URL structure (length, parameters, depth)

**US-3.4** Detect duplicate content via content hashing

**US-3.5** Analyze internal linking structure and link equity flow

**US-3.6** Identify orphan pages (no internal links pointing to them)

**US-3.7** Track external outbound links

**US-3.8** Analyze anchor text distribution

### Epic 4: Resource Analysis
**US-4.1** Crawl and analyze images (src, alt text, size, dimensions)

**US-4.2** Identify missing/empty alt text

**US-4.3** Track CSS and JavaScript files

**US-4.4** Identify render-blocking resources

**US-4.5** Calculate page size and resource counts

### Epic 5: Configuration & Robots
**US-5.1** Parse and display robots.txt with directive analysis

**US-5.2** Parse XML sitemaps and compare to crawled URLs

**US-5.3** Identify URLs in sitemap but not crawled (and vice versa)

**US-5.4** Custom user-agent configuration

**US-5.5** Include/exclude URL patterns (regex support)

**US-5.6** Respect/ignore robots.txt toggle

### Epic 6: Data Storage & Export
**US-6.1** Store all crawl data in SQLite database

**US-6.2** Export to CSV with customizable columns

**US-6.3** Export to Excel (.xlsx)

**US-6.4** Export to JSON

**US-6.5** Save and load crawl projects

### Epic 7: Web UI Dashboard
**US-7.1** Modern responsive web interface (FastAPI + React or HTMX)

**US-7.2** Dashboard showing crawl progress in real-time

**US-7.3** Filterable/sortable data tables for all crawled pages

**US-7.4** Summary cards showing key metrics (pages, errors, warnings)

**US-7.5** Visualizations: site structure tree, link graph

**US-7.6** Issue reports with severity levels (Errors, Warnings, Notices)

**US-7.7** Detail view for individual URLs showing all extracted data

### Epic 8: Reports
**US-8.1** SEO Overview report

**US-8.2** Crawl Summary report

**US-8.3** Issues report (missing titles, broken links, etc.)

**US-8.4** Redirect report (chains, loops)

**US-8.5** Duplicate Content report

**US-8.6** Internal Linking report

---

## 🏗️ Technical Architecture

### Directory Structure
```
/app/
├── webcrawler/
│   ├── __init__.py
│   ├── spider/
│   │   ├── __init__.py
│   │   ├── crawler.py          # Main crawl engine
│   │   ├── url_manager.py      # URL queue and deduplication
│   │   ├── robots_parser.py    # robots.txt handling
│   │   ├── sitemap_parser.py   # XML sitemap parsing
│   │   └── rate_limiter.py     # Polite crawling
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── seo.py              # Title, meta, headings
│   │   ├── links.py            # Internal/external links
│   │   ├── resources.py        # Images, CSS, JS
│   │   ├── structured_data.py  # JSON-LD, schema
│   │   └── technical.py        # Status, redirects, timing
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── duplicates.py       # Duplicate detection
│   │   ├── issues.py           # Issue identification
│   │   └── reports.py          # Report generation
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite operations
│   │   ├── models.py           # Data models
│   │   └── export.py           # CSV, Excel, JSON export
│   └── api/
│       ├── __init__.py
│       ├── main.py             # FastAPI app
│       ├── routes/
│       │   ├── crawl.py        # Crawl endpoints
│       │   ├── data.py         # Data retrieval
│       │   └── export.py       # Export endpoints
│       └── websocket.py        # Real-time updates
├── frontend/
│   ├── index.html
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── templates/
├── tests/
│   ├── test_spider.py
│   ├── test_extractors.py
│   ├── test_storage.py
│   └── test_api.py
├── requirements.txt
├── Dockerfile
└── README.md
```

### Tech Stack
- **Spider**: Python 3.11+, Playwright (async), aiohttp
- **Storage**: SQLite with aiosqlite
- **API**: FastAPI with WebSocket support
- **Frontend**: HTMX + Alpine.js + Tailwind CSS (lightweight, no build step)
- **Export**: pandas, openpyxl
- **Container**: Docker

---

## 📝 Implementation Steps

### Phase 1: Enhanced Spider Core (Steps 1-10)
1. Refactor spider into modular components
2. Implement URL manager with priority queue
3. Add robots.txt parser with directive support
4. Add XML sitemap parser
5. Implement rate limiter
6. Add redirect chain tracking
7. Implement pause/resume functionality
8. Add crawl state persistence
9. Write unit tests for spider components
10. Integration test: crawl a test site

### Phase 2: Comprehensive Extractors (Steps 11-20)
11. Build SEO extractor (title, meta, headings, canonicals)
12. Build link extractor (internal, external, anchor text)
13. Build resource extractor (images, CSS, JS)
14. Build structured data extractor (JSON-LD, schema)
15. Build technical extractor (timing, size, headers)
16. Add duplicate content detection (SimHash)
17. Add hreflang extraction
18. Add Open Graph/Twitter Card extraction
19. Write unit tests for all extractors
20. Integration test: extract from sample pages

### Phase 3: Storage & Analysis (Steps 21-30)
21. Design comprehensive database schema
22. Implement database models with SQLAlchemy-style interface
23. Build export module (CSV)
24. Add Excel export (.xlsx)
25. Add JSON export
26. Build issue detection engine
27. Build report generator
28. Implement crawl project save/load
29. Write storage tests
30. Integration test: full crawl with storage

### Phase 4: Web API (Steps 31-40)
31. Set up FastAPI application structure
32. Implement crawl control endpoints (start, pause, stop)
33. Implement data retrieval endpoints
34. Implement export endpoints
35. Add WebSocket for real-time progress
36. Add authentication (optional, configurable)
37. Add API documentation (auto-generated)
38. Write API tests
39. Integration test: API with crawler
40. Load testing

### Phase 5: Web UI (Steps 41-50)
41. Set up frontend structure (HTMX + Tailwind)
42. Build dashboard layout
43. Implement crawl control panel
44. Build real-time progress display
45. Build data tables with filtering/sorting
46. Build URL detail view
47. Build issues panel
48. Add visualizations (site tree)
49. Implement export UI
50. End-to-end testing

---

## ✅ Acceptance Criteria

### Must Pass Before Completion:
1. [x] Can crawl 1000+ page site without crashing (local benchmark on March 11, 2026: 1201 pages crawled, 0 failed; see `benchmarks/benchmark_1000_pages.py`)
2. [x] Extracts ALL Screaming Frog equivalent data (latest parity matrix on March 11, 2026: 122/122 filters fully implemented; see `reports/filter_parity_matrix.md`)
3. [x] Web UI shows real-time crawl progress
4. [x] Can filter and sort all data tables
5. [x] Exports work (CSV, Excel, JSON)
6. [x] Respects robots.txt correctly
7. [x] Handles JavaScript-rendered pages
8. [x] All tests pass (current: 28 passed, 0 skipped)
9. [x] Runs entirely in Docker
10. [x] Documentation complete

---

## 📊 Progress Tracker

| Phase | Status | Steps Done | Notes |
|-------|--------|------------|-------|
| Phase 1: Spider Core | 🟢 Complete | 10/10 | Core crawl flow running; 1000+ page local benchmark documented |
| Phase 2: Extractors | 🟢 Complete | 10/10 | Screaming Frog filter parity validated at 122/122 |
| Phase 3: Storage | 🟢 Complete | 10/10 | Storage, sitemap persistence, and exports validated |
| Phase 4: API | 🟢 Complete | 10/10 | Crawl/data/analysis plus named report APIs fully implemented |
| Phase 5: UI | 🟢 Complete | 10/10 | Filter parity synced in UI with validated report/export flows |

---

## 🚀 Getting Started

Ralph, start with Phase 1, Step 1. Work through each step sequentially. After completing each step:
1. Test it inside Docker
2. Update the Progress Tracker above
3. Move to the next step
4. If you get stuck, document the issue and attempt a fix

Begin now. Good luck! 🕷️
