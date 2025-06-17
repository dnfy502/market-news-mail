#!/usr/bin/env python3
"""
Hash Database Manager - Simple database for tracking processed articles

This module manages a lightweight database that stores hashes of processed articles
to prevent duplicate email alerts when running the RSS processor frequently.
"""

import duckdb
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from pathlib import Path

class HashDatabaseManager:
    """Manages a simple database for tracking processed article hashes"""
    
    def __init__(self, db_path: str = "processed_articles.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        """Initialize the hash tracking database"""
        try:
            with duckdb.connect(self.db_path) as conn:
                # Create processed hashes table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_hashes (
                        content_hash TEXT PRIMARY KEY,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        title TEXT,
                        company_name TEXT,
                        article_link TEXT
                    )
                """)
                
                # Create index for fast lookups
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processed_hash 
                    ON processed_hashes(content_hash)
                """)
                
                # Create index for cleanup operations
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processed_date 
                    ON processed_hashes(processed_at)
                """)
                
                self.logger.info("Hash database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize hash database: {e}")
            raise
    
    def generate_content_hash(self, article: Dict) -> str:
        """Generate a unique hash for an article based on its content"""
        # Use title, summary, and partial link for hash generation
        title = article.get('title', '').strip()
        summary = article.get('summary', '').strip()
        link = article.get('link', '')
        
        # Use first 100 chars of link to handle URL variations
        stable_link = link[:100] if link else ""
        
        # Combine content for hash
        content = f"{title}|{summary}|{stable_link}"
        
        # Generate MD5 hash
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def is_article_processed(self, article: Dict) -> bool:
        """Check if an article has already been processed"""
        content_hash = self.generate_content_hash(article)
        return self.is_hash_processed(content_hash)
    
    def is_hash_processed(self, content_hash: str) -> bool:
        """Check if a specific hash has been processed"""
        try:
            with duckdb.connect(self.db_path) as conn:
                result = conn.execute(
                    "SELECT 1 FROM processed_hashes WHERE content_hash = ? LIMIT 1",
                    [content_hash]
                ).fetchone()
                
                return result is not None
                
        except Exception as e:
            self.logger.error(f"Error checking hash {content_hash}: {e}")
            return False  # On error, assume not processed to avoid missing articles
    
    def get_processed_hashes(self, limit: int = 1000) -> Set[str]:
        """Get a set of recently processed hashes for batch checking"""
        try:
            with duckdb.connect(self.db_path) as conn:
                results = conn.execute(
                    """SELECT content_hash FROM processed_hashes 
                       ORDER BY processed_at DESC LIMIT ?""",
                    [limit]
                ).fetchall()
                
                return {row[0] for row in results}
                
        except Exception as e:
            self.logger.error(f"Error getting processed hashes: {e}")
            return set()
    
    def mark_article_processed(self, article: Dict, company_name: str = None) -> bool:
        """Mark an article as processed"""
        try:
            content_hash = self.generate_content_hash(article)
            
            with duckdb.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO processed_hashes 
                    (content_hash, processed_at, title, company_name, article_link)
                    VALUES (?, ?, ?, ?, ?)
                """, [
                    content_hash,
                    datetime.now(),
                    article.get('title', '')[:200],  # Limit title length
                    company_name or self._extract_company_name(article.get('title', '')),
                    article.get('link', '')
                ])
                
                self.logger.debug(f"Marked article as processed: {content_hash}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error marking article as processed: {e}")
            return False
    
    def mark_articles_processed(self, articles: List[Dict], company_names: Dict[str, str] = None) -> int:
        """Mark multiple articles as processed (batch operation)"""
        if not articles:
            return 0
        
        company_names = company_names or {}
        processed_count = 0
        
        try:
            with duckdb.connect(self.db_path) as conn:
                for article in articles:
                    content_hash = self.generate_content_hash(article)
                    title = article.get('title', '')
                    company_name = company_names.get(title, self._extract_company_name(title))
                    
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO processed_hashes 
                            (content_hash, processed_at, title, company_name, article_link)
                            VALUES (?, ?, ?, ?, ?)
                        """, [
                            content_hash,
                            datetime.now(),
                            title[:200],
                            company_name,
                            article.get('link', '')
                        ])
                        processed_count += 1
                        
                    except Exception as e:
                        self.logger.error(f"Error processing individual article: {e}")
                        continue
                
                self.logger.info(f"Marked {processed_count} articles as processed")
                return processed_count
                
        except Exception as e:
            self.logger.error(f"Error in batch processing articles: {e}")
            return processed_count
    
    def filter_new_articles(self, articles: List[Dict]) -> List[Dict]:
        """Filter out articles that have already been processed"""
        if not articles:
            return []
        
        # Get batch of processed hashes for efficiency
        processed_hashes = self.get_processed_hashes(limit=10000)
        
        new_articles = []
        for article in articles:
            content_hash = self.generate_content_hash(article)
            if content_hash not in processed_hashes:
                new_articles.append(article)
        
        self.logger.info(f"Filtered {len(articles)} articles -> {len(new_articles)} new articles")
        return new_articles
    
    def get_processing_stats(self) -> Dict:
        """Get statistics about processed articles"""
        try:
            with duckdb.connect(self.db_path) as conn:
                # Total processed
                total = conn.execute("SELECT COUNT(*) FROM processed_hashes").fetchone()[0]
                
                # Today's processed
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_count = conn.execute(
                    "SELECT COUNT(*) FROM processed_hashes WHERE processed_at >= ?",
                    [today_start]
                ).fetchone()[0]
                
                # Last 24 hours
                day_ago = datetime.now() - timedelta(days=1)
                last_24h = conn.execute(
                    "SELECT COUNT(*) FROM processed_hashes WHERE processed_at >= ?",
                    [day_ago]
                ).fetchone()[0]
                
                # Most recent
                recent = conn.execute(
                    "SELECT processed_at FROM processed_hashes ORDER BY processed_at DESC LIMIT 1"
                ).fetchone()
                
                last_processed = recent[0] if recent else None
                
                return {
                    'total_processed': total,
                    'today_processed': today_count,
                    'last_24h_processed': last_24h,
                    'last_processed_at': last_processed
                }
                
        except Exception as e:
            self.logger.error(f"Error getting processing stats: {e}")
            return {
                'total_processed': 0,
                'today_processed': 0,
                'last_24h_processed': 0,
                'last_processed_at': None
            }
    
    def cleanup_old_hashes(self, days_to_keep: int = 30) -> int:
        """Remove old processed hashes to keep database size manageable"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with duckdb.connect(self.db_path) as conn:
                result = conn.execute(
                    "DELETE FROM processed_hashes WHERE processed_at < ?",
                    [cutoff_date]
                )
                
                deleted_count = result.fetchone()[0] if result.fetchone() else 0
                
                if deleted_count > 0:
                    self.logger.info(f"Cleaned up {deleted_count} old processed hashes")
                
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old hashes: {e}")
            return 0
    
    def reset_database(self):
        """Reset the database (delete all processed hashes)"""
        try:
            with duckdb.connect(self.db_path) as conn:
                conn.execute("DELETE FROM processed_hashes")
                self.logger.info("Reset hash database - all processed hashes cleared")
                
        except Exception as e:
            self.logger.error(f"Error resetting database: {e}")
            raise
    
    def _extract_company_name(self, title: str) -> str:
        """Extract company name from article title (helper method)"""
        import re
        
        if not title:
            return "Unknown"
        
        cleaned_title = title.strip()
        
        # Company name patterns
        patterns = [
            r'^([^-]+Limited)',
            r'^([^-]+Ltd)',
            r'^([A-Za-z0-9\s&\(\)\.]+?(?:Limited|Ltd))',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, cleaned_title, re.IGNORECASE)
            if match:
                return re.sub(r'\s+', ' ', match.group(1).strip())
        
        # Fallback
        separators = [' has informed', ' informs', '-', '|']
        for sep in separators:
            if sep in cleaned_title:
                potential = cleaned_title.split(sep)[0].strip()
                if len(potential) > 3:
                    return potential
        
        return cleaned_title[:50].strip()

def main():
    """Test the hash database manager"""
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # Test the hash database
    hash_db = HashDatabaseManager("test_hashes.db")
    
    # Test data
    test_articles = [
        {
            'title': 'Test Company Ltd wins major contract',
            'summary': 'Test summary content',
            'link': 'http://example.com/1'
        },
        {
            'title': 'Another Corp bags infrastructure project',
            'summary': 'Another test summary',
            'link': 'http://example.com/2'
        }
    ]
    
    print("Testing hash database...")
    
    # Filter new articles (should return all initially)
    new_articles = hash_db.filter_new_articles(test_articles)
    print(f"New articles: {len(new_articles)}")
    
    # Mark as processed
    hash_db.mark_articles_processed(new_articles)
    
    # Filter again (should return none)
    new_articles = hash_db.filter_new_articles(test_articles)
    print(f"New articles after processing: {len(new_articles)}")
    
    # Get stats
    stats = hash_db.get_processing_stats()
    print(f"Stats: {stats}")
    
    print("Hash database test completed!")

if __name__ == "__main__":
    main() 