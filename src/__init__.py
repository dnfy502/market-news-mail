"""
RSS Awards Processing System

A comprehensive system for monitoring NSE RSS feeds, detecting awards/contracts,
and sending automated email alerts with AI-generated summaries.
"""

__version__ = "2.0.0"
__author__ = "RSS Awards System"

# Make key components easily importable
try:
    from src.core.processor import process_rss_awards, get_email_config_from_env
    from src.core.scheduler import RSSScheduler
    from src.communication.email_sender import EmailSender
    from src.data.rss_fetcher import RSSFetcher
except ImportError:
    # Handle relative imports when package is imported
    pass

__all__ = [
    'process_rss_awards',
    'get_email_config_from_env', 
    'RSSScheduler',
    'EmailSender',
    'RSSFetcher'
] 