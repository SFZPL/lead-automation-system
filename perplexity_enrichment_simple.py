#!/usr/bin/env python3
"""
Perplexity Manual Enrichment Tool
This script helps you enrich leads using Perplexity.ai
"""

import sys
import os
from pathlib import Path
from modules.perplexity_workflow import PerplexityWorkflow
from config import Config

def print_header():
    print("=" * 60)
    print("PERPLEXITY LEAD ENRICHMENT TOOL")
    print("=" * 60)
    print()

def print_usage():
    print("Usage:")
    print("  python perplexity_enrichment_simple.py generate    # Generate prompt for Perplexity")
    print("  python perplexity_enrichment_simple.py parse <file>  # Parse Perplexity results")
    print()

def generate_prompt():
    """Generate a prompt for Perplexity enrichment"""
    print("Generating enrichment prompt...")
    print()

    config = Config()
    workflow = PerplexityWorkflow(config)

    try:
        prompt, leads = workflow.generate_enrichment_prompt()

        if not leads:
            print("No unenriched leads found.")
            return

        print(f"Found {len(leads)} leads to enrich")
        print()
        print("COPY THE FOLLOWING PROMPT TO PERPLEXITY.AI:")
        print("=" * 60)
        print(prompt)
        print("=" * 60)
        print()
        print("INSTRUCTIONS:")
        print("1. Copy the above prompt")
        print("2. Go to https://perplexity.ai")
        print("3. Paste the prompt and run it")
        print("4. Copy Perplexity's response to a text file")
        print("5. Run: python perplexity_enrichment_simple.py parse <filename>")
        print()

    except Exception as e:
        print(f"Error generating prompt: {e}")

def parse_results(file_path):
    """Parse Perplexity results and update Odoo"""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Parsing results from: {file_path}")
    print()

    config = Config()
    workflow = PerplexityWorkflow(config)

    try:
        # Load Perplexity results
        with open(file_path, 'r', encoding='utf-8') as f:
            perplexity_output = f.read()

        # Get original leads for reference
        _, original_leads = workflow.generate_enrichment_prompt()

        if not original_leads:
            print("No original leads found to match against.")
            return

        print(f"Processing {len(original_leads)} leads...")

        # Parse results
        enriched_leads = workflow.parse_perplexity_results(perplexity_output, original_leads)

        if not enriched_leads:
            print("No enriched data could be parsed.")
            return

        print(f"Successfully parsed {len(enriched_leads)} leads")
        print()

        # Show preview of parsed data
        print("PARSED DATA PREVIEW:")
        print("-" * 40)
        for i, lead in enumerate(enriched_leads, 1):
            print(f"Lead {i}: {lead.get('Full Name', 'Unknown')}")
            fields_found = []
            for field in ['LinkedIn Link', 'Job Role', 'Company Name', 'website', 'Phone', 'Mobile', 'Quality (Out of 5)']:
                if lead.get(field) and str(lead.get(field)).strip():
                    fields_found.append(field)
            print(f"  Found: {', '.join(fields_found) if fields_found else 'No additional data'}")
        print("-" * 40)
        print()

        # Ask for confirmation
        confirm = input("Update leads in Odoo? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled. No changes made to Odoo.")
            return

        print("Updating leads in Odoo...")

        # Update Odoo
        results = workflow.update_leads_in_odoo(enriched_leads)

        print()
        print("UPDATE RESULTS:")
        print(f"Successfully updated: {results.get('updated', 0)} leads")
        print(f"Failed: {results.get('failed', 0)} leads")

        if results.get('errors'):
            print()
            print("ERRORS:")
            for error in results['errors']:
                print(f"  - {error}")

        print()
        print("Enrichment complete!")

    except Exception as e:
        print(f"Error processing results: {e}")

def main():
    print_header()

    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1].lower()

    if command == 'generate':
        generate_prompt()
    elif command == 'parse':
        if len(sys.argv) < 3:
            print("Error: Please specify the results file")
            print("   Usage: python perplexity_enrichment_simple.py parse <file>")
            return
        parse_results(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        print_usage()

if __name__ == '__main__':
    main()