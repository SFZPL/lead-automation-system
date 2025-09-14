import json
from typing import Dict, Any
from dataclasses import dataclass

from config import Config

try:
    # OpenAI SDK v1+ style import; adjust if your environment differs
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


@dataclass
class ExtractionResult:
    website: str
    company_name: str
    company_size: str
    industry: str
    revenue_estimate: str
    company_year_est: str
    description: str


class LLMExtractor:
    """LLM-powered extractor that turns raw HTML into normalized company info."""

    def __init__(self, config: Config = None):
        self.config = config or Config()
        if OpenAI is None:
            raise RuntimeError("OpenAI client not available. Install openai and ensure compatibility.")
        if not self.config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required for LLM extraction.")
        self.client = OpenAI(api_key=self.config.OPENAI_API_KEY)

    def extract_company_info(self, html_text: str, website_url: str = "", company_name_hint: str = "") -> Dict[str, Any]:
        if not html_text or len(html_text.strip()) == 0:
            return {}

        system = (
            "You are a data extraction engine. Parse provided website HTML and return a minimal JSON "
            "object with fields: company_size, industry, revenue_estimate, company_year_est, description. "
            "Only infer from content; do not hallucinate. Prefer explicit values found in the HTML. "
            "If unknown, return an empty string."
        )

        user = (
            f"Website URL: {website_url}\n"
            f"Company name hint: {company_name_hint}\n"
            "\nHTML:\n" + html_text[:120000]  # guard token usage
        )

        try:
            response = self.client.chat.completions.create(
                model=self.config.OPENAI_MODEL,
                temperature=self.config.LLM_SCRAPE_TEMPERATURE,
                max_tokens=self.config.LLM_SCRAPE_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            normalized = {
                "website": website_url,
                "company_name": company_name_hint,
                "company_size": str(data.get("company_size", "")),
                "industry": str(data.get("industry", "")),
                "revenue_estimate": str(data.get("revenue_estimate", "")),
                "company_year_est": str(data.get("company_year_est", "")),
                "description": str(data.get("description", "")),
            }
            return normalized
        except Exception:
            return {}


