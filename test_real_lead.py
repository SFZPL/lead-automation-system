#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.enrichment_pipeline import EnrichmentPipeline
from config import Config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_real_lead():
    """Test enrichment with actual lead data"""
    
    # Using the actual lead data from your system
    test_lead = {
        'id': 1,
        'Full Name': 'Fares Haddad', 
        'Company Name': '',
        'email': 'faris.haddad@prezlab.com',
        'LinkedIn Link': '',
        'Job Role': '',
        'Industry': ''
    }
    
    # Initialize enrichment pipeline
    config = Config()
    pipeline = EnrichmentPipeline(config)
    
    print(f"Testing Enhanced Enrichment for: {test_lead['Full Name']}")
    print(f"Email: {test_lead['email']}")
    print("=" * 60)
    
    try:
        # Test single lead enrichment
        enriched_lead = await pipeline._enrich_single_lead(test_lead)
        
        print(f"\nEnrichment Results:")
        print(f"Status: {enriched_lead.get('Enriched', 'Unknown')}")
        print(f"Sources: {enriched_lead.get('enrichment_sources', 'None')}")
        print(f"Job Role: {enriched_lead.get('Job Role', 'Not found')}")
        print(f"Company Name: {enriched_lead.get('Company Name', 'Not found')}")
        print(f"Industry: {enriched_lead.get('Industry', 'Not found')}")
        print(f"LinkedIn: {enriched_lead.get('LinkedIn Link', 'Not found')}")
        print(f"Company Size: {enriched_lead.get('Company Size', 'Not found')}")
        print(f"Quality Score: {enriched_lead.get('Quality (Out of 5)', 'Not calculated')}")
        
        # Show additional enriched fields
        additional_fields = [
            'linkedin_location', 'linkedin_connections', 'linkedin_about',
            'company_search_confirmed', 'Company Revenue Estimated', 
            'Company year EST', 'enrichment_date'
        ]
        
        print(f"\nAdditional Enriched Data:")
        for field in additional_fields:
            if enriched_lead.get(field):
                print(f"{field.replace('_', ' ').title()}: {enriched_lead[field]}")
                
    except Exception as e:
        print(f"Error enriching {test_lead['Full Name']}: {e}")
        logger.error(f"Enrichment error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_real_lead())