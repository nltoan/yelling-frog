"""
Screaming Frog CSV Exporter
Exports crawl data in EXACT Screaming Frog format (72 columns)
"""
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime
from .database import Database
from .models import CrawledURL


# Screaming Frog column order (72 columns) - MUST match exactly
SCREAMING_FROG_COLUMNS = [
    "Address",
    "Content Type",
    "Status Code",
    "Status",
    "Indexability",
    "Indexability Status",
    "Title 1",
    "Title 1 Length",
    "Title 1 Pixel Width",
    "Meta Description 1",
    "Meta Description 1 Length",
    "Meta Description 1 Pixel Width",
    "Meta Keywords 1",
    "Meta Keywords 1 Length",
    "H1-1",
    "H1-1 Length",
    "H2-1",
    "H2-1 Length",
    "H2-2",
    "H2-2 Length",
    "Meta Robots 1",
    "X-Robots-Tag 1",
    "Meta Refresh 1",
    "Canonical Link Element 1",
    'rel="next" 1',
    'rel="prev" 1',
    'HTTP rel="next" 1',
    'HTTP rel="prev" 1',
    "amphtml Link Element",
    "Size (bytes)",
    "Transferred (bytes)",
    "Total Transferred (bytes)",
    "CO2 (mg)",
    "Carbon Rating",
    "Word Count",
    "Sentence Count",
    "Average Words Per Sentence",
    "Flesch Reading Ease Score",
    "Readability",
    "Text Ratio",
    "Crawl Depth",
    "Folder Depth",
    "Link Score",
    "Inlinks",
    "Unique Inlinks",
    "Unique JS Inlinks",
    "% of Total",
    "Outlinks",
    "Unique Outlinks",
    "Unique JS Outlinks",
    "External Outlinks",
    "Unique External Outlinks",
    "Unique External JS Outlinks",
    "Closest Near Duplicate Match",
    "No. Near Duplicates",
    "Spelling Errors",
    "Grammar Errors",
    "Hash",
    "Response Time",
    "Last Modified",
    "Redirect URL",
    "Redirect Type",
    "Cookies",
    "Language",
    "HTTP Version",
    "Mobile Alternate Link",
    "Closest Semantically Similar Address",
    "Semantic Similarity Score",
    "No. Semantically Similar",
    "Semantic Relevance Score",
    "URL Encoded Address",
    "Crawl Timestamp",
]


def get_readability_grade(flesch_score: float) -> str:
    """
    Convert Flesch Reading Ease score to grade
    
    90-100: Very Easy
    80-89: Easy
    70-79: Fairly Easy
    60-69: Normal
    50-59: Fairly Hard
    30-49: Hard
    0-29: Very Hard
    """
    if flesch_score is None:
        return ""
    if flesch_score >= 90:
        return "Very Easy"
    elif flesch_score >= 80:
        return "Easy"
    elif flesch_score >= 70:
        return "Fairly Easy"
    elif flesch_score >= 60:
        return "Normal"
    elif flesch_score >= 50:
        return "Fairly Hard"
    elif flesch_score >= 30:
        return "Hard"
    else:
        return "Very Hard"


def calculate_co2(transferred_bytes: int) -> float:
    """
    Calculate CO2 emissions in mg based on transferred bytes
    
    Uses Website Carbon Calculator formula:
    CO2 per byte = 0.000000389673 kg CO2/byte (grid intensity)
    Convert to mg: multiply by 1,000,000
    """
    if not transferred_bytes or transferred_bytes == 0:
        return 0.0
    
    # Website Carbon Calculator average: ~0.39g CO2 per kB
    # = 0.00039 g/byte = 0.39 mg/byte / 1000 = 0.00039 mg/byte
    co2_per_byte = 0.00039  # mg per byte
    co2_mg = transferred_bytes * co2_per_byte
    return round(co2_mg, 3)


def get_carbon_rating(co2_mg: float, transferred_bytes: int) -> str:
    """
    Get carbon rating (A+ to F) based on CO2 and page size
    
    Based on Website Carbon Calculator ratings:
    A+: < 0.095g CO2 (< 95mg)
    A: < 0.185g CO2 (< 185mg)
    B: < 0.341g CO2 (< 341mg)
    C: < 0.493g CO2 (< 493mg)
    D: < 0.656g CO2 (< 656mg)
    E: < 0.846g CO2 (< 846mg)
    F: >= 0.846g CO2 (>= 846mg)
    """
    if co2_mg == 0:
        return ""
    
    # Convert to grams for comparison
    co2_g = co2_mg / 1000
    
    if co2_g < 0.095:
        return "A+"
    elif co2_g < 0.185:
        return "A"
    elif co2_g < 0.341:
        return "B"
    elif co2_g < 0.493:
        return "C"
    elif co2_g < 0.656:
        return "D"
    elif co2_g < 0.846:
        return "E"
    else:
        return "F"


