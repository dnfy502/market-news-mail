#!/usr/bin/env python3
"""
RSS Awards Processor - Modular RSS processing for awards/bagging announcements

This module provides clean, reusable functions for processing RSS feeds,
filtering for awards/bagging articles, getting financial data, and sending emails.
Designed to be called from schedulers or other automation systems.
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import existing modules
from src.data.rss_fetcher import RSSFetcher
from src.core.filter_engine import FilterEngine, PresetFilters
from src.communication.email_sender import EmailSender
from src.data.hash_database_manager import HashDatabaseManager

# Import financial data tool (optional)
try:
    from src.ai.financial_data_tool import FinancialDataTool
    FINANCIAL_DATA_AVAILABLE = True
except ImportError:
    FINANCIAL_DATA_AVAILABLE = False

# PDF Summarization imports
try:
    from google import genai
    from google.genai import types
    from src.ai.pdf_text_extractor import pdf_url_to_text
    PDF_SUMMARIZATION_AVAILABLE = True
except ImportError:
    PDF_SUMMARIZATION_AVAILABLE = False

def summarize_text_with_gemini(text: str) -> str:
    """
    Send text to Gemini for summarization.
    
    Args:
        text (str): The text content to summarize
        
    Returns:
        str: Gemini's summary response
    """
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not found")
    
    # Initialize client
    client = genai.Client(api_key=api_key)
    model_id = "models/gemini-2.5-flash-preview-05-20"
    
    # Create the prompt
    prompt = f"""Analyze this NSE company filing about a new order. Provide a brief summary followed by key details.

RESPONSE FORMAT:
First, give a short summary (1-2 sentences) of what this order is about.

Then list available key details:
- Order Value: Rs. [amount] Crores (inclusive/exclusive GST) - if not specified, write "Amount not specified". Avoid words like "approximately".
- Expiry: [date/timeline - only if mentioned]
- Sector: [sector/industry - only if clear]
- Client: [customer name - only if mentioned]
- Details: [very brief gist of order type/scope - keep it short, only if available]

Only include the bullet points for information that is actually present in the document.

If this document is NOT about a new order, simply respond:
"Not a new order announcement - [brief description of what the document contains]"

REQUIREMENTS:
- Use simple text only (no formatting symbols)
- Be concise but include key numbers
- Skip unnecessary legal/regulatory boilerplate
- Focus on business-relevant information
- Keep details section very brief

