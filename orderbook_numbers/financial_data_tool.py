#!/usr/bin/env python3
"""
Financial Data Tool using Gemini 2.5 Flash with Search Grounding
Fetches audited annual revenue, unexecuted orderbook, unaudited and provisional revenue and orderbook
"""

import os
import json
import argparse
from typing import Dict, List, Optional
from google import genai
from google.genai import types
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, will rely on system environment variables
    pass

class FinancialDataTool:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the financial data tool with Gemini API"""
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key not found. Set GEMINI_API_KEY environment variable.")
        
        # Initialize client
        self.client = genai.Client(api_key=self.api_key)
    
    def get_company_financial_data(self, company_name: str, exchange: str = "NSE") -> Dict:
        """
        Get comprehensive financial data for a specific company using two-step approach
        
        Args:
            company_name: Name of the company
            exchange: Stock exchange (NSE, BSE, etc.)
        
        Returns:
            Dictionary containing financial data
        """
        try:
            print(f"🔍 Searching for verified financial data for {company_name}...")
            
            # Step 1: Get grounded research data
            model_id = "models/gemini-2.5-flash-preview-05-20"
            
            # Setup grounding tool
            google_search_tool = Tool(
                google_search=GoogleSearch()
            )
            
            # Create name variations for better search coverage
            company_variations = [company_name]
            
            # Add common variations
            if "Limited" in company_name:
                company_variations.append(company_name.replace(" Limited", ""))
                company_variations.append(company_name.replace(" Limited", " Ltd"))
            if "Ltd" in company_name:
                company_variations.append(company_name.replace(" Ltd", ""))
                company_variations.append(company_name.replace(" Ltd", " Limited"))
            
            # Create a robust search prompt with multiple name variations
            variations_text = " OR ".join([f'"{var}"' for var in company_variations])
            
            research_prompt = f"""Search far and wide for accurate information. Think deeply to solve the following problem:

1) Find data for the audited revenue and order book for the last financial year.
2) Find data for the provisional and unaudited revenue and order book for the current financial year.

Search for the company using any of these name variations: {variations_text}
All these refer to the same company: {company_name}

Return this data in the the following table format:
Fiscal Year	Revenue (₹ crore)	Order Book (₹ crore)	Order Book/Revenue Ratio
FY24	2,369	19,434	8.2x
FY25*	3,300+ 	22,700 	6.8x

Do this exercise for the company: {company_name}

IMPORTANT: After your research, you MUST provide the final answer in the exact table format shown above. Do not stop at just thinking - provide the complete table with the actual data you found."""
            
            # Step 1: Generate grounded response
            research_response = self.client.models.generate_content(
                model=model_id,
                contents=research_prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                    temperature=0.1,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=4096,
                )
            )
            
            # Extract the research text with error handling
            research_text = ""
            try:
                if not research_response.candidates:
                    return {"error": "No candidates received from research step"}
                
                if not research_response.candidates[0].content.parts:
                    return {"error": "No content parts received from research step"}
                
                for part in research_response.candidates[0].content.parts:
                    if part.text:
                        research_text += part.text + "\n"
            except (AttributeError, IndexError) as e:
                return {"error": f"Error extracting research text: {str(e)}"}
            
            if not research_text.strip():
                # Try fallback with shorter company name if available
                fallback_name = None
                if "Limited" in company_name:
                    fallback_name = company_name.replace(" Limited", "")
                elif "Ltd" in company_name:
                    fallback_name = company_name.replace(" Ltd", "")
                
                if fallback_name and fallback_name != company_name:
                    print(f"🔄 Retrying with shorter name: {fallback_name}")
                    
                    # Retry with simpler prompt and shorter name
                    fallback_prompt = f"""Find financial data for {fallback_name}:

1) FY24 audited revenue and order book
2) FY25 provisional revenue and order book

