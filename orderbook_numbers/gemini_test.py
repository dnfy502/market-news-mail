#!/usr/bin/env python3
"""
Simple Gemini API test with grounding for financial data
"""

import os
import json
from google import genai
from google.genai import types
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

def test_gemini_grounding():
    """Test Gemini with grounding using the exact prompt that worked"""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ Error: GEMINI_API_KEY environment variable not found")
        print("Get your API key from: https://ai.google.dev/")
        return
    
    # Initialize client
    client = genai.Client(api_key=api_key)
    model_id = "models/gemini-2.5-flash-preview-05-20"
    
    # Setup grounding tool
    google_search_tool = Tool(
        google_search=GoogleSearch()
    )
    
    # The exact prompt that worked
    prompt = """Search far and wide for accurate information. Think deeply to solve the following problem:

1) Find data for the audited revenue and order book for the last financial year.
2) Find data for the provisional and unaudited revenue and order book for the current financial year.

Return this data in the the following table format:
Fiscal Year	Revenue (₹ crore)	Order Book (₹ crore)	Order Book/Revenue Ratio
FY24	2,369	19,434	8.2x
FY25*	3,300+ 	22,700 	6.8x

Do this exercise for the company: Bharat Dynamics Limited

IMPORTANT: After your research, you MUST provide the final answer in the exact table format shown above. Do not stop at just thinking - provide the complete table with the actual data you found."""
    
    print("🔍 Testing Gemini with grounding...")
    print(f"📝 Prompt: {prompt[:100]}...")
    print("⏳ Searching...")
    
    try:
        # Generate response with grounding - removed thinking to get cleaner output
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                response_modalities=["TEXT"],
                temperature=0.1,
                top_p=0.8,
                top_k=40,
                max_output_tokens=4096,  # Increased token limit
            )
        )
        
        # Print the response
        print("\n" + "="*80)
        print("📊 GEMINI RESPONSE:")
        print("="*80)
        
        for part in response.candidates[0].content.parts:
            if part.text:
                print(part.text)
                print()
        
        # Print grounding metadata if available
        try:
            grounding_info = response.candidates[0].grounding_metadata.search_entry_point.rendered_content
            print("\n" + "="*80)
            print("🔗 GROUNDING SOURCES:")
            print("="*80)
            print(grounding_info)
        except (AttributeError, IndexError):
            print("\n⚠️  No grounding metadata available")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def test_different_company():
    """Test with a different company"""
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return
    
    client = genai.Client(api_key=api_key)
    model_id = "models/gemini-2.5-flash-preview-05-20"
    
    google_search_tool = Tool(
        google_search=GoogleSearch()
    )
    
    prompt = """Search far and wide for accurate information. Think deeply to solve the following problem:

1) Find data for the audited revenue and order book for the last financial year.
2) Find data for the provisional and unaudited revenue and order book for the current financial year.

Return this data in the the following table format:
Fiscal Year	Revenue (₹ crore)	Order Book (₹ crore)	Order Book/Revenue Ratio
FY24	2,369	19,434	8.2x
FY25*	3,300+ 	22,700 	6.8x

Do this exercise for the company: Reliance Industries

IMPORTANT: After your research, you MUST provide the final answer in the exact table format shown above. Do not stop at just thinking - provide the complete table with the actual data you found."""
    
    print("\n\n🔍 Testing with Reliance Industries...")
    
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                response_modalities=["TEXT"],
                temperature=0.1,
                top_p=0.8,
                top_k=40,
                max_output_tokens=4096,
            )
        )
        
        print("\n" + "="*80)
        print("📊 RELIANCE INDUSTRIES RESPONSE:")
        print("="*80)
        
        for part in response.candidates[0].content.parts:
            if part.text:
                print(part.text)
                print()
            
    except Exception as e:
        print(f"❌ Error: {e}")