Document text:
{text}"""
    
    try:
        # Generate response without any tools
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
                temperature=0.1,
                top_p=0.8,
                top_k=40,
                max_output_tokens=2048,  # Increased from 1024 to allow longer summaries
            )
        )
        
        # Extract and return the text response
        for part in response.candidates[0].content.parts:
            if part.text:
                return part.text.strip()
        
        return "No response received from Gemini"
        
    except Exception as e:
        raise Exception(f"Error getting Gemini response: {e}")

def summarize_pdf_from_url(url: str) -> str:
    """
    Download PDF from URL, extract text, and summarize with Gemini.
    
    Args:
        url (str): The URL of the PDF file
        
    Returns:
        str: Gemini's summary of the PDF content
    """
    if not PDF_SUMMARIZATION_AVAILABLE:
        return "PDF summarization not available - missing dependencies"
    
    print(f"Processing PDF from: {url}")
    
    # Extract text from PDF
    text = pdf_url_to_text(url)
    if not text:
        raise Exception("Failed to extract text from PDF")
    
    print(f"Extracted {len(text)} characters from PDF")
    
    # Handle very long texts by truncating to avoid token limits
    # Gemini 2.5 Flash can handle ~1M tokens input, but let's be conservative
    max_chars = 100000  # ~25,000 tokens approximately
    if len(text) > max_chars:
        print(f"⚠️ Text too long ({len(text)} chars), truncating to {max_chars} chars")
        # Try to truncate at a reasonable point (sentence or paragraph break)
        truncated_text = text[:max_chars]
        # Find last complete sentence
        last_period = truncated_text.rfind('.')
        if last_period > max_chars * 0.8:  # If we find a period in the last 20%
            text = truncated_text[:last_period + 1]
        else:
            text = truncated_text
        print(f"Truncated to {len(text)} characters")
    
    print("Sending to Gemini for summarization...")
    
    # Summarize with Gemini with retry logic
    max_retries = 2
    for attempt in range(max_retries):
        try:
            summary = summarize_text_with_gemini(text)
            
            # Check if summary seems complete (not truncated)
            if len(summary) < 50:
                print(f"⚠️ Summary seems too short ({len(summary)} chars), might be incomplete")
            
            return summary
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise Exception(f"Failed to get Gemini summary after {max_retries} attempts: {e}")
            else:
                print("Retrying...")
                import time
                time.sleep(2)  # Wait 2 seconds before retry

class RSSAwardsProcessor:
    """Clean, modular RSS processor for awards/bagging announcements"""
    
    def __init__(self, 
                 email_config: Dict[str, str],
                 hash_db_path: str = "processed_articles.db",
                 max_financial_requests: int = 10):
        """
        Initialize the RSS Awards Processor
        
        Args:
            email_config: Dictionary with email configuration
            hash_db_path: Path to hash database file
            max_financial_requests: Maximum financial data API calls per run
        """
        self.logger = self._setup_logging()
        
        # Initialize components
        self.hash_db = HashDatabaseManager(hash_db_path)
        self.rss_fetcher = RSSFetcher()  # Uses default database
        self.filter_engine = FilterEngine()
        self.email_sender = EmailSender(email_config["provider"])
        
        # Configuration
        self.email_config = email_config
        self.max_financial_requests = max_financial_requests
        
        # Initialize financial tool if available
        self.financial_tool = None
        if FINANCIAL_DATA_AVAILABLE and os.getenv('GEMINI_API_KEY'):
            try:
                self.financial_tool = FinancialDataTool()
                self.logger.info("✅ Financial data tool initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize financial tool: {e}")
        else:
            self.logger.info("📊 Financial data tool not available")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the processor"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def fetch_rss_articles(self) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Fetch fresh RSS articles
        
        Returns:
            Tuple of (articles_list, fetch_stats)
        """
        self.logger.info("🔄 Fetching RSS articles...")
        
        try:
            # Fetch and store in RSS database with improved error handling
            fetch_stats = self.rss_fetcher.fetch_and_store()
            
            # Log errors but don't fail the entire process
            if fetch_stats.get('errors', 0) > 0:
                self.logger.warning(f"RSS fetch completed with {fetch_stats['errors']} errors (likely duplicates)")
            
            # Get articles from RSS database (we'll filter against hash DB separately)
            from src.data.database_manager import DatabaseManager
            db_manager = DatabaseManager()
            
            # Get recent articles (last few hours to ensure we catch everything)
            articles = db_manager.search_articles(limit=1000)
            
            self.logger.info(
                f"RSS fetch completed: {fetch_stats['fetched']} fetched, "
                f"{fetch_stats['inserted']} new, retrieved {len(articles)} articles"
            )
            
            return articles, fetch_stats
            
        except Exception as e:
            self.logger.error(f"Error fetching RSS articles: {e}")
            # Return empty results but don't fail completely
            return [], {'fetched': 0, 'inserted': 0, 'updated': 0, 'errors': 1}
    
    def filter_awards_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Filter articles for awards/bagging announcements
        
        Args:
            articles: List of articles to filter
            
        Returns:
            List of articles matching awards/bagging criteria
        """
        self.logger.info("🎯 Filtering for awards/bagging...")
        
        if not articles:
            self.logger.info("No articles to filter")
            return []
        
        try:
            # Apply awards/bagging filter
            awards_filter = PresetFilters.awards_bagging_filter()
            filtered_articles = self.filter_engine.apply_rule(articles, awards_filter)
            
            self.logger.info(f"Found {len(filtered_articles)} articles matching awards/bagging criteria")
            return filtered_articles
            
        except Exception as e:
            self.logger.error(f"Error filtering articles: {e}")
            return []
    
    def get_new_articles_only(self, articles: List[Dict]) -> List[Dict]:
        """
        Filter out articles that have already been processed
        
        Args:
            articles: List of articles to check
            
        Returns:
            List of articles that haven't been processed before
        """
        self.logger.info("🔍 Checking for new articles...")
        
        try:
            new_articles = self.hash_db.filter_new_articles(articles)
            self.logger.info(f"Found {len(new_articles)} new articles (not previously processed)")
            return new_articles
            
        except Exception as e:
            self.logger.error(f"Error checking for new articles: {e}")
            return articles  # On error, return all to avoid missing articles
    
    def extract_company_name(self, title: str) -> str:
        """Extract company name from article title"""
        if not title:
            return "Unknown Company"
        
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
        
        # Fallback: extract before separators
        separators = [' has informed', ' informs', '-', '|']
        for sep in separators:
            if sep in cleaned_title:
                potential = cleaned_title.split(sep)[0].strip()
                if len(potential) > 3:
                    return potential
        
        return cleaned_title[:50].strip()
    
    def get_financial_data(self, articles: List[Dict]) -> Dict[str, Dict]:
        """
        Get financial data for companies in articles
        
        Args:
            articles: List of articles to get financial data for
            
        Returns:
            Dictionary mapping company names to financial data
        """
        if not self.financial_tool or not articles:
            self.logger.info("📊 Skipping financial data (not available or no articles)")
            return {}
        
        self.logger.info("💰 Getting financial data...")
        
        financial_data = {}
        processed_count = 0
        
        for article in articles:
            if processed_count >= self.max_financial_requests:
                self.logger.info(f"Reached max financial requests limit ({self.max_financial_requests})")
                break
            
            try:
                company_name = self.extract_company_name(article['title'])
                
                # Skip if already processed this company
                if company_name in financial_data:
                    continue
                
                self.logger.info(f"📈 Getting financial data for: {company_name}")
                
                # Get financial data with retry logic
                data = None
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        data = self.financial_tool.get_company_financial_data(company_name)
                        
                        if "error" not in data:
                            financial_data[company_name] = data
                            self.logger.info(f"✅ Financial data retrieved for {company_name}")
                            break
                        else:
                            if attempt < max_retries - 1:
                                self.logger.warning(f"⚠️ Attempt {attempt + 1} failed for {company_name}, retrying...")
                                import time
                                time.sleep(2)  # Wait 2 seconds before retry
                            else:
                                self.logger.warning(f"⚠️ Could not get financial data for {company_name} after {max_retries} attempts")
                                financial_data[company_name] = {"error": data["error"]}
                                
                    except Exception as e:
                        if attempt < max_retries - 1:
                            self.logger.warning(f"⚠️ Exception on attempt {attempt + 1} for {company_name}: {e}, retrying...")
                            import time
                            time.sleep(2)
                        else:
                            self.logger.warning(f"⚠️ Could not get financial data for {company_name} after {max_retries} attempts: {e}")
                            financial_data[company_name] = {"error": str(e)}
                
                processed_count += 1
                
            except Exception as e:
                self.logger.error(f"Error getting financial data for {article.get('title', 'unknown')}: {e}")
                continue
        
        success_count = len([k for k, v in financial_data.items() if 'error' not in v])
        self.logger.info(f"Financial data retrieved for {success_count}/{len(financial_data)} companies")
        
        return financial_data
    
    def create_simple_email_content(self, articles: List[Dict], financial_data: Dict[str, Dict]) -> Tuple[str, str]:
        """
        Create rich HTML email content with financial data tables
        
        Args:
            articles: List of new articles
            financial_data: Financial data for companies
            
        Returns:
            Tuple of (subject, html_body)
        """
        now = datetime.now()
        
        # Rich subject
        if len(articles) == 1:
            subject = f"[Market News] Update: {self.extract_company_name(articles[0]['title'])}"
        else:
            subject = f"[Market News] Update: {len(articles)} companies"
        
        # HTML Email Body
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 20px; border: 1px solid #ddd; }}
        .article {{ border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 5px; }}
        .article-title {{ color: #2c3e50; font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
        .article-meta {{ color: #333 !important; font-size: 13px; margin-bottom: 10px; }}
        .article-summary {{ margin-bottom: 15px; color: #333; }}
        .financial-data {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 15px; }}
        .financial-data h4 {{ color: #333 !important; }}
        .stats {{ background-color: #e8f5e8; padding: 20px; border-radius: 5px; margin-bottom: 20px; border: 1px solid #ddd; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; color: #333; }}
        th {{ background-color: #f2f2f2; font-weight: bold; }}
        .link-button {{ display: inline-block; padding: 8px 16px; background-color: #3498db; color: white !important; text-decoration: none; border-radius: 3px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #333; font-size: 12px; }}
        .no-articles {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; }}
        p, div, span {{ color: #333; }}
        h1, h2, h3, h4 {{ color: #2c3e50; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>RSS Awards/Bagging Alert</h1>
        <ul>
            <li><strong>Generated:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')}</li>
            <li><strong>New Articles Found:</strong> {len(articles)}</li>
        </ul>
    </div>
"""

        if not articles:
            html_body += """
    <div class="no-articles">
        <h3>No new awards/bagging articles found</h3>
        <p>No new articles matching awards/bagging criteria were detected since the last check.</p>
    </div>
"""
        else:
            html_body += f"""
    <div class="stats">
        <h2>Summary</h2>
        <ul>
            <li><strong>New Articles:</strong> {len(articles)}</li>
            <li><strong>Companies with Financial Data:</strong> {len([k for k, v in financial_data.items() if 'error' not in v])}</li>
            <li><strong>Financial Data Errors:</strong> {len([k for k, v in financial_data.items() if 'error' in v])}</li>
        </ul>
    </div>

    <h2>New Awards/Bagging Articles</h2>
"""
            
            for i, article in enumerate(articles, 1):
                company_name = self.extract_company_name(article['title'])
                
                html_body += f"""
    <div class="article">
        <div class="article-title">{i}. {article['title']}</div>
        <div class="article-meta">
            Published: {article.get('published', 'Unknown date')} | 
            Company: {company_name}
        </div>
        <div class="article-summary">
            <strong>Summary:</strong> {self._get_enhanced_summary(article)}
        </div>
        <a href="{article.get('link', '#')}" class="link-button">Read Full Article</a>
"""
                
                # Add financial data if available
                if company_name in financial_data:
                    fin_data = financial_data[company_name]
                    if "error" not in fin_data:
                        html_body += f"""
        <div class="financial-data">
            <h4>Financial Data for {company_name}</h4>
            <table>
                <tr><th>Fiscal Year</th><th>Revenue (Rs. crore)</th><th>Order Book (Rs. crore)</th><th>OB/Revenue Ratio</th></tr>
"""
                        
                        # Add audited data
                        if fin_data.get('audited_data'):
                            aud = fin_data['audited_data']
                            html_body += f"""
                <tr>
                    <td>{aud.get('fiscal_year', 'N/A')}</td>
                    <td>{aud.get('revenue_crores', 'N/A')}</td>
                    <td>{aud.get('orderbook_crores', 'N/A')}</td>
                    <td>{aud.get('orderbook_revenue_ratio', 'N/A')}</td>
                </tr>
"""
                        
                        # Add provisional data
                        if fin_data.get('provisional_data'):
                            prov = fin_data['provisional_data']
                            html_body += f"""
                <tr>
                    <td>{prov.get('fiscal_year', 'N/A')}*</td>
                    <td>{prov.get('revenue_crores', 'N/A')}</td>
                    <td>{prov.get('orderbook_crores', 'N/A')}</td>
                    <td>{prov.get('orderbook_revenue_ratio', 'N/A')}</td>
                </tr>
"""
                        
                        html_body += "</table>"
                        if fin_data.get('provisional_data'):
                            html_body += "<p><small>*Provisional and unaudited data</small></p>"
                        html_body += "</div>"
                    else:
                        html_body += f"""
        <div class="financial-data">
            <p><strong>Financial Data:</strong> ⚠️ {fin_data.get('error', 'Unknown error')}</p>
        </div>
"""
                
                html_body += "</div>"

        html_body += """
    <div class="footer">
        <p>This alert was generated automatically by RSS Awards Processor.</p>
        <p>Running every 15 minutes to detect new awards/bagging announcements.</p>
        <p>Only new articles (not previously processed) are included in this alert.</p>
    </div>
</body>
</html>
"""
        
        return subject, html_body
    
    def send_email_alert(self, articles: List[Dict], financial_data: Dict[str, Dict]) -> bool:
        """
        Send email alert for new articles
        
        Args:
            articles: List of new articles  
            financial_data: Financial data for companies
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not articles:
            self.logger.info("📧 No new articles to email")
            return True  # Consider this success
        
        self.logger.info(f"📧 Sending email alert for {len(articles)} new articles...")
        
        try:
            # Create email content
            subject, html_body = self.create_simple_email_content(articles, financial_data)
            
            # Send email
            success = self.email_sender.send_email(
                sender_email=self.email_config["sender_email"],
                sender_password=self.email_config["sender_password"],
                recipient_email=self.email_config["recipient_email"],
                subject=subject,
                body=html_body,
                is_html=True  # HTML email
            )
            
            if success:
                self.logger.info(f"✅ Email sent to {self.email_config['recipient_email']}")
            else:
                self.logger.error("❌ Failed to send email")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending email: {e}")
            return False
    
    def mark_articles_processed(self, articles: List[Dict]) -> bool:
        """
        Mark articles as processed in hash database
        
        Args:
            articles: List of articles to mark as processed
            
        Returns:
            True if successful, False otherwise
        """
        if not articles:
            return True
        
        self.logger.info(f"📝 Marking {len(articles)} articles as processed...")
        
        try:
            # Create company name mapping
            company_names = {}
            for article in articles:
                title = article.get('title', '')
                company_names[title] = self.extract_company_name(title)
            
            # Mark as processed
            processed_count = self.hash_db.mark_articles_processed(articles, company_names)
            
            if processed_count == len(articles):
                self.logger.info(f"✅ Successfully marked {processed_count} articles as processed")
                return True
            else:
                self.logger.warning(f"⚠️ Only marked {processed_count}/{len(articles)} articles as processed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error marking articles as processed: {e}")
            return False
    
    def get_processing_stats(self) -> Dict:
        """Get processing statistics from hash database"""
        try:
            return self.hash_db.get_processing_stats()
        except Exception as e:
            self.logger.error(f"Error getting processing stats: {e}")
            return {}
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old processed hashes"""
        try:
            return self.hash_db.cleanup_old_hashes(days_to_keep)
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            return 0
    
    def _get_enhanced_summary(self, article: Dict) -> str:
        """
        Get enhanced summary using Gemini for PDFs or fallback to RSS summary
        
        Args:
            article: Article dictionary with title, link, summary, etc.
            
        Returns:
            Enhanced summary string
        """
        try:
            # Check if article link points to a PDF
            article_link = article.get('link', '')
            if article_link and (article_link.lower().endswith('.pdf') or 'pdf' in article_link.lower()):
                self.logger.info(f"📄 Found PDF link, generating Gemini summary: {article_link}")
                
                try:
                    # Use Gemini to summarize the PDF
                    gemini_summary = summarize_pdf_from_url(article_link)
                    self.logger.info(f"✅ Gemini summary generated ({len(gemini_summary)} chars): {gemini_summary[:100]}...")
                    
                    # Check if summary seems truncated
                    if len(gemini_summary) < 100:
                        self.logger.warning(f"⚠️ Summary seems very short, might be incomplete: '{gemini_summary}'")
                    
                    # Convert newlines to HTML breaks for proper email formatting
                    formatted_summary = gemini_summary.replace('\n', '<br>')
                    return formatted_summary
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to generate Gemini summary for PDF: {e}")
                    # Fallback to RSS summary
                    return article.get('summary', 'No summary available')
            else:
                # No PDF link, use original RSS summary
                return article.get('summary', 'No summary available')
                
        except Exception as e:
            self.logger.error(f"Error getting enhanced summary: {e}")
            return article.get('summary', 'No summary available')

