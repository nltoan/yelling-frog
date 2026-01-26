"""
Redirect Analysis - Track and analyze redirect chains
"""
from typing import Dict, List, Set, Optional
from collections import defaultdict


class RedirectAnalyzer:
    """Analyzes redirect chains and patterns"""
    
    def __init__(self):
        self.redirect_chains: Dict[str, List[str]] = {}
        self.redirect_types: Dict[str, str] = {}  # URL -> redirect type (301, 302, etc.)
        self.redirect_loops: List[List[str]] = []
        
    def add_redirect_chain(self, start_url: str, chain: List[str], status_codes: List[int]):
        """
        Add a redirect chain
        
        Args:
            start_url: The original URL
            chain: List of URLs in the redirect chain
            status_codes: HTTP status codes for each redirect
        """
        if chain:
            self.redirect_chains[start_url] = chain
            
            # Store redirect types
            for i, url in enumerate(chain[:-1]):
                if i < len(status_codes):
                    status = status_codes[i]
                    if status in [301, 302, 303, 307, 308]:
                        self.redirect_types[url] = str(status)
            
            # Check for loops
            if self._is_redirect_loop(chain):
                self.redirect_loops.append(chain)
    
    def _is_redirect_loop(self, chain: List[str]) -> bool:
        """Check if a redirect chain contains a loop"""
        seen = set()
        for url in chain:
            if url in seen:
                return True
            seen.add(url)
        return False
    
    def get_redirect_chain(self, url: str) -> Optional[List[str]]:
        """Get the redirect chain for a URL"""
        return self.redirect_chains.get(url)
    
    def get_all_redirects(self) -> Dict[str, List[str]]:
        """Get all redirect chains"""
        return self.redirect_chains
    
    def get_redirect_loops(self) -> List[List[str]]:
        """Get all detected redirect loops"""
        return self.redirect_loops
    
    def count_by_type(self) -> Dict[str, int]:
        """Count redirects by type (301, 302, etc.)"""
        counts = defaultdict(int)
        for redirect_type in self.redirect_types.values():
            counts[redirect_type] += 1
        return dict(counts)
    
    def get_long_chains(self, min_length: int = 3) -> List[tuple]:
        """Get redirect chains longer than specified length"""
        long_chains = []
        for start_url, chain in self.redirect_chains.items():
            if len(chain) >= min_length:
                long_chains.append((start_url, chain))
        return long_chains
    
    def get_temporary_redirects(self) -> List[str]:
        """Get URLs with temporary redirects (302, 303, 307)"""
        temp_codes = ['302', '303', '307']
        return [url for url, code in self.redirect_types.items() if code in temp_codes]
    
    def get_permanent_redirects(self) -> List[str]:
        """Get URLs with permanent redirects (301, 308)"""
        perm_codes = ['301', '308']
        return [url for url, code in self.redirect_types.items() if code in perm_codes]
    
    def get_stats(self) -> Dict:
        """Get redirect statistics"""
        return {
            'total_redirects': len(self.redirect_chains),
            'redirect_loops': len(self.redirect_loops),
            'by_type': self.count_by_type(),
            'long_chains': len(self.get_long_chains()),
            'temporary_redirects': len(self.get_temporary_redirects()),
            'permanent_redirects': len(self.get_permanent_redirects())
        }
    
    def generate_report(self) -> str:
        """Generate a human-readable redirect report"""
        stats = self.get_stats()
        
        report = []
        report.append("=" * 60)
        report.append("REDIRECT ANALYSIS REPORT")
        report.append("=" * 60)
        report.append(f"\nTotal Redirects: {stats['total_redirects']}")
        report.append(f"Redirect Loops: {stats['redirect_loops']}")
        report.append(f"Long Chains (3+ hops): {stats['long_chains']}")
        
        report.append("\nRedirects by Type:")
        for rtype, count in stats['by_type'].items():
            redirect_name = {
                '301': 'Permanent (301)',
                '302': 'Temporary (302)',
                '303': 'See Other (303)',
                '307': 'Temporary Redirect (307)',
                '308': 'Permanent Redirect (308)'
            }.get(rtype, f'Unknown ({rtype})')
            report.append(f"   {redirect_name}: {count}")
        
        if self.redirect_loops:
            report.append("\n⚠️  REDIRECT LOOPS DETECTED:")
            for i, loop in enumerate(self.redirect_loops, 1):
                report.append(f"\n   Loop {i}:")
                for url in loop:
                    report.append(f"      → {url}")
        
        long_chains = self.get_long_chains()
        if long_chains:
            report.append(f"\n⚠️  LONG REDIRECT CHAINS ({len(long_chains)}):")
            for start_url, chain in long_chains[:5]:  # Show first 5
                report.append(f"\n   {start_url}")
                for url in chain:
                    report.append(f"      → {url}")
        
        return "\n".join(report)


def detect_redirects_in_database(database, session_id: str) -> Dict[str, any]:
    """
    Detect redirect chains and loops for all URLs in a crawl session

    Args:
        database: Database instance
        session_id: Session ID to analyze

    Returns:
        Dictionary with redirect detection results
    """
    analyzer = RedirectAnalyzer()

    # Get all URLs from database
    urls = database.get_all_urls(session_id)

    # Build redirect mapping
    redirect_map = {}
    for url_data in urls:
        if url_data.redirect_uri and url_data.status_code in [301, 302, 303, 307, 308]:
            redirect_map[url_data.url] = {
                'target': url_data.redirect_uri,
                'status_code': url_data.status_code
            }

    # Build redirect chains
    for start_url in redirect_map.keys():
        chain = [start_url]
        status_codes = []
        current_url = start_url
        visited = set()

        # Follow the redirect chain
        while current_url in redirect_map:
            if current_url in visited:
                # Redirect loop detected
                chain.append(current_url)
                break

            visited.add(current_url)
            redirect_info = redirect_map[current_url]
            next_url = redirect_info['target']
            status_codes.append(redirect_info['status_code'])

            chain.append(next_url)
            current_url = next_url

            # Safety limit to prevent infinite loops
            if len(chain) > 20:
                break

        # Only add if it's actually a redirect chain (more than 1 URL)
        if len(chain) > 1:
            analyzer.add_redirect_chain(start_url, chain, status_codes)

    # Get results
    stats = analyzer.get_stats()
    redirect_loops = analyzer.get_redirect_loops()
    long_chains = analyzer.get_long_chains(min_length=3)

    return {
        'redirect_chains': analyzer.get_all_redirects(),
        'redirect_loops': redirect_loops,
        'long_chains': [{'start': start, 'chain': chain} for start, chain in long_chains],
        'statistics': stats,
        'report': analyzer.generate_report()
    }
