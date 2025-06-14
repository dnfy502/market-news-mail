#!/usr/bin/env python3
"""
PDF Text Extractor
Downloads a PDF from a URL and extracts text content.
"""

import requests
import io
from typing import Optional
import PyPDF2
import sys


def download_pdf(url: str) -> Optional[bytes]:
    """
    Download PDF content from a URL.
    
    Args:
        url (str): The URL of the PDF file
        
    Returns:
        Optional[bytes]: PDF content as bytes, or None if download fails
    """
    try:
        print(f"Downloading PDF from: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Check if the content is actually a PDF
        if response.headers.get('content-type', '').lower() not in ['application/pdf', 'application/octet-stream']:
            print(f"Warning: Content type is {response.headers.get('content-type')}, expected PDF")
        
        print(f"Successfully downloaded PDF ({len(response.content)} bytes)")
        return response.content
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading PDF: {e}")
        return None


def extract_text_from_pdf(pdf_content: bytes) -> Optional[str]:
    """
    Extract text content from PDF bytes.
    
    Args:
        pdf_content (bytes): PDF file content as bytes
        
    Returns:
        Optional[str]: Extracted text content, or None if extraction fails
    """
    try:
        print("Extracting text from PDF...")
        
        # Create a file-like object from bytes
        pdf_file = io.BytesIO(pdf_content)
        
        # Create PDF reader object
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        print(f"PDF has {len(pdf_reader.pages)} pages")
        
        # Extract text from all pages
        text_content = ""
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                text_content += f"\n--- Page {page_num + 1} ---\n"
                text_content += page_text
            except Exception as e:
                print(f"Error extracting text from page {page_num + 1}: {e}")
                continue
        
        print(f"Successfully extracted text ({len(text_content)} characters)")
        return text_content.strip()
        
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None


def pdf_url_to_text(url: str) -> Optional[str]:
    """
    Download PDF from URL and extract text content.
    
    Args:
        url (str): The URL of the PDF file
        
    Returns:
        Optional[str]: Extracted text content, or None if process fails
    """
    # Download PDF
    pdf_content = download_pdf(url)
    if pdf_content is None:
        return None
    
    # Extract text
    text_content = extract_text_from_pdf(pdf_content)
    return text_content


def main():
    """Main function for command line usage."""
    if len(sys.argv) != 2:
        print("Usage: python pdf_text_extractor.py <pdf_url>")
        print("Example: python pdf_text_extractor.py https://example.com/document.pdf")
        sys.exit(1)
    
    url = sys.argv[1]
    
    print("=" * 50)
    print("PDF Text Extractor")
    print("=" * 50)
    
    text = pdf_url_to_text(url)
    
    if text:
        print("\n" + "=" * 50)
        print("EXTRACTED TEXT:")
        print("=" * 50)
        print(text)
        print("\n" + "=" * 50)
        print(f"Total characters extracted: {len(text)}")
    else:
        print("Failed to extract text from PDF")
        sys.exit(1)


if __name__ == "__main__":
    main() 