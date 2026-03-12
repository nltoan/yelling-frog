# 🕷️ Web Crawler - Screaming Frog-Inspired SEO Crawler

A Python SEO crawler inspired by Screaming Frog, with crawl control, SEO extraction, issue auditing, and export workflows.

## 📌 Current Status (March 11, 2026)

- Core crawling, extraction, analysis, and exports are working in this repo.
- Some "100% complete" claims in older docs were overstated and have been revised.
- Current automated test run in this environment: `28 passed, 0 skipped`.
- Local 1000+ page benchmark passed on March 11, 2026 (`1201` pages crawled, `0` failed).

## ✨ Features

### Core Crawling
- ✅ **Smart URL Queue Management** - Efficient BFS crawling with depth control
- ✅ **robots.txt Parsing** - Respects robots.txt rules per user-agent
- ✅ **XML Sitemap Parsing** - Discovers and parses all sitemap types
- ✅ **Rate Limiting** - Configurable requests per second with token bucket algorithm
- ✅ **Redirect Following** - Supports all redirect types (301, 302, 303, 307, 308, meta refresh, JavaScript)
- ✅ **Status Code Tracking** - Complete HTTP status code tracking (2xx, 3xx, 4xx, 5xx)

### SEO Data Extraction (55+ Columns)
- ✅ **Page Titles** - Multiple title detection, length, pixel width calculation
- ✅ **Meta Descriptions** - Complete meta description analysis
- ✅ **Headings (H1-H6)** - All heading levels with multiple instance tracking
- ✅ **Meta Robots & X-Robots-Tag** - All directive types (noindex, nofollow, none, etc.)
- ✅ **Canonical Tags** - Link element and HTTP header canonicals
- ✅ **Pagination** - rel="next" and rel="prev" detection
- ✅ **Open Graph & Twitter Cards** - Social media meta tags
- ✅ **Structured Data** - JSON-LD, Microdata, RDFa extraction and validation

### Content Analysis
- ✅ **Word Count** - Accurate body text word counting
- ✅ **Text Ratio** - Non-HTML to total character percentage
- ✅ **Readability Score** - Flesch reading ease calculation
- ✅ **Content Hash** - MD5 hashing for duplicate detection
- ✅ **Exact Duplicates** - Hash-based exact duplicate detection
- ✅ **Near Duplicates** - Similarity-based near-duplicate detection (90%+ match)

### Link Analysis
- ✅ **Internal/External Links** - Complete link graph with anchor text
- ✅ **Link Metrics** - Inlinks, outlinks, unique counts
- ✅ **Link Score** - PageRank-like internal link scoring (0-100)
- ✅ **Crawl Depth** - Distance from start URL
- ✅ **Folder Depth** - URL path depth analysis
- ✅ **Orphan Pages** - Pages with no internal inlinks

### Technical SEO
- ✅ **Security Headers** - HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- ✅ **Mixed Content Detection** - HTTPS pages with HTTP resources
- ✅ **Insecure Forms** - Forms on HTTP or submitting to HTTP
- ✅ **URL Structure Analysis** - Length, parameters, non-ASCII, underscores, uppercase
- ✅ **Performance Metrics** - Response time, TTFB, size, transferred bytes
- ✅ **HTTP Version** - HTTP/1.1 vs HTTP/2 detection

### Advanced Analysis
- ✅ **Redirect Chains** - Multi-hop redirect detection
- ✅ **Redirect Loops** - Infinite redirect loop detection
- ✅ **Canonical Chains** - Chained canonical references
- ✅ **Hreflang Analysis** - International SEO with return link validation
- ✅ **Image Analysis** - Alt text, dimensions, file size, missing attributes

### Filters (30+ Issue Detectors)
- ✅ Response code filters (2xx, 3xx, 4xx, 5xx)
- ✅ Title filters (missing, duplicate, too long/short)
- ✅ Meta description filters (missing, duplicate, too long/short)
- ✅ Heading filters (missing H1, multiple H1, too long)
- ✅ Content filters (low content, low text ratio)
- ✅ Canonical filters (missing, chains, loops)
- ✅ Security filters (HTTP URLs, mixed content, missing HSTS)
- ✅ URL filters (too long, parameters, special characters)
- ✅ Indexability filters (indexable, non-indexable, noindex)