Return in table format:
Fiscal Year | Revenue (₹ crore) | Order Book (₹ crore) | Ratio"""

                    try:
                        fallback_response = self.client.models.generate_content(
                            model=model_id,
                            contents=fallback_prompt,
                            config=types.GenerateContentConfig(
                                tools=[google_search_tool],
                                response_modalities=["TEXT"],
                                temperature=0.1,
                                top_p=0.8,
                                top_k=40,
                                max_output_tokens=4096,
                            )
                        )
                        
                        # Extract fallback research text
                        fallback_research_text = ""
                        if (fallback_response.candidates and 
                            fallback_response.candidates[0].content.parts):
                            for part in fallback_response.candidates[0].content.parts:
                                if part.text:
                                    fallback_research_text += part.text + "\n"
                        
                        if fallback_research_text.strip():
                            research_text = fallback_research_text
                            print(f"✅ Fallback successful with: {fallback_name}")
                        else:
                            return {"error": f"No research data received for both '{company_name}' and fallback '{fallback_name}'"}
                            
                    except Exception as fallback_error:
                        return {"error": f"Primary search failed, fallback also failed: {str(fallback_error)}"}
                else:
                    return {"error": "No research data received from first step"}
            
            # Step 2: Convert to structured JSON using function calling
            conversion_model = "models/gemini-2.0-flash-exp"
            
            # Define function for structured output
            def create_financial_data_function():
                return types.FunctionDeclaration(
                    name="return_financial_data",
                    description="Return financial data in structured JSON format",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "company": types.Schema(
                                type=types.Type.STRING,
                                description="Company name"
                            ),
                            "fy24_revenue": types.Schema(
                                type=types.Type.STRING,
                                description="FY24 audited revenue in crore, use 'N/A' if not available"
                            ),
                            "fy24_order_book": types.Schema(
                                type=types.Type.STRING,
                                description="FY24 audited order book in crore, use 'N/A' if not available"
                            ),
                            "fy24_ratio": types.Schema(
                                type=types.Type.STRING,
                                description="FY24 order book to revenue ratio, use 'N/A' if not available"
                            ),
                            "fy25_revenue": types.Schema(
                                type=types.Type.STRING,
                                description="FY25 provisional revenue in crore, use 'N/A' if not available"
                            ),
                            "fy25_order_book": types.Schema(
                                type=types.Type.STRING,
                                description="FY25 provisional order book in crore, use 'N/A' if not available"
                            ),
                            "fy25_ratio": types.Schema(
                                type=types.Type.STRING,
                                description="FY25 order book to revenue ratio, use 'N/A' if not available"
                            ),
                            "source": types.Schema(
                                type=types.Type.STRING,
                                description="Primary source of the data"
                            )
                        },
                        required=["company", "fy24_revenue", "fy24_order_book", "fy24_ratio", "fy25_revenue", "fy25_order_book", "fy25_ratio"]
                    )
                )
            
            # Create the function tool
            financial_tool = types.Tool(
                function_declarations=[create_financial_data_function()]
            )
            
            # Conversion prompt
            conversion_prompt = f"""Analyze the following research data about {company_name} and extract the financial information.

Research data:
{research_text}

