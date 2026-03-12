# Filter Parity Matrix

- Generated at (UTC): `2026-03-11T07:23:05+00:00`
- Spec source: `SCREAMING_FROG_SPEC.md`
- DB filter codes found: `124`
- API filter codes found: `124`
- Frontend filter codes found: `124`

## Summary

| Metric | Count |
|---|---:|
| Total spec filters | 122 |
| Implemented (DB+API+UI) | 122 |
| Partial (at least one layer) | 0 |
| Missing (no layer) | 0 |

## Matrix

| Category | Spec Filter | Expected Code | DB | API | UI | Status | Note |
|---|---|---|:---:|:---:|:---:|---|---|
| Response Codes | Blocked by Robots.txt | `blocked_by_robots_txt` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | Blocked Resource | `blocked_resource` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | No Response | `crawl_error` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | Success (2XX) | `success_2xx` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | Redirection (3XX) | `redirection_3xx` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | Redirection (JavaScript) | `redirection_javascript` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | Redirection (Meta Refresh) | `redirection_meta_refresh` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | Redirect Chain | `redirect_chain` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | Redirect Loop | `redirect_loop` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | Client Error (4XX) | `client_error_4xx` | Y | Y | Y | implemented | Matched by category alias |
| Response Codes | Server Error (5XX) | `server_error_5xx` | Y | Y | Y | implemented | Matched by category alias |
| Page Titles | Missing | `missing_title` | Y | Y | Y | implemented | Matched by category alias |
| Page Titles | Duplicate | `duplicate_title` | Y | Y | Y | implemented | Matched by category alias |
| Page Titles | Over 60 Characters | `title_over_60_chars` | Y | Y | Y | implemented | Matched by category alias |
| Page Titles | Below 30 Characters | `title_below_30_chars` | Y | Y | Y | implemented | Matched by category alias |
| Page Titles | Over 568 Pixels | `title_over_568_pixels` | Y | Y | Y | implemented | Matched by category alias |
| Page Titles | Below 200 Pixels | `title_below_200_pixels` | Y | Y | Y | implemented | Matched by category alias |
| Page Titles | Same as H1 | `same_as_h1` | Y | Y | Y | implemented | Matched by category alias |
| Page Titles | Multiple | `multiple_titles` | Y | Y | Y | implemented | Matched by category alias |
| Meta Description | Missing | `missing_meta_description` | Y | Y | Y | implemented | Matched by category alias |
| Meta Description | Duplicate | `duplicate_meta_description` | Y | Y | Y | implemented | Matched by category alias |
| Meta Description | Over 155 Characters | `meta_description_over_155_chars` | Y | Y | Y | implemented | Matched by category alias |
| Meta Description | Below 70 Characters | `meta_description_below_70_chars` | Y | Y | Y | implemented | Matched by category alias |
| Meta Description | Over 990 Pixels | `meta_description_over_990_pixels` | Y | Y | Y | implemented | Matched by category alias |
| Meta Description | Below 400 Pixels | `meta_description_below_400_pixels` | Y | Y | Y | implemented | Matched by category alias |
| Meta Description | Multiple | `multiple_meta_descriptions` | Y | Y | Y | implemented | Matched by category alias |
| Headings | Missing H1 | `missing_h1` | Y | Y | Y | implemented | Matched by category alias |
| Headings | Duplicate H1 | `duplicate_h1` | Y | Y | Y | implemented | Matched by category alias |
| Headings | Over 70 Characters H1 | `h1_over_70_chars` | Y | Y | Y | implemented | Matched by category alias |
| Headings | Multiple H1 | `multiple_h1` | Y | Y | Y | implemented | Matched by category alias |
| Headings | Missing H2 | `missing_h2` | Y | Y | Y | implemented | Matched by category alias |
| Headings | Non-Sequential Headings | `non_sequential_headings` | Y | Y | Y | implemented | Matched by category alias |
| Content | Low Content | `low_content` | Y | Y | Y | implemented | Matched by category alias |
| Content | Near Duplicates | `near_duplicates` | Y | Y | Y | implemented | Matched by category alias |
| Content | Exact Duplicates | `exact_duplicates` | Y | Y | Y | implemented | Matched by category alias |
| Content | Spelling Errors | `spelling_errors` | Y | Y | Y | implemented | Matched by category alias |
| Content | Grammar Errors | `grammar_errors` | Y | Y | Y | implemented | Matched by category alias |
| Content | Low Text Ratio | `low_text_ratio` | Y | Y | Y | implemented | Matched by category alias |
| Directives | Index | `indexable` | Y | Y | Y | implemented | Matched by category alias |
| Directives | Noindex | `noindex` | Y | Y | Y | implemented | Matched by category alias |
| Directives | Follow | `follow` | Y | Y | Y | implemented | Matched by category alias |
| Directives | Nofollow | `nofollow` | Y | Y | Y | implemented | Matched by category alias |
| Directives | None | `none` | Y | Y | Y | implemented | Matched by category alias |
| Directives | NoArchive | `noarchive` | Y | Y | Y | implemented | Matched by category alias |
| Directives | NoSnippet | `nosnippet` | Y | Y | Y | implemented | Matched by category alias |
| Directives | Max-Snippet | `max_snippet` | Y | Y | Y | implemented | Matched by category alias |
| Directives | Max-Image-Preview | `max_image_preview` | Y | Y | Y | implemented | Matched by category alias |
| Directives | Max-Video-Preview | `max_video_preview` | Y | Y | Y | implemented | Matched by category alias |
| Directives | NoImageIndex | `noimageindex` | Y | Y | Y | implemented | Matched by category alias |
| Directives | Unavailable_After | `unavailable_after` | Y | Y | Y | implemented | Matched by category alias |
| Canonicals | Contains Canonical | `contains_canonical` | Y | Y | Y | implemented | Matched by category alias |
| Canonicals | Self Referencing | `self_referencing_canonical` | Y | Y | Y | implemented | Matched by category alias |
| Canonicals | Canonicalised | `canonicalised` | Y | Y | Y | implemented | Matched by category alias |
| Canonicals | Missing | `missing_canonical` | Y | Y | Y | implemented | Matched by category alias |
| Canonicals | Non-Indexable Canonical | `canonical_to_non_indexable` | Y | Y | Y | implemented | Matched by category alias |
| Canonicals | Canonical Chain | `canonical_chain` | Y | Y | Y | implemented | Matched by category alias |
| Canonicals | Canonical Loop | `canonical_loop` | Y | Y | Y | implemented | Matched by category alias |
| Pagination | Contains Pagination | `contains_pagination` | Y | Y | Y | implemented | Matched by category alias |
| Pagination | First Page | `pagination_first_page` | Y | Y | Y | implemented | Matched by category alias |
| Pagination | Paginated 2+ Page | `pagination_2_plus_page` | Y | Y | Y | implemented | Matched by category alias |
| Pagination | Pagination URL Not In Anchor | `pagination_url_not_in_anchor` | Y | Y | Y | implemented | Matched by category alias |
| Pagination | Non-200 Pagination URL | `non_200_pagination_url` | Y | Y | Y | implemented | Matched by category alias |
| Pagination | Unlinked Pagination URL | `unlinked_pagination_url` | Y | Y | Y | implemented | Matched by category alias |
| Pagination | Non-Indexable | `non_indexable_pagination_url` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Contains hreflang | `contains_hreflang` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Non-200 hreflang URL | `non_200_hreflang_url` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Unlinked hreflang URL | `unlinked_hreflang_url` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Missing Return Links | `missing_return_links` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Inconsistent Language | `inconsistent_language` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Incorrect Language/Region Codes | `invalid_hreflang_codes` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Multiple Entries | `multiple_hreflang_entries` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Missing Self Reference | `missing_self_reference` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Not Using Canonical | `hreflang_not_using_canonical` | Y | Y | Y | implemented | Matched by category alias |
| Hreflang | Missing X-Default | `missing_x_default` | Y | Y | Y | implemented | Matched by category alias |
| Images | Over 100KB | `images_over_100kb` | Y | Y | Y | implemented | Matched by category alias |
| Images | Missing Alt Text | `missing_alt_text` | Y | Y | Y | implemented | Matched by category alias |
| Images | Missing Alt Attribute | `missing_alt_attribute` | Y | Y | Y | implemented | Matched by category alias |
| Images | Alt Text Over 100 Characters | `alt_text_over_100_chars` | Y | Y | Y | implemented | Matched by category alias |
| Images | Missing Size Attributes | `missing_size_attributes` | Y | Y | Y | implemented | Matched by category alias |
| Security | HTTP URLs | `http_urls` | Y | Y | Y | implemented | Matched by category alias |
| Security | HTTPS URLs | `https_urls` | Y | Y | Y | implemented | Matched by category alias |
| Security | Mixed Content | `mixed_content` | Y | Y | Y | implemented | Matched by category alias |
| Security | Form URL Insecure | `insecure_forms` | Y | Y | Y | implemented | Matched by category alias |
| Security | Form on HTTP URL | `form_on_http_url` | Y | Y | Y | implemented | Matched by category alias |
| Security | Unsafe Cross-Origin Links | `unsafe_cross_origin_links` | Y | Y | Y | implemented | Matched by category alias |
| Security | Protocol-Relative Links | `protocol_relative_links` | Y | Y | Y | implemented | Matched by category alias |
| Security | Missing HSTS Header | `missing_hsts` | Y | Y | Y | implemented | Matched by category alias |
| Security | Missing Content-Security-Policy | `missing_csp` | Y | Y | Y | implemented | Matched by category alias |
| Security | Missing X-Content-Type-Options | `missing_x_content_type_options` | Y | Y | Y | implemented | Matched by category alias |
| Security | Missing X-Frame-Options | `missing_x_frame_options` | Y | Y | Y | implemented | Matched by category alias |
| Security | Missing Secure Referrer-Policy | `missing_secure_referrer_policy` | Y | Y | Y | implemented | Matched by category alias |
| Security | Bad Content Type | `bad_content_type` | Y | Y | Y | implemented | Matched by category alias |
| URL | Non ASCII Characters | `url_with_non_ascii` | Y | Y | Y | implemented | Matched by category alias |
| URL | Underscores | `url_with_underscores` | Y | Y | Y | implemented | Matched by category alias |
| URL | Uppercase | `url_with_uppercase` | Y | Y | Y | implemented | Matched by category alias |
| URL | Parameters | `url_with_parameters` | Y | Y | Y | implemented | Matched by category alias |
| URL | Over 115 Characters | `url_over_115_chars` | Y | Y | Y | implemented | Matched by category alias |
| URL | Duplicate | `duplicate_url` | Y | Y | Y | implemented | Matched by category alias |
| URL | Broken Bookmarks | `broken_bookmarks` | Y | Y | Y | implemented | Matched by category alias |
| JavaScript | Pages with JavaScript Links | `javascript_links` | Y | Y | Y | implemented | Matched by category alias |
| JavaScript | Pages with JavaScript Content | `javascript_content` | Y | Y | Y | implemented | Matched by category alias |
| JavaScript | JavaScript-only Titles | `javascript_only_titles` | Y | Y | Y | implemented | Matched by category alias |
| JavaScript | JavaScript-only Descriptions | `javascript_only_descriptions` | Y | Y | Y | implemented | Matched by category alias |
| JavaScript | JavaScript-only H1 | `javascript_only_h1` | Y | Y | Y | implemented | Matched by category alias |
| JavaScript | JavaScript-only Canonicals | `javascript_only_canonicals` | Y | Y | Y | implemented | Matched by category alias |
| Structured Data | Contains Structured Data | `contains_structured_data` | Y | Y | Y | implemented | Matched by category alias |
| Structured Data | JSON-LD | `json_ld` | Y | Y | Y | implemented | Matched by category alias |
| Structured Data | Microdata | `microdata` | Y | Y | Y | implemented | Matched by category alias |
| Structured Data | RDFa | `rdfa` | Y | Y | Y | implemented | Matched by category alias |
| Structured Data | Validation Errors | `validation_errors` | Y | Y | Y | implemented | Matched by category alias |
| Structured Data | Validation Warnings | `validation_warnings` | Y | Y | Y | implemented | Matched by category alias |
| Structured Data | Missing Fields | `schema_missing_fields` | Y | Y | Y | implemented | Matched by category alias |
| AMP | Valid AMP | `valid_amp` | Y | Y | Y | implemented | Matched by category alias |
| AMP | AMP Validation Errors | `amp_validation_errors` | Y | Y | Y | implemented | Matched by category alias |
| AMP | AMP Validation Warnings | `amp_validation_warnings` | Y | Y | Y | implemented | Matched by category alias |
| AMP | Non-200 AMP URL | `non_200_amp_url` | Y | Y | Y | implemented | Matched by category alias |
| AMP | Missing Non-AMP Return | `missing_non_amp_return` | Y | Y | Y | implemented | Matched by category alias |
| Sitemaps | In Sitemap | `in_sitemap` | Y | Y | Y | implemented | Matched by category alias |
| Sitemaps | Not In Sitemap | `not_in_sitemap` | Y | Y | Y | implemented | Matched by category alias |
| Sitemaps | Orphan URLs | `orphan_urls` | Y | Y | Y | implemented | Matched by category alias |
| Sitemaps | Non-200 In Sitemap | `non_200_in_sitemap` | Y | Y | Y | implemented | Matched by category alias |
| Sitemaps | Non-Indexable In Sitemap | `non_indexable_in_sitemap` | Y | Y | Y | implemented | Matched by category alias |