def process_rss_awards(email_config: Dict[str, str], 
                      hash_db_path: str = "processed_articles.db",
                      max_financial_requests: int = 10) -> Dict:
    """
    Main function to process RSS feeds for new awards/bagging articles
    
    This is the main entry point that can be called from schedulers.
    
    Args:
        email_config: Email configuration dictionary
        hash_db_path: Path to hash database
        max_financial_requests: Max financial API calls per run
        
    Returns:
        Dictionary with processing results
    """
    start_time = datetime.now()
    
    # Initialize processor
    processor = RSSAwardsProcessor(email_config, hash_db_path, max_financial_requests)
    
    results = {
        "start_time": start_time,
        "success": False,
        "new_articles_count": 0,
        "email_sent": False,
        "financial_data_count": 0,
        "errors": [],
        "warnings": []
    }
    
    try:
        # Step 1: Fetch RSS articles
        processor.logger.info("🚀 Starting RSS awards processing...")
        all_articles, fetch_stats = processor.fetch_rss_articles()
        
        # Handle database errors as warnings, not failures
        if fetch_stats.get('errors', 0) > 0:
            warning_msg = f"RSS database had {fetch_stats['errors']} insertion errors (likely duplicates)"
            results["warnings"].append(warning_msg)
            processor.logger.warning(warning_msg)
        
        # Step 2: Filter for awards/bagging
        filtered_articles = processor.filter_awards_articles(all_articles)
        
        # Step 3: Get only new articles (not previously processed)
        new_articles = processor.get_new_articles_only(filtered_articles)
        results["new_articles_count"] = len(new_articles)
        
        if not new_articles:
            processor.logger.info("✅ No new awards/bagging articles found")
            results["success"] = True
            results["end_time"] = datetime.now()
            results["processing_time"] = (results["end_time"] - start_time).total_seconds()
            return results
        
        # Step 4: Get financial data for new articles
        financial_data = processor.get_financial_data(new_articles)
        results["financial_data_count"] = len([k for k, v in financial_data.items() if 'error' not in v])
        
        # Step 5: Send email alert
        email_sent = processor.send_email_alert(new_articles, financial_data)
        results["email_sent"] = email_sent
        
        if not email_sent:
            results["errors"].append("Failed to send email")
        
        # Step 6: Mark articles as processed (only if email was sent successfully)
        if email_sent:
            processed_successfully = processor.mark_articles_processed(new_articles)
            if not processed_successfully:
                results["warnings"].append("Failed to mark some articles as processed")
        
        # Final results
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        results.update({
            "end_time": end_time,
            "processing_time": processing_time,
            "success": len(results["errors"]) == 0  # Warnings don't count as failures
        })
        
        processor.logger.info("🎉 RSS awards processing completed!")
        processor.logger.info(f"⏱️ Processing time: {processing_time:.2f}s")
        processor.logger.info(f"📊 New articles: {len(new_articles)}")
        processor.logger.info(f"💰 Financial data: {results['financial_data_count']}")
        processor.logger.info(f"📧 Email sent: {'Yes' if email_sent else 'No'}")
        
        if results["warnings"]:
            processor.logger.info(f"⚠️ Warnings: {len(results['warnings'])}")
        
        return results
        
    except Exception as e:
        processor.logger.error(f"❌ Critical error in processing: {e}")
        results["errors"].append(f"Critical error: {str(e)}")
        results["success"] = False
        results["end_time"] = datetime.now()
        results["processing_time"] = (results["end_time"] - start_time).total_seconds()
        return results