### Data Export
- ✅ **CSV Export** - All columns with filter support
- ✅ **JSON Export** - Complete structured data export
- ✅ **Excel Export** - Multi-sheet workbooks with formatting

### Web Interface
- ✅ **Real-time Dashboard** - Live crawl progress with WebSocket updates
- ✅ **Data Tables** - Sortable, filterable URL lists
- ✅ **Statistics Panel** - Indexability, status codes, performance metrics
- ✅ **Filter Buttons** - Quick access to all issue filters
- ✅ **Export Controls** - One-click CSV/JSON/Excel export

## 🏗️ Architecture

```
webcrawler/
├── spider/                 # Core crawling engine
│   ├── crawler.py         # Main crawler with async/await
│   ├── url_manager.py     # URL queue and state management
│   ├── robots_parser.py   # robots.txt handling
│   ├── sitemap_parser.py  # XML sitemap parsing
│   └── rate_limiter.py    # Token bucket rate limiting
│
├── extractors/            # Data extraction modules
│   ├── seo.py            # Titles, meta, headings, directives
│   ├── links.py          # Link extraction and metrics
│   ├── content.py        # Word count, readability, text ratio
│   ├── resources.py      # Images, scripts, CSS
│   ├── technical.py      # Security, performance, URL analysis
│   └── structured_data.py # JSON-LD, Microdata, Open Graph
│
├── analysis/              # Advanced analysis
│   ├── duplicates.py     # Exact and near-duplicate detection
│   ├── orphans.py        # Orphan page detection
│   └── redirects.py      # Redirect chain/loop analysis
│
├── storage/               # Data persistence
│   ├── models.py         # SQLite schema (55+ columns)
│   ├── database.py       # Database operations
│   ├── export.py         # CSV/JSON/Excel export
│   └── persistence.py    # Session management
│
├── processing/            # Data processing
│   └── page_processor.py # Orchestrates all extractors
│
└── api/                   # REST API
    ├── main.py           # FastAPI app with WebSocket
    └── routes/           # API endpoints

frontend/                  # Web UI
├── index.html            # Alpine.js + Tailwind CSS
└── static/               # Static assets
```

## 🚀 Quick Start

### Docker (Recommended)

```bash
# Build and start the container
docker build -t webcrawler:dev .
docker run -d --name webcrawler-dev webcrawler:dev tail -f /dev/null

# Install dependencies
docker exec webcrawler-dev pip install -r /app/requirements.txt

# Run integration test
docker exec webcrawler-dev python /app/test_integration.py

# Start the web server
docker exec -d webcrawler-dev python /app/run_server.py

# Access the application
# Web UI: http://localhost:8000/
# API: http://localhost:8000/api
# API Docs: http://localhost:8000/api/docs
```

### Local Installation

```bash
# Clone the repository
git clone <repository-url>
cd webcrawler

# Install dependencies
pip install -r requirements.txt

# Run tests
python test_crawler.py
python test_extractors.py
python test_integration.py

# Start the server
python run_server.py
```

## 📚 API Usage

### Start a Crawl

```bash
curl -X POST http://localhost:8000/api/crawl/start \
  -H "Content-Type: application/json" \
  -d '{
    "start_url": "https://example.com",
    "max_urls": 100,
    "max_depth": 5,
    "crawl_non_html": false,
    "requests_per_second": 1.0,
    "use_playwright": true,
    "respect_robots": true,
    "user_agent": "WebCrawler/1.0"
  }'
```

### Get Crawl Status

```bash
curl http://localhost:8000/api/crawl/{session_id}/status
```

### Get URLs with Filter

```bash
# Get all missing titles
curl http://localhost:8000/api/data/{session_id}/urls?filter=missing_title

# Get 4xx errors
curl http://localhost:8000/api/data/{session_id}/urls?filter=client_error_4xx

# Get non-indexable pages
curl http://localhost:8000/api/data/{session_id}/urls?filter=non_indexable
```

