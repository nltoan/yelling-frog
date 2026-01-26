# Screaming Frog CSV Output Specification

**Reference file:** /Users/remotelodestarm2/.clawdbot/media/inbound/d14b1bfb-9c70-4af4-8060-e4cabab2086b.csv

Our output MUST match this format EXACTLY - same columns, same order, same naming.

## Column List (72 columns)

| # | Column Name |
|---|-------------|
| 1 | Address |
| 2 | Content Type |
| 3 | Status Code |
| 4 | Status |
| 5 | Indexability |
| 6 | Indexability Status |
| 7 | Title 1 |
| 8 | Title 1 Length |
| 9 | Title 1 Pixel Width |
| 10 | Meta Description 1 |
| 11 | Meta Description 1 Length |
| 12 | Meta Description 1 Pixel Width |
| 13 | Meta Keywords 1 |
| 14 | Meta Keywords 1 Length |
| 15 | H1-1 |
| 16 | H1-1 Length |
| 17 | H2-1 |
| 18 | H2-1 Length |
| 19 | H2-2 |
| 20 | H2-2 Length |
| 21 | Meta Robots 1 |
| 22 | X-Robots-Tag 1 |
| 23 | Meta Refresh 1 |
| 24 | Canonical Link Element 1 |
| 25 | rel="next" 1 |
| 26 | rel="prev" 1 |
| 27 | HTTP rel="next" 1 |
| 28 | HTTP rel="prev" 1 |
| 29 | amphtml Link Element |
| 30 | Size (bytes) |
| 31 | Transferred (bytes) |
| 32 | Total Transferred (bytes) |
| 33 | CO2 (mg) |
| 34 | Carbon Rating |
| 35 | Word Count |
| 36 | Sentence Count |
| 37 | Average Words Per Sentence |
| 38 | Flesch Reading Ease Score |
| 39 | Readability |
| 40 | Text Ratio |
| 41 | Crawl Depth |
| 42 | Folder Depth |
| 43 | Link Score |
| 44 | Inlinks |
| 45 | Unique Inlinks |
| 46 | Unique JS Inlinks |
| 47 | % of Total |
| 48 | Outlinks |
| 49 | Unique Outlinks |
| 50 | Unique JS Outlinks |
| 51 | External Outlinks |
| 52 | Unique External Outlinks |
| 53 | Unique External JS Outlinks |
| 54 | Closest Near Duplicate Match |
| 55 | No. Near Duplicates |
| 56 | Spelling Errors |
| 57 | Grammar Errors |
| 58 | Hash |
| 59 | Response Time |
| 60 | Last Modified |
| 61 | Redirect URL |
| 62 | Redirect Type |
| 63 | Cookies |
| 64 | Language |
| 65 | HTTP Version |
| 66 | Mobile Alternate Link |
| 67 | Closest Semantically Similar Address |
| 68 | Semantic Similarity Score |
| 69 | No. Semantically Similar |
| 70 | Semantic Relevance Score |
| 71 | URL Encoded Address |
| 72 | Crawl Timestamp |

## Key Implementation Notes

### Pixel Width Calculations
- Title and Meta Description have pixel width columns
- Screaming Frog uses a standard font rendering calculation
- Approximate: multiply character count by ~9.5 for titles, ~6 for descriptions (vary by character)

### Indexability
- "Indexable" or "Non-Indexable"
- Status column explains why (e.g., "Redirected", "Blocked by robots.txt", "Noindex")

### Readability Grades
- Based on Flesch Reading Ease Score:
  - 90-100: Very Easy
  - 80-89: Easy
  - 70-79: Fairly Easy
  - 60-69: Normal
  - 50-59: Fairly Hard
  - 30-49: Hard
  - 0-29: Very Hard

### CO2 and Carbon Rating
- CO2 in mg based on page size/transferred bytes
- Carbon Rating: A+, A, B, C, D, E, F

### Link Metrics
- Inlinks: pages linking TO this URL (within the crawl)
- Outlinks: links FROM this URL
- Unique = deduplicated
- JS Inlinks/Outlinks = discovered via JavaScript execution

### Hash
- MD5 hash of page content for duplicate detection

### Response Time
- In seconds (e.g., 0.322)

### Crawl Timestamp
- Format: YYYY-MM-DD HH:MM:SS

## Sample Row (homepage)

```csv
"https://hepisontheway.com/","text/html; charset=utf-8","200","OK","Indexable","","HEP is on the way!","18","164","One Call Does It All—HEP handles heating & air, electrical, plumbing, roofing. 24/7 repairs & installs keep your home safe, comfy, and efficient.","145","867","","0","is on the way!","14","HEP","3","Our Trades","10","","","","","","","","","","273719","37612","37612","14.657","","729","273","2.670","48.154","Hard","2.488","0","0","","1324","333","0","100.000","188","182","0","0","0","0","","","","","e0eedea8a5eb47ebca4e2aefc80d5a42","0.322","","","","","en","1.1","","","","","","https://hepisontheway.com/","2026-01-25 09:34:06"
```

## Priority Columns (must work first)

1. Address, Status Code, Status
2. Title 1, Title 1 Length
3. Meta Description 1, Meta Description 1 Length
4. H1-1, H1-1 Length, H2-1, H2-2
5. Word Count
6. Crawl Depth, Folder Depth
7. Inlinks, Outlinks (basic counts)
8. Hash, Response Time, Crawl Timestamp

Then expand to remaining columns.
