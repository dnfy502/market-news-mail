import os
from pathlib import Path

# Database Configuration
DATABASE_PATH = "rss_articles.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# RSS Feed Configuration
RSS_CONFIG = {
    "url": "http://nsearchives.nseindia.com/content/RSS/Online_announcements.xml",
    "timeout": 30,
    "headers": {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
}

# Scheduler Configuration
SCHEDULER_CONFIG = {
    "fetch_interval_minutes": 15,  # How often to check for new articles
    "max_workers": 4,  # For concurrent processing
    "batch_size": 1000,  # For batch inserts
}

# Filtering Configuration
DEFAULT_FILTERS = {
    "keywords": ["award", "bagging", "contract"],  # Default keywords for custom filter
    "default_filter": "Awards/Bagging",  # Default preset filter
    "date_range_days": 7,  # Default to last 7 days
    "max_results": 100,
}

# Logging Configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": "rss_system.log",
    "max_bytes": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5,
}

# Streamlit Configuration
STREAMLIT_CONFIG = {
    "page_title": "RSS Article Filter",
    "page_icon": "📰",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

# Paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True) 