### Get Statistics

```bash
curl http://localhost:8000/api/data/{session_id}/stats
```

### Get Named Reports (Spec-aligned)

```bash
# List all report types
curl http://localhost:8000/api/reports/{session_id}

# Fetch one report (examples)
curl http://localhost:8000/api/reports/{session_id}/crawl_overview
curl http://localhost:8000/api/reports/{session_id}/issues_report
curl http://localhost:8000/api/reports/{session_id}/link_score

# Export one named report to CSV
curl http://localhost:8000/api/reports/{session_id}/response_codes/csv -o response_codes.csv

# Export one named report to JSON / XLSX
curl http://localhost:8000/api/reports/{session_id}/response_codes/json -o response_codes.json
curl http://localhost:8000/api/reports/{session_id}/response_codes/xlsx -o response_codes.xlsx
```

### Run Analysis

```bash
# Duplicate detection
curl http://localhost:8000/api/analysis/{session_id}/duplicates

# Orphan pages
curl http://localhost:8000/api/analysis/{session_id}/orphans

# Redirect chains and loops
curl http://localhost:8000/api/analysis/{session_id}/redirects

# Comprehensive issues report
curl http://localhost:8000/api/analysis/{session_id}/issues
```

### Export Data

```bash
# Export to CSV
curl http://localhost:8000/api/export/{session_id}/csv > crawl.csv

# Export to JSON
curl http://localhost:8000/api/export/{session_id}/json > crawl.json

# Export to Excel
curl http://localhost:8000/api/export/{session_id}/excel > crawl.xlsx
```

### WebSocket (Real-time Updates)

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/{session_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'progress') {
    console.log(`Crawled: ${data.crawled_urls} / ${data.total_urls}`);
  } else if (data.type === 'completed') {
    console.log('Crawl completed!');
  }
};
```

## 🧪 Testing

The project includes comprehensive tests:

- **test_crawler.py** - Spider engine tests
- **test_extractors.py** - All extractor modules
- **test_integration.py** - Full end-to-end test

```bash
# Recommended test command
pytest -q

# 1000+ page local benchmark
python benchmarks/benchmark_1000_pages.py --pages 1200 --rps 800
```

Latest local run (March 11, 2026): `28 passed, 0 skipped`.
Latest benchmark run (March 11, 2026): `1201` crawled, `0` failed, `state=completed`.

```bash
# Generate Screaming Frog filter parity matrix (spec vs implementation)
python scripts/generate_filter_parity_matrix.py

# Generate Screaming Frog report parity matrix (spec vs implementation)
python scripts/generate_report_parity_matrix.py

# Validate full parity (filters + reports), exits non-zero if not complete
python scripts/validate_spec_parity.py
```

Generated outputs:
- `reports/filter_parity_matrix.md`
- `reports/filter_parity_matrix.json`
- `reports/report_parity_matrix.md`
- `reports/report_parity_matrix.json`

Latest parity run (March 11, 2026):
- Spec filters: `122`
- Fully implemented across DB+API+UI: `122`
- Partial: `0`
- Missing: `0`

Latest report parity run (March 11, 2026):
- Spec reports: `16`
- Implemented: `16`
- Missing: `0`

## 📊 Data Schema

The crawler stores a broad internal URL schema (100+ fields) and can export a Screaming Frog-style CSV (72 columns):

### Core Data
- URL, Status Code, Content Type, Indexability

### SEO Data
- Title (1 & 2), Meta Description (1 & 2), Meta Keywords
- H1-H6 (2 instances each with lengths)
- Meta Robots, X-Robots-Tag
- Canonical Links, Pagination (next/prev)

### Content Metrics
- Word Count, Text Ratio, Readability Score
- Content Hash, Duplicate Detection

### Link Metrics
- Crawl Depth, Folder Depth, Link Score
- Inlinks, Outlinks (internal & external)
- Unique link counts

### Technical
- Response Time, TTFB, Size, Transferred
- HTTP Version, Last-Modified
- Security Headers (HSTS, CSP, X-Frame-Options, etc.)

### Structured Data
- JSON-LD, Microdata, RDFa
- Schema Types, Validation Errors/Warnings
- Open Graph, Twitter Cards

### Security & Issues
- HTTPS, Mixed Content, Insecure Forms
- URL Structure (length, parameters, special chars)

## 🎯 Performance

- **Concurrent Crawling**: Async/await for high performance
- **Rate Limiting**: Token bucket algorithm prevents server overload
- **Efficient Storage**: SQLite with indexes for fast queries
- **Memory Management**: Streaming processing, no full DOM storage
- **Progress Tracking**: Real-time WebSocket updates

## 📝 Configuration

### Crawler Settings

```python
from webcrawler.spider.crawler import WebCrawler

