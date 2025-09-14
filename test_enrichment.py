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

async def test_enrichment():
    """Test the enhanced enrichment system with sample leads"""
    
    # Sample test leads with minimal data (like what user described)
    test_leads = [
        {
            'id': 1,
            'Full Name': 'John Smith', 
            'Company Name': 'Tech Corp',
            'email': 'john@techcorp.com',
            'LinkedIn Link': '',
            'Job Role': '',
            'Industry': ''
        },
        {
            'id': 2,
            'Full Name': 'Sarah Johnson',
            'Company Name': '',
            'email': 'sarah@gmail.com',
            'LinkedIn Link': '',
            'Job Role': '',
            'Industry': ''
        }
    ]
    
    # Initialize enrichment pipeline
    config = Config()
    pipeline = EnrichmentPipeline(config)
    
    print("Testing Enhanced Enrichment System")
    print("=" * 50)
    
    for lead in test_leads:
        print(f"\nTesting lead: {lead['Full Name']}")
        print(f"   Company: {lead.get('Company Name', 'Unknown')}")
        print(f"   Email: {lead.get('email', 'None')}")
        
        # Test single lead enrichment
        try:
            enriched_lead = await pipeline._enrich_single_lead(lead)
            
            print(f"\nEnrichment Results:")
            print(f"   Status: {enriched_lead.get('Enriched', 'Unknown')}")
            print(f"   Sources: {enriched_lead.get('enrichment_sources', 'None')}")
            print(f"   Job Role: {enriched_lead.get('Job Role', 'Not found')}")
            print(f"   Industry: {enriched_lead.get('Industry', 'Not found')}")
            print(f"   LinkedIn: {enriched_lead.get('LinkedIn Link', 'Not found')}")
            print(f"   Company Size: {enriched_lead.get('Company Size', 'Not found')}")
            
            # Show additional fields that might have been found
            additional_fields = ['linkedin_location', 'linkedin_connections', 'company_search_confirmed']
            for field in additional_fields:
                if enriched_lead.get(field):
                    print(f"   {field.replace('_', ' ').title()}: {enriched_lead[field]}")
                    
        except Exception as e:
            print(f"Error enriching {lead['Full Name']}: {e}")
            logger.error(f"Enrichment error: {e}", exc_info=True)
        
        print("-" * 40)
    
    print(f"\nPipeline Statistics:")
    print(f"   Leads enriched: {pipeline.stats['leads_enriched']}")
    print(f"   Web scraping success: {pipeline.stats['web_scraping_success']}")
    print(f"   LinkedIn enrichment success: {pipeline.stats['linkedin_enrichment_success']}")
    print(f"   Errors: {len(pipeline.stats['errors'])}")
    
    if pipeline.stats['errors']:
        print("\nErrors encountered:")
        for error in pipeline.stats['errors']:
            print(f"   - {error}")

if __name__ == "__main__":
    asyncio.run(test_enrichment())