def get_email_config_from_env() -> Dict[str, str]:
    """
    Load email configuration from environment variables
    
    Returns:
        Dictionary with email configuration
        
    Raises:
        ValueError: If required environment variables are missing
    """
    email_config = {
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"), 
        "recipient_email": os.getenv("RECIPIENT_EMAIL"),
        "provider": os.getenv("EMAIL_PROVIDER", "gmail")
    }
    
    # Validate that required environment variables are set
    required_vars = ["SENDER_EMAIL", "SENDER_PASSWORD", "RECIPIENT_EMAIL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}. Please check your .env file.")
    
    return email_config

def main():
    """Test the RSS awards processor"""
    try:
        # Load configuration from environment variables
        email_config = get_email_config_from_env()
    except ValueError as e:
        print(f"❌ Error: {e}")
        return
    
    print("🧪 Testing RSS Awards Processor...")
    print("=" * 50)
    
    # Run the processor
    results = process_rss_awards(email_config)
    
    # Display results
    print(f"Success: {'✅' if results['success'] else '❌'}")
    print(f"New articles: {results['new_articles_count']}")
    print(f"Financial data: {results['financial_data_count']}")
    print(f"Email sent: {'✅' if results['email_sent'] else '❌'}")
    print(f"Processing time: {results.get('processing_time', 0):.2f}s")
    
    if results['errors']:
        print("\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")
    
    if results['warnings']:
        print("\nWarnings:")
        for warning in results['warnings']:
            print(f"  - {warning}")
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    main() 