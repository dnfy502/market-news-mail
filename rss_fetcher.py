import feedparser
import requests
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse

from config import RSS_CONFIG, SCHEDULER_CONFIG
from database_manager import DatabaseManager

class RSSFetcher:
    """Modular RSS feed fetcher with database storage"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or DatabaseManager()
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update(RSS_CONFIG["headers"])
    
    def fetch_feed(self, feed_url: str = None, timeout: int = None) -> Optional[feedparser.FeedParserDict]:
        """Fetch and parse RSS feed"""
        url = feed_url or RSS_CONFIG["url"]
        timeout = timeout or RSS_CONFIG["timeout"]
        
        self.logger.info(f"Fetching RSS feed from: {url}")
        
        try:
            response = self.session.get(url, timeout=timeout)
            self.logger.info(f"HTTP Status: {response.status_code}, Content Length: {len(response.content)} bytes")
            
            if response.status_code != 200:
                self.logger.error(f"HTTP {response.status_code} error fetching feed")
                return None
            
            # Parse the RSS feed
            self.logger.info("Parsing RSS feed...")
            start_time = time.time()
            feed = feedparser.parse(response.content)
            parse_time = time.time() - start_time
            self.logger.info(f"Parsing completed in {parse_time:.2f} seconds")
            
            # Check if feed was parsed successfully
            if hasattr(feed, 'bozo') and feed.bozo:
                self.logger.warning(f"Feed parsing issue: {feed.bozo_exception}")
            
            if not hasattr(feed, 'feed') or not hasattr(feed.feed, 'title'):
                self.logger.error("No valid RSS feed found at this URL")
                return None
            
            self.logger.info(f"Feed: {feed.feed.title}, Total entries: {len(feed.entries)}")
            return feed
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error accessing URL: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching feed: {e}")
            return None
    
    def extract_article_data(self, entry: feedparser.FeedParserDict, source_feed: str) -> Dict:
        """Extract and normalize article data from feed entry"""
        return {
            'title': getattr(entry, 'title', 'No title'),
            'link': getattr(entry, 'link', ''),
            'summary': getattr(entry, 'summary', 'No summary'),
            'published': getattr(entry, 'published', 'No date'),
            'guid': getattr(entry, 'guid', getattr(entry, 'id', None)),
            'author': getattr(entry, 'author', None),
            'source_feed': source_feed,
            'tags': [tag.term for tag in getattr(entry, 'tags', [])] if hasattr(entry, 'tags') else []
        }
    
    def process_feed_entries(self, feed: feedparser.FeedParserDict) -> List[Dict]:
        """Process all entries in a feed and return article data"""
        articles = []
        source_feed = getattr(feed.feed, 'title', 'Unknown Feed')
        
        for entry in feed.entries:
            try:
                article_data = self.extract_article_data(entry, source_feed)
                articles.append(article_data)
            except Exception as e:
                self.logger.error(f"Error processing entry {getattr(entry, 'link', 'unknown')}: {e}")
                continue
        
        return articles
    
    def fetch_and_store(self, feed_url: str = None) -> Dict[str, int]:
        """Main method: fetch feed and store articles in database"""
        start_time = time.time()
        
        # Fetch the feed
        feed = self.fetch_feed(feed_url)
        if not feed:
            return {'fetched': 0, 'inserted': 0, 'updated': 0, 'errors': 1}
        
        # Process entries
        articles = self.process_feed_entries(feed)
        if not articles:
            self.logger.warning("No articles found in feed")
            return {'fetched': 0, 'inserted': 0, 'updated': 0, 'errors': 0}
        
        # Store in database
        try:
            inserted, updated = self.db_manager.insert_articles(articles)
            
            total_time = time.time() - start_time
            self.logger.info(
                f"Feed processing completed in {total_time:.2f} seconds: "
                f"{len(articles)} fetched, {inserted} inserted, {updated} updated"
            )
            
            return {
                'fetched': len(articles),
                'inserted': inserted,
                'updated': updated,
                'errors': 0,
                'processing_time': total_time
            }
            
        except Exception as e:
            self.logger.error(f"Error storing articles: {e}")
            return {'fetched': len(articles), 'inserted': 0, 'updated': 0, 'errors': 1}
    
    def fetch_multiple_feeds(self, feed_urls: List[str]) -> Dict[str, Dict[str, int]]:
        """Fetch multiple RSS feeds"""
        results = {}
        
        for url in feed_urls:
            self.logger.info(f"Processing feed: {url}")
            try:
                result = self.fetch_and_store(url)
                results[url] = result
            except Exception as e:
                self.logger.error(f"Failed to process feed {url}: {e}")
                results[url] = {'fetched': 0, 'inserted': 0, 'updated': 0, 'errors': 1}
        
        # Summary statistics
        total_stats = {
            'total_fetched': sum(r['fetched'] for r in results.values()),
            'total_inserted': sum(r['inserted'] for r in results.values()),
            'total_updated': sum(r['updated'] for r in results.values()),
            'total_errors': sum(r['errors'] for r in results.values()),
            'feeds_processed': len(feed_urls)
        }
        
        self.logger.info(
            f"Multi-feed processing complete: {total_stats['feeds_processed']} feeds, "
            f"{total_stats['total_fetched']} articles fetched, "
            f"{total_stats['total_inserted']} inserted, {total_stats['total_updated']} updated"
        )
        
        results['summary'] = total_stats
        return results

def main():
    """Standalone execution for testing"""
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    fetcher = RSSFetcher()
    result = fetcher.fetch_and_store()
    
    print(f"Fetch completed: {result}")

if __name__ == "__main__":
    main() 