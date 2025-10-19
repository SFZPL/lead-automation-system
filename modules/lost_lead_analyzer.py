import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import Config
from modules.llm_client import LLMClient
from modules.odoo_client import OdooClient
from modules.outlook_client import OutlookClient
from modules.email_token_store import EmailTokenStore

logger = logging.getLogger(__name__)


def _strip_html(value: Optional[str]) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _format_datetime(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


class LostLeadAnalyzer:
    """Gather lost-lead context from Odoo and summarise with an LLM."""

    def __init__(
        self,
        config: Optional[Config] = None,
        odoo_client: Optional[OdooClient] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.config = config or Config()
        self.odoo = odoo_client or OdooClient(self.config)
        self.llm = llm_client

    def _ensure_odoo_connection(self) -> None:
        if self.odoo.session is None:
            if not self.odoo.connect():
                raise RuntimeError("Failed to connect to Odoo")

    def _ensure_llm(self) -> None:
        if self.llm is None:
            if not self.config.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY is not configured.")
            self.llm = LLMClient(self.config)

    def list_lost_leads(
        self,
        limit: int = 20,
        salesperson_name: Optional[str] = None,
        type_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self._ensure_odoo_connection()
        return self.odoo.get_lost_leads(
            limit=limit,
            salesperson_name=salesperson_name,
            type_filter=type_filter
        )

    def _fetch_outlook_emails(
        self,
        user_identifier: str,
        lead_data: Dict[str, Any],
        max_emails: int,
        group_name: str = "engage"
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from Outlook engage group for a lead.

        Args:
            user_identifier: User's email identifier for token lookup
            lead_data: Lead information from Odoo
            max_emails: Maximum number of emails to return
            group_name: Name of the Microsoft 365 group to search (default: "engage")

        Returns:
            List of formatted email messages
        """
        try:
            outlook = OutlookClient(config=self.config)
            token_store = EmailTokenStore()

            # Get tokens
            tokens = token_store.get_tokens(user_identifier)
            if not tokens:
                logger.info(f"No email tokens found for user: {user_identifier}")
                return []

            # Refresh token if expired
            access_token = tokens.get("access_token")
            if token_store.is_token_expired(user_identifier):
                logger.info(f"Refreshing expired token for {user_identifier}")
                refresh_token = tokens.get("refresh_token")
                token_response = outlook.refresh_access_token(refresh_token)
                access_token = token_response.get("access_token")
                token_store.update_access_token(
                    user_identifier,
                    access_token,
                    token_response.get("expires_in", 3600)
                )

            # Find the engage group
            groups = outlook.get_user_groups(access_token)
            engage_group = None
            for group in groups:
                display_name = group.get("displayName", "").lower()
                mail = group.get("mail", "").lower()
                if group_name.lower() in display_name or group_name.lower() in mail:
                    engage_group = group
                    break

            if not engage_group:
                logger.warning(f"Could not find '{group_name}' group for user {user_identifier}")
                # Fallback to personal inbox search
                outlook_emails = outlook.search_emails_for_lead(
                    access_token=access_token,
                    lead_data=lead_data,
                    limit=max_emails,
                    days_back=self.config.EMAIL_SEARCH_DAYS_BACK,
                )
            else:
                # Search emails from the engage group
                all_group_emails = outlook.get_group_conversations(
                    access_token=access_token,
                    group_id=engage_group['id'],
                    days_back=self.config.EMAIL_SEARCH_DAYS_BACK,
                    limit=200
                )

                # Filter emails related to this lead
                lead_email = lead_data.get("email_from", "")
                partner_email = lead_data.get("partner_email", "")
                contact_email = lead_data.get("contact_email", "")
                lead_name = lead_data.get("name", "").lower()
                company_name = (lead_data.get("partner_name") or "").lower()

                outlook_emails = []
                for email in all_group_emails:
                    email_from = email.get("from", "").lower()
                    email_to = email.get("to", "").lower()
                    email_subject = email.get("subject", "").lower()
                    email_body = email.get("body", "").lower()

                    # Check if email is related to this lead
                    if (
                        (lead_email and lead_email.lower() in email_from) or
                        (lead_email and lead_email.lower() in email_to) or
                        (partner_email and partner_email.lower() in email_from) or
                        (partner_email and partner_email.lower() in email_to) or
                        (contact_email and contact_email.lower() in email_from) or
                        (contact_email and contact_email.lower() in email_to) or
                        (lead_name and lead_name in email_subject) or
                        (company_name and len(company_name) > 3 and company_name in email_subject) or
                        (company_name and len(company_name) > 3 and company_name in email_body)
                    ):
                        outlook_emails.append(email)

                outlook_emails = outlook_emails[:max_emails]

            # Format for analysis
            formatted_emails = [
                outlook.format_email_for_analysis(email)
                for email in outlook_emails
            ]

            logger.info(f"Found {len(formatted_emails)} Outlook emails for lead {lead_data.get('id')} from {group_name} group")
            return formatted_emails

        except Exception as e:
            logger.error(f"Error fetching Outlook emails: {e}")
            return []

    def _prepare_context(
        self,
        lead_id: int,
        max_internal_notes: int,
        max_emails: int,
        user_identifier: Optional[str] = None,
        include_outlook_emails: bool = False,
    ) -> Dict[str, Any]:
        lead = self.odoo.get_lead_details(lead_id)
        if not lead:
            raise RuntimeError(f"Lead with id {lead_id} not found.")

        fetch_limit = max(max_internal_notes, max_emails, 1) * 3
        messages = self.odoo.get_lead_messages(lead_id, limit=fetch_limit)

        internal_notes: List[Dict[str, Any]] = []
        emails: List[Dict[str, Any]] = []
        for message in messages:
            m_type = (message.get("message_type") or "").lower()
            subtype = (message.get("subtype_name") or "").lower()
            body_text = _strip_html(message.get("body"))
            if not body_text:
                continue
            prepared = {
                "id": message.get("id"),
                "date": message.get("date"),
                "author": message.get("author_name") or message.get("email_from") or "Unknown",
                "subject": message.get("subject"),
                "body": body_text,
            }
            if m_type == "email":
                emails.append(prepared)
            elif m_type == "comment" and ("note" in subtype or not message.get("email_from")):
                internal_notes.append(prepared)

        # Optionally fetch Outlook emails
        if include_outlook_emails and user_identifier:
            outlook_emails = self._fetch_outlook_emails(user_identifier, lead, max_emails)
            if outlook_emails:
                # Merge with existing emails and sort by date
                all_emails = emails + outlook_emails
                all_emails.sort(key=lambda x: x.get("date") or "", reverse=True)
                emails = all_emails

        internal_notes = sorted(internal_notes, key=lambda item: item.get("date") or "", reverse=True)[:max_internal_notes]
        emails = sorted(emails, key=lambda item: item.get("date") or "", reverse=True)[:max_emails]

        for entry in internal_notes + emails:
            entry["formatted_date"] = _format_datetime(entry.get("date"))

        return {
            "lead": lead,
            "internal_notes": internal_notes,
            "emails": emails,
        }

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        lead = context["lead"]
        internal_notes: List[Dict[str, Any]] = context["internal_notes"]
        emails: List[Dict[str, Any]] = context["emails"]

        def format_messages(title: str, messages: List[Dict[str, Any]]) -> str:
            if not messages:
                return f"{title}: None available."
            lines = [f"{title}:"]
            for message in messages:
                timestamp = message.get("formatted_date") or "Unknown date"
                author = message.get("author") or "Unknown"
                subject = message.get("subject")
                header = f"- [{timestamp}] {author}"
                if subject:
                    header += f" — {subject}"
                body = message.get("body") or ""
                lines.append(f"{header}\n  {body}")
            return "\n".join(lines)

        # Build lead summary with all available context
        lead_summary = [
            f"Opportunity: {lead.get('name') or 'Unknown'}",
            f"Type: {lead.get('type') or 'Unknown'}",
            f"Customer: {lead.get('partner_name') or 'Unknown'}",
            f"Contact: {lead.get('contact_name') or 'Unknown'}",
            f"Email: {lead.get('email_from') or 'Not provided'}",
            f"Phone: {lead.get('phone') or lead.get('mobile') or 'Not provided'}",
        ]

        # Add address if available
        address_parts = []
        if lead.get('street'):
            address_parts.append(lead['street'])
        if lead.get('city'):
            address_parts.append(lead['city'])
        if lead.get('country_id'):
            address_parts.append(lead['country_id'])
        if address_parts:
            lead_summary.append(f"Location: {', '.join(address_parts)}")

        # Add website and LinkedIn
        if lead.get('website'):
            lead_summary.append(f"Website: {lead['website']}")
        if lead.get('x_studio_linkedin_profile'):
            linkedin_clean = _strip_html(lead['x_studio_linkedin_profile'])
            lead_summary.append(f"LinkedIn: {linkedin_clean}")

        # Add opportunity details
        lead_summary.extend([
            f"Stage: {lead.get('stage_id') or 'Unknown'}",
            f"Probability: {lead.get('probability')}%",
            f"Expected Revenue: {lead.get('expected_revenue') or 'N/A'}",
            f"Service: {lead.get('x_studio_service') or 'Not specified'}",
            f"Agreement Type: {lead.get('x_studio_agreement_type') or 'Not specified'}",
            f"Quality Score: {lead.get('x_studio_quality') or 'Not rated'}",
        ])

        # Add loss information
        lead_summary.extend([
            f"Won Status: {lead.get('won_status') or 'Unknown'}",
            f"Lost Reason: {lead.get('lost_reason_id') or 'Not specified'}",
        ])

        # Add tracking information
        lead_summary.extend([
            f"Salesperson: {lead.get('user_id') or 'Unassigned'}",
            f"Team: {lead.get('team_id') or 'Not assigned'}",
            f"Source: {lead.get('source_id') or 'Unknown'}",
            f"Campaign: {lead.get('campaign_id') or 'None'}",
            f"Medium: {lead.get('medium_id') or 'None'}",
        ])

        if lead.get('referred'):
            lead_summary.append(f"Referred By: {lead['referred']}")

        if lead.get('priority'):
            priority_map = {'0': 'Low', '1': 'Medium', '2': 'High', '3': 'Very High'}
            priority_label = priority_map.get(str(lead['priority']), str(lead['priority']))
            lead_summary.append(f"Priority: {priority_label}")

        # Add dates
        lead_summary.extend([
            f"Creation Date: {lead.get('create_date') or 'Unknown'}",
            f"Last Update: {lead.get('write_date') or 'Unknown'}",
        ])

        if lead.get('date_closed'):
            lead_summary.append(f"Date Closed: {lead['date_closed']}")
        if lead.get('date_deadline'):
            lead_summary.append(f"Expected Close Date: {lead['date_deadline']}")

        # Add description last
        if lead.get('description'):
            lead_summary.append(f"Description: {_strip_html(lead['description'])}")
        else:
            lead_summary.append("Description: No description recorded.")

        sections = [
            "You are a senior revenue strategist reviewing a lost opportunity.",
            "Use the CRM context to determine why the deal was lost and craft a smart re-engagement plan.",
            "",
            "Lead Overview:",
            "\n".join(f"  {line}" for line in lead_summary),
            "",
            format_messages("Internal Notes", internal_notes),
            "",
            format_messages("Email Threads", emails),
            "",
            "Produce a JSON object with the following structure:",
            '{',
            '  "loss_summary": "Concise narrative (3-5 sentences)",',
            '  "key_factors": ["Ordered list of the top 3-5 factors that led to the loss"],',
            '  "follow_up_plan": {',
            '    "objective": "Primary goal for re-engaging the account",',
            '    "talking_points": ["Specific points tailored to this opportunity"],',
            '    "proposed_actions": ["Chronological list of 3-5 actions with owners where possible"],',
            '    "recommended_timeline": "Suggested timeline or trigger events for outreach",',
            '    "risks": ["Potential pitfalls to monitor during re-engagement"]',
            '  },',
            '  "intel_gaps": ["Missing data that would strengthen future conversations"]',
            '}',
            "",
            "Only return valid JSON. Do not include any additional commentary.",
        ]
        return "\n".join(sections)

    def analyze_lost_lead(
        self,
        lead_id: int,
        max_internal_notes: Optional[int] = None,
        max_emails: Optional[int] = None,
        user_identifier: Optional[str] = None,
        include_outlook_emails: bool = False,
    ) -> Dict[str, Any]:
        self._ensure_odoo_connection()
        max_notes = max_internal_notes if max_internal_notes is not None else self.config.LOST_LEAD_MAX_NOTES
        max_email_entries = max_emails if max_emails is not None else self.config.LOST_LEAD_MAX_EMAILS

        context = self._prepare_context(
            lead_id,
            max_notes,
            max_email_entries,
            user_identifier=user_identifier,
            include_outlook_emails=include_outlook_emails,
        )
        self._ensure_llm()

        prompt = self._build_prompt(context)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert SaaS revenue leader who diagnoses lost deals and writes "
                    "clear, personalised re-engagement plans. Always provide practical suggestions."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        analysis = self.llm.chat_completion_json(
            messages,
            max_tokens=self.config.LOST_LEAD_ANALYSIS_SUMMARY_LENGTH,
            temperature=0.4,
        )

        return {
            "lead": context["lead"],
            "analysis": analysis,
            "internal_notes": context["internal_notes"],
            "emails": context["emails"],
        }

