import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from email.utils import parseaddr

from config import Config
from modules.llm_client import LLMClient
from modules.odoo_client import OdooClient
from modules.outlook_client import OutlookClient
from modules.email_token_store import EmailTokenStore

logger = logging.getLogger(__name__)


def _strip_html(value: Optional[str]) -> str:
    """Remove HTML tags from text."""
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _format_datetime(value: Optional[str]) -> str:
    """Format datetime string."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def _extract_email(address: str) -> str:
    """Extract email address from 'Name <email>' format."""
    _, email = parseaddr(address)
    return email.lower() if email else address.lower()


class ProposalFollowupAnalyzer:
    """Analyze email threads from engage inbox for proposal follow-ups."""

    # Keywords that indicate a proposal/quotation was sent
    PROPOSAL_KEYWORDS = [
        "proposal", "quotation", "quote", "pricing", "estimate",
        "attached proposal", "our proposal", "the proposal"
    ]

    def __init__(
        self,
        config: Optional[Config] = None,
        odoo_client: Optional[OdooClient] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.config = config or Config()
        self.odoo = odoo_client or OdooClient(self.config)
        self.llm = llm_client or LLMClient(self.config)
        self.token_store = EmailTokenStore()

    def _ensure_odoo_connection(self) -> None:
        """Ensure Odoo client is connected."""
        if self.odoo.session is None:
            if not self.odoo.connect():
                raise RuntimeError("Failed to connect to Odoo")

    def get_engage_emails(
        self,
        user_identifier: str,
        days_back: int = 7,
        group_name: str = "engage"
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from the engage group.

        Args:
            user_identifier: Email address of the engage monitoring account
            days_back: Number of days to look back
            group_name: Name of the Microsoft 365 group (default: "engage")

        Returns:
            List of email messages with their metadata
        """
        tokens = self.token_store.get_tokens(user_identifier)
        if not tokens:
            raise ValueError(f"No tokens found for {user_identifier}")

        outlook = OutlookClient(self.config)

        # First, find the engage group
        groups = outlook.get_user_groups(tokens['access_token'])
        engage_group = None
        for group in groups:
            display_name = group.get("displayName")
            mail = group.get("mail")

            # Handle None values
            if display_name:
                display_name = display_name.lower()
            else:
                display_name = ""

            if mail:
                mail = mail.lower()
            else:
                mail = ""

            if group_name.lower() in display_name or group_name.lower() in mail:
                engage_group = group
                logger.info(f"Found engage group: {group.get('displayName')} (ID: {group.get('id')})")
                break

        if not engage_group:
            logger.warning(f"Could not find group matching '{group_name}'. Available groups: {[g.get('displayName') for g in groups]}")
            raise ValueError(f"Could not find group matching '{group_name}'")

        # Fetch emails from the group
        emails = outlook.get_group_conversations(
            access_token=tokens['access_token'],
            group_email=engage_group['mail'],
            days_back=days_back,
            limit=200
        )

        logger.info(f"Found {len(emails)} emails in engage group from past {days_back} days")
        return emails

    def _is_internal_email(self, email: str) -> bool:
        """Check if email is from prezlab domain."""
        return email.endswith("@prezlab.com")

    def _contains_proposal_keywords(self, subject: str, body: str) -> bool:
        """Check if email contains proposal/quotation keywords."""
        combined_text = f"{subject} {body}".lower()
        return any(keyword in combined_text for keyword in self.PROPOSAL_KEYWORDS)

    def _has_proposal_attachment(self, attachments: List[Dict[str, Any]]) -> bool:
        """Check if email has proposal-related attachments."""
        if not attachments:
            return False

        for attachment in attachments:
            name = attachment.get("name", "").lower()
            if any(keyword in name for keyword in ["proposal", "quote", "quotation", "pricing"]):
                return True
        return False

    def _classify_as_lead(self, subject: str, body: str, external_email: str) -> Dict[str, Any]:
        """
        Use AI to classify if an email thread is a potential lead or noise.

        Returns:
            Dict with is_lead (bool), confidence (float), category (str)
        """
        prompt = f"""Classify this email as either a LEAD (potential business opportunity) or NOISE (job application, spam, newsletter, etc).

Subject: {subject}
From: {external_email}
Preview: {body[:300]}

Respond in JSON format:
{{
  "is_lead": true/false,
  "confidence": 0.0-1.0,
  "category": "lead|job_application|newsletter|event_invitation|supplier|recruitment|spam|other"
}}

A LEAD is: client inquiry, partnership opportunity, sales opportunity, project request, proposal request.
NOISE is: job applications, recruitment, newsletters, ads, automated notifications, supplier solicitations."""

        try:
            messages = [
                {"role": "system", "content": "You are an expert at classifying business emails."},
                {"role": "user", "content": prompt}
            ]

            result = self.llm.chat_completion_json(
                messages,
                max_tokens=64000,  # High limit for reasoning models
                temperature=0.3
            )

            return result
        except Exception as e:
            logger.warning(f"Error classifying email: {e}")
            return {"is_lead": True, "confidence": 0.5, "category": "unknown"}

    def categorize_threads(
        self,
        emails: List[Dict[str, Any]],
        no_response_days: int = 3
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Categorize email threads into unanswered and pending proposals.

        Args:
            emails: List of email messages
            no_response_days: Days threshold for "no response"

        Returns:
            Tuple of (unanswered_threads, pending_proposals)
        """
        # Group emails by conversation ID
        conversations: Dict[str, List[Dict[str, Any]]] = {}
        for email in emails:
            conv_id = email.get("conversationId", email.get("id"))
            if conv_id not in conversations:
                conversations[conv_id] = []
            conversations[conv_id].append(email)

        # Sort each conversation by received time
        for conv_id in conversations:
            conversations[conv_id].sort(
                key=lambda e: e.get("receivedDateTime", ""),
                reverse=False  # Oldest first
            )

        unanswered = []
        pending_proposals = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=no_response_days)

        for conv_id, thread in conversations.items():
            if not thread:
                continue

            last_email = thread[-1]
            last_sender = _extract_email(last_email.get("from", {}).get("emailAddress", {}).get("address", ""))
            last_received = datetime.fromisoformat(
                last_email.get("receivedDateTime", "").replace("Z", "+00:00")
            )

            # Check if last email is from external sender (unanswered)
            if not self._is_internal_email(last_sender):
                if last_received < cutoff_date:
                    # Extract external sender's email
                    external_email = last_sender

                    # Classify the email
                    subject = last_email.get("subject", "")
                    body = _strip_html(last_email.get("body", {}).get("content", ""))
                    classification = self._classify_as_lead(subject, body, external_email)

                    unanswered.append({
                        "conversation_id": conv_id,
                        "thread": thread,
                        "last_email": last_email,
                        "external_email": external_email,
                        "last_contact_date": last_received.isoformat(),
                        "subject": last_email.get("subject", ""),
                        "days_waiting": (datetime.now(timezone.utc) - last_received).days,
                        "classification": classification
                    })

            # Check if we sent a proposal and haven't heard back
            else:
                # Look for proposal in the thread
                has_proposal = False
                proposal_date = None

                for email in thread:
                    sender = _extract_email(email.get("from", {}).get("emailAddress", {}).get("address", ""))
                    if self._is_internal_email(sender):
                        subject = email.get("subject", "")
                        body = _strip_html(email.get("body", {}).get("content", ""))
                        attachments = email.get("attachments", [])

                        if (self._contains_proposal_keywords(subject, body) or
                            self._has_proposal_attachment(attachments)):
                            has_proposal = True
                            proposal_date = datetime.fromisoformat(
                                email.get("receivedDateTime", "").replace("Z", "+00:00")
                            )
                            break

                if has_proposal and proposal_date and proposal_date < cutoff_date:
                    # Check if there's been an external reply AFTER the proposal
                    has_external_reply_after_proposal = False
                    for email in thread:
                        email_date = datetime.fromisoformat(
                            email.get("receivedDateTime", "").replace("Z", "+00:00")
                        )
                        if email_date > proposal_date:
                            sender = _extract_email(email.get("from", {}).get("emailAddress", {}).get("address", ""))
                            if not self._is_internal_email(sender):
                                has_external_reply_after_proposal = True
                                break

                    # Check if we've sent a recent internal follow-up (within no_response_days)
                    # If we recently followed up, don't flag this as needing attention
                    has_recent_internal_followup = False
                    if last_received >= cutoff_date:  # Last email is recent and internal
                        has_recent_internal_followup = True

                    # Only add to pending proposals if:
                    # 1. They haven't replied since the proposal
                    # 2. We haven't sent a recent follow-up email
                    if not has_external_reply_after_proposal and not has_recent_internal_followup:
                        # Find external sender email
                        external_email = None
                        for email in thread:
                            sender = _extract_email(email.get("from", {}).get("emailAddress", {}).get("address", ""))
                            if not self._is_internal_email(sender):
                                external_email = sender
                                break

                        if external_email:
                            # Classify the email
                            subject = last_email.get("subject", "")
                            body = _strip_html(last_email.get("body", {}).get("content", ""))
                            classification = self._classify_as_lead(subject, body, external_email)

                            pending_proposals.append({
                                "conversation_id": conv_id,
                                "thread": thread,
                                "last_email": last_email,
                                "external_email": external_email,
                                "proposal_date": proposal_date.isoformat(),
                                "subject": last_email.get("subject", ""),
                                "days_waiting": (datetime.now(timezone.utc) - proposal_date).days,
                                "classification": classification
                            })

        logger.info(f"Categorized {len(unanswered)} unanswered threads and {len(pending_proposals)} pending proposals")
        return unanswered, pending_proposals

    def match_to_odoo(
        self,
        categorized_threads: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Match email threads to Odoo leads/opportunities by email address.

        Args:
            categorized_threads: Dict with 'unanswered' and 'pending_proposals' keys

        Returns:
            Same dict but enriched with Odoo data
        """
        self._ensure_odoo_connection()

        for category in ["unanswered", "pending_proposals"]:
            threads = categorized_threads.get(category, [])

            for thread in threads:
                external_email = thread.get("external_email")
                if not external_email:
                    continue

                # Search Odoo for matching lead/opportunity
                odoo_record = self.odoo.search_lead_by_email(external_email)

                if odoo_record:
                    thread["odoo_lead"] = {
                        "id": odoo_record.get("id"),
                        "name": odoo_record.get("name"),
                        "partner_name": odoo_record.get("partner_name"),
                        "contact_name": odoo_record.get("contact_name"),
                        "stage": odoo_record.get("stage_id", [None, "Unknown"])[1] if isinstance(odoo_record.get("stage_id"), list) else "Unknown",
                        "probability": odoo_record.get("probability", 0),
                        "expected_revenue": odoo_record.get("expected_revenue", 0),
                        "type": odoo_record.get("type", "lead")
                    }
                else:
                    thread["odoo_lead"] = None

        return categorized_threads

    def analyze_thread_with_llm(
        self,
        thread_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze email thread and generate follow-up draft.

        Args:
            thread_data: Thread data with emails and Odoo context

        Returns:
            Analysis with summary, sentiment, urgency, and draft email
        """
        thread = thread_data.get("thread", [])
        odoo_lead = thread_data.get("odoo_lead")

        # Build email thread context
        thread_text = []
        for email in thread[-5:]:  # Last 5 emails
            sender = email.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
            date = _format_datetime(email.get("receivedDateTime", ""))
            subject = email.get("subject", "")
            body = _strip_html(email.get("body", {}).get("content", ""))[:500]  # First 500 chars

            thread_text.append(f"From: {sender}\nDate: {date}\nSubject: {subject}\n{body}\n")

        thread_context = "\n---\n".join(thread_text)

        # Build Odoo context
        odoo_context = ""
        if odoo_lead:
            odoo_context = f"""
Odoo Lead Information:
- Company: {odoo_lead.get('partner_name', 'Unknown')}
- Contact: {odoo_lead.get('contact_name', 'Unknown')}
- Stage: {odoo_lead.get('stage', 'Unknown')}
- Type: {odoo_lead.get('type', 'lead')}
- Probability: {odoo_lead.get('probability', 0)}%
"""

        # Create LLM prompt
        prompt = f"""You are analyzing an email thread from PrezLab's engage inbox to help draft a follow-up email.

{odoo_context}

Email Thread (most recent emails):
{thread_context}

Please analyze this thread and provide:
1. A brief summary of the conversation (2-3 sentences)
2. The current sentiment/tone (positive, neutral, negative, urgent)
3. Urgency level (high, medium, low)
4. Key points or concerns raised by the client
5. A draft follow-up email that:
   - Acknowledges their last message
   - Addresses any questions or concerns
   - Moves the conversation forward
   - Is professional and concise

Respond in JSON format with these keys:
- summary
- sentiment
- urgency
- key_points (array of strings)
- draft_email
"""

        try:
            messages = [
                {"role": "system", "content": "You are a sales communication expert helping draft follow-up emails."},
                {"role": "user", "content": prompt}
            ]

            analysis = self.llm.chat_completion_json(
                messages,
                max_tokens=2000,
                temperature=0.7
            )

            return analysis
        except Exception as e:
            logger.error(f"Error analyzing thread with LLM: {e}")
            return {
                "summary": "Unable to analyze thread",
                "sentiment": "unknown",
                "urgency": "medium",
                "key_points": [],
                "draft_email": ""
            }

    def get_proposal_followups(
        self,
        user_identifier: str,
        days_back: int = 7,
        no_response_days: int = 3
    ) -> Dict[str, Any]:
        """
        Main method to get all proposal follow-up data.

        Args:
            user_identifier: Email of engage monitoring account
            days_back: Days to look back for emails
            no_response_days: Days threshold for "no response"

        Returns:
            Dict with unanswered and pending_proposals lists
        """
        # Get emails from engage inbox
        emails = self.get_engage_emails(user_identifier, days_back)

        # Categorize threads
        unanswered, pending_proposals = self.categorize_threads(emails, no_response_days)

        categorized = {
            "unanswered": unanswered,
            "pending_proposals": pending_proposals
        }

        # Match to Odoo
        enriched = self.match_to_odoo(categorized)

        # Analyze only threads classified as leads (limit to avoid excessive API calls)
        for category in ["unanswered", "pending_proposals"]:
            analyzed_count = 0
            for thread in enriched[category]:
                # Only analyze if classified as a lead
                classification = thread.get("classification", {})
                if classification.get("is_lead", True) and analyzed_count < 10:
                    thread["analysis"] = self.analyze_thread_with_llm(thread)
                    analyzed_count += 1

        # Add summary counts
        result = {
            "summary": {
                "unanswered_count": len(enriched["unanswered"]),
                "pending_proposals_count": len(enriched["pending_proposals"]),
                "total_count": len(enriched["unanswered"]) + len(enriched["pending_proposals"]),
                "days_back": days_back,
                "no_response_days": no_response_days
            },
            "unanswered": enriched["unanswered"],
            "pending_proposals": enriched["pending_proposals"]
        }

        return result
