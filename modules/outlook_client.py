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
        """Generate OAuth2 authorization URL for user to grant access (includes Teams permissions)."""
        scopes = [
            "Mail.Read",           # Read emails
            "User.Read",           # Read user profile
            "User.Read.All",       # Read all users (for Teams member list)
            "Group.Read.All",      # Read groups/teams
            "TeamMember.Read.All", # Read team members
            "Chat.ReadWrite",      # Send Teams chat messages
            "offline_access"       # Refresh tokens
        ]
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
            group = next((g for g in groups if g.get("mail") and g.get("mail").lower() == group_email.lower()), None)

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

                                # Construct webLink for group conversation
                                # Format: https://outlook.office.com/mail/group_email/inbox/id/conversation_id
                                web_link = f"https://outlook.office.com/mail/{group_email}/inbox/id/{conv_id}"

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
                                    "webLink": web_link,
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

    def search_group_emails_for_contact(
        self,
        access_token: str,
        group_email: str,
        contact_emails: List[str],
        days_back: int = 90,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for emails in a Microsoft 365 Group related to specific contact email addresses.
        Uses Microsoft Graph search API for efficient querying.

        Args:
            access_token: OAuth2 access token
            group_email: Email address of the group (e.g., engage@prezlab.com)
            contact_emails: List of email addresses to search for (lead, partner, contact emails)
            days_back: Number of days to look back
            limit: Maximum number of emails to return

        Returns:
            List of email messages
        """
        try:
            # Filter out empty/None emails
            valid_emails = [e.strip() for e in contact_emails if e and e.strip()]
            if not valid_emails:
                logger.warning("No valid contact emails provided for search")
                return []

            headers = {"Authorization": f"Bearer {access_token}"}

            # Find the group by email
            groups = self.get_user_groups(access_token)
            group = next((g for g in groups if g.get("mail") and g.get("mail").lower() == group_email.lower()), None)

            if not group:
                logger.error(f"Group not found with email: {group_email}")
                return []

            group_id = group["id"]
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            cutoff_str = cutoff_date.strftime("%Y-%m-%dT%H:%M:%SZ")

            all_emails = []
            seen_ids = set()

            # Search for each contact email
            for contact_email in valid_emails[:3]:  # Limit to first 3 emails to avoid too many requests
                logger.info(f"Searching group emails for contact: {contact_email}")

                # Use $search parameter to find emails with this participant
                # Note: $search works on various fields including from, to, cc, subject, body
                url = f"{self.GRAPH_API_BASE}/groups/{group_id}/conversations"
                params = {
                    "$top": 25,
                    "$orderby": "lastDeliveredDateTime desc"
                }

                try:
                    response = requests.get(url, headers=headers, params=params, timeout=60)
                    response.raise_for_status()
                    data = response.json()
                    conversations = data.get("value", [])

                    for conv in conversations:
                        conv_id = conv.get("id")
                        if not conv_id or conv_id in seen_ids:
                            continue

                        # Check date
                        last_delivered = conv.get("lastDeliveredDateTime")
                        if last_delivered:
                            delivered_dt = datetime.fromisoformat(last_delivered.replace("Z", "+00:00"))
                            if delivered_dt < cutoff_date:
                                continue

                        # Fetch threads to get actual email content
                        try:
                            threads_url = f"{self.GRAPH_API_BASE}/groups/{group_id}/conversations/{conv_id}/threads"
                            threads_response = requests.get(threads_url, headers=headers, timeout=30)
                            threads_response.raise_for_status()
                            threads = threads_response.json().get("value", [])

                            for thread in threads:
                                thread_id = thread.get("id")
                                if not thread_id:
                                    continue

                                # Fetch posts (actual emails)
                                posts_url = f"{self.GRAPH_API_BASE}/groups/{group_id}/conversations/{conv_id}/threads/{thread_id}/posts"
                                posts_response = requests.get(posts_url, headers=headers, timeout=30)
                                posts_response.raise_for_status()
                                posts = posts_response.json().get("value", [])

                                for post in posts:
                                    post_id = post.get("id")
                                    if post_id in seen_ids:
                                        continue

                                    # Check if this email involves the contact
                                    from_addr = post.get("from", {}).get("emailAddress", {}).get("address", "").lower()
                                    recipients_list = post.get("toRecipients", []) + post.get("ccRecipients", [])
                                    to_addrs = [r.get("emailAddress", {}).get("address", "").lower() for r in recipients_list]
                                    subject = post.get("subject", "")
                                    body = post.get("body", {}).get("content", "")

                                    # Check if contact email appears in from or to
                                    contact_lower = contact_email.lower()
                                    if contact_lower in from_addr or any(contact_lower in addr for addr in to_addrs):
                                        received_dt_str = post.get("receivedDateTime", "")
                                        received_dt = None
                                        if received_dt_str:
                                            try:
                                                received_dt = datetime.fromisoformat(received_dt_str.replace("Z", "+00:00"))
                                            except:
                                                pass

                                        email_msg = {
                                            "id": post_id,
                                            "subject": subject,
                                            "from": from_addr,
                                            "to": ", ".join(to_addrs),
                                            "body": body,
                                            "date": received_dt_str,
                                            "formatted_date": received_dt.strftime("%b %d, %Y %I:%M %p") if received_dt else ""
                                        }

                                        all_emails.append(email_msg)
                                        seen_ids.add(post_id)

                                        if len(all_emails) >= limit:
                                            break

                                if len(all_emails) >= limit:
                                    break

                        except Exception as e:
                            logger.warning(f"Error fetching thread/posts: {e}")
                            continue

                        seen_ids.add(conv_id)

                        if len(all_emails) >= limit:
                            break

                except Exception as e:
                    logger.warning(f"Error searching for {contact_email}: {e}")
                    continue

                if len(all_emails) >= limit:
                    break

            logger.info(f"Found {len(all_emails)} emails for contacts: {', '.join(valid_emails)}")
            return all_emails[:limit]

        except Exception as exc:
            logger.error(f"Error searching group emails: {exc}")
            return []

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

    def send_email_with_attachment(
        self,
        access_token: str,
        to: List[str],
        subject: str,
        body: str,
        attachment_path: str,
        attachment_name: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """
        Send an email with a file attachment using Microsoft Graph API.

        Args:
            access_token: Valid access token
            to: List of recipient email addresses
            subject: Email subject
            body: Email body (HTML supported)
            attachment_path: Path to the file to attach
            attachment_name: Name to give the attachment in the email
            cc: List of CC email addresses (optional)
            bcc: List of BCC email addresses (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        import base64
        import os

        try:
            # Read and encode the attachment
            if not os.path.exists(attachment_path):
                logger.error(f"Attachment file not found: {attachment_path}")
                return False

            with open(attachment_path, 'rb') as f:
                attachment_content = base64.b64encode(f.read()).decode('utf-8')

            # Get file size
            file_size = os.path.getsize(attachment_path)

            url = f"{self.GRAPH_API_BASE}/me/sendMail"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Build recipients
            to_recipients = [{"emailAddress": {"address": email}} for email in to]
            cc_recipients = [{"emailAddress": {"address": email}} for email in (cc or [])]
            bcc_recipients = [{"emailAddress": {"address": email}} for email in (bcc or [])]

            # Build message with attachment
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body
                    },
                    "toRecipients": to_recipients,
                    "attachments": [
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": attachment_name,
                            "contentType": "application/pdf",
                            "contentBytes": attachment_content
                        }
                    ]
                }
            }

            if cc_recipients:
                message["message"]["ccRecipients"] = cc_recipients

            if bcc_recipients:
                message["message"]["bccRecipients"] = bcc_recipients

            response = requests.post(url, headers=headers, json=message)
            response.raise_for_status()

            logger.info(f"Email with attachment sent successfully to {', '.join(to)}")
            return True

        except requests.exceptions.HTTPError as exc:
            logger.error(f"Error sending email with attachment: {exc}")
            if exc.response.status_code == 401:
                raise RuntimeError("Access token expired. Please refresh token.")
            raise
        except Exception as exc:
            logger.error(f"Unexpected error sending email with attachment: {exc}")
            return False

    def send_reply(
        self,
        access_token: str,
        conversation_id: str,
        reply_body: str,
        subject: str,
        reply_to_message_id: Optional[str] = None
    ) -> bool:
        """
        Send a reply email in a specific conversation thread.

        Args:
            access_token: Microsoft Graph API access token
            conversation_id: The conversation ID to reply in
            reply_body: HTML body of the reply
            subject: Email subject
            reply_to_message_id: Specific message ID to reply to (if None, replies to latest in thread)

        Returns:
            True if reply sent successfully, False otherwise
        """
        try:
            # If no specific message ID provided, get the latest message from the conversation
            if not reply_to_message_id:
                # Find the latest message in this conversation
                messages = self.get_group_conversations(
                    access_token=access_token,
                    group_id=None,  # Will use default engage group
                    days_back=90
                )

                # Find message in this conversation
                for msg in messages:
                    if msg.get("conversationId") == conversation_id:
                        reply_to_message_id = msg.get("id")
                        break

                if not reply_to_message_id:
                    logger.error(f"No message found for conversation {conversation_id}")
                    return False

            # Use the reply endpoint
            url = f"{self.GRAPH_API_BASE}/me/messages/{reply_to_message_id}/reply"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            message = {
                "comment": reply_body
            }

            response = requests.post(url, headers=headers, json=message)
            response.raise_for_status()

            logger.info(f"Reply sent successfully to conversation {conversation_id}")
            return True

        except requests.exceptions.HTTPError as exc:
            logger.error(f"Error sending reply: {exc}")
            if exc.response.status_code == 401:
                raise RuntimeError("Access token expired. Please refresh token.")
            raise
        except Exception as exc:
            logger.error(f"Unexpected error sending reply: {exc}")
            return False

    def get_user_auth_tokens(self, user_identifier: str, token_store=None, db=None) -> Optional[Dict[str, Any]]:
        """
        Get authenticated user's Outlook tokens with auto-refresh.
        Reads from database first (persistent), then falls back to file system.

        Args:
            user_identifier: User identifier (email or user ID)
            token_store: EmailTokenStore instance (will create if not provided)
            db: Database instance (will try to import if not provided)

        Returns:
            Dictionary with access_token, refresh_token, etc., or None if not authenticated
        """
        from datetime import datetime, timedelta

        tokens = None

        # Try to get tokens from database first (persistent across deployments)
        if db is None:
            try:
                from api.supabase_database import SupabaseDatabase
                db = SupabaseDatabase()
                logger.info(f"✅ Successfully loaded Supabase database for token retrieval")
            except Exception as e:
                logger.error(f"❌ Could not load database: {e}")

        if db is not None:
            try:
                # user_identifier is the user ID (as string)
                user_id = int(user_identifier) if user_identifier.isdigit() else None
                if user_id:
                    logger.info(f"🔍 Attempting to retrieve Outlook tokens from database for user {user_id}")
                    settings = db.get_user_settings(user_id)
                    outlook_tokens = settings.get("outlook_tokens")

                    if outlook_tokens:
                        logger.info(f"✅ Found Outlook tokens in database for user {user_id}")
                    else:
                        logger.warning(f"⚠️ No Outlook tokens found in database for user {user_id}")

                    if outlook_tokens and isinstance(outlook_tokens, dict):
                        # Check if token is expired
                        expires_at_str = outlook_tokens.get("expires_at")
                        is_expired = True

                        if expires_at_str:
                            try:
                                expires_at = datetime.fromisoformat(expires_at_str)
                                is_expired = datetime.utcnow() >= (expires_at - timedelta(minutes=5))
                            except:
                                pass

                        # If expired, refresh it
                        if is_expired and outlook_tokens.get("refresh_token"):
                            logger.info(f"Access token expired for user {user_identifier}, refreshing from database...")
                            try:
                                refresh_token = outlook_tokens.get("refresh_token")
                                token_response = self.refresh_access_token(refresh_token)
                                new_access_token = token_response.get("access_token")
                                expires_in = token_response.get("expires_in", 3600)

                                # Update database
                                new_expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
                                outlook_tokens["access_token"] = new_access_token
                                outlook_tokens["expires_at"] = new_expires_at
                                outlook_tokens["updated_at"] = datetime.utcnow().isoformat()

                                db.update_user_settings(
                                    user_id=user_id,
                                    outlook_tokens=outlook_tokens
                                )

                                logger.info(f"Successfully refreshed access token from database for user {user_identifier}")
                                return outlook_tokens
                            except Exception as e:
                                logger.error(f"Failed to refresh token from database: {e}")
                        else:
                            logger.info(f"Using valid tokens from database for user {user_identifier}")
                            return outlook_tokens
            except Exception as e:
                logger.warning(f"Error reading tokens from database: {e}")

        # Fall back to file system (legacy/backwards compatibility)
        if token_store is None:
            from modules.email_token_store import EmailTokenStore
            token_store = EmailTokenStore()

        tokens = token_store.get_tokens(user_identifier)
        if not tokens:
            logger.warning(f"No tokens found for user: {user_identifier}")
            return None

        # Check if token is expired and refresh if needed
        if token_store.is_token_expired(user_identifier):
            logger.info(f"Access token expired for {user_identifier}, refreshing from file system...")
            try:
                refresh_token = tokens.get("refresh_token")
                if not refresh_token:
                    logger.error("No refresh token available")
                    return None

                # Refresh the token
                token_response = self.refresh_access_token(refresh_token)
                new_access_token = token_response.get("access_token")
                expires_in = token_response.get("expires_in", 3600)

                # Update stored token
                token_store.update_access_token(user_identifier, new_access_token, expires_in)

                # Update tokens dict with new access token
                tokens["access_token"] = new_access_token
                logger.info(f"Successfully refreshed access token from file system for {user_identifier}")

            except Exception as e:
                logger.error(f"Failed to refresh token for {user_identifier}: {e}")
                return None

        return tokens

    def get_conversation_messages(
        self,
        access_token: str,
        conversation_id: str,
        limit: int = 50,
        shared_mailbox: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all messages in a conversation thread.

        Args:
            access_token: OAuth2 access token
            conversation_id: Conversation ID to fetch messages for
            limit: Maximum number of messages to return
            shared_mailbox: Email address of shared mailbox to search (default: user's mailbox)

        Returns:
            List of message dictionaries sorted by date (oldest first)
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}

            # Determine which mailbox to search
            if shared_mailbox:
                # Search in shared mailbox
                url = f"{self.GRAPH_API_BASE}/users/{shared_mailbox}/messages"
                logger.info(f"Searching shared mailbox: {shared_mailbox}")
            else:
                # Search in user's personal mailbox
                url = f"{self.GRAPH_API_BASE}/me/messages"
                logger.info(f"Searching personal mailbox")

            params = {
                "$top": 250,  # Fetch more to ensure we get the full conversation
                "$orderby": "receivedDateTime desc",
                "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,bodyPreview,hasAttachments,importance,conversationId,webLink"
            }

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            all_messages = data.get("value", [])

            logger.info(f"Fetched {len(all_messages)} total messages from mailbox")
            logger.info(f"Looking for conversation ID: {conversation_id}")

            # Log first few conversation IDs to debug
            if all_messages:
                logger.info(f"Sample conversation IDs: {[msg.get('conversationId') for msg in all_messages[:3]]}")

            # Filter messages by conversation ID client-side
            messages = [msg for msg in all_messages if msg.get("conversationId") == conversation_id]

            # Sort by date (oldest first)
            messages.sort(key=lambda x: x.get("receivedDateTime", ""))

            # Limit results
            messages = messages[:limit]

            logger.info(f"Fetched {len(messages)} messages for conversation {conversation_id}")
            return messages

        except requests.exceptions.HTTPError as exc:
            logger.error(f"Error fetching conversation messages: {exc}")
            if exc.response.status_code == 401:
                raise RuntimeError("Access token expired. Please refresh token.")
            # For other HTTP errors, log the response content for debugging
            try:
                error_detail = exc.response.json()
                logger.error(f"Graph API error detail: {error_detail}")
            except:
                pass
            raise
        except Exception as exc:
            logger.error(f"Unexpected error fetching conversation messages: {exc}")
            return []

    # ============================================================================
    # TEAMS INTEGRATION METHODS
    # ============================================================================

    def get_organization_users(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Get all users in the organization (Azure AD directory).

        Args:
            access_token: OAuth2 access token with User.Read.All permission

        Returns:
            List of user dictionaries with id, displayName, email
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            url = f"{self.GRAPH_API_BASE}/users"
            params = {
                "$select": "id,displayName,mail,userPrincipalName",
                "$top": 999  # Get up to 999 users (max per page)
            }

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            users = data.get("value", [])

            # Format users for easier consumption
            formatted_users = []
            for user in users:
                user_id = user.get("id")
                display_name = user.get("displayName", "Unknown")
                email = user.get("mail") or user.get("userPrincipalName", "")

                if user_id and display_name:
                    formatted_users.append({
                        "id": user_id,
                        "name": display_name,
                        "email": email
                    })

            logger.info(f"Found {len(formatted_users)} users in organization")
            return formatted_users

        except requests.exceptions.HTTPError as exc:
            logger.error(f"Error fetching organization users: {exc}")
            if exc.response.status_code == 401:
                raise RuntimeError("Access token expired or insufficient permissions")
            elif exc.response.status_code == 403:
                raise RuntimeError("Insufficient permissions to read users. Please re-authorize with User.Read.All permission")
            raise
        except Exception as exc:
            logger.error(f"Unexpected error fetching organization users: {exc}")
            return []

    def send_teams_chat_message(
        self,
        access_token: str,
        user_id: str,
        message_text: str,
        message_html: Optional[str] = None
    ) -> bool:
        """
        Send a 1:1 chat message to a user in Microsoft Teams.

        Args:
            access_token: OAuth2 access token with Chat.ReadWrite permission
            user_id: Microsoft user ID (Azure AD user ID)
            message_text: Plain text message content
            message_html: Optional HTML formatted message

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Step 1: Get current user ID (sender)
            me_response = requests.get(f"{self.GRAPH_API_BASE}/me", headers=headers, timeout=30)
            me_response.raise_for_status()
            me_data = me_response.json()
            my_user_id = me_data.get("id")

            # Step 2: Create or get existing 1:1 chat with the user
            # Must include both sender and recipient in members array
            chat_payload = {
                "chatType": "oneOnOne",
                "members": [
                    {
                        "@odata.type": "#microsoft.graph.aadUserConversationMember",
                        "roles": ["owner"],
                        "user@odata.bind": f"{self.GRAPH_API_BASE}/users/{my_user_id}"
                    },
                    {
                        "@odata.type": "#microsoft.graph.aadUserConversationMember",
                        "roles": ["owner"],
                        "user@odata.bind": f"{self.GRAPH_API_BASE}/users/{user_id}"
                    }
                ]
            }

            create_chat_url = f"{self.GRAPH_API_BASE}/chats"
            chat_response = requests.post(create_chat_url, headers=headers, json=chat_payload, timeout=30)
            chat_response.raise_for_status()
            chat_data = chat_response.json()
            chat_id = chat_data.get("id")

            if not chat_id:
                logger.error("Failed to create/get chat")
                return False

            logger.info(f"Created/got chat with ID: {chat_id}")

            # Step 3: Send message to the chat
            message_body = {
                "contentType": "html" if message_html else "text",
                "content": message_html or message_text
            }

            message_payload = {
                "body": message_body
            }

            send_message_url = f"{self.GRAPH_API_BASE}/chats/{chat_id}/messages"
            message_response = requests.post(send_message_url, headers=headers, json=message_payload, timeout=30)
            message_response.raise_for_status()

            logger.info(f"Teams message sent successfully to user {user_id}")
            return True

        except requests.exceptions.HTTPError as exc:
            logger.error(f"Error sending Teams message: {exc}")
            if exc.response.status_code == 401:
                raise RuntimeError("Access token expired or insufficient permissions")
            elif exc.response.status_code == 403:
                raise RuntimeError("Insufficient permissions to send chat messages. Please re-authorize with Chat.ReadWrite permission")
            try:
                error_detail = exc.response.json()
                logger.error(f"Teams API error detail: {error_detail}")
            except:
                pass
            return False
        except Exception as exc:
            logger.error(f"Unexpected error sending Teams message: {exc}")
            return False

    def send_lead_assignment_notification(
        self,
        access_token: str,
        assignee_user_id: str,
        assignee_name: str,
        lead_subject: str,
        lead_email: str,
        lead_company: Optional[str] = None,
        notes: Optional[str] = None,
        app_url: Optional[str] = None
    ) -> bool:
        """
        Send a formatted lead assignment notification via Teams chat.

        Args:
            access_token: OAuth2 access token
            assignee_user_id: Microsoft user ID of person being assigned
            assignee_name: Display name of assignee
            lead_subject: Subject/title of the lead
            lead_email: Contact email for the lead
            lead_company: Company name (optional)
            notes: Additional notes (optional)
            app_url: URL to view lead in app (optional)

        Returns:
            True if notification sent successfully
        """
        # Build HTML message with structured format
        message_html = f"""
<h2>🔔 New Lead Assigned to You</h2>
<p>Hi {assignee_name},</p>
<p>You've been assigned a new lead:</p>
<ul>
<li><strong>Subject:</strong> {lead_subject}</li>
<li><strong>Contact:</strong> {lead_email}</li>
"""

        if lead_company:
            message_html += f"<li><strong>Company:</strong> {lead_company}</li>\n"

        if notes:
            message_html += f"<li><strong>Summary:</strong> {notes}</li>\n"

        message_html += "</ul>\n"

        if app_url:
            message_html += f'<p><a href="{app_url}">View in Lead Hub</a></p>\n'

        message_html += "<p>Please follow up at your earliest convenience.</p>"

        # Send the message
        return self.send_teams_chat_message(
            access_token=access_token,
            user_id=assignee_user_id,
            message_text=f"New lead assigned: {lead_subject}",
            message_html=message_html
        )
