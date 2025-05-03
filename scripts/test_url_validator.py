#!/usr/bin/env python
"""
URL Validator and Resource Enhancement Test Script

This script tests the URL validation and Google Search API integration
for enhancing card resources. It provides a simple CLI to test various
validation and search scenarios.
"""

import os
import sys
import json
import asyncio
import argparse
from typing import Dict, List, Optional, Any

# Add the root directory to path to allow importing from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.url_validator import is_valid_url, search_google, get_valid_resources
from app.services.ai_generator import generate_card_with_ai, get_card_generator_agent

async def test_url_validation(url: str) -> Dict[str, Any]:
    """Test if a specific URL is valid"""
    is_valid = is_valid_url(url)
    return {
        "url": url,
        "is_valid": is_valid,
        "message": "URL is valid and accessible" if is_valid else "URL is invalid or inaccessible"
    }

async def test_google_search(query: str, num_results: int = 3) -> Dict[str, Any]:
    """Test Google Search with a specific query"""
    results = search_google(query, num_results)
    return {
        "query": query,
        "num_results_requested": num_results,
        "num_results_received": len(results),
        "results": results
    }

async def test_resource_enhancement(
    keyword: str, 
    context: Optional[str] = None,
    resources: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """Test resource enhancement with existing and new resources"""
    if resources is None:
        # Use some test resources with mix of valid and invalid URLs
        resources = [
            {"url": "https://example.com/invalid", "title": "Invalid Resource"},
            {"url": "https://www.google.com", "title": "Valid Resource"},
            {"url": "https://non-existent-domain-12345.com", "title": "Another Invalid Resource"}
        ]
    
    valid_resources = get_valid_resources(
        keyword=keyword,
        context=context,
        existing_resources=resources
    )
    
    return {
        "keyword": keyword,
        "context": context,
        "original_resources": resources,
        "enhanced_resources": valid_resources,
        "num_original": len(resources),
        "num_enhanced": len(valid_resources)
    }

async def test_card_generation(keyword: str, context: Optional[str] = None) -> Dict[str, Any]:
    """Test the full card generation process with URL validation"""
    try:
        card_generator = get_card_generator_agent()
        card_data = await card_generator.generate_card(
            keyword=keyword,
            context=context,
            difficulty="intermediate"
        )
        
        # Convert Pydantic model to dict for JSON serialization if needed
        if hasattr(card_data, "dict"):
            card_dict = card_data.dict()
        else:
            card_dict = card_data
            
        return {
            "success": True,
            "keyword": keyword,
            "context": context,
            "card_data": card_dict
        }
    except Exception as e:
        return {
            "success": False,
            "keyword": keyword,
            "context": context,
            "error": str(e)
        }

async def main():
    parser = argparse.ArgumentParser(description="Test URL validation and resource enhancement")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # URL validation test
    validate_parser = subparsers.add_parser("validate", help="Test URL validation")
    validate_parser.add_argument("url", help="URL to validate")
    
    # Google search test
    search_parser = subparsers.add_parser("search", help="Test Google Search API")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--num", type=int, default=3, help="Number of results (default: 3)")
    
    # Resource enhancement test
    enhance_parser = subparsers.add_parser("enhance", help="Test resource enhancement")
    enhance_parser.add_argument("keyword", help="Keyword for enhancement")
    enhance_parser.add_argument("--context", help="Optional context")
    enhance_parser.add_argument("--resources", help="JSON string of resources (array of url/title objects)")
    
    # Card generation test
    generate_parser = subparsers.add_parser("generate", help="Test card generation with validation")
    generate_parser.add_argument("keyword", help="Keyword for card generation")
    generate_parser.add_argument("--context", help="Optional context")
    
    # Batch test
    batch_parser = subparsers.add_parser("batch", help="Batch test with invalid URLs")
    
    args = parser.parse_args()
    
    if args.command == "validate":
        result = await test_url_validation(args.url)
    elif args.command == "search":
        result = await test_google_search(args.query, args.num)
    elif args.command == "enhance":
        resources = None
        if args.resources:
            try:
                resources = json.loads(args.resources)
            except json.JSONDecodeError:
                print("Error: Invalid JSON for resources")
                return
        result = await test_resource_enhancement(args.keyword, args.context, resources)
    elif args.command == "generate":
        result = await test_card_generation(args.keyword, args.context)
    elif args.command == "batch":
        # Test a batch of predefined scenarios
        results = []
        
        # Test 1: Valid URL validation
        results.append(await test_url_validation("https://www.google.com"))
        
        # Test 2: Invalid URL validation
        results.append(await test_url_validation("https://non-existent-domain-12345.com"))
        
        # Test 3: Google Search
        results.append(await test_google_search("Python programming tutorial"))
        
        # Test 4: Resource enhancement with mixed URLs
        resources = [
            {"url": "https://example.com/invalid", "title": "Invalid Resource"},
            {"url": "https://www.google.com", "title": "Valid Resource"},
            {"url": "https://non-existent-domain-12345.com", "title": "Another Invalid Resource"}
        ]
        results.append(await test_resource_enhancement("Python programming", "beginners guide", resources))
        
        # Test 5: Card generation
        results.append(await test_card_generation("Machine Learning", "overview for beginners"))
        
        result = {"batch_results": results}
    else:
        parser.print_help()
        return
    
    # Pretty print the result
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main()) 