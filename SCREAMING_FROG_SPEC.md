# Complete Screaming Frog Feature Specification
## Every Column, Filter, and Feature - No Stone Left Unturned

---

## 📊 DATA COLUMNS (55+ columns per URL)

### Core URL Data
| Column | Description |
|--------|-------------|
| Address | The URL address |
| Content | Content type (text/html, image/jpeg, etc.) |
| Status Code | HTTP response code (200, 301, 404, etc.) |
| Status | HTTP header response text |
| Indexability | Indexable or Non-Indexable |
| Indexability Status | Reason why Non-Indexable (canonicalised, noindex, etc.) |
| URL Encoded Address | URL with non-ASCII characters percent encoded |
| Hash | MD5 hash for exact duplicate detection |

### Page Title Data
| Column | Description |
|--------|-------------|
| Title 1 | First page title discovered |
| Title 1 Length | Character length of title |
| Title 1 Pixel Width | Pixel width in SERP display |
| Title 2 | Second title if multiple exist |
| Title 2 Length | Character length of second title |

### Meta Description Data
| Column | Description |
|--------|-------------|
| Meta Description 1 | First meta description |
| Meta Description 1 Length | Character length |
| Meta Description 1 Pixel Width | Pixel width in SERP |
| Meta Description 2 | Second if multiple exist |
| Meta Keywords 1 | Meta keywords content |
| Meta Keywords Length | Character length |

### Heading Data
| Column | Description |
|--------|-------------|
| H1-1 | First H1 heading text |
| H1-Len-1 | Character length of H1 |
| H1-2 | Second H1 if multiple |
| H2-1 | First H2 heading text |
| H2-Len-1 | Character length |
| H2-2 | Second H2 if multiple |
| (Continue for H3-H6) | All heading levels |

### Directives Data
| Column | Description |
|--------|-------------|
| Meta Robots 1 | Meta robots directives (index, noindex, follow, nofollow, none, noarchive, nosnippet, etc.) |
| Meta Robots 2 | Second meta robots if multiple |
| X-Robots-Tag 1 | X-Robots-Tag HTTP header directives |
| X-Robots-Tag 2 | Second if multiple |
| Meta Refresh 1 | Meta refresh data |

### Canonical & Pagination
| Column | Description |
|--------|-------------|
| Canonical Link Element 1 | Canonical URL specified |
| Canonical Link Element 2 | Second canonical if multiple |
| rel="next" 1 | Pagination next URL |
| rel="prev" 1 | Pagination previous URL |
| HTTP rel="next" 1 | HTTP header pagination |
| HTTP rel="prev" 1 | HTTP header pagination |

### Size & Performance
| Column | Description |
|--------|-------------|
| Size | Size in bytes (from Content-Length header) |
| Transferred | Actual bytes transferred (may be compressed) |
| Total Transferred | Total bytes including all resources (JS rendering) |
| Response Time | Time in seconds to download |
| TTFB | Time To First Byte |
| Last-Modified | Last-Modified header value |

### Content Analysis
| Column | Description |
|--------|-------------|
| Word Count | Words inside body tag (excluding nav/footer by default) |
| Text Ratio | Non-HTML chars / total chars as percentage |
| Readability | Flesch reading ease score |
| Closest Similarity Match | Highest % similarity to near-duplicate URL |
| No. Near Duplicates | Count of near-duplicate pages (90%+ match) |
| Spelling Errors | Total spelling errors |
| Grammar Errors | Total grammar errors |
| Language | HTML lang attribute |

### Link Metrics
| Column | Description |
|--------|-------------|
| Crawl Depth | Clicks from start page |
| Folder Depth | Number of subfolders in URL path |
| Link Score | PageRank-like internal link score (0-100) |
| Inlinks | Number of internal links TO this URL |
| Unique Inlinks | Unique internal inlinks |
| Unique JS Inlinks | Internal inlinks only in rendered HTML |
| % of Total | Percentage of total pages linking to this URL |
| Outlinks | Number of internal links FROM this URL |
| Unique Outlinks | Unique internal outlinks |
| Unique JS Outlinks | Internal outlinks only in rendered HTML |
| External Outlinks | Links to external domains |
| Unique External Outlinks | Unique external outlinks |
| Unique External JS Outlinks | External outlinks only in rendered HTML |

### Redirect Data
| Column | Description |
|--------|-------------|
| Redirect URI | Target URL if redirecting |
| Redirect Type | HTTP Redirect, HSTS Policy, JavaScript Redirect, Meta Refresh |
| HTTP Version | HTTP/1.1 or HTTP/2 |

### Images
| Column | Description |
|--------|-------------|
| Image URL | Source URL of image |
| Alt Text | Alt attribute content |
| Alt Text Length | Character length |
| File Size | Size in bytes |
| Width | Image width in pixels |
| Height | Image height in pixels |
| Missing Alt | Boolean |
| Missing Size Attributes | Boolean |

### Structured Data
| Column | Description |
|--------|-------------|
| Structured Data Type | JSON-LD, Microdata, RDFa |
| Schema Types | Schema.org types found |
| Validation Errors | Schema validation errors |
| Validation Warnings | Schema validation warnings |

