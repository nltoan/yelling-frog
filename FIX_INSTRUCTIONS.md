# CRITICAL BUG FIX REQUIRED - Yelling Frog Crawler

## The Problem

The crawler is NOT working like Screaming Frog. When crawling https://mastersroofinginc.com/:

**What we got:**
- Only 2 pages found (should be 20+)
- Title: null (actual: "Top Roofing Company In Charlotte | Masters Roofing")
- H1: null (actual: "Your Trusted Roofing Company in Charlotte, North Carolina")
- Meta description: null (site has one)
- Word count: 0 (site has 1000+ words)
- Internal links not being followed

**What Screaming Frog does:**
1. Uses breadth-first algorithm to discover ALL internal links
2. Extracts title from `<title>` tag
3. Extracts meta description from `<meta name="description">`
4. Extracts H1-H6 from heading tags
5. Counts words in body text
6. Follows ALL `<a href>` links within the same domain
7. Respects robots.txt
8. Parses XML sitemaps

## Files to Debug

1. `webcrawler/extractors/seo.py` - Title, meta, H1 extraction is broken
2. `webcrawler/extractors/content.py` - Word count returning 0
3. `webcrawler/extractors/links.py` - Not finding internal links
4. `webcrawler/spider/crawler.py` - Not following discovered links

## Test Case

URL: https://mastersroofinginc.com/

Expected results:
- Title: "Top Roofing Company In Charlotte | Masters Roofing"
- H1: "Your Trusted Roofing Company in Charlotte, North Carolina"
- Internal links found: /service-areas/charlotte-roofing-company/, /service-areas/wilmington-roofing-company/, /about, etc.
- Word count: 500+ words
- Pages discovered: 15+

## Fix Requirements

1. **SEO Extractor** - Must properly parse BeautifulSoup/lxml to get:
   - `soup.title.string` for title
   - `soup.find('meta', attrs={'name': 'description'})['content']` for meta
   - `soup.find('h1').get_text()` for H1

2. **Link Discovery** - Must find all `<a href>` tags:
   - Filter to same domain only
   - Normalize URLs (handle relative paths)
   - Add to crawl queue

3. **Content Extractor** - Must count words:
   - Strip HTML tags
   - Count words in body text
   - Exclude nav/footer boilerplate if possible

4. **Crawler Loop** - Must actually crawl the queue:
   - Pop URL from queue
   - Fetch and parse
   - Extract links, add new ones to queue
   - Continue until queue empty or max_pages reached

## Verification

After fix, run:
```bash
curl -X POST "http://localhost:8000/api/crawl/start" \
  -H "Content-Type: application/json" \
  -d '{"start_url": "https://mastersroofinginc.com/", "max_pages": 50}'
```

Should return:
- 10+ pages discovered
- Titles populated (not null)
- H1s populated (not null)
- Word counts > 0

## Priority

This is blocking. Fix the extractors first, then the link following.
