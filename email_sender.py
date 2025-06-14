#!/usr/bin/env python3
"""
Email Sender Script - A comprehensive guide to sending emails with Python

This script demonstrates how to send emails using Python's built-in smtplib library.
It includes examples for different email providers and security configurations.

Requirements:
- Python 3.6+
- Built-in libraries: smtplib, email, ssl
- For Gmail: App-specific password (not your regular Gmail password)
- For other providers: SMTP settings and authentication
- google-genai library for PDF summarization

Security Notes:
- Never hardcode passwords in your script
- Use environment variables or config files for sensitive data
- Enable 2FA and use app-specific passwords when available
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import os
from typing import List, Optional
import getpass

# PDF Summarization imports
try:
    from google import genai
    from google.genai import types
    from pdf_text_extractor import pdf_url_to_text
    PDF_SUMMARIZATION_AVAILABLE = True
except ImportError:
    PDF_SUMMARIZATION_AVAILABLE = False
    print("⚠️  Warning: PDF summarization requires 'google-genai' and 'pdf_text_extractor' modules")


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
- Order Value: [amount - if not specified, write "Amount not specified"]
- Expiry: [date/timeline - only if mentioned]
- Sector: [sector/industry - only if clear]
- Client: [customer name - only if mentioned]
- Details: [brief description of order type/scope - only if available]

Only include the bullet points for information that is actually present in the document.

If this document is NOT about a new order, simply respond:
"Not a new order announcement - [brief description of what the document contains]"

REQUIREMENTS:
- Use simple text only (no formatting symbols)
- Be concise but include key numbers
- Skip unnecessary legal/regulatory boilerplate
- Focus on business-relevant information

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
                max_output_tokens=1024,
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
    print("Sending to Gemini for summarization...")
    
    # Summarize with Gemini
    summary = summarize_text_with_gemini(text)
    return summary


class EmailSender:
    """
    A class to handle email sending with different SMTP providers
    """
    
    # Common SMTP configurations for popular email providers
    SMTP_CONFIGS = {
        'gmail': {
            'server': 'smtp.gmail.com',
            'port': 587,
            'use_tls': True
        },
        'outlook': {
            'server': 'smtp-mail.outlook.com',
            'port': 587,
            'use_tls': True
        },
        'yahoo': {
            'server': 'smtp.mail.yahoo.com',
            'port': 587,
            'use_tls': True
        },
        'icloud': {
            'server': 'smtp.mail.me.com',
            'port': 587,
            'use_tls': True
        }
    }
    
    def __init__(self, provider: str = 'gmail'):
        """
        Initialize the EmailSender with a specific provider
        
        Args:
            provider (str): Email provider ('gmail', 'outlook', 'yahoo', 'icloud')
        """
        if provider not in self.SMTP_CONFIGS:
            raise ValueError(f"Unsupported provider: {provider}. Supported: {list(self.SMTP_CONFIGS.keys())}")
        
        self.config = self.SMTP_CONFIGS[provider]
        self.provider = provider
        
    def send_company_filter_alert(self,
                                sender_email: str,
                                sender_password: str,
                                recipient_email: str,
                                company_name: str,
                                pdf_url: str,
                                additional_info: str = "") -> bool:
        """
        Send an email alert when a company hits the filter, including PDF summary and clickable button
        
        Args:
            sender_email (str): Sender's email address
            sender_password (str): Sender's password (preferably app-specific password)
            recipient_email (str): Recipient's email address
            company_name (str): Name of the company that hit the filter
            pdf_url (str): URL to the PDF document
            additional_info (str): Additional information about the alert
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Get PDF summary
            print(f"📄 Summarizing PDF for {company_name}...")
            try:
                pdf_summary = summarize_pdf_from_url(pdf_url)
                print(f"✅ PDF summary generated: {pdf_summary[:100]}...")
            except Exception as e:
                print(f"⚠️  Failed to summarize PDF: {e}")
                pdf_summary = "Unable to generate PDF summary - please review the document manually."
            
            # Create email subject
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subject = f"🚨 Filter Alert: {company_name} - {current_time}"
            
            # Create HTML email body
            html_body = f"""
            <html>
                <head>
                    <style>
                        body {{
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                            line-height: 1.6;
                            color: #333;
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 20px;
                        }}
                        .header {{
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            padding: 20px;
                            border-radius: 10px 10px 0 0;
                            text-align: center;
                        }}
                        .content {{
                            background: #f8f9fa;
                            padding: 30px;
                            border-radius: 0 0 10px 10px;
                            border: 1px solid #e9ecef;
                        }}
                        .company-name {{
                            font-size: 24px;
                            font-weight: bold;
                            color: #2c3e50;
                            margin-bottom: 20px;
                        }}
                        .summary-section {{
                            background: white;
                            padding: 20px;
                            border-radius: 8px;
                            margin-bottom: 25px;
                            border-left: 4px solid #007bff;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        }}
                        .summary-title {{
                            font-weight: bold;
                            color: #495057;
                            margin-bottom: 10px;
                            font-size: 16px;
                        }}
                        .summary-text {{
                            color: #6c757d;
                            font-style: italic;
                            line-height: 1.5;
                        }}
                        .button-container {{
                            text-align: center;
                            margin: 25px 0;
                        }}
                        .pdf-button {{
                            display: inline-block;
                            background: linear-gradient(45deg, #28a745, #20c997);
                            color: white;
                            padding: 15px 30px;
                            text-decoration: none;
                            border-radius: 25px;
                            font-weight: bold;
                            font-size: 16px;
                            box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
                            transition: transform 0.2s;
                        }}
                        .pdf-button:hover {{
                            transform: translateY(-2px);
                            box-shadow: 0 6px 20px rgba(40, 167, 69, 0.4);
                        }}
                        .info-section {{
                            background: white;
                            padding: 15px;
                            border-radius: 8px;
                            margin-top: 20px;
                            border: 1px solid #dee2e6;
                        }}
                        .timestamp {{
                            color: #6c757d;
                            font-size: 14px;
                            text-align: center;
                            margin-top: 20px;
                        }}
                        .alert-icon {{
                            font-size: 48px;
                            margin-bottom: 10px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <div class="alert-icon">🚨</div>
                        <h1>Company Filter Alert</h1>
                        <p>A company has triggered your monitoring filter</p>
                    </div>
                    
                    <div class="content">
                        <div class="company-name">
                            📈 {company_name}
                        </div>
                        
                        <div class="summary-section">
                            <div class="summary-title">📄 Document Summary:</div>
                            <div class="summary-text">{pdf_summary}</div>
                        </div>
                        
                        <div class="button-container">
                            <a href="{pdf_url}" class="pdf-button" target="_blank">
                                📄 View Full Document
                            </a>
                        </div>
                        
                        {f'<div class="info-section"><strong>Additional Information:</strong><br>{additional_info}</div>' if additional_info else ''}
                        
                        <div class="timestamp">
                            Alert generated on {current_time}
                        </div>
                    </div>
                </body>
            </html>
            """
            
            # Send the email
            print(f"📧 Sending filter alert email for {company_name}...")
            success = self.send_email(
                sender_email=sender_email,
                sender_password=sender_password,
                recipient_email=recipient_email,
                subject=subject,
                body=html_body,
                is_html=True
            )
            
            if success:
                print(f"✅ Company filter alert sent successfully for {company_name}")
            
            return success
            
        except Exception as e:
            print(f"❌ Error sending company filter alert: {str(e)}")
            return False
        
    def send_email(self, 
                   sender_email: str, 
                   sender_password: str, 
                   recipient_email: str, 
                   subject: str, 
                   body: str, 
                   is_html: bool = False,
                   attachments: Optional[List[str]] = None) -> bool:
        """
        Send an email with optional attachments
        
        Args:
            sender_email (str): Sender's email address
            sender_password (str): Sender's password (preferably app-specific password)
            recipient_email (str): Recipient's email address
            subject (str): Email subject
            body (str): Email body content
            is_html (bool): Whether the body contains HTML content
            attachments (List[str], optional): List of file paths to attach
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = recipient_email
            message["Subject"] = subject
            
            # Add body to email
            if is_html:
                message.attach(MIMEText(body, "html"))
            else:
                message.attach(MIMEText(body, "plain"))
            
            # Add attachments if provided
            if attachments:
                for file_path in attachments:
                    if os.path.isfile(file_path):
                        self._add_attachment(message, file_path)
                    else:
                        print(f"Warning: Attachment file not found: {file_path}")
            
            # Create SMTP session
            server = smtplib.SMTP(self.config['server'], self.config['port'])
            
            if self.config['use_tls']:
                server.starttls()  # Enable TLS encryption
            
            # Login and send email
            server.login(sender_email, sender_password)
            text = message.as_string()
            server.sendmail(sender_email, recipient_email, text)
            server.quit()
            
            print(f"✅ Email sent successfully to {recipient_email}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print("❌ Authentication failed. Check your email and password/app password.")
            return False
        except smtplib.SMTPRecipientsRefused:
            print("❌ Recipient email address was refused.")
            return False
        except smtplib.SMTPServerDisconnected:
            print("❌ SMTP server disconnected unexpectedly.")
            return False
        except Exception as e:
            print(f"❌ An error occurred: {str(e)}")
            return False
    
    def _add_attachment(self, message: MIMEMultipart, file_path: str):
        """
        Add an attachment to the email message
        
        Args:
            message (MIMEMultipart): The email message object
            file_path (str): Path to the file to attach
        """
        with open(file_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {os.path.basename(file_path)}'
        )
        
        message.attach(part)


def send_company_filter_demo():
    """
    Interactive demo function to test the company filter alert email
    """
    print("🚀 Company Filter Alert Email Demo")
    print("=" * 50)
    
    # Get user input
    print("\nSelect your email provider:")
    providers = list(EmailSender.SMTP_CONFIGS.keys())
    for i, provider in enumerate(providers, 1):
        print(f"{i}. {provider.title()}")
    
    while True:
        try:
            choice = int(input(f"\nEnter choice (1-{len(providers)}): ")) - 1
            if 0 <= choice < len(providers):
                provider = providers[choice]
                break
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")
    
    sender_email = input(f"\nEnter your {provider} email address: ")
    
    print(f"\n⚠️  Important: For {provider}, use an app-specific password, not your regular password!")
    if provider == 'gmail':
        print("   📖 To create Gmail app password: https://support.google.com/accounts/answer/185833")
    
    sender_password = getpass.getpass("Enter your password (app-specific password recommended): ")
    
    recipient_email = input("Enter recipient email address (can be same as sender): ")
    
    company_name = input("Enter company name for demo (e.g., 'Tesla Inc.'): ")
    
    pdf_url = input("Enter PDF URL for demo (or press Enter for example): ")
    if not pdf_url:
        pdf_url = "https://example.com/sample-report.pdf"
    
    additional_info = input("Enter additional info (optional): ")
    
    # Send the company filter alert email
    print(f"\n📧 Sending company filter alert for {company_name}...")
    
    email_sender = EmailSender(provider)
    success = email_sender.send_company_filter_alert(
        sender_email=sender_email,
        sender_password=sender_password,
        recipient_email=recipient_email,
        company_name=company_name,
        pdf_url=pdf_url,
        additional_info=additional_info
    )
    
    if success:
        print(f"\n🎉 Success! Company filter alert sent for {company_name}.")
        print(f"Check {recipient_email} for the alert email with PDF summary and clickable button.")
    else:
        print("\n💔 Failed to send company filter alert. Please check your credentials and try again.")


def send_dummy_email():
    """
    Interactive function to send a dummy email
    This function will prompt for credentials and send a test email
    """
    print("🚀 Python Email Sender - Dummy Email Test")
    print("=" * 50)
    
    # Get user input
    print("\nSelect your email provider:")
    providers = list(EmailSender.SMTP_CONFIGS.keys())
    for i, provider in enumerate(providers, 1):
        print(f"{i}. {provider.title()}")
    
    while True:
        try:
            choice = int(input(f"\nEnter choice (1-{len(providers)}): ")) - 1
            if 0 <= choice < len(providers):
                provider = providers[choice]
                break
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")
    
    sender_email = input(f"\nEnter your {provider} email address: ")
    
    print(f"\n⚠️  Important: For {provider}, use an app-specific password, not your regular password!")
    if provider == 'gmail':
        print("   📖 To create Gmail app password: https://support.google.com/accounts/answer/185833")
    
    sender_password = getpass.getpass("Enter your password (app-specific password recommended): ")
    
    recipient_email = input("Enter recipient email address (can be same as sender): ")
    
    # Create email content
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"🐍 Test Email from Python Script - {current_time}"
    
    body = f"""
