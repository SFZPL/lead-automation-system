import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around OpenAI's chat/completions API."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        if not self.config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required for LLM operations.")

        self.client = OpenAI(
            api_key=self.config.OPENAI_API_KEY,
            base_url=self.config.OPENAI_API_BASE,
        )
        self.model = self.config.OPENAI_MODEL

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute a chat completion and return the content of the first choice."""
        model_lower = self.model.lower()

        params: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        # Some models (o1, o3, gpt-5) don't support custom temperature parameter
        if not any(x in model_lower for x in ["o1-", "o3-", "gpt-5"]):
            params["temperature"] = temperature if temperature is not None else self.config.LLM_SCRAPE_TEMPERATURE

        # Use max_completion_tokens for newer models (gpt-4o, gpt-5, o1, o3 series)
        if max_tokens is not None:
            # Newer models require max_completion_tokens instead of max_tokens
            if any(x in model_lower for x in ["gpt-4o", "gpt-5", "o1-", "o3-"]):
                params["max_completion_tokens"] = max_tokens
            else:
                params["max_tokens"] = max_tokens

        if response_format:
            params["response_format"] = response_format

        try:
            response = self.client.chat.completions.create(**params)
        except Exception as exc:
            logger.error("LLM chat completion failed: %s", exc)
            raise

        choice = response.choices[0]
        content = choice.message.content if choice.message else None
        if not content:
            logger.error("LLM response missing content: %s", response)
            raise RuntimeError("LLM response missing content")
        return content

    def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Request a JSON-formatted response and parse it."""
        raw = self.chat_completion(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM response not valid JSON; returning raw text.")
            return {"raw_text": raw}

