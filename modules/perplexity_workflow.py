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

    def analyze_lead_complexity(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single lead's enrichment complexity"""
        complexity_score = 0
        factors = []

        # Missing basic info = higher complexity
        if not lead.get('Full Name'):
            complexity_score += 3
            factors.append("Missing name")
        elif len(lead.get('Full Name', '').split()) < 2:
            complexity_score += 2
            factors.append("Incomplete name")

        # Non-English/Arabic names = higher complexity (harder to search)
        name = lead.get('Full Name', '')
        if name and not all(c.isascii() or c.isspace() for c in name):
            complexity_score += 1
            factors.append("Non-Latin characters")

        # Missing email = higher complexity
        if not lead.get('email'):
            complexity_score += 2
            factors.append("No email")

        # Missing company = higher complexity
        if not lead.get('Company Name'):
            complexity_score += 2
            factors.append("No company")

        # Missing phone = moderate complexity
        if not lead.get('Phone') and not lead.get('Mobile'):
            complexity_score += 1
            factors.append("No phone")

        # Common names = higher complexity (more disambiguation needed)
        common_names = ['john', 'mohammed', 'mohamed', 'ahmad', 'ali', 'sarah', 'david', 'michael']
        first_name = name.split()[0].lower() if name else ''
        if first_name in common_names:
            complexity_score += 1
            factors.append("Common name (disambiguation needed)")

        # Determine complexity level
        if complexity_score >= 7:
            level = "Very High"
        elif complexity_score >= 5:
            level = "High"
        elif complexity_score >= 3:
            level = "Medium"
        else:
            level = "Low"

        return {
            "lead_id": lead.get('id'),
            "name": lead.get('Full Name', 'Unknown'),
            "complexity_score": complexity_score,
            "complexity_level": level,
            "factors": factors
        }

    def optimize_batch_split(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Split leads into optimal batches for manual enrichment"""
        # Analyze complexity for all leads
        lead_analyses = [self.analyze_lead_complexity(lead) for lead in leads]

        # Sort by complexity (high complexity first for better focus)
        sorted_leads_with_analysis = sorted(
            zip(leads, lead_analyses),
            key=lambda x: x[1]['complexity_score'],
            reverse=True
        )

        batches = []
        current_batch = []
        current_batch_complexity = 0
        max_batch_complexity = 12  # Optimal complexity per batch
        max_leads_per_batch = 5    # Max leads per batch

        for lead, analysis in sorted_leads_with_analysis:
            lead_complexity = analysis['complexity_score']

            # Start new batch if adding this lead exceeds limits
            if (current_batch_complexity + lead_complexity > max_batch_complexity or
                len(current_batch) >= max_leads_per_batch) and current_batch:
                batches.append({
                    "batch_number": len(batches) + 1,
                    "leads": current_batch.copy(),
                    "total_complexity": current_batch_complexity,
                    "lead_count": len(current_batch)
                })
                current_batch = []
                current_batch_complexity = 0

            current_batch.append({
                "lead": lead,
                "analysis": analysis
            })
            current_batch_complexity += lead_complexity

        # Add final batch
        if current_batch:
            batches.append({
                "batch_number": len(batches) + 1,
                "leads": current_batch,
                "total_complexity": current_batch_complexity,
                "lead_count": len(current_batch)
            })

        return batches

    def generate_single_lead_prompt(self, lead: Dict[str, Any]) -> str:
        """Generate enrichment prompt for a single lead"""
        return self._build_comprehensive_prompt([lead])

    def parse_single_lead_response(self, perplexity_output: str, original_lead: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Perplexity output for a single lead"""
        # Even for single leads, the prompt includes **LEAD 1:** marker
        # So we need to extract the content after the marker

        # Try to find and extract content after **LEAD 1:**
        lead_match = re.search(r'\*\*LEAD \d+:(.+)', perplexity_output, re.DOTALL)
        if lead_match:
            content = lead_match.group(1)
            enriched_lead = self._parse_single_lead_section(content, original_lead)
        else:
            # Fallback: if no marker found, parse the whole response
            enriched_lead = self._parse_single_lead_section(perplexity_output, original_lead)

        # Check for duplicates before returning
        enriched_lead = self._check_for_duplicates(enriched_lead)
        return enriched_lead

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
            "**CRITICAL: COMPANY MATCHING AND MULTI-COMPANY HANDLING:**",
            "- **PRIMARY RULE:** If lead states a company, find their role AT THAT SPECIFIC COMPANY (even if it's not their topmost LinkedIn position)",
            "- **Abbreviations/Misspellings:** Check if company abbreviations match full names (e.g., 'DMT' = 'Department of Municipalities and Transport', 'ADNOC' = 'Abu Dhabi National Oil Company')",
            "- **Example Scenario:** If Sanad states 'AI MENA' as company, but LinkedIn shows he's 'AI Lead at Prezlab' (topmost) and 'Founder at AI MENA' (second position):",
            "  1. Job Title = 'Founder' (his role at the stated company AI MENA)",
            "  2. Company = 'AI MENA' (as stated)",
            "  3. Notes = 'Also currently serves as: AI Lead at Prezlab (Technology, [size], [description]). Prior notable roles: [any relevant past positions]'",
            "- **Multi-Position Professionals:**",
            "  1. Enrich Job Title/Company based on their role at the STATED company (search their LinkedIn for this specific company)",
            "  2. In Notes, list ALL other CURRENT positions (with 'Present' or current end date on LinkedIn)",
            "  3. In Notes, also include NOTABLE PRIOR positions that are relevant or prestigious",
            "  4. Format: 'Also currently serves as: [Role] at [Company] ([Industry], [Size]); [Role2] at [Company2]. Prior roles: [Role] at [Company] ([dates])'",
            "- **If NO company stated:** Use their topmost LinkedIn position as Job Title/Company",
            "- **Always verify:** Cross-check stated company against LinkedIn to find the correct position at that company",
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
                # Skip company research for personal email domains
                personal_domains = ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'icloud.com', 'me.com', 'live.com', 'msn.com', 'aol.com', 'mail.com', 'protonmail.com', 'yandex.com']
                if domain and domain.lower() not in personal_domains:
                    lead_section.append(f"- Email Domain Company: {domain} (research this company too)")

            if lead.get('Company Name'):
                lead_section.append(f"- Stated Company: {lead['Company Name']}")

            # Detect country from phone or other data
            country_hint = None
            if lead.get('Phone') or lead.get('Mobile'):
                phone = lead.get('Phone') or lead.get('Mobile')
                lead_section.append(f"- Phone: {phone}")
                # Add country hint based on phone format
                country_hint = self._guess_country_from_phone(phone)
                if country_hint:
                    lead_section.append(f"- Likely Location: {country_hint}")

            # Also check for explicit country field
            if not country_hint and lead.get('Country'):
                country_hint = lead['Country']
                lead_section.append(f"- Country: {country_hint}")

            lead_section.append("")
            prompt_parts.extend(lead_section)

        # Add comprehensive requirements
        prompt_parts.extend([
            "**INFORMATION TO FIND FOR EACH LEAD:**",
            "",
            "For each person, please research and provide:",
            "1. **LinkedIn Profile URL** - Direct link to their personal LinkedIn (REQUIRED - this is the primary source of truth)",
            "2. **Current Job Title/Role** - Their CURRENT position from LinkedIn's Experience section (the topmost/most recent role)",
            "3. **Company Name** - The company from their CURRENT LinkedIn position (if no stated company) OR the stated company (if provided)",
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
            "- Notes: [CRITICAL: 1) List ALL other CURRENT positions not listed as Job Title above (board memberships, advisory roles, consulting, other full-time roles). 2) Include notable PRIOR positions if prestigious or relevant. 3) Format: 'Also currently serves as: [Role] at [Company] ([Industry], [Size], [brief description]); [Role2] at [Company2]. Prior notable roles: [Role] at [Company] ([Years], [brief context])'. Example: 'Also currently serves as: AI Lead at Prezlab (Technology, 50-200 employees, presentation software); Board Member at Alawneh Pay (FinTech, mobile payments). Prior roles: Senior Developer at Microsoft (2018-2020, cloud infrastructure)']",
            "---",
            "",
            "**SEARCH STRATEGY:**",
            "- **ALWAYS start with LinkedIn search** - this is the most important source",
            "- **Primary LinkedIn Search Method:** Use the format '[Full Name] LinkedIn [Country]' (e.g., 'John Smith LinkedIn UAE') - this manual search method often finds profiles that other methods miss",
            "- If country is known, ALWAYS include it in your LinkedIn search query",
            "- Look at the person's LinkedIn Experience section - the TOPMOST position is their current role",
            "- If LinkedIn shows multiple current positions (e.g., 'Present' on multiple roles), list the main full-time one as Job Title/Company, and list ALL others in Notes",
            "- Research email domain companies as secondary confirmation (skip for personal domains like gmail.com)",
            "- Cross-reference company websites and professional databases",
            "- Look for recent activity, posts, or mentions",
            "- If you find conflicting company information between stated company and LinkedIn, use the stated company BUT note the LinkedIn position in Notes",
            "- For foreign names, consider transliterations and cultural variations",
            "- **CRITICAL:** Always try the manual LinkedIn search format '[Name] LinkedIn [Country]' even if other methods fail - this is how humans find profiles manually",
            "",
            "**CRITICAL REMINDER:**",
            "- LinkedIn is your PRIMARY source - always check it first",
            "- The topmost position in LinkedIn Experience = current role",
            "- List ALL other concurrent positions in the Notes field",
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

    def _check_for_duplicates(self, enriched_lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for duplicate leads in Odoo based on email and name.
        If duplicates found, enrich the current lead AND apply same enrichment to all duplicates.

        Args:
            enriched_lead: The enriched lead data

        Returns:
            Lead data with duplicate information stored for batch update
        """
        try:
            email = enriched_lead.get('email', '').strip()
            name = enriched_lead.get('Full Name', '').strip()
            current_id = enriched_lead.get('id')

            if not email and not name:
                return enriched_lead

            # Check for duplicates
            duplicates = self.odoo.find_duplicate_leads(email=email, name=name)

            # Filter out the current lead itself
            duplicates = [d for d in duplicates if d.get('id') != current_id]

            if duplicates:
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

                # Build list of duplicate IDs for updating
                duplicate_ids = [d.get('id') for d in duplicates]
                duplicate_info = []
                for dup in duplicates:
                    dup_name = dup.get('name', 'Unknown')
                    dup_company = dup.get('partner_name', 'N/A')
                    dup_email = dup.get('email_from', 'N/A')
                    dup_id = dup.get('id', 'N/A')
                    duplicate_info.append(f"ID {dup_id}: {dup_name} at {dup_company} ({dup_email})")

                # Add note to the enriched lead about bulk update
                bulk_update_note = f"🔄 Bulk Enrichment ({timestamp}): This enrichment was applied to {len(duplicates) + 1} duplicate lead(s): Current (ID {current_id}), {', '.join([f'ID {did}' for did in duplicate_ids])}"

                existing_notes = enriched_lead.get('Notes', '')
                if existing_notes:
                    enriched_lead['Notes'] = f"{existing_notes}. {bulk_update_note}"
                else:
                    enriched_lead['Notes'] = bulk_update_note

                # Store duplicate IDs in the enriched lead for batch update
                enriched_lead['_duplicate_ids'] = duplicate_ids
                enriched_lead['_bulk_update_note'] = bulk_update_note

                print(f"🔄 Duplicate detected for '{name}' ({email}): Will update {len(duplicates)} additional lead(s)")
                print(f"   Duplicates: {', '.join([f'ID {did}' for did in duplicate_ids])}")

        except Exception as e:
            print(f"Warning: Could not check for duplicates: {e}")

        return enriched_lead

    def parse_perplexity_results(self, perplexity_output: str, original_leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse Perplexity output and convert to structured data for Odoo update"""

        enriched_leads = []

        # Create a map of original leads by name for matching
        original_leads_map = {}
        for lead in original_leads:
            # Try multiple name fields to create the map
            name = lead.get('Full Name') or lead.get('name') or lead.get('contact_name', '')
            if name:
                # Normalize name for matching (lowercase, strip whitespace)
                normalized_name = name.lower().strip()
                original_leads_map[normalized_name] = lead

        # Split into individual lead sections
        lead_sections = re.split(r'\*\*LEAD \d+:', perplexity_output)

        for i, section in enumerate(lead_sections[1:], 1):  # Skip the first empty section
            try:
                # Extract name from this section first
                name_match = re.search(r'^([^*]+)\*', section.strip())
                if name_match:
                    perplexity_name = name_match.group(1).strip()
                    normalized_perplexity_name = perplexity_name.lower().strip()

                    # Find matching original lead by name
                    matching_lead = original_leads_map.get(normalized_perplexity_name)

                    if matching_lead:
                        lead_data = self._parse_single_lead_section(section, matching_lead)
                        # Check for duplicates
                        lead_data = self._check_for_duplicates(lead_data)
                        enriched_leads.append(lead_data)
                    else:
                        print(f"Warning: Could not find original lead for name '{perplexity_name}'. Available names: {list(original_leads_map.keys())}")
                        # Fallback to position-based matching if name not found
                        if i-1 < len(original_leads):
                            print(f"Falling back to position-based matching for lead {i}")
                            lead_data = self._parse_single_lead_section(section, original_leads[i-1])
                            lead_data = self._check_for_duplicates(lead_data)
                            enriched_leads.append(lead_data)
                else:
                    print(f"Warning: Could not extract name from Perplexity section {i}")
                    # Fallback to position-based matching
                    if i-1 < len(original_leads):
                        lead_data = self._parse_single_lead_section(section, original_leads[i-1])
                        lead_data = self._check_for_duplicates(lead_data)
                        enriched_leads.append(lead_data)

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

        # Remove Perplexity reference citations section at the end (everything after the first [1](...) style reference)
        # This removes the entire reference list at the bottom
        section = re.sub(r'\n\[\d+\]\(http[^\)]+\)[\s\S]*$', '', section, flags=re.MULTILINE)

        # Start with original lead data
        enriched_lead = original_lead.copy()

        # Keep original name - Perplexity responses are too unreliable for name extraction
        enriched_lead['Full Name'] = original_lead.get('Full Name', original_lead.get('name', 'Unknown'))

        # Parse each field using regex with improved patterns
        field_patterns = {
            # Add Full Name to patterns but we'll skip it in the loop to prevent Perplexity from overwriting
            'Full Name': r'Full Name:\s*(.+?)(?:\n|$)',
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
            'Company Description': r'Company Description:\s*(.+?)(?:\n|$)',
            'Notes': r'Notes:\s*(.+?)(?:\n|$)',
            'Quality (Out of 5)': r'Quality Rating:\s*(\d+)'
        }

        for field_name, pattern in field_patterns.items():
            match = re.search(pattern, section, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()

                # Remove Perplexity citation references like [1], [2], etc.
                value = re.sub(r'\[\d+\]', '', value).strip()

                # Skip if value starts with "not found" or similar (case insensitive)
                value_lower = value.lower()
                if value and not any(value_lower.startswith(x) for x in ['not found', 'not explicitly', 'n/a', 'none', 'not available']):
                    # NEVER overwrite Full Name - we set it from original above
                    if field_name == 'Full Name':
                        continue
                    # Special handling for email - extract just the email address
                    elif field_name == 'email':
                        # Look for email pattern in the value
                        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', value)
                        if email_match:
                            enriched_lead[field_name] = email_match.group(0)
                        # Skip if no valid email found
                    # Validate URLs for website and LinkedIn fields
                    elif field_name in ['website', 'LinkedIn Link']:
                        # Only accept if it looks like a valid URL
                        if value.startswith(('http://', 'https://', 'www.')) or '.' in value:
                            # Special validation for LinkedIn URLs
                            if field_name == 'LinkedIn Link':
                                # LinkedIn profile URLs must have format /in/something
                                if re.search(r'/in/[^/]+/?$', value):
                                    enriched_lead[field_name] = value
                                else:
                                    # Reject invalid LinkedIn URLs
                                    enriched_lead['Notes'] = enriched_lead.get('Notes', '') + f' [WARNING: LinkedIn URL appears invalid: {value}]'
                            else:
                                enriched_lead[field_name] = value
                    else:
                        enriched_lead[field_name] = value

        # Extract location info for address fields
        location_match = re.search(r'Location:\s*(.+?)(?:\n|$)', section, re.IGNORECASE)
        if location_match:
            location = location_match.group(1).strip()
            # Remove citation references
            location = re.sub(r'\[\d+\]', '', location).strip()

            if location and location.lower() not in ['not found', 'not explicitly', 'n/a', 'none', 'not available']:
                enriched_lead['Location'] = location
                # Try to parse city, country from location
                if ',' in location:
                    parts = [p.strip() for p in location.split(',')]
                    if len(parts) >= 2:
                        enriched_lead['City'] = parts[0]
                        # Always populate Country field - last part is usually country
                        country = parts[-1]
                        enriched_lead['Country'] = country

                        # Also populate street2 with full location for reference
                        enriched_lead['street2'] = location
                elif location:
                    # If no comma, treat entire location as country
                    enriched_lead['Country'] = location

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

            # Remove markdown link format: [url](url) or [text](url)
            markdown_match = re.search(r'\[([^\]]+)\]\(([^\)]+)\)', website)
            if markdown_match:
                # Use the URL from the parentheses
                website = markdown_match.group(2)

            if not website.startswith(('http://', 'https://')):
                if website.startswith('www.'):
                    website = f'https://{website}'
                elif '.' in website:
                    website = f'https://{website}'
            enriched_lead['website'] = website

        # Clean LinkedIn Link from markdown format too
        if 'LinkedIn Link' in enriched_lead and enriched_lead['LinkedIn Link']:
            linkedin = enriched_lead['LinkedIn Link']

            # Remove markdown link format: [url](url) or [text](url)
            markdown_match = re.search(r'\[([^\]]+)\]\(([^\)]+)\)', linkedin)
            if markdown_match:
                # Use the URL from the parentheses
                linkedin = markdown_match.group(2)

            enriched_lead['LinkedIn Link'] = linkedin

        # Mark as enriched
        enriched_lead['Enriched'] = 'Yes'

        return enriched_lead

    def update_leads_in_odoo(self, enriched_leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update the enriched leads back in Odoo.
        If duplicates are detected, applies same enrichment to all duplicate leads.
        """

        if not self.odoo.connect():
            return {'success': False, 'error': 'Failed to connect to Odoo'}

        results = {
            'success': True,
            'updated': 0,
            'failed': 0,
            'errors': [],
            'duplicates_updated': 0
        }

        for lead in enriched_leads:
            try:
                if 'id' not in lead:
                    results['failed'] += 1
                    results['errors'].append("Lead missing ID field")
                    continue

                # Extract duplicate information if present
                duplicate_ids = lead.pop('_duplicate_ids', [])
                bulk_update_note = lead.pop('_bulk_update_note', '')

                # Update the primary lead
                success = self.odoo.update_lead(lead['id'], lead)
                if success:
                    results['updated'] += 1
                    print(f"[OK] Updated lead: {lead.get('Full Name', 'Unknown')} (ID: {lead['id']})")
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to update lead {lead['id']}")
                    continue  # Don't update duplicates if primary failed

                # Update all duplicate leads with the same enrichment data
                if duplicate_ids:
                    print(f"🔄 Applying same enrichment to {len(duplicate_ids)} duplicate lead(s)...")

                    # Prepare enrichment data for duplicates (copy from primary)
                    duplicate_enrichment = lead.copy()

                    for dup_id in duplicate_ids:
                        try:
                            # Update the duplicate with the same enrichment
                            duplicate_enrichment['id'] = dup_id
                            dup_success = self.odoo.update_lead(dup_id, duplicate_enrichment)

                            if dup_success:
                                results['duplicates_updated'] += 1
                                print(f"   [OK] Updated duplicate lead ID: {dup_id}")
                            else:
                                results['errors'].append(f"Failed to update duplicate lead {dup_id}")

                        except Exception as dup_error:
                            error_msg = f"Error updating duplicate lead {dup_id}: {str(dup_error)}"
                            results['errors'].append(error_msg)
                            print(f"   [ERROR] {error_msg}")

            except Exception as e:
                results['failed'] += 1
                error_msg = f"Error updating lead {lead.get('Full Name', 'Unknown')}: {str(e)}"
                results['errors'].append(error_msg)

        # Add summary message if duplicates were updated
        if results['duplicates_updated'] > 0:
            print(f"\n✅ Bulk Update Summary: {results['updated']} primary lead(s) + {results['duplicates_updated']} duplicate(s) = {results['updated'] + results['duplicates_updated']} total leads updated")

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
