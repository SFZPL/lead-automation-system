#!/usr/bin/env python3

import asyncio
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.web_scraper import WebScraper
from modules.linkedin_enricher import LinkedInEnricher
from config import Config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_web_scraper_search():
    """Test enhanced web scraper search_person_info functionality"""
    print("Testing Enhanced Web Scraper Search")
    print("=" * 50)
    
    config = Config()
    web_scraper = WebScraper(config)
    
    # Test cases with different scenarios
    test_cases = [
        {
            'full_name': 'Elon Musk',
            'company_name': 'Tesla',
            'email': 'elon@tesla.com'
        },
        {
            'full_name': 'Tim Cook',
            'company_name': 'Apple',
            'email': ''
        },
        {
            'full_name': 'Sundar Pichai',
            'company_name': '',
            'email': 'sundar@gmail.com'  # Should not trigger domain search
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['full_name']}")
        print(f"   Company: {test_case['company_name'] or 'None'}")
        print(f"   Email: {test_case['email'] or 'None'}")
        
        start_time = time.time()
        try:
            result = await web_scraper.search_person_info(
                test_case['full_name'],
                test_case['company_name'],
                test_case['email']
            )
            end_time = time.time()
            
            print(f"   Duration: {end_time - start_time:.2f}s")
            print(f"   Results found: {len(result)} fields")
            
            for key, value in result.items():
                print(f"      {key}: {value}")
                
            # Verify expected fields are searchable
            expected_fields = ['job_title', 'linkedin_url', 'industry_hint', 'company_confirmed']
            found_fields = [field for field in expected_fields if field in result]
            print(f"   Expected fields found: {found_fields}")
            
        except Exception as e:
            print(f"   Error: {e}")
            logger.error(f"Web scraper test error: {e}", exc_info=True)
        
        print("-" * 40)

async def test_linkedin_search():
    """Test enhanced LinkedIn search functionality"""
    print("\nTesting Enhanced LinkedIn Search")
    print("=" * 50)
    
    config = Config()
    linkedin_enricher = LinkedInEnricher(config)
    
    # Test cases for LinkedIn search
    test_cases = [
        {
            'full_name': 'Reid Hoffman',
            'company_name': 'LinkedIn'
        },
        {
            'full_name': 'Melinda French Gates',
            'company_name': 'Pivotal Ventures'
        },
        {
            'full_name': 'Marc Benioff',
            'company_name': 'Salesforce'
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['full_name']}")
        print(f"   Company: {test_case['company_name']}")
        
        start_time = time.time()
        try:
            result = await linkedin_enricher.search_linkedin_profile(
                test_case['full_name'],
                test_case['company_name']
            )
            end_time = time.time()
            
            print(f"   Duration: {end_time - start_time:.2f}s")
            print(f"   Profile found: {'Yes' if result else 'No'}")
            
            if result:
                print(f"   LinkedIn URL: {result.get('linkedin_url', 'Not found')}")
                print(f"   Job Title: {result.get('job_title', 'Not found')}")
                print(f"   Company: {result.get('company_name', 'Not found')}")
                print(f"   Industry: {result.get('industry', 'Not found')}")
            
        except Exception as e:
            print(f"   Error: {e}")
            logger.error(f"LinkedIn search test error: {e}", exc_info=True)
        
        print("-" * 40)

async def test_search_engines_parallel():
    """Test that all search engines are being used in parallel"""
    print("\nTesting Parallel Search Engine Usage")
    print("=" * 50)
    
    config = Config()
    linkedin_enricher = LinkedInEnricher(config)
    
    # Test a well-known person to increase chance of results
    full_name = "Satya Nadella"
    
    print(f"Searching for: {full_name}")
    print("This should hit DuckDuckGo, Bing, and Google in parallel...")
    
    start_time = time.time()
    try:
        # Test the internal parallel search method
        query = f'"{full_name}" linkedin'
        urls = await linkedin_enricher._search_linkedin_parallel(query)
        end_time = time.time()
        
        print(f"Duration: {end_time - start_time:.2f}s")
        print(f"URLs found: {len(urls)}")
        print(f"Unique URLs: {len(set(urls))}")
        
        # Show first few URLs found
        unique_urls = list(set(urls))
        for i, url in enumerate(unique_urls[:5], 1):
            print(f"   {i}. {url}")
            
        # Verify we got results from multiple engines (duration should be fast due to parallel)
        if end_time - start_time < 30:  # Should be much faster than serial
            print("✓ Search appears to be running in parallel (fast completion)")
        else:
            print("✗ Search may not be running in parallel (slow completion)")
            
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f"Parallel search test error: {e}", exc_info=True)

async def test_comprehensive_search():
    """Test the comprehensive search that combines web + LinkedIn"""
    print("\nTesting Comprehensive Search Integration")
    print("=" * 50)
    
    from modules.enrichment_pipeline import EnrichmentPipeline
    
    config = Config()
    pipeline = EnrichmentPipeline(config)
    
    # Create a test lead that should benefit from enhanced search
    test_lead = {
        'id': 999,
        'Full Name': 'Jensen Huang',
        'Company Name': 'NVIDIA',
        'email': 'jensen@nvidia.com',
        'LinkedIn Link': '',  # No direct LinkedIn link
        'Job Role': '',       # No job role
        'Industry': ''        # No industry
    }
    
    print(f"Testing comprehensive search for: {test_lead['Full Name']}")
    print(f"   Company: {test_lead['Company Name']}")
    print(f"   Starting LinkedIn Link: {test_lead['LinkedIn Link'] or 'None'}")
    print(f"   Starting Job Role: {test_lead['Job Role'] or 'None'}")
    
    start_time = time.time()
    try:
        # This should trigger both web search and LinkedIn search
        enriched_lead = await pipeline._enrich_single_lead(test_lead)
        end_time = time.time()
        
        print(f"\nResults after {end_time - start_time:.2f}s:")
        print(f"   Enrichment Status: {enriched_lead.get('Enriched', 'Unknown')}")
        print(f"   Sources: {enriched_lead.get('enrichment_sources', 'None')}")
        print(f"   Final LinkedIn Link: {enriched_lead.get('LinkedIn Link', 'Not found')}")
        print(f"   Final Job Role: {enriched_lead.get('Job Role', 'Not found')}")
        print(f"   Final Industry: {enriched_lead.get('Industry', 'Not found')}")
        print(f"   Company Size: {enriched_lead.get('Company Size', 'Not found')}")
        print(f"   Quality Score: {enriched_lead.get('Quality (Out of 5)', 'Not calculated')}")
        
        # Show all additional fields that were discovered
        additional_fields = {}
        for key, value in enriched_lead.items():
            if key not in test_lead and value and not key.startswith('enrichment'):
                additional_fields[key] = value
        
        if additional_fields:
            print(f"\nAdditional fields discovered:")
            for key, value in additional_fields.items():
                print(f"   {key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
        
        # Verify the search found LinkedIn profile and job info
        success_criteria = [
            ('LinkedIn URL found', bool(enriched_lead.get('LinkedIn Link'))),
            ('Job role found', bool(enriched_lead.get('Job Role'))),
            ('Industry found', bool(enriched_lead.get('Industry'))),
            ('Multiple sources used', len(enriched_lead.get('enrichment_sources', '').split(', ')) > 1)
        ]
        
        print(f"\nSuccess Criteria:")
        for criteria, met in success_criteria:
            print(f"   {'✓' if met else '✗'} {criteria}")
        
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f"Comprehensive search test error: {e}", exc_info=True)

async def main():
    """Run all enhanced search tests"""
    print("Enhanced Search Functionality Tests")
    print("=" * 60)
    print("Testing the improved Step 2 (web person search) and")
    print("Step 3 (LinkedIn enrichment) with concurrent requests")
    print("=" * 60)
    
    # Run all test suites
    await test_web_scraper_search()
    await test_linkedin_search()
    await test_search_engines_parallel()
    await test_comprehensive_search()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("Check the output above to verify:")
    print("1. Web person search hits all engines and finds job titles/LinkedIn URLs")
    print("2. LinkedIn search uses parallel requests across DuckDuckGo, Bing, Google")
    print("3. Search completion times are faster due to concurrency")
    print("4. Integration works end-to-end in the enrichment pipeline")

if __name__ == "__main__":
    asyncio.run(main())