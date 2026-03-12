"""
Structured Data Extractor
Extracts JSON-LD, Microdata, and RDFa structured data with validation
"""
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import json
import re


class StructuredDataExtractor:
    """Extract and validate structured data"""

    def __init__(self):
        pass

    def _iter_json_ld_nodes(self, data: Any):
        """Yield every JSON-LD node, including nested @graph and list items."""
        if isinstance(data, list):
            for item in data:
                yield from self._iter_json_ld_nodes(item)
            return

        if isinstance(data, dict):
            yield data
            for key in ('@graph', 'itemListElement', 'mainEntity', 'mainEntityOfPage'):
                nested = data.get(key)
                if nested:
                    yield from self._iter_json_ld_nodes(nested)

    def extract_all(self, html: str) -> Dict[str, Any]:
        """
        Extract all structured data types

        Returns:
            - json_ld: List of JSON-LD objects
            - microdata: List of microdata items
            - rdfa: List of RDFa items
            - schema_types: Set of Schema.org types found
            - has_structured_data: Boolean
        """
        result = {
            'json_ld': [],
            'microdata': [],
            'rdfa': [],
            'schema_types': set(),
            'has_structured_data': False,
        }

        soup = BeautifulSoup(html, 'lxml')

        # Extract JSON-LD
        json_ld_data = self.extract_json_ld(soup)
        result['json_ld'] = json_ld_data

        # Extract Microdata
        microdata = self.extract_microdata(soup)
        result['microdata'] = microdata

        # Extract RDFa
        rdfa = self.extract_rdfa(soup)
        result['rdfa'] = rdfa

        # Collect all schema types
        schema_types = set()

        # From JSON-LD
        for item in json_ld_data:
            for node in self._iter_json_ld_nodes(item):
                type_val = node.get('@type')
                if type_val:
                    if isinstance(type_val, list):
                        schema_types.update(str(entry) for entry in type_val if str(entry).strip())
                    else:
                        schema_types.add(str(type_val))

        # From Microdata
        for item in microdata:
            if 'type' in item:
                schema_types.add(item['type'])

        # From RDFa
        for item in rdfa:
            if 'typeof' in item:
                schema_types.add(item['typeof'])

        result['schema_types'] = list(schema_types)
        result['has_structured_data'] = bool(json_ld_data or microdata or rdfa)

        return result

    def extract_json_ld(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract JSON-LD structured data

        Returns:
            List of parsed JSON-LD objects
        """
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        json_ld_data = []

        for script in json_ld_scripts:
            try:
                content = script.string
                if content:
                    data = json.loads(content)
                    json_ld_data.append(data)
            except json.JSONDecodeError:
                # Invalid JSON, skip
                pass

        return json_ld_data

    def extract_microdata(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract Microdata structured data

        Returns:
            List of microdata items with properties
        """
        items = []

        # Find all elements with itemscope attribute
        itemscope_elements = soup.find_all(attrs={'itemscope': True})

        for element in itemscope_elements:
            item_data = {
                'type': element.get('itemtype', ''),
                'properties': {},
            }

            # Extract properties
            props = element.find_all(attrs={'itemprop': True})
            for prop in props:
                prop_name = prop.get('itemprop')
                prop_value = self._extract_microdata_value(prop)

                if prop_name:
                    if prop_name not in item_data['properties']:
                        item_data['properties'][prop_name] = []
                    item_data['properties'][prop_name].append(prop_value)

            items.append(item_data)

        return items

    def _extract_microdata_value(self, element) -> str:
        """Extract value from microdata property"""
        # Check for itemscope (nested item)
        if element.has_attr('itemscope'):
            return element.get('itemtype', 'nested item')

        # Meta tag
        if element.name == 'meta':
            return element.get('content', '')

        # Link/a tag
        if element.name in ['link', 'a']:
            return element.get('href', '')

        # Img tag
        if element.name == 'img':
            return element.get('src', '')

        # Time tag
        if element.name == 'time':
            return element.get('datetime', element.get_text().strip())

        # Default: text content
        return element.get_text().strip()

    def extract_rdfa(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract RDFa structured data

        Returns:
            List of RDFa items with properties
        """
        items = []

        # Find all elements with typeof attribute (RDFa)
        typeof_elements = soup.find_all(attrs={'typeof': True})

        for element in typeof_elements:
            item_data = {
                'typeof': element.get('typeof', ''),
                'vocab': element.get('vocab', ''),
                'properties': {},
            }

            # Extract properties with 'property' attribute
            props = element.find_all(attrs={'property': True})
            for prop in props:
                prop_name = prop.get('property')
                prop_value = self._extract_rdfa_value(prop)

                if prop_name:
                    if prop_name not in item_data['properties']:
                        item_data['properties'][prop_name] = []
                    item_data['properties'][prop_name].append(prop_value)

            items.append(item_data)

        return items

    def _extract_rdfa_value(self, element) -> str:
        """Extract value from RDFa property"""
        # Check for content attribute
        if element.has_attr('content'):
            return element.get('content', '')

        # Check for resource attribute
        if element.has_attr('resource'):
            return element.get('resource', '')

        # Link/a tag
        if element.name in ['link', 'a'] and element.has_attr('href'):
            return element.get('href', '')

        # Default: text content
        return element.get_text().strip()

    def validate_schema_org(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform basic validation on Schema.org structured data

        Returns:
            - errors: List of validation errors
            - warnings: List of validation warnings
            - has_errors: Boolean
            - has_warnings: Boolean
        """
        errors = []
        warnings = []

        # Validate JSON-LD
        for idx, item in enumerate(structured_data.get('json_ld', [])):
            nodes = list(self._iter_json_ld_nodes(item))
            for node_idx, node in enumerate(nodes):
                if not isinstance(node, dict):
                    continue
                prefix = f"JSON-LD item {idx}" if node_idx == 0 else f"JSON-LD item {idx}.{node_idx}"

                # Check for @context on the root payload only.
                if node_idx == 0 and '@context' not in node:
                    errors.append(f"{prefix}: Missing @context")

                # Check for @type
                if '@type' not in node:
                    errors.append(f"{prefix}: Missing @type")

                # Validate common required fields based on type
                item_type = node.get('@type', '')
                if item_type:
                    if isinstance(item_type, list):
                        item_type = item_type[0] if item_type else ''
                    if item_type:
                        validation_errors = self._validate_schema_type(item_type, node)
                        errors.extend([f"{prefix}: {err}" for err in validation_errors])

        # Validate Microdata
        for idx, item in enumerate(structured_data.get('microdata', [])):
            if not item.get('type'):
                errors.append(f"Microdata item {idx}: Missing itemtype")

        return {
            'errors': errors,
            'warnings': warnings,
            'has_errors': bool(errors),
            'has_warnings': bool(warnings),
        }

    def _validate_schema_type(self, schema_type, data: Dict[str, Any]) -> List[str]:
        """
        Validate required fields for common Schema.org types

        Returns:
            List of error messages
        """
        errors = []
        
        # Ensure schema_type is a string (could be list from JSON-LD)
        if isinstance(schema_type, list):
            schema_type = schema_type[0] if schema_type else ''
        if not isinstance(schema_type, str):
            return errors

        # Define required fields for common types
        required_fields = {
            'Organization': ['name'],
            'Person': ['name'],
            'Article': ['headline', 'author'],
            'BlogPosting': ['headline', 'author'],
            'NewsArticle': ['headline', 'author'],
            'Product': ['name'],
            'Offer': ['price', 'priceCurrency'],
            'Review': ['reviewRating', 'author'],
            'Recipe': ['name', 'recipeIngredient'],
            'Event': ['name', 'startDate', 'location'],
            'LocalBusiness': ['name', 'address'],
            'WebSite': ['name', 'url'],
            'BreadcrumbList': ['itemListElement'],
        }

        if schema_type in required_fields:
            for field in required_fields[schema_type]:
                if field not in data:
                    errors.append(f"Missing required field: {field} for type {schema_type}")

        return errors

    def extract_open_graph(self, html: str) -> Dict[str, Any]:
        """
        Extract Open Graph meta tags

        Returns dict with:
        - og:title, og:description, og:image, og:type, og:url, og:site_name, etc.
        """
        soup = BeautifulSoup(html, 'lxml')
        og_data = {}

        og_tags = soup.find_all('meta', property=re.compile(r'^og:', re.I))

        for tag in og_tags:
            property_name = tag.get('property', '').lower()
            content = tag.get('content', '').strip()

            if property_name and content:
                og_data[property_name] = content

        return og_data

    def extract_twitter_cards(self, html: str) -> Dict[str, Any]:
        """
        Extract Twitter Card meta tags

        Returns dict with:
        - twitter:card, twitter:title, twitter:description, twitter:image, etc.
        """
        soup = BeautifulSoup(html, 'lxml')
        twitter_data = {}

        twitter_tags = soup.find_all('meta', attrs={'name': re.compile(r'^twitter:', re.I)})

        for tag in twitter_tags:
            name = tag.get('name', '').lower()
            content = tag.get('content', '').strip()

            if name and content:
                twitter_data[name] = content

        return twitter_data

    def extract_hreflang(self, html: str, headers: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """
        Extract hreflang tags

        Returns list of dicts with:
        - language: Language code (e.g., 'en', 'es')
        - region: Region code (e.g., 'US', 'MX')
        - url: Target URL
        - source: 'html' or 'http_header'
        """
        soup = BeautifulSoup(html, 'lxml')
        hreflang_data = []
        headers = headers or {}

        # Extract from HTML link tags
        hreflang_links = soup.find_all('link', rel='alternate', hreflang=True)

        for link in hreflang_links:
            hreflang = link.get('hreflang', '').strip().lower()
            href = link.get('href', '').strip()

            if hreflang and href:
                # Parse language and region
                parts = hreflang.split('-')
                language = parts[0] if parts else hreflang
                region = parts[1] if len(parts) > 1 else None

                hreflang_data.append({
                    'hreflang': hreflang,
                    'language': language,
                    'region': region,
                    'url': href,
                    'source': 'html',
                })

        # Extract from HTTP Link header
        link_header = headers.get('link', '')
        if link_header:
            # Parse Link header: <url>; rel="alternate"; hreflang="en-us"
            matches = re.finditer(
                r'<([^>]+)>;\s*rel=["\']?alternate["\']?;\s*hreflang=["\']?([^"\';\s]+)["\']?',
                link_header,
                re.I
            )

            for match in matches:
                url = match.group(1)
                hreflang = match.group(2).strip().lower()

                parts = hreflang.split('-')
                language = parts[0] if parts else hreflang
                region = parts[1] if len(parts) > 1 else None

                hreflang_data.append({
                    'hreflang': hreflang,
                    'language': language,
                    'region': region,
                    'url': url,
                    'source': 'http_header',
                })

        return hreflang_data

    def analyze_hreflang_issues(
        self,
        hreflang_data: List[Dict[str, Any]],
        all_urls: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Analyze hreflang for issues

        Args:
            hreflang_data: List of hreflang tags
            all_urls: Dict mapping URL to status code

        Returns:
            - missing_return_links: URLs without reciprocal hreflang
            - non_200_urls: hreflang URLs with errors
            - duplicate_languages: Languages specified multiple times
            - invalid_codes: Invalid ISO language/region codes
            - missing_x_default: No x-default tag present
        """
        issues = {
            'missing_return_links': [],
            'non_200_urls': [],
            'duplicate_languages': [],
            'invalid_codes': [],
            'missing_x_default': True,
            'missing_self_reference': True,
        }

        # Check for x-default
        for item in hreflang_data:
            if item['hreflang'] == 'x-default':
                issues['missing_x_default'] = False
                break

        # Check for duplicate languages
        seen_languages = {}
        for item in hreflang_data:
            lang = item['hreflang']
            if lang in seen_languages:
                issues['duplicate_languages'].append(lang)
            seen_languages[lang] = item['url']

        # Check for non-200 URLs
        for item in hreflang_data:
            url = item['url']
            status = all_urls.get(url)
            if status and status != 200:
                issues['non_200_urls'].append({
                    'url': url,
                    'status': status,
                    'hreflang': item['hreflang'],
                })

        # Validate language codes (basic check)
        valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'zh', 'ko', 'ar', 'nl', 'pl', 'tr', 'x-default']
        for item in hreflang_data:
            lang = item['language']
            if lang not in valid_languages and lang != 'x':
                issues['invalid_codes'].append(item['hreflang'])

        return issues