### Hreflang
| Column | Description |
|--------|-------------|
| hreflang Language | Language code |
| hreflang Region | Region code |
| hreflang URL | Target URL |
| Return Link | Whether return link exists |
| Return Link Status | Valid/Missing/Inconsistent |

### Security Headers
| Column | Description |
|--------|-------------|
| HSTS | Strict-Transport-Security header present |
| Content-Security-Policy | CSP header present |
| X-Content-Type-Options | nosniff header present |
| X-Frame-Options | DENY/SAMEORIGIN present |
| Referrer-Policy | Secure policy present |

### Open Graph & Twitter Cards
| Column | Description |
|--------|-------------|
| og:title | Open Graph title |
| og:description | Open Graph description |
| og:image | Open Graph image |
| og:type | Open Graph type |
| og:url | Open Graph URL |
| twitter:card | Twitter card type |
| twitter:title | Twitter title |
| twitter:description | Twitter description |
| twitter:image | Twitter image |

---

## 🔍 FILTERS (Issue Detection)

### Response Codes Tab Filters
- **Blocked by Robots.txt** - URLs disallowed by robots.txt
- **Blocked Resource** - Resources blocked from rendering
- **No Response** - Connection timeout, refused, DNS failure
- **Success (2XX)** - 200 OK responses
- **Redirection (3XX)** - 301, 302, 303, 307, 308 redirects
- **Redirection (JavaScript)** - JS-triggered redirects
- **Redirection (Meta Refresh)** - Meta refresh redirects
- **Redirect Chain** - URLs with multiple redirect hops
- **Redirect Loop** - Infinite redirect loops
- **Client Error (4XX)** - 400, 401, 403, 404, 410, 429, etc.
- **Server Error (5XX)** - 500, 502, 503, 504, etc.

### Page Titles Tab Filters
- **Missing** - No title tag
- **Duplicate** - Same title as another page
- **Over 60 Characters** - Too long for SERP
- **Below 30 Characters** - Too short
- **Over 568 Pixels** - Too wide for SERP
- **Below 200 Pixels** - Too narrow
- **Same as H1** - Title matches H1
- **Multiple** - More than one title tag

### Meta Description Tab Filters
- **Missing** - No meta description
- **Duplicate** - Same as another page
- **Over 155 Characters** - Too long
- **Below 70 Characters** - Too short
- **Over 990 Pixels** - Too wide
- **Below 400 Pixels** - Too narrow
- **Multiple** - More than one meta description

### Headings Tab Filters
- **Missing H1** - No H1 tag
- **Duplicate H1** - Same H1 as another page
- **Over 70 Characters H1** - H1 too long
- **Multiple H1** - More than one H1
- **Missing H2** - No H2 tags
- **Non-Sequential Headings** - H2 before H1, H4 before H3, etc.

### Content Tab Filters
- **Low Content** - Under 200 words
- **Near Duplicates** - 90%+ similarity match
- **Exact Duplicates** - 100% match (same hash)
- **Spelling Errors** - Pages with spelling issues
- **Grammar Errors** - Pages with grammar issues
- **Low Text Ratio** - High HTML to text ratio

### Directives Tab Filters
- **Index** - Indexable pages
- **Noindex** - Meta noindex
- **Follow** - Links followed
- **Nofollow** - Meta nofollow
- **None** - Meta none
- **NoArchive** - Meta noarchive
- **NoSnippet** - Meta nosnippet
- **Max-Snippet** - Max snippet directives
- **Max-Image-Preview** - Image preview directives
- **Max-Video-Preview** - Video preview directives
- **NoImageIndex** - Meta noimageindex
- **Unavailable_After** - Expiration date set

### Canonicals Tab Filters
- **Contains Canonical** - Has canonical tag
- **Self Referencing** - Canonical points to itself
- **Canonicalised** - Points to different URL
- **Missing** - No canonical tag
- **Non-Indexable Canonical** - Canonical points to non-indexable URL
- **Canonical Chain** - Canonical points to URL that also has canonical
- **Canonical Loop** - Circular canonical reference

### Pagination Tab Filters
- **Contains Pagination** - Has rel next/prev
- **First Page** - First in paginated series
- **Paginated 2+ Page** - Subsequent pages
- **Pagination URL Not In Anchor** - Pagination URLs missing
- **Non-200 Pagination URL** - Pagination target errors
- **Unlinked Pagination URL** - Orphan pagination pages
- **Non-Indexable** - Paginated pages with noindex

### Hreflang Tab Filters
- **Contains hreflang** - Has hreflang tags
- **Non-200 hreflang URL** - Hreflang target errors
- **Unlinked hreflang URL** - Missing return tags
- **Missing Return Links** - No reciprocal hreflang
- **Inconsistent Language** - Conflicting language codes
- **Incorrect Language/Region Codes** - Invalid ISO codes
- **Multiple Entries** - Same language multiple times
- **Missing Self Reference** - No self-referential hreflang
- **Not Using Canonical** - Hreflang on non-canonical
- **Missing X-Default** - No x-default fallback

