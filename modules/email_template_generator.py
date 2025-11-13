"""
Email template generator for lead outreach.
Generates personalized or basic email drafts based on enrichment data.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class EmailTemplateGenerator:
    """Generates email templates for lead outreach."""

    def __init__(self):
        pass

    def generate_subject(self, lead_data: Dict[str, Any]) -> str:
        """
        Generate email subject line based on lead data.

        Args:
            lead_data: Enriched lead data containing company info

        Returns:
            Email subject line
        """
        company = lead_data.get('Company', '').strip()

        if company and company.lower() not in ['not found', 'n/a', 'none', '']:
            return f"{company} x PrezLab - Collaboration"
        else:
            return "Thank you for your interest in PrezLab"

    def generate_email_body(self, lead_data: Dict[str, Any]) -> str:
        """
        Generate email body based on lead data.
        Creates personalized version if company is known, otherwise basic version.

        Args:
            lead_data: Enriched lead data

        Returns:
            Email body text
        """
        full_name = lead_data.get('Full Name', '').strip()
        company = lead_data.get('Company', '').strip()

        # Extract first name from full name
        if full_name:
            # Split by space and take the first part
            first_name = full_name.split()[0] if full_name.split() else full_name
        else:
            first_name = ''

        # Format greeting: "Dear [First Name]" or just "Dear" if no name
        greeting = f"Dear {first_name}" if first_name else "Dear"

        # Check if we have a valid company name
        has_company = company and company.lower() not in ['not found', 'n/a', 'none', '']

        if has_company:
            # Personalized template with company name
            body = f"""{greeting},

Thank you for reaching out to PrezLab. We are excited to connect with you and learn more about your project needs at {company}.

Brief intro about PrezLab - we're a presentation and information design consultancy specializing in presentations, keynotes & events, reports, infographics, videos, branding, and interactive digital experiences. Attached you'll find a brief company profile.

Please let us know if there is a convenient time for a brief call.

Looking forward to hearing from you.

Best regards,"""
        else:
            # Basic template without company
            body = f"""{greeting},

Thank you for reaching out to PrezLab. We are excited to connect with you and learn more about your project needs.

Brief intro about PrezLab - we're a presentation and information design consultancy specializing in presentations, keynotes & events, reports, infographics, videos, branding, and interactive digital experiences. Attached you'll find a brief company profile.

Please let us know if there is a convenient time for a brief call.

Looking forward to hearing from you.

Best regards,"""

        return body

    def generate_draft(self, lead_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate complete email draft with subject and body.

        Args:
            lead_data: Enriched lead data

        Returns:
            Dictionary with 'subject' and 'body' keys
        """
        try:
            subject = self.generate_subject(lead_data)
            body = self.generate_email_body(lead_data)

            return {
                'subject': subject,
                'body': body,
                'has_company': bool(lead_data.get('Company', '').strip() and
                                   lead_data.get('Company', '').strip().lower() not in ['not found', 'n/a', 'none', ''])
            }
        except Exception as e:
            logger.error(f"Error generating email draft: {e}")
            # Return a safe default
            return {
                'subject': 'Thank you for your interest in PrezLab',
                'body': f"""Hello,

Thank you for reaching out to PrezLab. We are excited to connect with you and learn more about your project needs.

Brief intro about PrezLab - we're a presentation and information design consultancy specializing in presentations, keynotes & events, reports, infographics, videos, branding, and interactive digital experiences. Attached you'll find a brief company profile.

Please let us know if there is a convenient time for a brief call.

Looking forward to hearing from you.

Best regards,""",
                'has_company': False
            }
