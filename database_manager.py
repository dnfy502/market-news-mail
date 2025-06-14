import duckdb
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json

from config import DATABASE_PATH, DATA_DIR

@dataclass
class Article:
    """Article data structure"""
    title: str
    link: str
    summary: str
    published: str
    source_feed: str
    content_hash: str
    created_at: datetime
    updated_at: datetime
    guid: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    
class DatabaseManager:
    """High-performance database manager using DuckDB for RSS articles"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DATA_DIR / DATABASE_PATH)
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        """Initialize database with optimized schema"""
        with duckdb.connect(self.db_path) as conn:
            # Create main articles table with optimizations for fast filtering
            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS articles_id_seq;
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY DEFAULT nextval('articles_id_seq'),
                    title TEXT NOT NULL,
                    link TEXT NOT NULL UNIQUE,
                    summary TEXT,
                    published TEXT,
                    published_parsed TIMESTAMP,
                    source_feed TEXT NOT NULL,
                    content_hash TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    guid TEXT,
                    author TEXT,
                    tags TEXT
                )
            """)
            
            # Create indexes for fast filtering
            conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_parsed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_feed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(content_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at)")
            
            # Create filters table for storing user-defined filters
            conn.execute("""
                CREATE TABLE IF NOT EXISTS filters (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    keywords TEXT,  -- JSON array of keywords
                    exclude_keywords TEXT,  -- JSON array of keywords to exclude
                    date_from TIMESTAMP,
                    date_to TIMESTAMP,
                    source_feeds TEXT,  -- JSON array of source feeds
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            self.logger.info("Database initialized successfully")
    
    def _generate_content_hash(self, title: str, summary: str, link: str) -> str:
        """Generate a hash for content deduplication based on stable content"""
        # Use title and summary only for hash to avoid link inconsistencies
        # Add first 100 chars of link if it's a real URL (not internal)
        stable_link = ""
        if link and not link.startswith("internal://"):
            stable_link = link[:100]  # Use partial link to handle URL variations
        
        content = f"{title.strip()}|{summary.strip()}|{stable_link}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats from RSS feeds"""
        if not date_str or date_str == 'No date':
            return None
        
        # Common RSS date formats including NSE format
        formats = [
            "%d-%b-%Y %H:%M:%S",  # NSE format: 06-Jun-2025 07:00:00
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        self.logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def insert_articles(self, articles: List[Dict]) -> Tuple[int, int]:
        """Insert articles efficiently, handling duplicates"""
        if not articles:
            return 0, 0
        
        inserted = 0
        updated = 0
        skipped = 0
        
        with duckdb.connect(self.db_path) as conn:
            for article in articles:
                # Skip articles with missing essential data
                if not article.get('title') and not article.get('summary'):
                    skipped += 1
                    continue
                
                # Generate a unique link if missing
                link = article.get('link', '').strip()
                if not link:
                    # Create a pseudo-link based on title and source
                    title_part = article.get('title', 'no-title')[:50].replace(' ', '-').lower()
                    source_part = article.get('source_feed', 'unknown').replace(' ', '-').lower()
                    link = f"internal://{source_part}/{title_part}/{hash(str(article))}"
                
                content_hash = self._generate_content_hash(
                    article.get('title', ''),
                    article.get('summary', ''),
                    link
                )
                
                published_parsed = self._parse_date(article.get('published', ''))
                
                try:
                    # Check if article already exists
                    existing = conn.execute(
                        "SELECT id FROM articles WHERE content_hash = ?", 
                        [content_hash]
                    ).fetchone()
                    
                    now = datetime.now()
                    
                    if existing:
                        # Update existing article
                        conn.execute("""
                            UPDATE articles SET updated_at = ? WHERE content_hash = ?
                        """, [now, content_hash])
                        updated += 1
                    else:
                        # Insert new article (excluding id to let it auto-increment)
                        conn.execute("""
                            INSERT INTO articles (
                                title, link, summary, published, published_parsed,
                                source_feed, content_hash, guid, author, tags, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [
                            article.get('title', ''),
                            link,
                            article.get('summary', ''),
                            article.get('published', ''),
                            published_parsed,
                            article.get('source_feed', 'unknown'),
                            content_hash,
                            article.get('guid'),
                            article.get('author'),
                            json.dumps(article.get('tags', [])) if article.get('tags') else None,
                            now,
                            now
                        ])
                        inserted += 1
                    
                except Exception as e:
                    # Log constraint violations (duplicates) as debug, other errors as error
                    if "Constraint Error" in str(e) or "unique constraint" in str(e).lower():
                        self.logger.debug(f"Skipping duplicate article {link}: {e}")
                    else:
                        self.logger.error(f"Failed to insert article {link}: {e}")
                    skipped += 1
        
        self.logger.info(f"Processed {len(articles)} articles: {inserted} new, {updated} updated, {skipped} skipped")
        return inserted, updated
    
    def search_articles(self, 
                       keywords: List[str] = None,
                       exclude_keywords: List[str] = None,
                       date_from: datetime = None,
                       date_to: datetime = None,
                       limit: int = 100,
                       offset: int = 0) -> List[Dict]:
        """High-performance article search with multiple filters"""
        
        with duckdb.connect(self.db_path) as conn:
            query_parts = ["SELECT * FROM articles WHERE 1=1"]
            params = []
            
            # Keyword filtering (case-insensitive)
            if keywords:
                keyword_conditions = []
                for keyword in keywords:
                    keyword_conditions.append("(LOWER(title) LIKE ? OR LOWER(summary) LIKE ?)")
                    params.extend([f"%{keyword.lower()}%", f"%{keyword.lower()}%"])
                query_parts.append(f"AND ({' OR '.join(keyword_conditions)})")
            
            # Exclude keywords
            if exclude_keywords:
                for exclude_kw in exclude_keywords:
                    query_parts.append("AND LOWER(title) NOT LIKE ? AND LOWER(summary) NOT LIKE ?")
                    params.extend([f"%{exclude_kw.lower()}%", f"%{exclude_kw.lower()}%"])
            
            # Date range filtering
            if date_from:
                query_parts.append("AND published_parsed >= ?")
                params.append(date_from)
            
            if date_to:
                query_parts.append("AND published_parsed <= ?")
                params.append(date_to)
            
            # Order by most recent first
            query_parts.append("ORDER BY published_parsed DESC, created_at DESC")
            
            # Pagination
            query_parts.append("LIMIT ? OFFSET ?")
            params.extend([limit, offset])
            
            query = " ".join(query_parts)
            
            try:
                result = conn.execute(query, params).fetchall()
                columns = [desc[0] for desc in conn.description]
                
                articles = []
                for row in result:
                    article_dict = dict(zip(columns, row))
                    # Parse tags back from JSON if present
                    if article_dict.get('tags'):
                        try:
                            article_dict['tags'] = json.loads(article_dict['tags'])
                        except json.JSONDecodeError:
                            article_dict['tags'] = []
                    articles.append(article_dict)
                
                return articles
                
            except Exception as e:
                self.logger.error(f"Search failed: {e}")
                return []
    
    def get_article_stats(self) -> Dict:
        """Get database statistics"""
        with duckdb.connect(self.db_path) as conn:
            # Total articles
            total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            
            # Articles in last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE created_at >= ?", 
                [thirty_days_ago]
            ).fetchone()[0]
            
            # Daily activity (last 7 days)
            activity = conn.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count
                FROM articles 
                WHERE created_at >= ?
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """, [datetime.now() - timedelta(days=7)]).fetchall()
            
            return {
                'total_articles': total,
                'recent_articles': recent,
                'daily_activity': dict(activity)
            }
    
    def cleanup_old_articles(self, days_to_keep: int = 90):
        """Remove articles older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with duckdb.connect(self.db_path) as conn:
            deleted = conn.execute(
                "DELETE FROM articles WHERE created_at < ?", 
                [cutoff_date]
            ).rowcount
            
            self.logger.info(f"Cleaned up {deleted} articles older than {days_to_keep} days")
            return deleted
    
    def create_filter(self, name: str, **filter_params) -> int:
        """Create a named filter configuration"""
        with duckdb.connect(self.db_path) as conn:
            filter_id = conn.execute("""
                INSERT INTO filters (name, keywords, exclude_keywords, date_from, date_to, source_feeds)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id
            """, [
                name,
                json.dumps(filter_params.get('keywords', [])),
                json.dumps(filter_params.get('exclude_keywords', [])),
                filter_params.get('date_from'),
                filter_params.get('date_to'),
                json.dumps(filter_params.get('source_feeds', []))
            ]).fetchone()[0]
            
            return filter_id
    
    def get_filters(self) -> List[Dict]:
        """Get all saved filters"""
        with duckdb.connect(self.db_path) as conn:
            filters = conn.execute("""
                SELECT id, name, keywords, exclude_keywords, date_from, date_to, 
                       source_feeds, created_at, is_active
                FROM filters 
                WHERE is_active = TRUE
                ORDER BY created_at DESC
            """).fetchall()
            
            result = []
            for f in filters:
                filter_dict = {
                    'id': f[0],
                    'name': f[1],
                    'keywords': json.loads(f[2]) if f[2] else [],
                    'exclude_keywords': json.loads(f[3]) if f[3] else [],
                    'date_from': f[4],
                    'date_to': f[5],
                    'source_feeds': json.loads(f[6]) if f[6] else [],
                    'created_at': f[7],
                    'is_active': f[8]
                }
                result.append(filter_dict)
            
            return result 