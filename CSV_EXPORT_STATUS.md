# Screaming Frog CSV Export - Status Snapshot

## Snapshot Date

March 11, 2026

## Format Compliance (Last Verified Sample)

```
✅ Column Count: 72/72
✅ Column Order: Matches export spec
✅ Data Formats: All correct (integers, 3-decimal floats)
✅ Quoting: All fields quoted
✅ Encoding: UTF-8 with BOM
✅ Empty Values: Empty strings (not null)
✅ Timestamp: YYYY-MM-DD HH:MM:SS
```

Notes:
- This file records a validated sample run, not a blanket guarantee for every future crawl/session.
- Use this as an operational reference and re-validate after major exporter/schema changes.

## Implemented Features

### Core Columns (Validated)
- Address, Content Type, Status Code, Status
- Indexability, Indexability Status (with redirect/error handling)
- Title 1, Title 1 Length, Title 1 Pixel Width
- Meta Description 1, Length, Pixel Width
- Meta Keywords 1, Length
- H1-1, H1-1 Length, H2-1, H2-1 Length, H2-2, H2-2 Length
- Meta Robots 1, X-Robots-Tag 1, Meta Refresh 1
- Canonical Link Element 1
- rel="next" 1, rel="prev" 1, HTTP rel="next" 1, HTTP rel="prev" 1

### Content Analysis (Validated)
- Word Count
- Sentence Count ✨ NEW
- Average Words Per Sentence ✨ NEW  
- Flesch Reading Ease Score
- Readability (grade: Very Easy → Very Hard)
- Text Ratio
- Hash (MD5)

### Performance (Validated)
- Size (bytes)
- Transferred (bytes)
- Total Transferred (bytes)
- Response Time
- Last Modified

### Carbon/CO2 (Validated) ✨ NEW
- CO2 (mg) - calculated from page size
- Carbon Rating (A+ to F)

### Link Metrics (Validated)
- Crawl Depth
- Folder Depth
- Link Score (PageRank-style)
- Inlinks, Unique Inlinks, Unique JS Inlinks
- % of Total
- Outlinks, Unique Outlinks, Unique JS Outlinks
- External Outlinks, Unique External Outlinks, Unique External JS Outlinks

### Near Duplicates (Validated)
- Closest Near Duplicate Match
- No. Near Duplicates
- Based on content hash matching

### Redirects (Validated)
- Redirect URL
- Redirect Type (HTTP Redirect, Meta Refresh, JavaScript Redirect, HSTS Policy)

### Technical (Validated)
- Language
- HTTP Version
- URL Encoded Address
- Crawl Timestamp
- Cookies (when present)

## Empty by Design (Site-Dependent)
These columns are empty because the crawled site doesn't have these features:
- amphtml Link Element (site has no AMP)
- Mobile Alternate Link (site has no mobile-specific URLs)
- rel="next"/rel="prev" (no pagination)
- Meta Keywords (not used by site)
- X-Robots-Tag (not used by site)
- Meta Refresh (not used by site)

## Not Implemented (Would Require External Services)
- Spelling Errors - requires LanguageTool or similar
- Grammar Errors - requires LanguageTool or similar
- Semantic Similarity fields - requires vector embeddings

## Files Modified

1. **webcrawler/storage/screaming_frog_exporter.py** - NEW
   - Full 72-column export matching the local export specification
   - CO2 and Carbon Rating calculations
   - Proper formatting (quoting, decimals, timestamps)

2. **webcrawler/storage/models.py**
   - Added: sentence_count, avg_words_per_sentence, readability_grade
   - Added: unique_js_inlinks/outlinks fields
   - Added: semantic similarity fields
   - Updated SQL schema

3. **webcrawler/extractors/content.py**
   - Added sentence counting
   - Added readability grade calculation

4. **webcrawler/extractors/links.py**
   - Added URL normalization for inlink calculation
   - Fixed inlinks not matching due to www/non-www differences

5. **webcrawler/extractors/seo.py**
   - Enhanced indexability detection for redirects and errors

6. **webcrawler/processing/page_processor.py**
   - Added near duplicate detection
   - Improved link metrics post-processing

7. **crawl_site.py**
   - Uses ScreamingFrogExporter
   - Runs link metrics post-processing

## Usage

```bash
# Run crawl inside Docker
docker exec webcrawler-dev python crawl_site.py https://example.com --max-pages 50

# Output files:
# /app/data/crawl_XXXXXXXX_screaming_frog.csv  (Screaming Frog format)
# /app/data/crawl_XXXXXXXX.json                (JSON format)
```

## Test Results
```
8 passed, 2 skipped (async tests)
Format compliance checks for the sampled run: ✅ PASS
```
