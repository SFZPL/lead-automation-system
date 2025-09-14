import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration management for the lead automation system"""
    
    # Odoo Configuration
    ODOO_URL = os.getenv('ODOO_URL', 'https://prezlab-staging-22061821.dev.odoo.com')
    ODOO_DB = os.getenv('ODOO_DB', 'prezlab-staging-22061821')
    ODOO_USERNAME = os.getenv('ODOO_USERNAME')
    ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')
    ODOO_INSECURE_SSL = os.getenv('ODOO_INSECURE_SSL', '1').lower() in ('1', 'true', 'yes')
    
    # Google Sheets Configuration
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', './google_service_account.json')
    GSHEET_SPREADSHEET_ID = os.getenv('GSHEET_SPREADSHEET_ID')
    GSHEET_SPREADSHEET_TITLE = os.getenv('GSHEET_SPREADSHEET_TITLE', 'Lead Automation System')
    GSHEET_WORKSHEET_TITLE = os.getenv('GSHEET_WORKSHEET_TITLE', 'Leads')
    GSHEET_SHARE_WITH = os.getenv('GSHEET_SHARE_WITH')
    
    # Apify Configuration
    APIFY_API_TOKEN = os.getenv('APIFY_API_TOKEN')
    
    # Web Scraping Configuration
    USER_AGENT = os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    USE_LLM_SCRAPING = os.getenv('USE_LLM_SCRAPING', '0').lower() in ('1', 'true', 'yes')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5-mini')
    LLM_SCRAPE_MAX_TOKENS = int(os.getenv('LLM_SCRAPE_MAX_TOKENS', '800'))
    LLM_SCRAPE_TEMPERATURE = float(os.getenv('LLM_SCRAPE_TEMPERATURE', '0.2'))
    
    # Lead Processing Configuration
    SALESPERSON_NAME = os.getenv('SALESPERSON_NAME', 'Dareen Fuqaha')
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50'))
    MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '5'))
    
    # Headers for all columns in the sheet
    SHEET_HEADERS = [
        'Full Name',
        'Company Name', 
        'LinkedIn Link',
        'Company Size',
        'Industry',
        'Company Revenue Estimated',
        'Job Role',
        'Company year EST',
        'Phone',
        'Salesperson',
        'Quality (Out of 5)',
        'Enriched'
    ]
    
    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """Validate required configuration values"""
        errors = []
        warnings = []
        
        # Check required Odoo settings
        if not cls.ODOO_USERNAME:
            errors.append("ODOO_USERNAME is required")
        if not cls.ODOO_PASSWORD:
            errors.append("ODOO_PASSWORD is required")
            
        # Check Google Sheets settings
        if not os.path.exists(cls.GOOGLE_SERVICE_ACCOUNT_FILE):
            warnings.append(f"Google service account file not found: {cls.GOOGLE_SERVICE_ACCOUNT_FILE}")
            
        # Check Apify settings
        if not cls.APIFY_API_TOKEN:
            warnings.append("APIFY_API_TOKEN not set - LinkedIn enrichment will be disabled")

        # Check LLM scraping settings
        if cls.USE_LLM_SCRAPING:
            if not cls.OPENAI_API_KEY:
                errors.append("OPENAI_API_KEY is required when USE_LLM_SCRAPING is enabled")
            if not cls.OPENAI_MODEL:
                warnings.append("OPENAI_MODEL not set - using default 'gpt-5.1-mini'")
            
        return {
            'errors': errors,
            'warnings': warnings,
            'valid': len(errors) == 0
        }