def get_financial_data_json(company_name):
    """Get financial data for a company and return as JSON"""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return {"error": "GEMINI_API_KEY environment variable not found"}
    
    # Initialize client
    client = genai.Client(api_key=api_key)
    model_id = "models/gemini-2.5-flash-preview-05-20"
    
    # Setup grounding tool
    google_search_tool = Tool(
        google_search=GoogleSearch()
    )
    
    # Prompt for JSON output
    prompt = f"""Search far and wide for accurate information. Think deeply to solve the following problem:

1) Find data for the audited revenue and order book for the last financial year.
2) Find data for the provisional and unaudited revenue and order book for the current financial year.

Do this exercise for the company: {company_name}

IMPORTANT: Return your findings as a valid JSON object in this exact format:
{{
  "company": "{company_name}",
  "data": [
    {{
      "fiscal_year": "FY24",
      "revenue_crore": "2369",
      "order_book_crore": "19434",
      "ratio": "8.2x"
    }},
    {{
      "fiscal_year": "FY25*",
      "revenue_crore": "3300+",
      "order_book_crore": "22700",
      "ratio": "6.8x"
    }}
  ]
}}

Replace the example values with the actual data you find. Return the complete JSON object. Do not truncate the response. Make sure the JSON is valid and complete."""
    
    try:
        # Generate response with grounding
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                response_modalities=["TEXT"],
                temperature=0.1,
                top_p=0.8,
                top_k=40,
                max_output_tokens=4096,
            )
        )
        
        # Extract and return JSON from response
        for part in response.candidates[0].content.parts:
            if part.text:
                try:
                    # Clean the response text - remove markdown code blocks
                    text = part.text.strip()
                    
                    # Remove ```json and ``` if present
                    if text.startswith("```json"):
                        text = text[7:]  # Remove ```json
                    elif text.startswith("```"):
                        text = text[3:]  # Remove ```
                    
                    if text.endswith("```"):
                        text = text[:-3]  # Remove closing ```
                    
                    text = text.strip()
                    
                    # Try to parse as JSON
                    json_data = json.loads(text)
                    return json_data
                except json.JSONDecodeError as e:
                    # If not valid JSON, return the raw text for debugging
                    return {
                        "error": f"JSON parsing failed: {str(e)}", 
                        "raw_response": part.text.strip()
                    }
        
        return {"error": "No response received"}
            
    except Exception as e:
        return {"error": f"API call failed: {str(e)}"}

def get_financial_data_two_step(company_name):
    """Two-step approach: 1) Get grounded data, 2) Convert to structured JSON"""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return {"error": "GEMINI_API_KEY environment variable not found"}
    
    # Initialize client
    client = genai.Client(api_key=api_key)
    
    # Step 1: Get grounded research data (same as original test_gemini_grounding)
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
    
    try:
        # Step 1: Generate grounded response
        research_response = client.models.generate_content(
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
                    fallback_response = client.models.generate_content(
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
- Calculate ratios as shown (e.g., "8.2x") or use "N/A" if cannot be calculated"""
        
        # Step 2: Generate structured response using function calling
        json_response = client.models.generate_content(
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
                    
                    # Convert to the desired JSON format
                    json_data = {
                        "company": func_args.get("company", "N/A"),
                        "data": [
                            {
                                "fiscal_year": "FY24",
                                "revenue_crore": func_args.get("fy24_revenue", "N/A"),
                                "order_book_crore": func_args.get("fy24_order_book", "N/A"),
                                "ratio": func_args.get("fy24_ratio", "N/A")
                            },
                            {
                                "fiscal_year": "FY25*",
                                "revenue_crore": func_args.get("fy25_revenue", "N/A"),
                                "order_book_crore": func_args.get("fy25_order_book", "N/A"),
                                "ratio": func_args.get("fy25_ratio", "N/A")
                            }
                        ]
                    }
                    return json_data
            
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
        return {"error": f"Two-step process failed: {str(e)}"}

if __name__ == "__main__":
    print("🚀 Starting Gemini Grounding Test")
    print("Make sure GEMINI_API_KEY is set in your environment")
    print()
    
    # Test with Bharat Dynamics (the working example)
    # success = test_gemini_grounding()
    
    # if success:
    #     # Test with another company
    #     test_different_company()
    
    # print("\n✅ Test complete!") 

    result = get_financial_data_two_step("Solar Industries India")
    print(json.dumps(result, indent=2))