#!/usr/bin/env python3
"""Run database migration to add document_type column to knowledge_base_documents table."""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.supabase_client import get_supabase_client

def run_migration():
    """Run the migration to add document_type column."""
    supabase = get_supabase_client()

    migration_sql = """
    -- Add document_type column to knowledge_base_documents table
    ALTER TABLE knowledge_base_documents
    ADD COLUMN IF NOT EXISTS document_type TEXT DEFAULT 'general';

    -- Update existing records to have 'general' type
    UPDATE knowledge_base_documents
    SET document_type = 'general'
    WHERE document_type IS NULL;
    """

    try:
        # Execute the migration using raw SQL
        print("Running migration to add document_type column...")

        # Note: Supabase Python client doesn't directly support raw SQL execution
        # You need to run this in the Supabase SQL editor or use the PostgREST API
        print("\nPlease run the following SQL in your Supabase SQL Editor:")
        print("=" * 60)
        print(migration_sql)
        print("=" * 60)

        # Alternatively, update existing records using the ORM
        print("\nAlternatively, updating existing records via API...")
        response = supabase.client.table("knowledge_base_documents").select("id").execute()

        if response.data:
            print(f"Found {len(response.data)} existing documents")
            for doc in response.data:
                try:
                    supabase.client.table("knowledge_base_documents").update({
                        "document_type": "general"
                    }).eq("id", doc["id"]).execute()
                    print(f"  Updated document {doc['id']}")
                except Exception as e:
                    print(f"  Error updating document {doc['id']}: {e}")

        print("\nMigration steps completed!")
        print("Please also run the SQL in Supabase SQL Editor to add the column if it doesn't exist.")

    except Exception as e:
        print(f"Error during migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
