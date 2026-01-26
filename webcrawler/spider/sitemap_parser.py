"""
Sitemap Parser - Handles XML sitemap parsing
"""
import asyncio
from typing import List, Dict, Optional
from urllib.parse import urljoin
from datetime import datetime
import aiohttp
from xml.etree import ElementTree as ET


class SitemapParser:
    """Parses XML sitemaps and sitemap indexes"""
    
    def __init__(self):
        self.sitemap_urls: List[str] = []
        self.parsed_urls: List[Dict] = []
        self.sitemap_indexes: List[str] = []
        
    async def fetch_and_parse(self, sitemap_url: str) -> List[Dict]:
        """
        Fetch and parse a sitemap URL
        Returns list of URL entries with metadata
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        return []
                    
                    content = await response.text()
                    return self._parse_xml(content, sitemap_url)
        except Exception as e:
            print(f"Error fetching sitemap {sitemap_url}: {e}")
            return []
    
    def _parse_xml(self, xml_content: str, source_url: str) -> List[Dict]:
        """Parse XML sitemap content"""
        urls = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Handle namespace
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            # Check if this is a sitemap index
            if 'sitemapindex' in root.tag:
                # Parse sitemap index
                for sitemap in root.findall('.//ns:sitemap', namespace):
                    loc = sitemap.find('ns:loc', namespace)
                    if loc is not None and loc.text:
                        self.sitemap_indexes.append(loc.text)
            else:
                # Parse regular sitemap
                for url_elem in root.findall('.//ns:url', namespace):
                    url_data = self._extract_url_data(url_elem, namespace)
                    if url_data:
                        urls.append(url_data)
        except ET.ParseError as e:
            print(f"XML parse error for {source_url}: {e}")
        except Exception as e:
            print(f"Error parsing sitemap {source_url}: {e}")
        
        return urls
    
    def _extract_url_data(self, url_elem: ET.Element, namespace: Dict) -> Optional[Dict]:
        """Extract data from a URL element"""
        loc = url_elem.find('ns:loc', namespace)
        if loc is None or not loc.text:
            return None
        
        data = {
            'loc': loc.text,
            'lastmod': None,
            'changefreq': None,
            'priority': None
        }
        
        # Extract lastmod
        lastmod = url_elem.find('ns:lastmod', namespace)
        if lastmod is not None and lastmod.text:
            data['lastmod'] = lastmod.text
        
        # Extract changefreq
        changefreq = url_elem.find('ns:changefreq', namespace)
        if changefreq is not None and changefreq.text:
            data['changefreq'] = changefreq.text
        
        # Extract priority
        priority = url_elem.find('ns:priority', namespace)
        if priority is not None and priority.text:
            try:
                data['priority'] = float(priority.text)
            except ValueError:
                pass
        
        return data
    
    async def parse_all_sitemaps(self, sitemap_urls: List[str]) -> List[Dict]:
        """
        Parse multiple sitemaps, including sitemap indexes
        Returns combined list of all URLs found
        """
        all_urls = []
        processed_sitemaps = set()
        
        async def process_sitemap(url: str):
            if url in processed_sitemaps:
                return
            
            processed_sitemaps.add(url)
            urls = await self.fetch_and_parse(url)
            all_urls.extend(urls)
            
            # If this was a sitemap index, process child sitemaps
            if self.sitemap_indexes:
                child_sitemaps = self.sitemap_indexes.copy()
                self.sitemap_indexes.clear()
                
                tasks = [process_sitemap(child_url) for child_url in child_sitemaps]
                await asyncio.gather(*tasks)
        
        # Process all provided sitemap URLs
        tasks = [process_sitemap(url) for url in sitemap_urls]
        await asyncio.gather(*tasks)
        
        self.parsed_urls = all_urls
        return all_urls
    
    def get_urls(self) -> List[str]:
        """Get list of just the URLs (loc field)"""
        return [entry['loc'] for entry in self.parsed_urls]
    
    def get_urls_with_metadata(self) -> List[Dict]:
        """Get URLs with full metadata"""
        return self.parsed_urls
    
    def compare_with_crawled(self, crawled_urls: set) -> Dict:
        """
        Compare sitemap URLs with crawled URLs
        Returns dict with in_sitemap_only, in_crawl_only, in_both
        """
        sitemap_urls = set(self.get_urls())
        
        return {
            'in_sitemap_only': list(sitemap_urls - crawled_urls),
            'in_crawl_only': list(crawled_urls - sitemap_urls),
            'in_both': list(sitemap_urls & crawled_urls),
            'sitemap_count': len(sitemap_urls),
            'crawled_count': len(crawled_urls),
            'match_percentage': len(sitemap_urls & crawled_urls) / len(sitemap_urls) * 100 if sitemap_urls else 0
        }
