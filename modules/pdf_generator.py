"""PDF Generator for NDA/Contract auto-filling."""

import io
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

logger = logging.getLogger(__name__)

# Prezlab Entity Information
PREZLAB_ENTITIES = {
    "dubai": {
        "name": "Dubai",
        "company_name": "Prezlab FZ - LLC",
        "company_address": "A503, Fifth Floor, Building 1, Dubai Design District, Dubai, United Arab Emirates",
        "authorised_signatory": "Mai Awawdeh",
    },
    "abu_dhabi": {
        "name": "Abu Dhabi",
        "company_name": "Prezlab Digital Design Firm LLC",
        "company_address": "Al Danah, E 11 Abu Dhabi, United Arab Emirates",
        "authorised_signatory": "Zaid Abualfailat",
    },
    "riyadh": {
        "name": "Riyadh",
        "company_name": "Prezlab Advanced Design Company",
        "company_address": "3141 Anas Ibn Malik St, 8292 Almalqa District, Riyadh, Saudi Arabia",
        "authorised_signatory": "Zaid Abualfailat",
    },
}


def get_entity_info(entity_key: str) -> Optional[Dict[str, str]]:
    """Get entity information by key."""
    return PREZLAB_ENTITIES.get(entity_key)


def get_all_entities() -> Dict[str, Dict[str, str]]:
    """Get all available entities."""
    return PREZLAB_ENTITIES


class PDFGenerator:
    """Generate PDFs with auto-filled entity information."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='DocumentTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=30,
            textColor=colors.HexColor('#1a365d'),
        ))

        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#2d3748'),
        ))

        # Override existing BodyText style
        self.styles['BodyText'].fontSize = 11
        self.styles['BodyText'].alignment = TA_JUSTIFY
        self.styles['BodyText'].spaceAfter = 12
        self.styles['BodyText'].leading = 16

        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#718096'),
        ))

    def generate_nda_cover_page(
        self,
        entity_key: str,
        counterparty_name: str = "",
        document_title: str = "NON-DISCLOSURE AGREEMENT",
        additional_info: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Generate an NDA cover page with entity information filled in.

        Args:
            entity_key: The Prezlab entity key (dubai, abu_dhabi, riyadh)
            counterparty_name: Name of the other party
            document_title: Title of the document
            additional_info: Any additional information to include

        Returns:
            PDF bytes
        """
        entity = get_entity_info(entity_key)
        if not entity:
            raise ValueError(f"Unknown entity: {entity_key}")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1*inch,
            leftMargin=1*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )

        story = []

        # Title
        story.append(Paragraph(document_title, self.styles['DocumentTitle']))
        story.append(Spacer(1, 30))

        # Date
        current_date = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(f"<b>Date:</b> {current_date}", self.styles['BodyText']))
        story.append(Spacer(1, 20))

        # Parties Section
        story.append(Paragraph("PARTIES", self.styles['SectionTitle']))

        # Prezlab Entity Info
        story.append(Paragraph("<b>DISCLOSING PARTY:</b>", self.styles['BodyText']))

        prezlab_info = f"""
        <b>Company Name:</b> {entity['company_name']}<br/>
        <b>Address:</b> {entity['company_address']}<br/>
        <b>Authorised Signatory:</b> {entity['authorised_signatory']}
        """
        story.append(Paragraph(prezlab_info, self.styles['BodyText']))
        story.append(Spacer(1, 20))

        # Counterparty Info (if provided)
        if counterparty_name:
            story.append(Paragraph("<b>RECEIVING PARTY:</b>", self.styles['BodyText']))
            story.append(Paragraph(f"<b>Company Name:</b> {counterparty_name}", self.styles['BodyText']))
        else:
            story.append(Paragraph("<b>RECEIVING PARTY:</b> _______________________", self.styles['BodyText']))

        story.append(Spacer(1, 30))

        # Signature Section
        story.append(Paragraph("SIGNATURES", self.styles['SectionTitle']))

        # Create signature table
        sig_data = [
            ['For and on behalf of:', 'For and on behalf of:'],
            [entity['company_name'], counterparty_name or '_______________________'],
            ['', ''],
            ['_______________________', '_______________________'],
            ['Signature', 'Signature'],
            ['', ''],
            [entity['authorised_signatory'], '_______________________'],
            ['Name', 'Name'],
            ['', ''],
            ['_______________________', '_______________________'],
            ['Date', 'Date'],
        ]

        sig_table = Table(sig_data, colWidths=[3*inch, 3*inch])
        sig_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ]))

        story.append(sig_table)

        # Footer
        story.append(Spacer(1, 50))
        story.append(Paragraph(
            f"Generated by PrezLab Lead Automation System on {current_date}",
            self.styles['SmallText']
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def generate_filled_contract_info(
        self,
        entity_key: str,
        counterparty_name: str = "",
        project_name: str = "",
        additional_info: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Generate a contract information sheet with entity details.

        Args:
            entity_key: The Prezlab entity key
            counterparty_name: Name of the other party
            project_name: Name of the project
            additional_info: Additional details

        Returns:
            PDF bytes
        """
        entity = get_entity_info(entity_key)
        if not entity:
            raise ValueError(f"Unknown entity: {entity_key}")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1*inch,
            leftMargin=1*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )

        story = []

        # Title
        story.append(Paragraph("CONTRACT INFORMATION SHEET", self.styles['DocumentTitle']))
        story.append(Spacer(1, 20))

        # Date
        current_date = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(f"<b>Generated:</b> {current_date}", self.styles['SmallText']))
        story.append(Spacer(1, 20))

        # Entity Information Table
        story.append(Paragraph("PREZLAB ENTITY INFORMATION", self.styles['SectionTitle']))

        entity_data = [
            ['Field', 'Value'],
            ['Entity Location', entity['name']],
            ['Legal Company Name', entity['company_name']],
            ['Registered Address', entity['company_address']],
            ['Authorised Signatory', entity['authorised_signatory']],
        ]

        entity_table = Table(entity_data, colWidths=[2*inch, 4*inch])
        entity_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))

        story.append(entity_table)
        story.append(Spacer(1, 30))

        # Counterparty Section
        if counterparty_name or project_name:
            story.append(Paragraph("PROJECT DETAILS", self.styles['SectionTitle']))

            project_data = [['Field', 'Value']]
            if counterparty_name:
                project_data.append(['Client/Counterparty', counterparty_name])
            if project_name:
                project_data.append(['Project Name', project_name])
            if additional_info:
                for key, value in additional_info.items():
                    project_data.append([key, str(value)])

            project_table = Table(project_data, colWidths=[2*inch, 4*inch])
            project_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ]))

            story.append(project_table)

        # Footer
        story.append(Spacer(1, 50))
        story.append(Paragraph(
            "This information sheet was auto-generated upon document approval.",
            self.styles['SmallText']
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()


# Singleton instance
_pdf_generator = None


def get_pdf_generator() -> PDFGenerator:
    """Get or create the PDF generator singleton."""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFGenerator()
    return _pdf_generator
