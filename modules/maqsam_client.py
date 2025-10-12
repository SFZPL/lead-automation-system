import logging
from typing import Any, Dict, Optional

import requests

from config import Config

logger = logging.getLogger(__name__)


class MaqsamClient:
    """Simple client for retrieving Maqsam call transcriptions."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: Optional[int] = None,
        config: Optional[Config] = None,
    ) -> None:
        self.config = config or Config()
        self.api_key = api_key or self.config.MAQSAM_API_KEY
        self.base_url = (base_url or self.config.MAQSAM_BASE_URL).rstrip("/")
        self.timeout = timeout or self.config.MAQSAM_TIMEOUT
        self.session = session or requests.Session()
        if self.api_key:
            self.session.headers.setdefault("Authorization", f"Bearer {self.api_key}")
        self.session.headers.setdefault("Accept", "application/json")

    def _build_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    def get_transcription(self, call_id: str) -> Optional[str]:
        """Fetch transcription text for a Maqsam call id."""
        if not call_id:
            return None

        if not self.api_key:
            logger.debug("Maqsam API key missing; skipping transcription fetch.")
            return None

        url = self._build_url(f"/calls/{call_id}/transcription")
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to fetch Maqsam transcription for %s: %s", call_id, exc)
            return None

        return self._extract_transcription(response)

    @staticmethod
    def _extract_transcription(response: requests.Response) -> Optional[str]:
        content_type = response.headers.get("Content-Type", "").lower()
        text: Optional[str] = None

        if "application/json" in content_type:
            try:
                payload: Any = response.json()
            except ValueError:
                payload = None

            if isinstance(payload, dict):
                text = MaqsamClient._extract_from_dict(payload)
            elif isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        text = MaqsamClient._extract_from_dict(item)
                        if text:
                            break
        else:
            text = response.text

        if text:
            cleaned = text.strip()
            return cleaned or None
        return None

    @staticmethod
    def _extract_from_dict(data: Dict[str, Any]) -> Optional[str]:
        candidates = [
            data.get("transcription"),
            data.get("transcript"),
            data.get("text"),
            data.get("body"),
            data.get("content"),
        ]
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value
        return None

