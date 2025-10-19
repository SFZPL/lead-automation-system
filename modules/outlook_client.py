"""Microsoft Outlook/Graph API client for email search."""

import logging
from datetime import datetime, timedelta, timezone
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

    def get_authorization_url(self, state: str, force_account_selection: bool = False) -> str:
        """Generate OAuth2 authorization URL for user to grant access."""
        scopes = ["Mail.Read", "User.Read", "Group.Read.All", "offline_access"]
        scope_str = " ".join(scopes)

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": scope_str,
            "state": state,
        }

        # Force account selection for system email authentication
        if force_account_selection:
            params["prompt"] = "select_account"

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

        # Build parameters
        params = [f"$top={limit}"]

        # Add search filter only if query is provided
        if query and query.strip():
            search_params = f"$search=\"{query}\""
            params.insert(0, search_params)

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

    def get_user_groups(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Get all Microsoft 365 groups the user is a member of.

        Args:
            access_token: OAuth2 access token

        Returns:
            List of group objects with id, displayName, mail
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self.GRAPH_API_BASE}/me/memberOf/microsoft.graph.group"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            groups = data.get("value", [])
            logger.info(f"Found {len(groups)} groups")
            return groups
        except requests.exceptions.HTTPError as exc:
            logger.error(f"Error fetching groups: {exc}")
            if exc.response.status_code == 401:
                raise RuntimeError("Access token expired. Please refresh token.")
            raise

    def get_group_conversations(
        self,
        access_token: str,
        group_email: str,
        days_back: int = 7,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get email conversations from a Microsoft 365 Group using threads/posts model.

        Args:
            access_token: OAuth2 access token
            group_email: Email address of the group (e.g., engage@prezlab.com)
            days_back: Number of days to look back
            limit: Maximum number of conversations to return

        Returns:
            List of email messages formatted similar to search_emails
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}

            # Step 1: Find the group by email
            groups = self.get_user_groups(access_token)
            group = next((g for g in groups if g.get("mail", "").lower() == group_email.lower()), None)

            if not group:
                logger.error(f"Group not found with email: {group_email}")
                return []

            group_id = group["id"]
            logger.info(f"Found group {group_email} with ID {group_id}")

            # Step 2: Calculate date filter
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

            # Step 3: Fetch conversations - use simple endpoint without complex OData queries
            # The threads endpoint doesn't support $filter/$orderby/$expand properly
            url = f"{self.GRAPH_API_BASE}/groups/{group_id}/conversations"
            params = {
                "$top": 50  # Fetch in smaller batches
            }

            all_emails = []
            page_count = 0
            max_pages = 30  # Limit to prevent infinite loops

            while len(all_emails) < limit and page_count < max_pages:
                page_count += 1
                logger.info(f"📥 Fetching conversations page {page_count}")

                response = requests.get(url, headers=headers, params=params, timeout=60)
                response.raise_for_status()
                data = response.json()
                conversations = data.get("value", [])

                logger.info(f"✅ Got {len(conversations)} conversations on page {page_count}")

                if not conversations:
                    logger.info("❌ No more conversations found")
                    break

                # Process each conversation
                conv_processed = 0
                conv_skipped = 0
                for idx, conv in enumerate(conversations, 1):
                    conv_id = conv.get("id")
                    conv_topic = conv.get("topic", "No Subject")

                    # Check date filter
                    last_delivered = conv.get("lastDeliveredDateTime")
                    if last_delivered:
                        try:
                            delivered_dt = datetime.fromisoformat(last_delivered.replace("Z", "+00:00"))
                            if delivered_dt < cutoff_date:
                                logger.debug(f"⏭️  Skipping old conversation {idx}/{len(conversations)}: '{conv_topic}' (delivered: {last_delivered})")
                                conv_skipped += 1
                                continue  # Skip old conversations
                        except Exception as e:
                            logger.debug(f"⚠️  Could not parse date for conversation: {e}")
                            pass  # Include if can't parse date

                    logger.info(f"🔍 Processing conversation {idx}/{len(conversations)}: '{conv_topic[:50]}...' (ID: {conv_id[:20]}...)")

                    # Fetch threads for this conversation
                    threads_url = f"{self.GRAPH_API_BASE}/groups/{group_id}/conversations/{conv_id}/threads"

                    try:
                        logger.debug(f"   → Fetching threads from: {threads_url}")
                        threads_response = requests.get(threads_url, headers=headers, timeout=30)
                        threads_response.raise_for_status()
                        threads_data = threads_response.json()
                        threads = threads_data.get("value", [])

                        logger.info(f"   ✅ Found {len(threads)} thread(s)")

                        # Get first thread's posts
                        if threads:
                            thread = threads[0]
                            thread_id = thread.get("id")
                            posts_url = f"{self.GRAPH_API_BASE}/groups/{group_id}/threads/{thread_id}/posts"

                            logger.debug(f"   → Fetching posts from: {posts_url}")
                            posts_response = requests.get(posts_url, headers=headers, timeout=30)
                            posts_response.raise_for_status()
                            posts_data = posts_response.json()
                            posts = posts_data.get("value", [])

                            logger.info(f"   ✅ Found {len(posts)} post(s)")

                            # Add ALL posts from the thread, not just the first one
                            for post in posts:
                                # Extract sender info
                                from_data = post.get("from", {})
                                sender_name = from_data.get("emailAddress", {}).get("name", "Unknown")
                                sender_email = from_data.get("emailAddress", {}).get("address", "")

                                logger.debug(f"   📧 Post from: {sender_name} <{sender_email}>")

                                # Format as email message
                                email_msg = {
                                    "id": post.get("id", conv_id),
                                    "subject": conv.get("topic", "No Subject"),
                                    "from": {
                                        "emailAddress": {
                                            "name": sender_name,
                                            "address": sender_email
                                        }
                                    },
                                    "receivedDateTime": post.get("receivedDateTime") or post.get("createdDateTime"),
                                    "bodyPreview": conv.get("preview", ""),
                                    "body": post.get("body", {}),
                                    "hasAttachments": conv.get("hasAttachments", False),
                                    "conversationId": conv_id,
                                    "toRecipients": [],
                                    "ccRecipients": [],
                                    "importance": "normal"
                                }

                                all_emails.append(email_msg)

                            conv_processed += 1
                            logger.info(f"   ✅ Added {len(posts)} posts to results (total: {len(all_emails)}/{limit})")

                            if len(all_emails) >= limit:
                                logger.info(f"🎯 Reached limit of {limit} emails")
                                break
                        else:
                            logger.warning(f"   ⚠️  No threads found for conversation")
                    except Exception as e:
                        logger.warning(f"   ❌ Error fetching thread/posts for conversation {conv_id}: {e}")
                        continue

                logger.info(f"📊 Page {page_count} summary: {conv_processed} processed, {conv_skipped} skipped, {len(all_emails)} total collected")

                if len(all_emails) >= limit:
                    break

                # Check for next page
                next_link = data.get("@odata.nextLink")
                if not next_link:
                    logger.info("No next page link")
                    break

                url = next_link
                params = {}

            logger.info(f"Found {len(all_emails)} emails from {group_email} ({page_count} pages)")
            return all_emails[:limit]

        except Exception as exc:
            logger.error(f"Error fetching group conversations: {exc}")
            raise

    def send_email(
        self,
        access_token: str,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """
        Send an email using Microsoft Graph API.

        Args:
            access_token: Valid access token
            to: List of recipient email addresses
            subject: Email subject
            body: Email body (HTML supported)
            cc: List of CC email addresses (optional)
            bcc: List of BCC email addresses (optional)
            reply_to: Reply-to email address (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            url = f"{self.GRAPH_API_BASE}/me/sendMail"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Build recipients
            to_recipients = [{"emailAddress": {"address": email}} for email in to]
            cc_recipients = [{"emailAddress": {"address": email}} for email in (cc or [])]
            bcc_recipients = [{"emailAddress": {"address": email}} for email in (bcc or [])]

            # Build message
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body
                    },
                    "toRecipients": to_recipients,
                }
            }

            if cc_recipients:
                message["message"]["ccRecipients"] = cc_recipients

            if bcc_recipients:
                message["message"]["bccRecipients"] = bcc_recipients

            if reply_to:
                message["message"]["replyTo"] = [{"emailAddress": {"address": reply_to}}]

            response = requests.post(url, headers=headers, json=message)
            response.raise_for_status()

            logger.info(f"Email sent successfully to {', '.join(to)}")
            return True

        except requests.exceptions.HTTPError as exc:
            logger.error(f"Error sending email: {exc}")
            if exc.response.status_code == 401:
                raise RuntimeError("Access token expired. Please refresh token.")
            raise
        except Exception as exc:
            logger.error(f"Unexpected error sending email: {exc}")
            return False
