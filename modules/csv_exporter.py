"""
CSV Export Module for Lead Data
Provides functionality to export enriched leads to CSV format
"""

import csv
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)

class CSVExporter:
    """Handles CSV export functionality for lead data"""

    def __init__(self, config: Config = None):
        self.config = config or Config()

    def export_leads_to_csv(self, leads: List[Dict[str, Any]],
                           filename: Optional[str] = None,
                           output_dir: Optional[str] = None) -> str:
        """
        Export leads to CSV file

        Args:
            leads: List of lead dictionaries
            filename: Optional custom filename
            output_dir: Optional custom output directory

        Returns:
            Path to the exported CSV file
        """
        if not leads:
            raise ValueError("No leads provided for export")

        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"leads_export_{timestamp}.csv"

        # Set output directory
        if not output_dir:
            output_dir = os.getcwd()

        output_path = os.path.join(output_dir, filename)

        # Prepare CSV headers based on config
        headers = self.config.SHEET_HEADERS.copy()

        # Add additional fields if they exist in the data
        additional_field_labels = {
            'email': 'Email',
            'email_from': 'Email',
            'city': 'City',
            'country': 'Country',
            'website': 'Website',
            'description': 'Description',
            'source': 'Source',
            'creation_date': 'Creation Date',
            'enrichment_sources': 'Enrichment Sources',
            'enrichment_date': 'Enrichment Date',
            'enrichment_status': 'Enrichment Status',
            'enrichment_error': 'Enrichment Error',
            'linkedin_connections': 'LinkedIn Connections',
            'linkedin_location': 'LinkedIn Location',
            'linkedin_about': 'LinkedIn About',
            'company_search_confirmed': 'Company Search Confirmed',
        }

        for lead in leads:
            for key, header_label in additional_field_labels.items():
                if key in lead and header_label not in headers:
                    headers.append(header_label)

        try:
            # Write CSV with UTF-8 BOM for better Excel compatibility
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)

                # Write header row
                writer.writerow(headers)

                # Write data rows
                for lead in leads:
                    row = self._prepare_csv_row(lead, headers)
                    writer.writerow(row)

            logger.info(f"Successfully exported {len(leads)} leads to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error exporting leads to CSV: {e}")
            raise

    def _prepare_csv_row(self, lead: Dict[str, Any], headers: List[str]) -> List[str]:
        """Prepare a single row for CSV export"""
        row = []

        # Map of header names to lead data keys
        header_mapping = {
            'Full Name': ['Full Name', 'name', 'contact_name'],
            'Company Name': ['Company Name', 'partner_name', 'company_name'],
            'LinkedIn Link': ['LinkedIn Link', 'linkedin_profile', 'x_studio_linkedin_profile', 'linkedin_url'],
            'Company Size': ['Company Size', 'company_size'],
            'Industry': ['Industry', 'industry'],
            'Company Revenue Estimated': ['Company Revenue Estimated', 'company_revenue', 'revenue'],
            'Job Role': ['Job Role', 'function', 'job_title', 'position'],
            'Company year EST': ['Company year EST', 'company_founded', 'founded_year'],
            'Phone': ['Phone', 'phone', 'mobile'],
            'Salesperson': ['Salesperson', 'user_id', 'salesperson'],
            'Quality (Out of 5)': ['Quality (Out of 5)', 'x_studio_quality', 'quality'],
            'Enriched': ['Enriched', 'enrichment_status', 'enriched'],
            'Email': ['email', 'email_from'],
            'City': ['city', 'City'],
            'Country': ['country', 'country_id', 'Country'],
            'Website': ['website', 'Website'],
            'Description': ['description', 'Description'],
            'Source': ['source', 'Source'],
            'Creation Date': ['creation_date', 'create_date'],
            'Enrichment Sources': ['enrichment_sources'],
            'Enrichment Date': ['enrichment_date'],
            'Enrichment Status': ['enrichment_status'],
            'Enrichment Error': ['enrichment_error'],
            'LinkedIn Connections': ['linkedin_connections'],
            'LinkedIn Location': ['linkedin_location'],
            'LinkedIn About': ['linkedin_about'],
            'Company Search Confirmed': ['company_search_confirmed']
        }

        for header in headers:
            value = self._get_lead_value(lead, header, header_mapping)

            # Clean and format the value
            cleaned_value = self._clean_csv_value(value)
            row.append(cleaned_value)

        return row

    def _get_lead_value(self, lead: Dict[str, Any], header: str,
                       header_mapping: Dict[str, List[str]]) -> Any:
        """Get value from lead data based on header name"""
        # First try exact header match
        if header in lead:
            return lead[header]

        # Try mapped keys
        if header in header_mapping:
            for key in header_mapping[header]:
                if key in lead:
                    value = lead[key]
                    # Handle many2one fields from Odoo (stored as [id, name] tuples)
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        return value[1]  # Return the name part
                    return value

        # Try case-insensitive match
        for key, value in lead.items():
            if key.lower() == header.lower():
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    return value[1]
                return value

        return ''



    def _clean_csv_value(self, value: Any) -> str:
        """Clean and format a value for CSV export"""
        if value is None:
            return ''

        if isinstance(value, bool):
            return 'Yes' if value else 'No'

        # Convert to string
        str_value = str(value).strip()

        # Handle HTML content (extract URLs or clean text)
        if '<' in str_value and '>' in str_value:
            str_value = self._extract_from_html(str_value)

        # Prevent Excel from interpreting values like "1/5" as dates
        if str_value and '/' in str_value:
            parts = str_value.split('/')
            if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                if not str_value.startswith("'"):
                    str_value = f"'{str_value}"

        # Handle long text fields - truncate if too long
        if len(str_value) > 500:
            str_value = str_value[:497] + '...'

        return str_value

    def _extract_from_html(self, html_text: str) -> str:
        """Extract meaningful content from HTML"""
        if not html_text:
            return ""

        import re
        import html

        try:
            # First try to find URLs in href attributes
            href_match = re.search(r'href=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
            if href_match:
                return href_match.group(1)

            # If no href found, clean HTML tags and decode entities
            clean_text = re.sub(r'<[^>]+>', ' ', html_text)
            clean_text = html.unescape(clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            return clean_text

        except Exception:
            # If anything goes wrong, return original text
            return html_text

    def export_pipeline_results(self, pipeline_result: Dict[str, Any],
                               filename: Optional[str] = None) -> Optional[str]:
        """
        Export results from a pipeline run to CSV

        Args:
            pipeline_result: Result dictionary from pipeline execution
            filename: Optional custom filename

        Returns:
            Path to exported file or None if no data to export
        """
        if not pipeline_result or 'enriched_leads' not in pipeline_result:
            logger.warning("No enriched leads found in pipeline result")
            return None

        leads = pipeline_result['enriched_leads']
        if not leads:
            logger.warning("No leads to export")
            return None

        return self.export_leads_to_csv(leads, filename)
