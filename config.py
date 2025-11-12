import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _env_list(name: str, default: Optional[List[str]] = None) -> List[str]:
    value = os.getenv(name)
    if value is None:
        return list(default) if default else []
    return [item.strip() for item in value.split(',') if item.strip()]


class Config:
    """Minimal configuration for Perplexity-assisted lead enrichment."""

    # Odoo connection details
    ODOO_URL = os.getenv("ODOO_URL", "https://prezlab-staging-22061821.dev.odoo.com")
    ODOO_DB = os.getenv("ODOO_DB", "prezlab-staging-22061821")
    ODOO_USERNAME = os.getenv("ODOO_USERNAME")
    ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")
    ODOO_INSECURE_SSL = _env_bool("ODOO_INSECURE_SSL", True)

    # Lead ownership filter
    SALESPERSON_NAME = os.getenv("SALESPERSON_NAME", "Dareen Fuqaha")

    # Apollo configuration
    APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
    APOLLO_BASE_URL = os.getenv("APOLLO_BASE_URL", "https://api.apollo.io/api/v1")
    APOLLO_PAGE_SIZE = _env_int("APOLLO_PAGE_SIZE", 25)
    APOLLO_MAX_PAGES = _env_int("APOLLO_MAX_PAGES", 4)
    APOLLO_LOOKBACK_HOURS = _env_int("APOLLO_LOOKBACK_HOURS", 72)
    APOLLO_NO_ANSWER_DISPOSITIONS = _env_list(
        "APOLLO_NO_ANSWER_DISPOSITIONS",
        ["no answer", "no_answer", "missed"],
    )
    APOLLO_API_KEY_IN_BODY = _env_bool("APOLLO_API_KEY_IN_BODY", True)

    # Post-contact automation
    POST_CONTACT_MAX_CALLS = _env_int("POST_CONTACT_MAX_CALLS", 20)
    POST_CONTACT_LOOKBACK_HOURS = _env_int("POST_CONTACT_LOOKBACK_HOURS", 72)

    # Maqsam transcription service
    MAQSAM_API_KEY = os.getenv("MAQSAM_API_KEY")
    MAQSAM_BASE_URL = os.getenv("MAQSAM_BASE_URL", "https://api.maqsam.com")
    MAQSAM_TIMEOUT = _env_int("MAQSAM_TIMEOUT", 30)
    MAQSAM_CALL_ID_KEYS = _env_list(
        "MAQSAM_CALL_ID_KEYS",
        ["maqsam_call_id", "integration_call_id", "call_uuid", "external_id", "id"],
    )

    # Email dispatch configuration
    EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST")
    EMAIL_SMTP_PORT = _env_int("EMAIL_SMTP_PORT", 587)
    EMAIL_SMTP_USERNAME = os.getenv("EMAIL_SMTP_USERNAME")
    EMAIL_SMTP_PASSWORD = os.getenv("EMAIL_SMTP_PASSWORD")
    EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS")
    EMAIL_USE_TLS = _env_bool("EMAIL_SMTP_USE_TLS", True)

    # Follow-up email defaults
    FOLLOWUP_VALUE_PROP = os.getenv(
        "FOLLOWUP_VALUE_PROP",
        "show you how PrezLab helps teams ship on-brand creative faster without adding headcount.",
    )
    FOLLOWUP_CALENDAR_LINK = os.getenv("FOLLOWUP_CALENDAR_LINK")
    FOLLOWUP_SENDER_TITLE = os.getenv("FOLLOWUP_SENDER_TITLE")
    FOLLOWUP_SENDER_EMAIL = os.getenv("FOLLOWUP_SENDER_EMAIL")
    FOLLOWUP_PROPOSED_SLOT = os.getenv(
        "FOLLOWUP_PROPOSED_SLOT",
        "tomorrow at 10:00 AM (your local time)",
    )

    # OpenAI / LLM
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    LLM_SCRAPE_MAX_TOKENS = _env_int("LLM_SCRAPE_MAX_TOKENS", 32000)
    LLM_SCRAPE_TEMPERATURE = _env_float("LLM_SCRAPE_TEMPERATURE", 1.0)

    # Perplexity API
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
    PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
    PERPLEXITY_API_BASE = os.getenv("PERPLEXITY_API_BASE", "https://api.perplexity.ai")

    # Lost lead analysis
    LOST_LEAD_MAX_NOTES = _env_int("LOST_LEAD_MAX_NOTES", 12)
    LOST_LEAD_MAX_EMAILS = _env_int("LOST_LEAD_MAX_EMAILS", 8)
    LOST_LEAD_ANALYSIS_SUMMARY_LENGTH = _env_int("LOST_LEAD_ANALYSIS_SUMMARY_LENGTH", 64000)

    # Microsoft Outlook/Email OAuth2
    MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
    MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
    MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/outlook/callback")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3002")
    EMAIL_SEARCH_DAYS_BACK = _env_int("EMAIL_SEARCH_DAYS_BACK", 180)
    EMAIL_SEARCH_LIMIT_PER_LEAD = _env_int("EMAIL_SEARCH_LIMIT_PER_LEAD", 10)

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

        if not cls.APOLLO_API_KEY:
            warnings.append("APOLLO_API_KEY not set. Apollo follow-up workflow will be disabled.")

        if not cls.MAQSAM_API_KEY:
            warnings.append("MAQSAM_API_KEY not set. Answered-call transcription upload will be skipped.")

        if not cls.EMAIL_SMTP_HOST or not cls.EMAIL_SMTP_USERNAME:
            warnings.append("Email SMTP credentials missing. Follow-up emails will run in dry-run mode.")

        if not cls.OPENAI_API_KEY:
            warnings.append("OPENAI_API_KEY not set. LLM-driven analyses will be disabled.")

        return {
            "errors": errors,
            "warnings": warnings,
            "valid": len(errors) == 0,
        }

