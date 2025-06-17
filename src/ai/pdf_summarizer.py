#!/usr/bin/env python3
"""
PDF Summarizer using Gemini API
Sends PDF text to Gemini for summarization without tools or grounding.
"""

import os
import sys
from google import genai
from google.genai import types
from src.ai.pdf_text_extractor import pdf_url_to_text


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
    prompt = f"""Give me a short, one line description of this report. If the company accepted a new order, mention it specifically.

Text content:
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


def main():
    """Main function for command line usage."""
    if len(sys.argv) != 2:
        print("Usage: python pdf_summarizer.py <pdf_url>")
        print("Example: python pdf_summarizer.py https://example.com/document.pdf")
        print("\nMake sure GEMINI_API_KEY is set in your environment")
        sys.exit(1)
    
    url = sys.argv[1]
    
    try:
        print("=" * 60)
        print("PDF SUMMARIZER")
        print("=" * 60)
        
        summary = summarize_pdf_from_url(url)
        
        print("\n" + "=" * 60)
        print("SUMMARY:")
        print("=" * 60)
        print(summary)
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 