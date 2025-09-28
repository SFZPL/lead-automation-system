import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Minimal configuration for Perplexity-assisted lead enrichment."""

    # Odoo connection details
    ODOO_URL = os.getenv("ODOO_URL", "https://prezlab-staging-22061821.dev.odoo.com")
    ODOO_DB = os.getenv("ODOO_DB", "prezlab-staging-22061821")
    ODOO_USERNAME = os.getenv("ODOO_USERNAME")
    ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")
    ODOO_INSECURE_SSL = os.getenv("ODOO_INSECURE_SSL", "1").lower() in ("1", "true", "yes")

    # Lead ownership filter
    SALESPERSON_NAME = os.getenv("SALESPERSON_NAME", "Dareen Fuqaha")

    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """Validate required configuration values."""
        errors = []
        warnings = []

        if not cls.ODOO_USERNAME:
            errors.append("ODOO_USERNAME is required")
        if not cls.ODOO_PASSWORD:
            errors.append("ODOO_PASSWORD is required")
        if not cls.ODOO_URL:
            errors.append("ODOO_URL is required")
        if not cls.ODOO_DB:
            errors.append("ODOO_DB is required")

        if cls.ODOO_INSECURE_SSL:
            warnings.append("SSL verification disabled for Odoo (ODOO_INSECURE_SSL). Ensure this is intentional.")

        return {
            "errors": errors,
            "warnings": warnings,
            "valid": len(errors) == 0,
        }
