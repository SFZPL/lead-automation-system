#!/usr/bin/env python3
"""
Lead Automation System - Main Orchestrator

This script orchestrates the complete lead automation pipeline:
1. Extract unenriched leads from Odoo
2. Add them to Google Sheets
3. Enrich with web scraping and LinkedIn data
4. Update both Google Sheets and Odoo with enriched information
"""

import asyncio
import argparse
import sys
import os
import json
from datetime import datetime
from typing import List, Optional

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from modules.logger import setup_logging, log_pipeline_stats, create_audit_log
from modules.enrichment_pipeline import EnrichmentPipeline

def validate_configuration():
    """Validate system configuration before running"""
    print("Validating configuration...")
    
    validation_result = Config.validate()
    
    if validation_result['errors']:
        print("ERROR: Configuration errors found:")
        for error in validation_result['errors']:
            print(f"  - {error}")
        return False
    
    if validation_result['warnings']:
        print("WARNING: Configuration warnings:")
        for warning in validation_result['warnings']:
            print(f"  - {warning}")
        
        response = input("Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            return False
    
    print("SUCCESS: Configuration validated successfully")
    return True

async def run_full_pipeline(config: Config, logger):
    """Run the complete lead automation pipeline"""
    logger.info("Starting full lead automation pipeline")
    create_audit_log("pipeline_start", {"salesperson": config.SALESPERSON_NAME})
    
    pipeline = EnrichmentPipeline(config)
    
    try:
        result = await pipeline.run_full_pipeline()
        
        # Log results
        log_pipeline_stats(result['stats'], logger)
        
        if result['status'] == 'completed':
            print("\n🎉 Pipeline completed successfully!")
            print(f"📊 Leads extracted: {result['stats']['leads_extracted']}")
            print(f"✨ Leads enriched: {result['stats']['leads_enriched']}")
            print(f"🌐 Web scraping successes: {result['stats']['web_scraping_success']}")
            print(f"🔗 LinkedIn enrichment successes: {result['stats']['linkedin_enrichment_success']}")
            print(f"📝 Leads updated in Odoo: {result['stats']['leads_updated_in_odoo']}")
            
            if result.get('spreadsheet_url'):
                print(f"📊 Google Sheet: {result['spreadsheet_url']}")
            
            print(f"⏱️  Total duration: {result['duration_seconds']} seconds")
        else:
            print("❌ Pipeline failed!")
            if result['stats']['errors']:
                print("Errors encountered:")
                for error in result['stats']['errors']:
                    print(f"  - {error}")
        
        create_audit_log("pipeline_complete", {
            "status": result['status'],
            "duration": result['duration_seconds'],
            "stats": result['stats']
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        create_audit_log("pipeline_error", {"error": str(e)})
        print(f"❌ Pipeline failed with error: {e}")
        return None

async def enrich_specific_leads(config: Config, lead_ids: List[int], logger):
    """Enrich specific leads by their IDs"""
    logger.info(f"Starting enrichment for specific leads: {lead_ids}")
    
    pipeline = EnrichmentPipeline(config)
    
    try:
        result = await pipeline.enrich_specific_leads(lead_ids)
        
        if result['status'] == 'completed':
            print(f"✅ Successfully enriched {result['processed_leads']} leads")
            log_pipeline_stats(result['stats'], logger)
        else:
            print(f"❌ Enrichment failed: {result.get('message', result.get('error', 'Unknown error'))}")
        
        return result
        
    except Exception as e:
        logger.error(f"Specific lead enrichment failed: {e}", exc_info=True)
        print(f"❌ Enrichment failed with error: {e}")
        return None

def export_configuration():
    """Export current configuration to a file"""
    config = Config()
    config_data = {
        'odoo': {
            'url': config.ODOO_URL,
            'database': config.ODOO_DB,
            'username': config.ODOO_USERNAME,
            'insecure_ssl': config.ODOO_INSECURE_SSL
        },
        'sheets': {
            'service_account_file': config.GOOGLE_SERVICE_ACCOUNT_FILE,
            'spreadsheet_title': config.GSHEET_SPREADSHEET_TITLE,
            'worksheet_title': config.GSHEET_WORKSHEET_TITLE,
            'share_with': config.GSHEET_SHARE_WITH
        },
        'processing': {
            'salesperson_name': config.SALESPERSON_NAME,
            'batch_size': config.BATCH_SIZE,
            'max_concurrent_requests': config.MAX_CONCURRENT_REQUESTS
        },
        'columns': config.SHEET_HEADERS
    }
    
    filename = f"config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(config_data, f, indent=2)
    
    print(f"📄 Configuration exported to {filename}")

def print_system_info():
    """Print system information and status"""
    config = Config()
    
    print("\n" + "="*60)
    print("🤖 LEAD AUTOMATION SYSTEM")
    print("="*60)
    print(f"Salesperson: {config.SALESPERSON_NAME}")
    print(f"Odoo URL: {config.ODOO_URL}")
    print(f"Odoo Database: {config.ODOO_DB}")
    print(f"Batch Size: {config.BATCH_SIZE}")
    print(f"Max Concurrent Requests: {config.MAX_CONCURRENT_REQUESTS}")
    print(f"Google Service Account: {config.GOOGLE_SERVICE_ACCOUNT_FILE}")
    
    # Check file existence
    if os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE):
        print("✅ Google Service Account file found")
    else:
        print("❌ Google Service Account file not found")
    
    if config.APIFY_API_TOKEN:
        print("✅ Apify API token configured")
    else:
        print("❌ Apify API token not configured")
    
    print(f"\nColumns to be managed:")
    for i, column in enumerate(config.SHEET_HEADERS, 1):
        print(f"  {i:2d}. {column}")
    
    print("="*60)

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Lead Automation System - Extract, enrich, and manage leads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run full pipeline
  %(prog)s --validate               # Validate configuration only
  %(prog)s --leads 123 456 789      # Enrich specific leads by ID
  %(prog)s --export-config          # Export configuration to file
  %(prog)s --info                   # Show system information
        """
    )
    
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate configuration and exit'
    )
    
    parser.add_argument(
        '--leads',
        nargs='+',
        type=int,
        metavar='ID',
        help='Enrich specific leads by their Odoo IDs'
    )
    
    parser.add_argument(
        '--export-config',
        action='store_true',
        help='Export current configuration to JSON file'
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Show system information and configuration'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform a dry run without making changes'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    config = Config()
    logger = setup_logging(config, args.log_level)
    
    # Handle different modes
    if args.info:
        print_system_info()
        return
    
    if args.export_config:
        export_configuration()
        return
    
    if args.validate:
        if validate_configuration():
            print("SUCCESS: All configurations are valid")
            return
        else:
            print("ERROR: Configuration validation failed")
            sys.exit(1)
    
    # Validate configuration before running
    if not validate_configuration():
        sys.exit(1)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        logger.info("Running in dry-run mode")
    
    try:
        if args.leads:
            # Enrich specific leads
            print(f"🎯 Enriching specific leads: {args.leads}")
            result = await enrich_specific_leads(config, args.leads, logger)
        else:
            # Run full pipeline
            print("🚀 Starting full lead automation pipeline...")
            result = await run_full_pipeline(config, logger)
        
        if result is None:
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⚠️  Pipeline interrupted by user")
        logger.warning("Pipeline interrupted by user")
        create_audit_log("pipeline_interrupted", {"reason": "user_interrupt"})
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
        create_audit_log("pipeline_error", {"error": str(e), "type": "unexpected"})
        sys.exit(1)

if __name__ == "__main__":
    # Ensure we're using the right event loop policy on Windows
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())