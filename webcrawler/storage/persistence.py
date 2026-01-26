"""
Crawl State Persistence - Save and load crawl state
"""
import json
import pickle
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class CrawlPersistence:
    """Handles saving and loading crawl state"""
    
    def __init__(self, project_name: str, storage_dir: str = "/app/data"):
        self.project_name = project_name
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.state_file = self.storage_dir / f"{project_name}_state.pkl"
        self.metadata_file = self.storage_dir / f"{project_name}_metadata.json"
    
    async def save_state(self, crawler) -> bool:
        """
        Save crawler state to disk
        
        Args:
            crawler: WebCrawler instance
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare state data
            state_data = {
                'url_manager': {
                    'seen_urls': list(crawler.url_manager.seen_urls),
                    'queued_urls': list(crawler.url_manager.queued_urls),
                    'crawled_urls': list(crawler.url_manager.crawled_urls),
                    'queue': list(crawler.url_manager.queue),
                    'url_metadata': crawler.url_manager.url_metadata,
                    'base_url': crawler.url_manager.base_url,
                    'max_depth': crawler.url_manager.max_depth,
                    'max_urls': crawler.url_manager.max_urls
                },
                'results': {
                    url: self._serialize_page_result(result)
                    for url, result in crawler.results.items()
                },
                'redirect_chains': crawler.redirect_chains,
                'stats': crawler.stats,
                'state': crawler.state
            }
            
            # Save state as pickle
            with open(self.state_file, 'wb') as f:
                pickle.dump(state_data, f)
            
            # Save metadata as JSON (human-readable)
            metadata = {
                'project_name': self.project_name,
                'saved_at': datetime.now().isoformat(),
                'start_url': crawler.start_url,
                'pages_crawled': crawler.stats.get('pages_crawled', 0),
                'pages_failed': crawler.stats.get('pages_failed', 0),
                'state': crawler.state
            }
            
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error saving state: {e}")
            return False
    
    async def load_state(self) -> Optional[Dict]:
        """
        Load crawler state from disk
        
        Returns:
            State dictionary if successful, None otherwise
        """
        try:
            if not self.state_file.exists():
                return None
            
            with open(self.state_file, 'rb') as f:
                state_data = pickle.load(f)
            
            return state_data
            
        except Exception as e:
            print(f"Error loading state: {e}")
            return None
    
    def _serialize_page_result(self, result) -> Dict:
        """Convert PageResult to serializable dict"""
        return {
            'url': result.url,
            'status_code': result.status_code,
            'html': result.html,
            'headers': result.headers,
            'redirects': result.redirects,
            'error': result.error,
            'load_time': result.load_time,
            'ttfb': result.ttfb,
            'timestamp': result.timestamp,
            'links': result.links,
            'images': result.images,
            'scripts': result.scripts,
            'stylesheets': result.stylesheets
        }
    
    def get_metadata(self) -> Optional[Dict]:
        """Get saved crawl metadata"""
        try:
            if not self.metadata_file.exists():
                return None
            
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    def delete_state(self) -> bool:
        """Delete saved state files"""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
            if self.metadata_file.exists():
                self.metadata_file.unlink()
            return True
        except Exception:
            return False
    
    @staticmethod
    def list_saved_projects(storage_dir: str = "/app/data") -> list:
        """List all saved crawl projects"""
        storage_path = Path(storage_dir)
        if not storage_path.exists():
            return []
        
        projects = []
        for metadata_file in storage_path.glob("*_metadata.json"):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    projects.append(metadata)
            except Exception:
                continue
        
        return projects
