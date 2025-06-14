#!/usr/bin/env python3
"""
RSS Awards Processor Scheduler

Runs the RSS awards processor every 15 minutes using APScheduler.
Includes proper error handling, logging, and graceful shutdown.
"""

import logging
import signal
import sys
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the RSS processor
from rss_awards_processor import process_rss_awards, get_email_config_from_env

class RSSScheduler:
    """Scheduler for RSS Awards Processor"""
    
    def __init__(self):
        self.setup_logging()
        self.scheduler = None
        self.email_config = None
        self.running = False
        
    def setup_logging(self):
        """Setup logging for the scheduler"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('scheduler.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self):
        """Load email configuration from environment variables"""
        try:
            self.email_config = get_email_config_from_env()
            self.logger.info("✅ Email configuration loaded successfully")
        except ValueError as e:
            self.logger.error(f"❌ Configuration error: {e}")
            sys.exit(1)
    
    def run_processor(self):
        """Run the RSS awards processor with error handling"""
        job_start_time = datetime.now()
        self.logger.info("🔄 Starting scheduled RSS awards processing...")
        
        try:
            # Run the processor
            results = process_rss_awards(
                email_config=self.email_config,
                hash_db_path="processed_articles.db",
                max_financial_requests=10
            )
            
            # Log results
            if results['success']:
                self.logger.info(f"✅ Processing completed successfully!")
                self.logger.info(f"   📊 New articles: {results['new_articles_count']}")
                self.logger.info(f"   💰 Financial data: {results['financial_data_count']}")
                self.logger.info(f"   📧 Email sent: {'Yes' if results['email_sent'] else 'No'}")
                self.logger.info(f"   ⏱️ Processing time: {results.get('processing_time', 0):.2f}s")
            else:
                self.logger.error(f"❌ Processing failed with errors:")
                for error in results['errors']:
                    self.logger.error(f"   - {error}")
            
            # Log warnings if any
            if results.get('warnings'):
                for warning in results['warnings']:
                    self.logger.warning(f"⚠️ {warning}")
                    
        except Exception as e:
            self.logger.error(f"❌ Unexpected error during processing: {e}")
            
        job_end_time = datetime.now()
        job_duration = (job_end_time - job_start_time).total_seconds()
        self.logger.info(f"🏁 Job completed in {job_duration:.2f}s")
        
    def start(self):
        """Start the scheduler"""
        self.logger.info("🚀 Starting RSS Awards Processor Scheduler")
        self.logger.info("📅 Schedule: Every 15 minutes")
        
        # Load configuration
        self.load_config()
        
        # Configure scheduler
        executors = {
            'default': ThreadPoolExecutor(max_workers=1)  # Only one job at a time
        }
        
        job_defaults = {
            'coalesce': True,  # Combine multiple pending executions into one
            'max_instances': 1,  # Only one instance of the job can run at a time
            'misfire_grace_time': 300  # 5 minutes grace time for missed jobs
        }
        
        self.scheduler = BlockingScheduler(
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'  # Use UTC to avoid timezone issues
        )
        
        # Add the job - every 15 minutes
        self.scheduler.add_job(
            func=self.run_processor,
            trigger=IntervalTrigger(minutes=15),
            id='rss_awards_processor',
            name='RSS Awards Processor',
            replace_existing=True
        )
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            self.running = True
            self.logger.info("✅ Scheduler started successfully")
            self.logger.info("🔄 Running initial check...")
            
            # Run once immediately on startup
            self.run_processor()
            
            self.logger.info("⏰ Scheduler is now running. Press Ctrl+C to stop.")
            
            # Start the scheduler (this will block)
            self.scheduler.start()
            
        except KeyboardInterrupt:
            self.logger.info("🛑 Received interrupt signal")
        except Exception as e:
            self.logger.error(f"❌ Scheduler error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the scheduler gracefully"""
        if self.running and self.scheduler:
            self.logger.info("🛑 Stopping scheduler...")
            self.scheduler.shutdown(wait=True)
            self.running = False
            self.logger.info("✅ Scheduler stopped successfully")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"🛑 Received signal {signum}")
        self.stop()
        sys.exit(0)
    
    def get_status(self):
        """Get scheduler status"""
        if self.scheduler and self.running:
            jobs = self.scheduler.get_jobs()
            return {
                'running': True,
                'jobs_count': len(jobs),
                'next_run': jobs[0].next_run_time if jobs else None
            }
        return {'running': False}

def main():
    """Main function to start the scheduler"""
    print("RSS Awards Processor Scheduler")
    print("=" * 50)
    
    # Check if required packages are installed
    try:
        import apscheduler
    except ImportError:
        print("❌ Error: APScheduler not installed")
        print("Install it with: pip install apscheduler")
        sys.exit(1)
    
    # Create and start scheduler
    scheduler = RSSScheduler()
    
    try:
        scheduler.start()
    except Exception as e:
        print(f"❌ Failed to start scheduler: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 