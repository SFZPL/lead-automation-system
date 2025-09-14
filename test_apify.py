#!/usr/bin/env python3
"""
Test script for Apify LinkedIn integration
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.linkedin_enricher import LinkedInEnricher
from config import Config

def test_apify_integration():
    """Test the Apify integration"""
    print("🔍 Testing Apify LinkedIn Integration")
    print("=" * 50)
    
    # Initialize config
    config = Config()
    
    # Check if Apify token is configured
    if not config.APIFY_API_TOKEN:
        print("❌ APIFY_API_TOKEN not found in environment")
        print("💡 Make sure your .env file contains: APIFY_API_TOKEN=your_token")
        return False
    
    print(f"✅ Apify API Token configured: {config.APIFY_API_TOKEN[:20]}...")
    
    # Initialize LinkedIn enricher
    enricher = LinkedInEnricher(config)
    
    if not enricher.apify_client:
        print("❌ Apify client failed to initialize")
        return False
    
    print("✅ Apify client initialized successfully")
    
    # Test username extraction
    test_urls = [
        "https://linkedin.com/in/sarptecimer",
        "https://www.linkedin.com/in/sarptecimer/",
        "https://linkedin.com/in/sarptecimer?param=value"
    ]
    
    print("\n🔍 Testing LinkedIn URL parsing:")
    for url in test_urls:
        username = enricher._extract_linkedin_username(url)
        print(f"  URL: {url}")
        print(f"  Username: {username}")
        print()
    
    # Test actual enrichment (optional - comment out if you want to save API calls)
    test_enrichment = input("🤔 Do you want to test actual LinkedIn enrichment? (y/N): ").strip().lower()
    
    if test_enrichment == 'y':
        print("\n🚀 Testing LinkedIn profile enrichment...")
        try:
            result = enricher.enrich_linkedin_profile("https://linkedin.com/in/sarptecimer")
            if result:
                print("✅ LinkedIn enrichment successful!")
                print("📊 Sample data keys:", list(result.keys())[:5])
            else:
                print("⚠️  No data returned (might be normal depending on profile)")
        except Exception as e:
            print(f"❌ LinkedIn enrichment failed: {e}")
    
    print("\n🎉 Apify integration test completed!")
    return True

if __name__ == "__main__":
    test_apify_integration()