crawler = WebCrawler(
    start_url="https://example.com",
    max_depth=10,               # Maximum click depth
    max_urls=10000,             # Maximum URLs to crawl
    crawl_non_html=False,       # Skip obvious non-HTML resources
    requests_per_second=1.0,    # Rate limit
    use_playwright=False,       # JavaScript rendering (optional)
    user_agent="Custom Bot/1.0",
    respect_robots=True         # Follow robots.txt
)
```

### Database Location

By default, the database is stored at `/app/data/crawl_data.db`. Configure via:

```python
from webcrawler.storage.database import Database

db = Database("/custom/path/crawl.db")
```

## 🔍 Available Filters

### Response Codes
- `success_2xx` - 200-299 responses
- `redirection_3xx` - 300-399 redirects
- `client_error_4xx` - 400-499 errors
- `server_error_5xx` - 500-599 errors
- `crawl_error` - Crawl request failed (no status returned)

### Titles
- `missing_title` - No title tag
- `duplicate_title` - Duplicate title values
- `title_over_60_chars` - Title too long for SERP
- `title_below_30_chars` - Title too short
- `multiple_titles` - More than one title tag

### Meta Descriptions
- `missing_meta_description` - No meta description
- `duplicate_meta_description` - Duplicate meta description values
- `meta_description_over_155_chars` - Too long
- `meta_description_below_70_chars` - Too short

### Headings
- `missing_h1` - No H1 tag
- `duplicate_h1` - Duplicate H1 values
- `multiple_h1` - Multiple H1 tags
- `h1_over_70_chars` - H1 too long

### Content
- `low_content` - Less than 200 words
- `low_text_ratio` - High HTML to text ratio

### Canonicals
- `missing_canonical` - No canonical tag
- `contains_canonical` - Has canonical tag

### Security
- `http_urls` - Insecure HTTP URLs
- `https_urls` - Secure HTTPS URLs
- `mixed_content` - HTTPS with HTTP resources
- `insecure_forms` - Forms on/to HTTP
- `missing_hsts` - No HSTS header on HTTPS

### URL Issues
- `url_over_115_chars` - URL too long
- `url_with_parameters` - Query parameters present
- `url_with_underscores` - Underscores in URL
- `url_with_uppercase` - Uppercase characters

### Indexability
- `indexable` - Can be indexed
- `non_indexable` - Cannot be indexed
- `noindex` - Has noindex directive

## 🛠️ Technology Stack

- **Python 3.10+**
- **FastAPI** - Modern async web framework
- **aiohttp** - Async HTTP client
- **BeautifulSoup4** - HTML parsing
- **SQLite** - Lightweight database
- **WebSockets** - Real-time updates
- **Alpine.js** - Reactive frontend
- **Tailwind CSS** - Modern UI styling

## 📦 Dependencies

See `requirements.txt` for complete list:
- playwright (optional, for JavaScript rendering)
- aiohttp (HTTP client)
- beautifulsoup4 (HTML parsing)
- fastapi (API framework)
- uvicorn (ASGI server)
- pandas (data export)
- openpyxl (Excel export)

## 🤝 Contributing

Contributions welcome for:
- Additional export formats
- Performance optimizations
- UI enhancements
- Bug fixes

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

Inspired by [Screaming Frog SEO Spider](https://www.screamingfrog.co.uk/seo-spider/)

## 📞 Support

For issues, questions, or contributions, please open an issue on the repository.

---

**Built with ❤️ for SEO professionals and developers**
