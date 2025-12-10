"""AI-powered PDF filler that intelligently identifies and fills blank fields."""

import io
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch

from config import Config
from modules.pdf_generator import PREZLAB_ENTITIES, get_entity_info

logger = logging.getLogger(__name__)


@dataclass
class FillLocation:
    """Represents a location in the PDF where text should be filled."""
    page: int
    x: float
    y: float
    field_type: str  # e.g., "company_name", "address", "signatory", "date"
    value: str
    font_size: float = 10
    width: Optional[float] = None  # Max width for text wrapping


@dataclass
class PDFTextBlock:
    """Represents a text block extracted from PDF with position info."""
    text: str
    x0: float
    y0: float  # Bottom of text
    x1: float
    y1: float  # Top of text
    page: int


class AIPDFFiller:
    """Uses AI to identify fillable locations in PDFs and fills them."""

    def __init__(self, openai_client=None):
        self.openai_client = openai_client

    def extract_text_with_positions(self, pdf_bytes: bytes) -> Tuple[List[PDFTextBlock], Dict[str, Any]]:
        """
        Extract text blocks with their positions from a PDF.

        Returns:
            Tuple of (text_blocks, page_info)
        """
        text_blocks = []
        page_info = {"pages": [], "total_pages": 0}

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page_info["total_pages"] = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages):
                page_data = {
                    "page_number": page_num,
                    "width": page.width,
                    "height": page.height,
                }
                page_info["pages"].append(page_data)

                # Extract words with positions
                words = page.extract_words(
                    keep_blank_chars=True,
                    x_tolerance=3,
                    y_tolerance=3,
                )

                for word in words:
                    text_blocks.append(PDFTextBlock(
                        text=word["text"],
                        x0=word["x0"],
                        y0=word["bottom"],
                        x1=word["x1"],
                        y1=word["top"],
                        page=page_num,
                    ))

        return text_blocks, page_info

    def build_document_context(self, text_blocks: List[PDFTextBlock], page_info: Dict) -> str:
        """Build a text representation of the document for AI analysis."""
        context_parts = []

        for page_num in range(page_info["total_pages"]):
            page_blocks = [b for b in text_blocks if b.page == page_num]
            page_data = page_info["pages"][page_num]

            context_parts.append(f"\n=== PAGE {page_num + 1} (size: {page_data['width']:.0f}x{page_data['height']:.0f}) ===\n")

            # Sort by y position (top to bottom), then x (left to right)
            page_blocks.sort(key=lambda b: (-b.y1, b.x0))

            current_line_y = None
            current_line = []

            for block in page_blocks:
                # Group blocks into lines (within 5 units of y)
                if current_line_y is None or abs(block.y1 - current_line_y) > 5:
                    if current_line:
                        line_text = " ".join([b.text for b in current_line])
                        y_pos = current_line[0].y1
                        x_pos = current_line[0].x0
                        context_parts.append(f"[y={y_pos:.0f}, x={x_pos:.0f}] {line_text}")
                    current_line = [block]
                    current_line_y = block.y1
                else:
                    current_line.append(block)

            # Don't forget the last line
            if current_line:
                line_text = " ".join([b.text for b in current_line])
                y_pos = current_line[0].y1
                x_pos = current_line[0].x0
                context_parts.append(f"[y={y_pos:.0f}, x={x_pos:.0f}] {line_text}")

        return "\n".join(context_parts)

    def identify_fill_locations(
        self,
        pdf_bytes: bytes,
        entity_key: str,
        counterparty_name: Optional[str] = None,
    ) -> List[FillLocation]:
        """
        Use AI to identify where entity information should be filled in the PDF.

        Args:
            pdf_bytes: The PDF file bytes
            entity_key: Which Prezlab entity to use (dubai, abu_dhabi, riyadh)
            counterparty_name: Optional name of the other party

        Returns:
            List of FillLocation objects
        """
        if not self.openai_client:
            raise ValueError("OpenAI client required for AI-powered fill")

        entity = get_entity_info(entity_key)
        if not entity:
            raise ValueError(f"Unknown entity: {entity_key}")

        # Extract text with positions
        text_blocks, page_info = self.extract_text_with_positions(pdf_bytes)
        document_context = self.build_document_context(text_blocks, page_info)

        # Build the prompt for the AI
        prompt = f"""You are analyzing an NDA/contract document to identify where company information should be filled in.

ENTITY INFORMATION TO FILL:
- Company Name: {entity['company_name']}
- Company Address: {entity['company_address']}
- Authorised Signatory: {entity['authorised_signatory']}
{f"- Counterparty Name: {counterparty_name}" if counterparty_name else ""}

DOCUMENT TEXT WITH POSITIONS:
Each line shows [y=vertical_position, x=horizontal_position] followed by the text.
Higher y values are at the top of the page.

{document_context}

TASK:
Identify locations in this document where the entity information should be filled. Look for:
1. Blank lines after labels like "Company Name:", "Party A:", "Address:", "Name:", "Signature:"
2. Underscores or dotted lines (_____, ......) indicating fill areas
3. Placeholder text like "[Company Name]", "[Address]", "PARTY A"
4. Areas near "Disclosing Party", "Service Provider", "First Party" etc.

For each fill location, provide:
- page: Page number (0-indexed)
- x: Horizontal position (use the x coordinate from nearby text as reference)
- y: Vertical position (use y coordinate, but adjust DOWN by ~15 for blank lines below labels)
- field_type: One of "company_name", "company_address", "authorised_signatory", "counterparty_name", "date"
- font_size: Recommended font size (usually 10-12)

Return a JSON array of fill locations. Only include locations where you're confident text should be filled.
If the document already has the company info filled in, return an empty array.

Example response:
[
  {{"page": 0, "x": 72, "y": 650, "field_type": "company_name", "font_size": 11}},
  {{"page": 0, "x": 72, "y": 620, "field_type": "company_address", "font_size": 10}}
]

IMPORTANT:
- Be conservative - only identify clear fill locations
- The y coordinate in PDFs goes from bottom (0) to top
- When you see a label like "Company Name:" at y=700, the fill area is typically at y=685 or so (below it)
- Return ONLY the JSON array, no other text"""

        try:
            # Use config model (gpt-5-mini) with higher token limit
            config = Config()
            model = config.OPENAI_MODEL or "gpt-5-mini"

            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a document analysis expert. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=4000,
            )

            response_text = response.choices[0].message.content.strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            locations_data = json.loads(response_text)

            # Convert to FillLocation objects and add values
            fill_locations = []
            for loc in locations_data:
                field_type = loc.get("field_type", "")

                # Determine the value based on field type
                if field_type == "company_name":
                    value = entity["company_name"]
                elif field_type == "company_address":
                    value = entity["company_address"]
                elif field_type == "authorised_signatory":
                    value = entity["authorised_signatory"]
                elif field_type == "counterparty_name" and counterparty_name:
                    value = counterparty_name
                elif field_type == "date":
                    from datetime import datetime
                    value = datetime.now().strftime("%B %d, %Y")
                else:
                    continue  # Skip unknown field types

                fill_locations.append(FillLocation(
                    page=loc.get("page", 0),
                    x=loc.get("x", 72),
                    y=loc.get("y", 700),
                    field_type=field_type,
                    value=value,
                    font_size=loc.get("font_size", 10),
                    width=loc.get("width"),
                ))

            logger.info(f"AI identified {len(fill_locations)} fill locations")
            return fill_locations

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Response was: {response_text[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error in AI fill location identification: {e}")
            raise

    def create_overlay_pdf(
        self,
        fill_locations: List[FillLocation],
        page_sizes: List[Tuple[float, float]],
    ) -> bytes:
        """
        Create a PDF with text at the specified fill locations.

        Args:
            fill_locations: List of locations to fill
            page_sizes: List of (width, height) tuples for each page

        Returns:
            PDF bytes of the overlay
        """
        buffer = io.BytesIO()

        # Use the first page size as default
        default_size = page_sizes[0] if page_sizes else A4
        c = canvas.Canvas(buffer, pagesize=default_size)

        # Group locations by page
        locations_by_page = {}
        for loc in fill_locations:
            if loc.page not in locations_by_page:
                locations_by_page[loc.page] = []
            locations_by_page[loc.page].append(loc)

        # Create pages with text
        max_page = max(locations_by_page.keys()) if locations_by_page else 0

        for page_num in range(max_page + 1):
            if page_num < len(page_sizes):
                page_width, page_height = page_sizes[page_num]
            else:
                page_width, page_height = default_size

            c.setPageSize((page_width, page_height))

            if page_num in locations_by_page:
                for loc in locations_by_page[page_num]:
                    c.setFont("Helvetica", loc.font_size)

                    # Handle multi-line text for addresses
                    if loc.width and len(loc.value) > 50:
                        # Simple word wrap
                        words = loc.value.split()
                        lines = []
                        current_line = []
                        for word in words:
                            test_line = " ".join(current_line + [word])
                            if len(test_line) * loc.font_size * 0.5 < loc.width:
                                current_line.append(word)
                            else:
                                if current_line:
                                    lines.append(" ".join(current_line))
                                current_line = [word]
                        if current_line:
                            lines.append(" ".join(current_line))

                        y_offset = 0
                        for line in lines:
                            c.drawString(loc.x, loc.y - y_offset, line)
                            y_offset += loc.font_size + 2
                    else:
                        c.drawString(loc.x, loc.y, loc.value)

            c.showPage()

        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    def merge_pdfs(self, original_pdf: bytes, overlay_pdf: bytes) -> bytes:
        """
        Merge the overlay PDF onto the original PDF.

        Args:
            original_pdf: The original PDF bytes
            overlay_pdf: The overlay PDF with fill text

        Returns:
            Merged PDF bytes
        """
        original_reader = PdfReader(io.BytesIO(original_pdf))
        overlay_reader = PdfReader(io.BytesIO(overlay_pdf))
        writer = PdfWriter()

        for page_num in range(len(original_reader.pages)):
            original_page = original_reader.pages[page_num]

            # Merge overlay if it exists for this page
            if page_num < len(overlay_reader.pages):
                overlay_page = overlay_reader.pages[page_num]
                original_page.merge_page(overlay_page)

            writer.add_page(original_page)

        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        return output_buffer.getvalue()

    def fill_pdf(
        self,
        pdf_bytes: bytes,
        entity_key: str,
        counterparty_name: Optional[str] = None,
    ) -> Tuple[bytes, List[Dict[str, Any]]]:
        """
        Main method to fill a PDF with entity information using AI.

        Args:
            pdf_bytes: The original PDF bytes
            entity_key: Which Prezlab entity to use
            counterparty_name: Optional counterparty name

        Returns:
            Tuple of (filled_pdf_bytes, fill_report)
        """
        # Step 1: Extract text and identify fill locations
        text_blocks, page_info = self.extract_text_with_positions(pdf_bytes)

        # Step 2: Use AI to identify where to fill
        fill_locations = self.identify_fill_locations(
            pdf_bytes, entity_key, counterparty_name
        )

        if not fill_locations:
            logger.info("No fill locations identified - returning original PDF")
            return pdf_bytes, []

        # Step 3: Get page sizes
        page_sizes = [
            (p["width"], p["height"]) for p in page_info["pages"]
        ]

        # Step 4: Create overlay
        overlay_pdf = self.create_overlay_pdf(fill_locations, page_sizes)

        # Step 5: Merge
        filled_pdf = self.merge_pdfs(pdf_bytes, overlay_pdf)

        # Build fill report
        fill_report = [
            {
                "page": loc.page + 1,  # 1-indexed for display
                "field": loc.field_type,
                "value": loc.value,
                "position": {"x": loc.x, "y": loc.y},
            }
            for loc in fill_locations
        ]

        logger.info(f"Successfully filled PDF with {len(fill_locations)} fields")
        return filled_pdf, fill_report


# Singleton instance
_ai_pdf_filler = None


def get_ai_pdf_filler(openai_client=None) -> AIPDFFiller:
    """Get or create the AI PDF filler singleton."""
    global _ai_pdf_filler
    if _ai_pdf_filler is None:
        _ai_pdf_filler = AIPDFFiller(openai_client)
    elif openai_client and _ai_pdf_filler.openai_client is None:
        _ai_pdf_filler.openai_client = openai_client
    return _ai_pdf_filler
