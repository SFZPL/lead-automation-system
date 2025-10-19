"""
Perplexity API Client for lead enrichment
"""
import logging
import requests
from typing import Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)


class PerplexityClient:
    """Client for interacting with Perplexity AI API"""

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.api_key = self.config.PERPLEXITY_API_KEY
        self.model = self.config.PERPLEXITY_MODEL
        self.api_base = self.config.PERPLEXITY_API_BASE

        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not set. Perplexity enrichment will not work.")

    def search(self, prompt: str, max_tokens: int = 4096) -> Optional[str]:
        """
        Send a search query to Perplexity API

        Args:
            prompt: The search query/prompt
            max_tokens: Maximum tokens in response

        Returns:
            The response content from Perplexity, or None if error
        """
        if not self.api_key:
            logger.error("Cannot make Perplexity API call: API key not configured")
            return None

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional researcher. Your task is to enrich lead data by searching LinkedIn and professional sources. ALWAYS provide data in the requested format. If information is not found, write 'Not Found' - never refuse or explain limitations. Focus on finding and presenting the data."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,  # Lower temperature for more consistent formatting
            "top_p": 0.9,
            "search_domain_filter": ["linkedin.com"],  # Prioritize LinkedIn
            "return_images": False,
            "return_related_questions": False,
            "search_recency_filter": "month",  # Focus on recent data
            "top_k": 0,
            "stream": False,
            "presence_penalty": 0,
            "frequency_penalty": 1
        }

        try:
            logger.info(f"Sending request to Perplexity API with model: {self.model}")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()

            data = response.json()

            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                logger.info(f"Received response from Perplexity ({len(content)} characters)")
                return content
            else:
                logger.error(f"Unexpected Perplexity API response format: {data}")
                return None

        except requests.exceptions.Timeout:
            logger.error("Perplexity API request timed out")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"Perplexity API HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Perplexity API error: {str(e)}")
            return None

    def enrich_lead(self, lead_data: Dict[str, Any], enrichment_prompt: str) -> Optional[str]:
        """
        Enrich a single lead using Perplexity API

        Args:
            lead_data: Dictionary containing lead information
            enrichment_prompt: The formatted prompt for this specific lead

        Returns:
            Enrichment results as formatted text, or None if error
        """
        logger.info(f"Enriching lead: {lead_data.get('Full Name', 'Unknown')}")
        return self.search(enrichment_prompt, max_tokens=4096)