Hello!

This is a test email sent from a Python script using the smtplib library.

Email Details:
- Sent at: {current_time}
- Provider: {provider.title()}
- Script: email_sender.py

If you're reading this, the email sending functionality is working perfectly! ✅

Best regards,
Python Email Sender Bot 🤖
    """
    
    # Send the email
    print(f"\n📧 Sending email via {provider.title()}...")
    
    email_sender = EmailSender(provider)
    success = email_sender.send_email(
        sender_email=sender_email,
        sender_password=sender_password,
        recipient_email=recipient_email,
        subject=subject,
        body=body
    )
    
    if success:
        print(f"\n🎉 Success! Check {recipient_email} for the test email.")
    else:
        print("\n💔 Failed to send email. Please check your credentials and try again.")


def send_html_email_example():
    """
    Example function showing how to send HTML emails
    """
    # This is an example - you would need to provide actual credentials
    email_sender = EmailSender('gmail')
    
    html_body = """
    <html>
        <body>
            <h2>🌟 HTML Email Test</h2>
            <p>This email contains <b>HTML formatting</b>!</p>
            <ul>
                <li>✅ Bold text</li>
                <li>✅ Lists</li>
                <li>✅ Links: <a href="https://python.org">Python.org</a></li>
            </ul>
            <p style="color: blue;">Styled text in blue!</p>
        </body>
    </html>
    """
    
    # Note: Replace with actual credentials when using
    # success = email_sender.send_email(
    #     sender_email="your-email@gmail.com",
    #     sender_password="your-app-password",
    #     recipient_email="recipient@example.com",
    #     subject="HTML Email Test",
    #     body=html_body,
    #     is_html=True
    # )


def send_email_with_attachment_example():
    """
    Example function showing how to send emails with attachments
    """
    # This is an example - you would need to provide actual credentials
    email_sender = EmailSender('gmail')
    
    # Note: Replace with actual credentials and file paths when using
    # success = email_sender.send_email(
    #     sender_email="your-email@gmail.com",
    #     sender_password="your-app-password",
    #     recipient_email="recipient@example.com",
    #     subject="Email with Attachments",
    #     body="Please find the attached files.",
    #     attachments=["document.pdf", "image.jpg"]
    # )


if __name__ == "__main__":
    """
    Main function - provides options for different email sending modes
    """
    print(__doc__)
    
    try:
        print("\n🚀 Python Email Sender")
        print("=" * 50)
        print("Select mode:")
        print("1. 🚨 Company Filter Alert (with PDF summarization)")
        print("2. 📧 Send Dummy Test Email")
        print("3. ❌ Exit")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-3): ").strip()
                if choice == "1":
                    send_company_filter_demo()
                    break
                elif choice == "2":
                    send_dummy_email()
                    break
                elif choice == "3":
                    print("👋 Goodbye!")
                    break
                else:
                    print("Invalid choice. Please enter 1, 2, or 3.")
            except ValueError:
                print("Please enter a valid option.")
                
    except KeyboardInterrupt:
        print("\n\n👋 Email sending cancelled by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}") 