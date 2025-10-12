"""
Perplexity Manual Workflow Module
Handles generating prompts for manual Perplexity enrichment and parsing results back
"""

import re
import json
from typing import Dict, List, Any, Optional
from config import Config
from modules.odoo_client import OdooClient


class PerplexityWorkflow:
    def __init__(self, config: Config):
        self.config = config
        self.odoo = OdooClient(config)

    def generate_enrichment_prompt(self) -> tuple[str, List[Dict[str, Any]]]:
        """Generate a prompt for manual Perplexity enrichment with current unenriched leads"""

        # Connect to Odoo and fetch unenriched leads
        if not self.odoo.connect():
            raise Exception("Failed to connect to Odoo")

        leads = self.odoo.get_unenriched_leads()
        if not leads:
            return "No unenriched leads found.", []

        # Generate the prompt
        prompt = self._build_comprehensive_prompt(leads)
        return prompt, leads

    def _build_comprehensive_prompt(self, leads: List[Dict[str, Any]]) -> str:
        """Build comprehensive Perplexity prompt with name variations and quality scoring"""

        prompt_parts = [
            "I need you to enrich the following sales leads with comprehensive professional information. "
            "For each person, please find and return the missing data in a structured format.",
            "",
            "**IMPORTANT SEARCH INSTRUCTIONS:**",
            "- Search for name variations (nicknames, alternate spellings, different orders)",
            "- For unclear company associations, research both email domain companies and LinkedIn profiles",
            "- Cross-reference multiple sources and note any discrepancies",
            "- Include a quality rating (1-5) based on data completeness and verification confidence",
            "- If you find conflicting information, mention it clearly",
            "",
            "**CURRENT LEAD DATA:**",
            ""
        ]

        # Add each lead with enhanced context
        for i, lead in enumerate(leads, 1):
            lead_section = [f"**LEAD {i}:**"]

            # Add known information
            if lead.get('Full Name'):
                name = lead['Full Name']
                lead_section.append(f"- Name: {name}")

                # Add name variation suggestions
                name_variations = self._generate_name_variations(name)
                if name_variations:
                    lead_section.append(f"- Search Variations: {', '.join(name_variations)}")

            if lead.get('email'):
                email = lead['email']
                lead_section.append(f"- Email: {email}")
                domain = email.split('@')[1] if '@' in email else None
                if domain:
                    lead_section.append(f"- Email Domain Company: {domain} (research this company too)")

            if lead.get('Company Name'):
                lead_section.append(f"- Stated Company: {lead['Company Name']}")

            if lead.get('Phone') or lead.get('Mobile'):
                phone = lead.get('Phone') or lead.get('Mobile')
                lead_section.append(f"- Phone: {phone}")
                # Add country hint based on phone format
                country_hint = self._guess_country_from_phone(phone)
                if country_hint:
                    lead_section.append(f"- Likely Location: {country_hint}")

            lead_section.append("")
            prompt_parts.extend(lead_section)

        # Add comprehensive requirements
        prompt_parts.extend([
            "**INFORMATION TO FIND FOR EACH LEAD:**",
            "",
            "For each person, please research and provide:",
            "1. **LinkedIn Profile URL** - Direct link to their personal LinkedIn",
            "2. **Current Job Title/Role** - Their exact position",
            "3. **Company Name** - Full official company name (resolve any conflicts)",
            "4. **Company Website** - Official company website URL",
            "5. **Company LinkedIn URL** - Company's LinkedIn page",
            "6. **Industry** - What sector/industry the company operates in",
            "7. **Company Size** - Number of employees (ranges like 10-50, 51-200, 201-500, 501-1000, 1000+)",
            "8. **Company Revenue Estimate** - Annual revenue if available (e.g., <$1M, $1M-$5M, $5M-$10M, $10M+)",
            "9. **Company Founded Year** - When the company was established",
            "10. **Location** - City, country where they're based",
            "11. **Additional Phone Numbers** - Any professional contact numbers or mobile",
            "12. **Professional Email** - Work email if different from provided",
            "13. **Primary Language** - What language they primarily communicate in",
            "14. **Company Description** - Brief description of what the company does",
            "15. **Quality Rating (1-5)** - Rate the lead quality for sales purposes:",
            "    - 5: Senior decision-maker at growing company with clear contact info",
            "    - 4: Mid-level professional at established company with good contact info",
            "    - 3: Professional with some contact info but unclear decision-making power",
            "    - 2: Limited information found, basic professional profile",
            "    - 1: Minimal information, poor contact data, or inactive profiles",
            "",
            "**FORMAT YOUR RESPONSE EXACTLY LIKE THIS:**",
            "",
            "---",
            "**LEAD X: [Full Name]**",
            "- LinkedIn URL: [URL or 'Not Found']",
            "- Job Title: [Title or 'Not Found']",
            "- Company: [Full Company Name or 'Not Found']",
            "- Company Website: [URL or 'Not Found']",
            "- Company LinkedIn: [URL or 'Not Found']",
            "- Industry: [Industry or 'Not Found']",
            "- Company Size: [Employee Range or 'Not Found']",
            "- Revenue Estimate: [Amount or 'Not Found']",
            "- Founded: [Year or 'Not Found']",
            "- Location: [City, Country or 'Not Found']",
            "- Phone: [Number if found or 'Not Found']",
            "- Mobile: [Mobile number if found or 'Not Found']",
            "- Professional Email: [Email if found or 'Not Found']",
            "- Language: [Primary language or 'Not Found']",
            "- Company Description: [Brief description or 'Not Found']",
            "- Quality Rating: [1-5]/5",
            "- Confidence: [High/Medium/Low]",
            "- Notes: [Any conflicts, discrepancies, or additional context]",
            "---",
            "",
            "**SEARCH STRATEGY:**",
            "- Start with LinkedIn search using all name variations",
            "- Research email domain companies thoroughly",
            "- Cross-reference company websites and professional databases",
            "- Look for recent activity, posts, or mentions",
            "- If you find conflicting company information, investigate both",
            "- For foreign names, consider transliterations and cultural variations",
            "",
            "Please research each lead comprehensively and provide the enriched data in the exact format above."
        ])

        return '\n'.join(prompt_parts)

    def _generate_name_variations(self, full_name: str) -> List[str]:
        """Generate possible name variations for better search results"""
        if not full_name:
            return []

        variations = []
        name_parts = full_name.strip().split()

        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = name_parts[-1]

            # Common nickname mappings
            nickname_map = {
                'fares': ['faris'], 'faris': ['fares'],
                'mohammed': ['mohamed', 'mohammad', 'muhammad'],
                'mohamed': ['mohammed', 'mohammad', 'muhammad'],
                'michael': ['mike', 'mick'], 'mike': ['michael', 'mick'],
                'david': ['dave', 'davey'], 'dave': ['david'],
                'robert': ['rob', 'bob', 'bobby'], 'rob': ['robert'],
                'william': ['will', 'bill', 'billy'], 'will': ['william'],
                'james': ['jim', 'jimmy'], 'jim': ['james'],
                'alexander': ['alex', 'alexis'], 'alex': ['alexander']
            }

            # Add nickname variations
            first_lower = first_name.lower()
            if first_lower in nickname_map:
                for nickname in nickname_map[first_lower]:
                    variations.append(f"{nickname.title()} {last_name}")

            # Reverse name order
            variations.append(f"{last_name} {first_name}")

            # First name + initial
            variations.append(f"{first_name} {last_name[0]}.")

        return list(set(variations))  # Remove duplicates

    def _guess_country_from_phone(self, phone: str) -> Optional[str]:
        """Guess country from phone number format"""
        if not phone:
            return None

        clean_phone = re.sub(r'[^\d+]', '', phone)

        if clean_phone.startswith('+971') or clean_phone.startswith('971'):
            return "UAE"
        elif clean_phone.startswith('+7') or clean_phone.startswith('8'):
            return "Russia"
        elif clean_phone.startswith('+962') or clean_phone.startswith('962'):
            return "Jordan"
        elif clean_phone.startswith('+91') or clean_phone.startswith('91'):
            return "India"
        elif clean_phone.startswith('+1'):
            return "USA/Canada"
        elif clean_phone.startswith('+44'):
            return "UK"

        return None

    def parse_perplexity_results(self, perplexity_output: str, original_leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse Perplexity output and convert to structured data for Odoo update"""

        enriched_leads = []

        # Split into individual lead sections
        lead_sections = re.split(r'\*\*LEAD \d+:', perplexity_output)

        for i, section in enumerate(lead_sections[1:], 1):  # Skip the first empty section
            try:
                # Check if we have an original lead for this index
                if i-1 < len(original_leads):
                    lead_data = self._parse_single_lead_section(section, original_leads[i-1])
                    enriched_leads.append(lead_data)
                else:
                    print(f"Warning: Perplexity output has more leads ({i}) than original leads ({len(original_leads)}). Skipping lead {i}.")
            except Exception as e:
                print(f"Error parsing lead {i}: {e}")
                # Add original lead with error note if it exists
                if i-1 < len(original_leads):
                    error_lead = original_leads[i-1].copy()
                    error_lead['parsing_error'] = str(e)
                    enriched_leads.append(error_lead)
                else:
                    print(f"Cannot add error lead for index {i} - no corresponding original lead")

        return enriched_leads

    def _parse_single_lead_section(self, section: str, original_lead: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a single lead section from Perplexity output"""

        # Start with original lead data
        enriched_lead = original_lead.copy()

        # Extract name from section header
        name_match = re.search(r'^([^*]+)\*', section.strip())
        if name_match:
            enriched_lead['Full Name'] = name_match.group(1).strip()

        # Parse each field using regex with improved patterns
        field_patterns = {
            'LinkedIn Link': r'LinkedIn URL:\s*(.+?)(?:\n|$)',
            'Job Role': r'Job Title:\s*(.+?)(?:\n|$)',
            'Company Name': r'Company:\s*(.+?)(?:\n|$)',
            'website': r'Company Website:\s*(.+?)(?:\n|$)',
            'Company LinkedIn': r'Company LinkedIn:\s*(.+?)(?:\n|$)',
            'Industry': r'Industry:\s*(.+?)(?:\n|$)',
            'Company Size': r'Company Size:\s*(.+?)(?:\n|$)',
            'Company Revenue Estimated': r'Revenue Estimate:\s*(.+?)(?:\n|$)',
            'Company year EST': r'Founded:\s*(.+?)(?:\n|$)',
            'Phone': r'Phone:\s*(.+?)(?:\n|$)',
            'Mobile': r'Mobile:\s*(.+?)(?:\n|$)',
            'email': r'Professional Email:\s*(.+?)(?:\n|$)',
            'Language': r'Language:\s*(.+?)(?:\n|$)',
            'Quality (Out of 5)': r'Quality Rating:\s*(\d+)'
        }

        for field_name, pattern in field_patterns.items():
            match = re.search(pattern, section, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                if value and value.lower() not in ['not found', 'n/a', 'none', '', 'not available']:
                    enriched_lead[field_name] = value

        # Extract location info for address fields
        location_match = re.search(r'Location:\s*(.+?)(?:\n|$)', section, re.IGNORECASE)
        if location_match:
            location = location_match.group(1).strip()
            if location and location.lower() != 'not found':
                enriched_lead['Location'] = location
                # Try to parse city, country from location
                if ',' in location:
                    parts = [p.strip() for p in location.split(',')]
                    if len(parts) >= 2:
                        enriched_lead['City'] = parts[0]
                        enriched_lead['Country'] = parts[-1]

        # Extract company description for potential use
        desc_match = re.search(r'Company Description:\s*(.+?)(?:\n|$)', section, re.IGNORECASE | re.MULTILINE)
        if desc_match:
            description = desc_match.group(1).strip()
            if description and description.lower() != 'not found':
                enriched_lead['Company Description'] = description

        # Extract additional contact info that might be mentioned
        email_match = re.search(r'(?:Email|Contact Email):\s*([\w\.-]+@[\w\.-]+)', section, re.IGNORECASE)
        if email_match:
            email = email_match.group(1).strip()
            if email and '@' in email:
                enriched_lead['email'] = email

        # Clean and validate website URLs
        if 'website' in enriched_lead and enriched_lead['website']:
            website = enriched_lead['website']
            if not website.startswith(('http://', 'https://')):
                if website.startswith('www.'):
                    website = f'https://{website}'
                elif '.' in website:
                    website = f'https://{website}'
            enriched_lead['website'] = website

        # Mark as enriched
        enriched_lead['Enriched'] = 'Yes'

        return enriched_lead

    def update_leads_in_odoo(self, enriched_leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update the enriched leads back in Odoo"""

        if not self.odoo.connect():
            return {'success': False, 'error': 'Failed to connect to Odoo'}

        results = {
            'success': True,
            'updated': 0,
            'failed': 0,
            'errors': []
        }

        for lead in enriched_leads:
            try:
                if 'id' in lead:
                    success = self.odoo.update_lead(lead['id'], lead)
                    if success:
                        results['updated'] += 1
                        print(f"✓ Updated lead: {lead.get('Full Name', 'Unknown')}")
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"Failed to update lead {lead['id']}")
                else:
                    results['failed'] += 1
                    results['errors'].append("Lead missing ID field")

            except Exception as e:
                results['failed'] += 1
                error_msg = f"Error updating lead {lead.get('Full Name', 'Unknown')}: {str(e)}"
                # Encode to ASCII to avoid Windows console encoding issues
                results['errors'].append(error_msg.encode('ascii', 'replace').decode('ascii'))

        return results


def main():
    """Command line interface for the Perplexity workflow"""
    import argparse

    parser = argparse.ArgumentParser(description='Perplexity Manual Enrichment Workflow')
    parser.add_argument('action', choices=['generate-prompt', 'parse-results'],
                       help='Action to perform')
    parser.add_argument('--input-file', help='File containing Perplexity results (for parse-results)')
    parser.add_argument('--output-file', help='File to save prompt or results')

    args = parser.parse_args()

    config = Config()
    workflow = PerplexityWorkflow(config)

    if args.action == 'generate-prompt':
        try:
            prompt, leads = workflow.generate_enrichment_prompt()

            if args.output_file:
                with open(args.output_file, 'w', encoding='utf-8') as f:
                    f.write(prompt)
                print(f"Prompt saved to {args.output_file}")
            else:
                print("=== PERPLEXITY PROMPT ===")
                print(prompt)
                print("\n=== COPY THE ABOVE TO PERPLEXITY.AI ===")

        except Exception as e:
            print(f"Error generating prompt: {e}")

    elif args.action == 'parse-results':
        if not args.input_file:
            print("Error: --input-file required for parse-results")
            return

        try:
            # Load Perplexity results
            with open(args.input_file, 'r', encoding='utf-8') as f:
                perplexity_output = f.read()

            # Get original leads for reference
            _, original_leads = workflow.generate_enrichment_prompt()

            # Parse results
            enriched_leads = workflow.parse_perplexity_results(perplexity_output, original_leads)

            # Update Odoo
            results = workflow.update_leads_in_odoo(enriched_leads)

            print(f"Update Results:")
            print(f"✓ Updated: {results['updated']}")
            print(f"✗ Failed: {results['failed']}")

            if results['errors']:
                print("\nErrors:")
                for error in results['errors']:
                    print(f"  - {error}")

        except Exception as e:
            print(f"Error processing results: {e}")


if __name__ == '__main__':
    main()
