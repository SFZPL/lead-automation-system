"""
Seed script to load PDF documents from knowledge_base/ folder into Supabase.

Run this script to populate the knowledge base with PDFs stored in the repo.
This ensures PDFs are version-controlled and automatically loaded in all environments.

Usage:
    python scripts/seed_knowledge_base.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from api.supabase_client import SupabaseClient
import PyPDF2


def extract_pdf_text(pdf_path: str) -> str:
    """Extract text content from a PDF file."""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        text_content = ""
        for page in pdf_reader.pages:
            text_content += page.extract_text() + "\n"
    return text_content.strip()


def seed_knowledge_base():
    """Load all PDFs from knowledge_base/ folder into Supabase."""
    supabase = SupabaseClient()

    if not supabase.is_connected():
        print("[ERROR] Failed to connect to Supabase")
        return

    # Path to knowledge_base folder
    kb_folder = Path(__file__).parent.parent / "knowledge_base"

    if not kb_folder.exists():
        print(f"[ERROR] Knowledge base folder not found: {kb_folder}")
        print("   Create the folder and add PDF files to seed the knowledge base")
        return

    # Get all PDF files
    pdf_files = list(kb_folder.glob("*.pdf"))

    if not pdf_files:
        print(f"[WARNING] No PDF files found in {kb_folder}")
        return

    print(f"[INFO] Found {len(pdf_files)} PDF(s) to process")
    print()

    # Get existing documents to avoid duplicates
    try:
        existing = supabase.client.table("knowledge_base_documents")\
            .select("filename")\
            .eq("is_active", True)\
            .execute()
        existing_filenames = {doc["filename"] for doc in existing.data}
    except Exception as e:
        print(f"[WARNING] Could not check existing documents: {e}")
        existing_filenames = set()

    # Process each PDF
    for pdf_path in pdf_files:
        filename = pdf_path.name

        # Skip if already exists
        if filename in existing_filenames:
            print(f"[SKIP] {filename} (already exists)")
            continue

        print(f"[PROCESSING] {filename}...")

        try:
            # Extract text
            text_content = extract_pdf_text(str(pdf_path))

            if not text_content:
                print(f"   [WARNING] No text extracted from {filename}")
                continue

            # Get file size
            file_size = pdf_path.stat().st_size

            # Insert into Supabase
            # Use system user ID (1) as uploader for seeded documents
            result = supabase.client.table("knowledge_base_documents").insert({
                "filename": filename,
                "file_size": file_size,
                "content": text_content,
                "description": f"Auto-loaded from knowledge_base folder",
                "uploaded_by_user_id": 1,  # System/admin user
                "is_active": True
            }).execute()

            if result.data:
                char_count = len(text_content)
                print(f"   [SUCCESS] Uploaded successfully ({char_count:,} characters)")
            else:
                print(f"   [ERROR] Failed to upload")

        except Exception as e:
            print(f"   [ERROR] Error processing {filename}: {e}")

    print()
    print("[DONE] Knowledge base seeding complete!")


if __name__ == "__main__":
    seed_knowledge_base()