### Images Tab Filters
- **Over 100KB** - Large images
- **Missing Alt Text** - No alt attribute
- **Missing Alt Attribute** - Alt attribute absent entirely
- **Alt Text Over 100 Characters** - Alt text too long
- **Missing Size Attributes** - No width/height

### Security Tab Filters
- **HTTP URLs** - Insecure pages
- **HTTPS URLs** - Secure pages
- **Mixed Content** - HTTPS page with HTTP resources
- **Form URL Insecure** - Form action is HTTP
- **Form on HTTP URL** - Form on insecure page
- **Unsafe Cross-Origin Links** - target="_blank" without rel="noopener"
- **Protocol-Relative Links** - //example.com links
- **Missing HSTS Header** - No Strict-Transport-Security
- **Missing Content-Security-Policy** - No CSP header
- **Missing X-Content-Type-Options** - No nosniff header
- **Missing X-Frame-Options** - No frame protection
- **Missing Secure Referrer-Policy** - Insecure referrer policy
- **Bad Content Type** - MIME type mismatch

### URL Tab Filters
- **Non ASCII Characters** - Special characters in URL
- **Underscores** - Underscores instead of hyphens
- **Uppercase** - Uppercase letters in URL
- **Parameters** - Query parameters present
- **Over 115 Characters** - URL too long
- **Duplicate** - Same content, different URL
- **Broken Bookmarks** - Anchor links that don't exist

### JavaScript Tab Filters (Rendering Mode)
- **Pages with JavaScript Links** - Links only in rendered HTML
- **Pages with JavaScript Content** - Content only in rendered HTML
- **JavaScript-only Titles** - Titles require JS
- **JavaScript-only Descriptions** - Meta descriptions require JS
- **JavaScript-only H1** - H1 requires JS
- **JavaScript-only Canonicals** - Canonicals require JS

### Structured Data Tab Filters
- **Contains Structured Data** - Has any schema
- **JSON-LD** - Has JSON-LD
- **Microdata** - Has Microdata
- **RDFa** - Has RDFa
- **Validation Errors** - Schema invalid
- **Validation Warnings** - Schema has warnings
- **Missing Fields** - Required fields absent

### AMP Tab Filters
- **Valid AMP** - Passes validation
- **AMP Validation Errors** - Fails validation
- **AMP Validation Warnings** - Has warnings
- **Non-200 AMP URL** - AMP page errors
- **Missing Non-AMP Return** - No link to canonical

### Sitemaps Tab Filters  
- **In Sitemap** - URL found in XML sitemap
- **Not In Sitemap** - URL missing from sitemap
- **Orphan URLs** - In sitemap but no internal links
- **Non-200 In Sitemap** - Errors in sitemap
- **Non-Indexable In Sitemap** - Noindex pages in sitemap

---

## 📋 REPORTS TO GENERATE

1. **Crawl Overview** - Summary stats
2. **Internal All** - Full internal URL data
3. **External All** - Full external URL data
4. **Response Codes** - All URLs by status
5. **Redirect Chains** - All redirect sequences
6. **Redirect Loops** - Infinite redirects
7. **Canonicals** - All canonical data
8. **Pagination** - Pagination audit
9. **Hreflang** - International SEO audit
10. **Duplicate Content** - Exact + near duplicates
11. **Insecure Content** - All security issues
12. **Structured Data** - Schema validation
13. **Sitemaps** - Sitemap vs crawled URLs
14. **Orphan Pages** - Pages with no internal links
15. **Link Score** - Internal PageRank distribution
16. **Issues Report** - All errors/warnings/notices

---

## 🎯 IMPLEMENTATION PRIORITY

### Phase 1: Core Crawling (Must Have)
1. URL Queue management
2. robots.txt parsing
3. Sitemap parsing  
4. Rate limiting
5. Redirect following (all types)
6. Status code tracking

### Phase 2: SEO Extraction (Must Have)
1. Title extraction + analysis
2. Meta description extraction + analysis
3. Heading extraction (H1-H6)
4. Meta robots + X-Robots-Tag
5. Canonicals
6. Pagination (rel next/prev)
7. Internal/external link analysis
8. Image extraction + alt text

### Phase 3: Advanced Analysis (Must Have)
1. Duplicate content (hash-based)
2. Near-duplicate detection (similarity)
3. Word count + text ratio
4. Crawl depth
5. Link Score calculation
6. Orphan page detection
7. Redirect chain detection

### Phase 4: Technical SEO (Important)
1. Hreflang parsing
2. Structured data extraction + validation
3. Security header checking
4. Mixed content detection
5. Open Graph + Twitter Cards

### Phase 5: Web UI (Must Have)
1. Real-time crawl progress
2. Filterable data tables (all columns)
3. Issue summary dashboard
4. Export functionality
5. Crawl configuration panel

---

## 🚀 FOR RALPH

Read this spec carefully. Build EVERY feature listed above. 

Start with Phase 1 core crawling, then Phase 2 extraction, etc.

Test inside Docker: `docker exec webcrawler-dev python /app/script.py`

Update progress as you go. This is a BIG project - keep working until complete.

BEGIN NOW.
