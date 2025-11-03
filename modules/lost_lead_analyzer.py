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
        supabase_client: Optional[Any] = None,
    ) -> None:
        self.config = config or Config()
        self.odoo = odoo_client or OdooClient(self.config)
        self.llm = llm_client
        self.supabase = supabase_client

    def _ensure_odoo_connection(self) -> None:
        if not hasattr(self.odoo, "uid") or self.odoo.uid is None:
            if not self.odoo.connect():
                raise RuntimeError("Failed to connect to Odoo")

    def _ensure_llm(self) -> None:
        if self.llm is None:
            if not self.config.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY is not configured.")
            self.llm = LLMClient(self.config)

    def _get_knowledge_base_context(self) -> str:
        """Fetch all active knowledge base documents and combine their content."""
        if not self.supabase or not self.supabase.is_connected():
            return ""

        try:
            result = self.supabase.client.table("knowledge_base_documents")\
                .select("filename, content")\
                .eq("is_active", True)\
                .execute()

            if not result.data:
                return ""

            # Combine all document contents
            context_parts = []
            for doc in result.data:
                filename = doc.get("filename", "Unknown Document")
                content = doc.get("content", "")
                if content.strip():
                    context_parts.append(f"=== {filename} ===\n{content.strip()}")

            if context_parts:
                return "\n\n".join(context_parts)
            return ""

        except Exception as e:
            logger.warning(f"Failed to fetch knowledge base context: {e}")
            return ""

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
        lead_data: Dict[str, Any],
        max_emails: int,
        group_email: str = "engage@prezlab.com"
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from Outlook engage group for a lead using system email token.

        Args:
            lead_data: Lead information from Odoo
            max_emails: Maximum number of emails to return
            group_email: Email address of the Microsoft 365 group (default: engage@prezlab.com)

        Returns:
            List of formatted email messages
        """
        try:
            outlook = OutlookClient(config=self.config)
            token_store = EmailTokenStore()

            # Use system email token (automated.response@prezlab.com)
            system_identifier = "automated.response@prezlab.com"
            tokens = token_store.get_tokens(system_identifier)
            if not tokens:
                logger.info("No system email tokens found. Please configure system email authentication.")
                return []

            # Refresh token if expired
            access_token = tokens.get("access_token")
            if token_store.is_token_expired(system_identifier):
                logger.info("Refreshing expired system token")
                refresh_token = tokens.get("refresh_token")
                token_response = outlook.refresh_access_token(refresh_token)
                access_token = token_response.get("access_token")
                token_store.update_access_token(
                    system_identifier,
                    access_token,
                    token_response.get("expires_in", 3600)
                )

            # Collect all possible contact emails
            contact_emails = []
            if lead_data.get("email_from"):
                contact_emails.append(lead_data["email_from"])
            if lead_data.get("partner_email"):
                contact_emails.append(lead_data["partner_email"])
            if lead_data.get("contact_email"):
                contact_emails.append(lead_data["contact_email"])

            if not contact_emails:
                logger.warning("No contact emails found in lead data")
                return []

            # Use efficient search method
            outlook_emails = outlook.search_group_emails_for_contact(
                access_token=access_token,
                group_email=group_email,
                contact_emails=contact_emails,
                days_back=self.config.EMAIL_SEARCH_DAYS_BACK,
                limit=max_emails or 50
            )

            # Format for analysis
            formatted_emails = [
                outlook.format_email_for_analysis(email)
                for email in outlook_emails
            ]

            logger.info(f"Found {len(formatted_emails)} Outlook emails for lead {lead_data.get('id')} from {group_email}")
            return formatted_emails

        except Exception as e:
            logger.error(f"Error fetching Outlook emails: {e}")
            return []

    def _prepare_context(
        self,
        lead_id: int,
        max_internal_notes: Optional[int],
        max_emails: Optional[int],
        user_identifier: Optional[str] = None,
        include_outlook_emails: bool = False,
    ) -> Dict[str, Any]:
        lead = self.odoo.get_lead_details(lead_id)
        if not lead:
            raise RuntimeError(f"Lead with id {lead_id} not found.")

        # Fetch ALL messages from Odoo (no limit)
        messages = self.odoo.get_lead_messages(lead_id, limit=None)

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

        # Always fetch engage@prezlab.com emails using system token
        outlook_emails = self._fetch_outlook_emails(lead, max_emails or 50)
        if outlook_emails:
            # Merge with existing emails and sort by date
            all_emails = emails + outlook_emails
            all_emails.sort(key=lambda x: x.get("date") or "", reverse=True)
            emails = all_emails

        # Sort by date (newest first) and apply limits if specified
        internal_notes = sorted(internal_notes, key=lambda item: item.get("date") or "", reverse=True)
        emails = sorted(emails, key=lambda item: item.get("date") or "", reverse=True)

        if max_internal_notes is not None:
            internal_notes = internal_notes[:max_internal_notes]
        if max_emails is not None:
            emails = emails[:max_emails]

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

        # Get knowledge base context
        kb_context = self._get_knowledge_base_context()

        sections = [
            "You are a senior revenue strategist reviewing a lost opportunity.",
            "",
        ]

        # Add knowledge base context if available
        if kb_context:
            sections.extend([
                "IMPORTANT - Company Context & Knowledge Base:",
                "First, carefully review the following documents about PrezLab (our company, services, and offerings):",
                "",
                kb_context,
                "",
                "INSTRUCTIONS:",
                "- Study the above documents to understand what PrezLab offers and our value propositions",
                "- Use this knowledge to identify which PrezLab services could have addressed the client's needs",
                "- Reference specific PrezLab capabilities and services in your talking points and recommendations",
                "- Ensure your re-engagement strategy is grounded in what PrezLab actually provides",
                "",
            ])

        sections.append("Now, analyze the lost opportunity using the CRM context below:")
        sections.append("")

        sections.extend([
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
        ])
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
        # Use None to get ALL notes and emails (no limit)
        max_notes = max_internal_notes
        max_email_entries = max_emails

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