Please call the return_financial_data function with the extracted data:
- Extract FY24 (audited) and FY25 (provisional/unaudited) data
- If any data is not available or not found, use "N/A"
- Keep revenue and order book values as strings (e.g., "2,369", "19,434")
- Calculate ratios as shown (e.g., "8.2x") or use "N/A" if cannot be calculated
- Include the primary source of the data"""
            
            # Step 2: Generate structured response using function calling
            json_response = self.client.models.generate_content(
                model=conversion_model,
                contents=conversion_prompt,
                config=types.GenerateContentConfig(
                    tools=[financial_tool],
                    temperature=0.1,
                    max_output_tokens=2048,
                )
            )
            
            # Extract and parse the function call response with error handling
            try:
                if not json_response.candidates:
                    return {"error": "No candidates received from conversion step", "research_data": research_text}
                
                if not json_response.candidates[0].content.parts:
                    return {"error": "No content parts received from conversion step", "research_data": research_text}
                
                for part in json_response.candidates[0].content.parts:
                    if part.function_call:
                        # Extract function call arguments
                        func_args = part.function_call.args
                        
                        # Convert to the format expected by format_financial_data
                        return {
                            "company_name": func_args.get("company", company_name),
                            "exchange": exchange,
                            "data_timestamp": datetime.now().strftime('%Y-%m-%d %H:%M'),
                            "search_verification": f"Two-step grounding search completed for {company_name}",
                            "audited_data": {
                                "fiscal_year": "FY24",
                                "revenue_crores": func_args.get("fy24_revenue", "N/A"),
                                "orderbook_crores": func_args.get("fy24_order_book", "N/A"),
                                "orderbook_revenue_ratio": func_args.get("fy24_ratio", "N/A"),
                                "source": func_args.get("source", "Grounded search")
                            },
                            "provisional_data": {
                                "fiscal_year": "FY25",
                                "revenue_crores": func_args.get("fy25_revenue", "N/A"),
                                "orderbook_crores": func_args.get("fy25_order_book", "N/A"),
                                "orderbook_revenue_ratio": func_args.get("fy25_ratio", "N/A"),
                                "note": "provisional and unaudited",
                                "source": func_args.get("source", "Grounded search")
                            }
                        }
                
                # Fallback: if no function call, check for text response
                for part in json_response.candidates[0].content.parts:
                    if part.text:
                        return {
                            "error": "Expected function call but got text response",
                            "raw_response": part.text.strip(),
                            "research_data": research_text
                        }
                
                return {"error": "No function call received from conversion step", "research_data": research_text}
                
            except (AttributeError, IndexError) as e:
                return {"error": f"Error extracting function call response: {str(e)}", "research_data": research_text}
                
        except Exception as e:
            return {"error": f"Failed to fetch data for {company_name}: {str(e)}"}
    
    def _parse_response(self, response_text: str, company_name: str) -> Dict:
        """Parse the Gemini response and extract financial data"""
        try:
            # Try to extract JSON from the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_text = response_text[json_start:json_end]
                data = json.loads(json_text)
                
                # Add verification info to output
                if "search_verification" in data:
                    print(f"✅ Sources found: {data['search_verification']}")
                
                return data
            else:
                # If no JSON found, return the raw response
                print("⚠️  Warning: Could not parse structured response")
                return {
                    "company_name": company_name,
                    "raw_response": response_text,
                    "parsed": False
                }
        except json.JSONDecodeError:
            print("⚠️  Warning: Invalid JSON in response")
            return {
                "company_name": company_name,
                "raw_response": response_text,
                "parsed": False,
                "error": "Failed to parse JSON response"
            }
    
    def get_multiple_companies_data(self, companies: List[str], exchange: str = "NSE") -> Dict:
        """Get financial data for multiple companies"""
        results = {}
        for i, company in enumerate(companies, 1):
            print(f"\n📊 [{i}/{len(companies)}] Processing {company}...")
            results[company] = self.get_company_financial_data(company, exchange)
            # Add small delay to avoid rate limiting
            import time
            time.sleep(1)
        return results
    
    def format_financial_data(self, data: Dict) -> str:
        """Format financial data as a summary table"""
        if "error" in data:
            return f"❌ Error: {data['error']}"
        
        if not data.get("parsed", True):
            return f"Raw response for {data['company_name']}:\n{data['raw_response']}"
        
        company_name = data.get('company_name', 'Unknown Company')
        exchange = data.get('exchange', 'N/A')
        
        # Helper function to format numbers with commas
        def format_number(value):
            if value == 'N/A' or value is None:
                return 'N/A'
            try:
                # Try to convert to number and format with commas
                if isinstance(value, str):
                    # Remove any existing commas and + signs for conversion
                    clean_value = value.replace(',', '').replace('+', '')
                    if clean_value.replace('.', '').isdigit():
                        num_value = float(clean_value)
                        formatted = f"{int(num_value):,}" if num_value.is_integer() else f"{num_value:,.1f}"
                        # Add back the + if it was there
                        if '+' in value:
                            formatted += '+'
                        return formatted
                    else:
                        return value  # Return as-is if not a number
                elif isinstance(value, (int, float)):
                    return f"{int(value):,}" if isinstance(value, int) or value.is_integer() else f"{value:,.1f}"
                else:
                    return str(value)
            except (ValueError, TypeError):
                return str(value)
        
        # Create the summary table
        output = []
        output.append(f"\n{company_name} ({exchange}) - Summary Table")
        output.append("=" * 80)
        
        # Add verification info if available
        if verification := data.get('search_verification'):
            output.append(f"✅ Data Sources: {verification}")
        
        output.append("")
        
        # Table header
        output.append("┌─────────────┬─────────────────────┬─────────────────────┬──────────────────────────┐")
        output.append("│ Fiscal Year │ Revenue (₹ crore)   │ Order Book (₹ crore)│ Order Book/Revenue Ratio │")
        output.append("├─────────────┼─────────────────────┼─────────────────────┼──────────────────────────┤")
        
        # Audited data row
        if audited := data.get('audited_data'):
            fy = audited.get('fiscal_year', 'N/A')
            revenue = format_number(audited.get('revenue_crores', 'N/A'))
            orderbook = format_number(audited.get('orderbook_crores', 'N/A'))
            ratio = audited.get('orderbook_revenue_ratio', 'N/A')
            
            output.append(f"│ {fy:<11} │ {revenue:<19} │ {orderbook:<19} │ {ratio:<24} │")
            
            # Add source info
            if source := audited.get('source'):
                output.append(f"│             │ Source: {source:<65} │")
        
        # Provisional data row
        if provisional := data.get('provisional_data'):
            fy = provisional.get('fiscal_year', 'N/A')
            revenue = provisional.get('revenue_crores', 'N/A')
            orderbook = provisional.get('orderbook_crores', 'N/A') 
            ratio = provisional.get('orderbook_revenue_ratio', 'N/A')
            
            # Format numbers and add provisional indicators
            if revenue != 'N/A':
                revenue_formatted = format_number(revenue)
                revenue = f"{revenue_formatted} (prov.)"
            if orderbook != 'N/A':
                orderbook_formatted = format_number(orderbook)
                orderbook = f"{orderbook_formatted} (prov.)"
                
            fy_display = f"{fy}*" if fy != 'N/A' else 'N/A'
            
            output.append(f"│ {fy_display:<11} │ {revenue:<19} │ {orderbook:<19} │ {ratio:<24} │")
            
            # Add source info
            if source := provisional.get('source'):
                output.append(f"│             │ Source: {source:<65} │")
        
        output.append("└─────────────┴─────────────────────┴─────────────────────┴──────────────────────────┘")
        
        # Add footnote for provisional data
        if data.get('provisional_data'):
            note = data['provisional_data'].get('note', 'provisional and unaudited')
            output.append(f"\n*{data.get('provisional_data', {}).get('fiscal_year', 'FY25')} numbers are {note}.")
        
        # Add timestamp
        output.append(f"\nData retrieved: {data.get('data_timestamp', datetime.now().strftime('%Y-%m-%d %H:%M'))}")
        
        return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description='Financial Data Tool using Gemini 2.5 Flash')
    parser.add_argument('companies', nargs='+', help='Company names to analyze')
    parser.add_argument('--exchange', default='NSE', help='Stock exchange (default: NSE)')
    parser.add_argument('--output', choices=['json', 'table'], default='table', 
                       help='Output format (default: table)')
    
    args = parser.parse_args()
    
    try:
        tool = FinancialDataTool()
        
        if len(args.companies) == 1:
            data = tool.get_company_financial_data(args.companies[0], args.exchange)
            if args.output == 'json':
                print(json.dumps(data, indent=2))
            else:
                print(tool.format_financial_data(data))
        else:
            results = tool.get_multiple_companies_data(args.companies, args.exchange)
            if args.output == 'json':
                print(json.dumps(results, indent=2))
            else:
                for company, data in results.items():
                    print(tool.format_financial_data(data))
                    print("\n")
    
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 