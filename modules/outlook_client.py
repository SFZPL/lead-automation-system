"""Microsoft Outlook/Graph API client for email search."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import requests

from config import Config

logger = logging.getLogger(__name__)


class OutlookClient:
    """Client for searching emails via Microsoft Graph API."""

    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    AUTH_BASE = "https://login.microsoftonline.com/common/oauth2/v2.0"

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.client_id = self.config.MICROSOFT_CLIENT_ID
        self.client_secret = self.config.MICROSOFT_CLIENT_SECRET
        self.redirect_uri = self.config.MICROSOFT_REDIRECT_URI

    def get_authorization_url(self, state: str) -> str:
        """Generate OAuth2 authorization URL for user to grant access."""
        scopes = ["Mail.Read", "User.Read", "offline_access"]
        scope_str = " ".join(scopes)

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": scope_str,
            "state": state,
        }

        query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        return f"{self.AUTH_BASE}/authorize?{query}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens."""
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        response = requests.post(f"{self.AUTH_BASE}/token", data=data)
        response.raise_for_status()
        return response.json()

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token."""
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        response = requests.post(f"{self.AUTH_BASE}/token", data=data)
        response.raise_for_status()
        return response.json()

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get authenticated user's profile information."""
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{self.GRAPH_API_BASE}/me", headers=headers)
        response.raise_for_status()
        return response.json()

    def search_emails(
        self,
        access_token: str,
        query: str,
        folder: str = "inbox",
        limit: int = 25,
        days_back: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search emails using Microsoft Graph API.

        Args:
            access_token: OAuth2 access token
            query: Search query (e.g., contact name, company, email address)
            folder: Email folder to search (default: inbox)
            limit: Maximum number of results
            days_back: Only search emails from last N days

        Returns:
            List of email message dictionaries
        """
        headers = {"Authorization": f"Bearer {access_token}"}

        # Build search filter
        search_params = f"$search=\"{query}\""
        params = [search_params, f"$top={limit}"]

        # Add date filter if specified
        if days_back:
            cutoff = datetime.utcnow() - timedelta(days=days_back)
            date_filter = f"receivedDateTime ge {cutoff.isoformat()}Z"
            params.append(f"$filter={date_filter}")

        # Select specific fields to reduce payload
        select_fields = [
            "id", "subject", "from", "toRecipients", "ccRecipients",
            "receivedDateTime", "bodyPreview", "hasAttachments",
            "importance", "conversationId"
        ]
        params.append(f"$select={','.join(select_fields)}")

        query_string = "&".join(params)
        endpoint = f"{self.GRAPH_API_BASE}/me/mailFolders/{folder}/messages"
        url = f"{endpoint}?{query_string}"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("value", [])
        except requests.HTTPError as e:
            logger.error(f"Error searching emails: {e}")
            if e.response.status_code == 401:
                raise RuntimeError("Access token expired. Please refresh token.")
            raise

    def search_emails_for_lead(
        self,
        access_token: str,
        lead_data: Dict[str, Any],
        limit: int = 10,
        days_back: int = 180,
    ) -> List[Dict[str, Any]]:
        """
        Search emails related to a specific lead/opportunity.

        Args:
            access_token: OAuth2 access token
            lead_data: Lead information from Odoo
            limit: Maximum emails to return per query
            days_back: Search window in days

        Returns:
            List of relevant email messages
        """
        queries = []

        # Build search queries from lead data
        if lead_data.get("email_from"):
            queries.append(lead_data["email_from"])

        if lead_data.get("partner_name"):
            queries.append(lead_data["partner_name"])

        if lead_data.get("contact_name"):
            queries.append(lead_data["contact_name"])

        # Search for each query
        all_emails = []
        seen_ids = set()

        for query in queries[:3]:  # Limit to 3 queries to avoid rate limits
            try:
                emails = self.search_emails(
                    access_token=access_token,
                    query=query,
                    limit=limit,
                    days_back=days_back,
                )

                # Deduplicate by email ID
                for email in emails:
                    email_id = email.get("id")
                    if email_id and email_id not in seen_ids:
                        seen_ids.add(email_id)
                        all_emails.append(email)

                if len(all_emails) >= limit:
                    break

            except Exception as e:
                logger.warning(f"Error searching for '{query}': {e}")
                continue

        # Sort by date (newest first) and limit
        all_emails.sort(key=lambda x: x.get("receivedDateTime", ""), reverse=True)
        return all_emails[:limit]

    def format_email_for_analysis(self, email: Dict[str, Any]) -> Dict[str, str]:
        """Format Graph API email response for LLM analysis."""
        from_address = email.get("from", {}).get("emailAddress", {})
        from_name = from_address.get("name", "Unknown")
        from_email = from_address.get("address", "")

        received = email.get("receivedDateTime", "")
        if received:
            try:
                dt = datetime.fromisoformat(received.replace("Z", "+00:00"))
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_date = received
        else:
            formatted_date = "Unknown date"

        return {
            "id": email.get("id"),
            "date": received,
            "formatted_date": formatted_date,
            "author": f"{from_name} <{from_email}>" if from_email else from_name,
            "subject": email.get("subject", "No subject"),
            "body": email.get("bodyPreview", ""),
        }