def format_value(value: Any, decimal_places: int = 3) -> str:
    """
    Format a value for CSV output
    
    - None/null -> empty string
    - Floats -> fixed decimal places
    - Integers -> no decimal
    - Everything else -> string
    """
    if value is None:
        return ""
    
    if isinstance(value, bool):
        return "1" if value else "0"
    
    if isinstance(value, float):
        if value == 0.0:
            return "0" if decimal_places == 0 else f"0.{'0' * decimal_places}"
        return f"{value:.{decimal_places}f}"
    
    if isinstance(value, int):
        return str(value)
    
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    
    return str(value)


def format_timestamp(dt: Optional[datetime]) -> str:
    """Format datetime as YYYY-MM-DD HH:MM:SS"""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class ScreamingFrogExporter:
    """Export crawl data in exact Screaming Frog CSV format"""
    
    def __init__(self, database: Database):
        self.db = database
    
    def url_to_row(self, url_data: CrawledURL) -> Dict[str, str]:
        """
        Convert a CrawledURL to a Screaming Frog-compatible row dict
        All values are strings, empty string for missing values
        """
        # Calculate derived values
        transferred = getattr(url_data, 'transferred', 0) or getattr(url_data, 'size', 0) or 0
        co2_mg = calculate_co2(transferred)
        carbon_rating = get_carbon_rating(co2_mg, transferred)
        
        flesch_score = getattr(url_data, 'readability', None)
        if flesch_score is None:
            flesch_score = 0
        # Use stored grade if available, otherwise calculate
        readability_grade = getattr(url_data, 'readability_grade', None) or get_readability_grade(flesch_score)
        
        # Get sentence count and avg words (need to calculate if not stored)
        sentence_count = getattr(url_data, 'sentence_count', 0) or 0
        avg_words_per_sentence = getattr(url_data, 'avg_words_per_sentence', 0) or 0
        word_count = getattr(url_data, 'word_count', 0) or 0
        
        # Determine if it's HTML content
        content_type = getattr(url_data, 'content_type', '') or ''
        is_html = 'text/html' in content_type.lower() if content_type else False
        
        # Format text ratio as percentage with 3 decimals
        text_ratio = getattr(url_data, 'text_ratio', 0) or 0
        
        # Build row dict matching exact column order
        row = {
            "Address": getattr(url_data, 'url', '') or '',
            "Content Type": content_type,
            "Status Code": format_value(getattr(url_data, 'status_code', None), 0),
            "Status": getattr(url_data, 'status_text', '') or '',
            "Indexability": getattr(url_data, 'indexability', '') or '',
            "Indexability Status": getattr(url_data, 'indexability_status', '') or '',
            "Title 1": getattr(url_data, 'title_1', '') or '',
            "Title 1 Length": format_value(getattr(url_data, 'title_1_length', 0), 0),
            "Title 1 Pixel Width": format_value(getattr(url_data, 'title_1_pixel_width', 0), 0),
            "Meta Description 1": getattr(url_data, 'meta_description_1', '') or '',
            "Meta Description 1 Length": format_value(getattr(url_data, 'meta_description_1_length', 0), 0),
            "Meta Description 1 Pixel Width": format_value(getattr(url_data, 'meta_description_1_pixel_width', 0), 0),
            "Meta Keywords 1": getattr(url_data, 'meta_keywords_1', '') or '',
            "Meta Keywords 1 Length": format_value(getattr(url_data, 'meta_keywords_1_length', 0), 0),
            "H1-1": getattr(url_data, 'h1_1', '') or '',
            "H1-1 Length": format_value(getattr(url_data, 'h1_len_1', 0), 0),
            "H2-1": getattr(url_data, 'h2_1', '') or '',
            "H2-1 Length": format_value(getattr(url_data, 'h2_len_1', 0), 0),
            "H2-2": getattr(url_data, 'h2_2', '') or '',
            "H2-2 Length": format_value(getattr(url_data, 'h2_len_2', 0), 0),
            "Meta Robots 1": getattr(url_data, 'meta_robots_1', '') or '',
            "X-Robots-Tag 1": getattr(url_data, 'x_robots_tag_1', '') or '',
            "Meta Refresh 1": getattr(url_data, 'meta_refresh_1', '') or '',
            "Canonical Link Element 1": getattr(url_data, 'canonical_link_element_1', '') or '',
            'rel="next" 1': getattr(url_data, 'rel_next_1', '') or '',
            'rel="prev" 1': getattr(url_data, 'rel_prev_1', '') or '',
            'HTTP rel="next" 1': getattr(url_data, 'http_rel_next_1', '') or '',
            'HTTP rel="prev" 1': getattr(url_data, 'http_rel_prev_1', '') or '',
            "amphtml Link Element": getattr(url_data, 'amphtml_link', '') or '',
            "Size (bytes)": format_value(getattr(url_data, 'size', 0), 0),
            "Transferred (bytes)": format_value(transferred, 0),
            "Total Transferred (bytes)": format_value(transferred, 0),  # Same as transferred for single resource
            "CO2 (mg)": format_value(co2_mg, 3) if co2_mg > 0 else "",
            "Carbon Rating": carbon_rating if is_html else "",  # Only show for HTML pages
            "Word Count": format_value(word_count, 0),
            "Sentence Count": format_value(sentence_count, 0) if (is_html and word_count > 0) else "",
            "Average Words Per Sentence": format_value(avg_words_per_sentence, 3) if (is_html and word_count > 0) else "",
            "Flesch Reading Ease Score": format_value(flesch_score, 3) if (is_html and word_count > 0) else "",
            "Readability": readability_grade if (is_html and word_count > 0 and readability_grade) else "",
            "Text Ratio": format_value(text_ratio, 3) if text_ratio > 0 else "0.000",
            "Crawl Depth": format_value(getattr(url_data, 'crawl_depth', 0), 0),
            "Folder Depth": format_value(getattr(url_data, 'folder_depth', 0), 0),
            "Link Score": "",  # Screaming Frog doesn't show this by default
            "Inlinks": format_value(getattr(url_data, 'inlinks', 0), 0),
            "Unique Inlinks": format_value(getattr(url_data, 'unique_inlinks', 0), 0),
            "Unique JS Inlinks": format_value(getattr(url_data, 'unique_js_inlinks', 0), 0),
            "% of Total": format_value(getattr(url_data, 'percentage_of_total', 0), 3),
            "Outlinks": format_value(getattr(url_data, 'outlinks', 0), 0),
            "Unique Outlinks": format_value(getattr(url_data, 'unique_outlinks', 0), 0),
            "Unique JS Outlinks": format_value(getattr(url_data, 'unique_js_outlinks', 0), 0),
            "External Outlinks": format_value(getattr(url_data, 'external_outlinks', 0), 0),
            "Unique External Outlinks": format_value(getattr(url_data, 'unique_external_outlinks', 0), 0),
            "Unique External JS Outlinks": format_value(getattr(url_data, 'unique_external_js_outlinks', 0), 0),
            "Closest Near Duplicate Match": getattr(url_data, 'closest_similarity_match', '') or '',
            "No. Near Duplicates": format_value(getattr(url_data, 'no_near_duplicates', None), 0) if getattr(url_data, 'no_near_duplicates', None) else "",
            "Spelling Errors": getattr(url_data, 'spelling_errors', '') or '',
            "Grammar Errors": getattr(url_data, 'grammar_errors', '') or '',
            "Hash": getattr(url_data, 'hash', '') or '',
            "Response Time": format_value(getattr(url_data, 'response_time', 0), 3) if getattr(url_data, 'response_time', 0) else "",
            "Last Modified": getattr(url_data, 'last_modified', '') or '',
            "Redirect URL": getattr(url_data, 'redirect_uri', '') or '',
            "Redirect Type": getattr(url_data, 'redirect_type', '') or '',
            "Cookies": getattr(url_data, 'cookies', '') or '',
            "Language": getattr(url_data, 'language', '') or '',
            "HTTP Version": getattr(url_data, 'http_version', '').replace('HTTP/', '') if getattr(url_data, 'http_version', '') else '',
            "Mobile Alternate Link": getattr(url_data, 'mobile_alternate_link', '') or '',
            "Closest Semantically Similar Address": getattr(url_data, 'closest_semantic_match', '') or '',
            "Semantic Similarity Score": getattr(url_data, 'semantic_similarity_score', '') or '',
            "No. Semantically Similar": getattr(url_data, 'no_semantically_similar', '') or '',
            "Semantic Relevance Score": getattr(url_data, 'semantic_relevance_score', '') or '',
            "URL Encoded Address": getattr(url_data, 'url_encoded', '') or getattr(url_data, 'url', '') or '',
            "Crawl Timestamp": format_timestamp(getattr(url_data, 'crawled_at', None)),
        }
        
        return row
    
    def export_csv(
        self, 
        session_id: str, 
        output_path: str,
        filter_name: Optional[str] = None
    ) -> int:
        """
        Export to CSV in exact Screaming Frog format
        
        Args:
            session_id: Crawl session ID
            output_path: Output file path
            filter_name: Optional filter to apply
            
        Returns:
            Number of rows exported
        """
        # Get data
        if filter_name:
            urls = self.db.get_urls_by_filter(session_id, filter_name)
        else:
            urls = self.db.get_all_urls(session_id)
        
        if not urls:
            return 0
        
        # Write CSV with all values quoted
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(
                f, 
                fieldnames=SCREAMING_FROG_COLUMNS,
                quoting=csv.QUOTE_ALL,  # Quote all fields like Screaming Frog does
                extrasaction='ignore'
            )
            writer.writeheader()
            
            for url_data in urls:
                row = self.url_to_row(url_data)
                writer.writerow(row)
        
        return len(urls)
    
    def export_internal_html(self, session_id: str, output_path: str) -> int:
        """Export only internal HTML pages (main Screaming Frog export)"""
        urls = self.db.get_all_urls(session_id)
        
        # Filter to internal HTML only
        html_urls = [
            u for u in urls 
            if (getattr(u, 'content_type', '') or '').startswith('text/html')
        ]
        
        if not html_urls:
            return 0
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=SCREAMING_FROG_COLUMNS,
                quoting=csv.QUOTE_ALL,
                extrasaction='ignore'
            )
            writer.writeheader()
            
            for url_data in html_urls:
                row = self.url_to_row(url_data)
                writer.writerow(row)
        
        return len(html_urls)
