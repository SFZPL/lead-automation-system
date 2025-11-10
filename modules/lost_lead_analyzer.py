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

    def generate_lost_leads_report(
        self,
        limit: int = 50,
        salesperson_name: Optional[str] = None,
        type_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive lost leads report with statistics and analysis.

        Args:
            limit: Number of lost leads to analyze
            salesperson_name: Filter by salesperson
            type_filter: Filter by 'lead' or 'opportunity' or None for both

        Returns:
            Dict with statistics, reasons analysis, and top opportunities to re-contact
        """
        self._ensure_odoo_connection()
        self._ensure_llm()

        # Fetch lost leads
        logger.info(f"Fetching {limit} lost leads for report generation")
        lost_leads = self.odoo.get_lost_leads(
            limit=limit,
            salesperson_name=salesperson_name,
            type_filter=type_filter
        )

        if not lost_leads:
            return {
                "summary": {
                    "total_count": 0,
                    "total_missed_value": 0,
                    "average_deal_value": 0,
                    "leads_count": 0,
                    "opportunities_count": 0
                },
                "reasons_analysis": {},
                "top_opportunities": []
            }

        # Calculate statistics
        total_missed_value = sum(
            lead.get("expected_revenue", 0) or 0
            for lead in lost_leads
        )

        deals_with_value = [
            lead.get("expected_revenue", 0) or 0
            for lead in lost_leads
            if (lead.get("expected_revenue", 0) or 0) > 0
        ]

        average_deal_value = (
            sum(deals_with_value) / len(deals_with_value)
            if deals_with_value
            else 0
        )

        leads_count = sum(1 for lead in lost_leads if lead.get("type") == "lead")
        opportunities_count = sum(1 for lead in lost_leads if lead.get("type") == "opportunity")

        # Analyze lost reasons
        reasons_analysis = self._analyze_lost_reasons(lost_leads)

        # Analyze by stage
        stage_analysis = self._analyze_by_stage(lost_leads)

        # Identify top opportunities to re-contact (highest value + recent + specific reasons)
        top_opportunities = self._identify_reconnect_opportunities(lost_leads)

        return {
            "summary": {
                "total_count": len(lost_leads),
                "total_missed_value": round(total_missed_value, 2),
                "average_deal_value": round(average_deal_value, 2),
                "leads_count": leads_count,
                "opportunities_count": opportunities_count,
                "report_generated_at": datetime.now().isoformat()
            },
            "reasons_analysis": reasons_analysis,
            "stage_analysis": stage_analysis,
            "top_opportunities": top_opportunities[:10],  # Top 10
            "all_lost_leads": lost_leads  # Full list for reference
        }

    def _analyze_lost_reasons(self, lost_leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze and categorize reasons for losing leads."""
        reasons_count = {}
        reasons_value = {}
        total_count = len(lost_leads)

        for lead in lost_leads:
            reason = lead.get("lost_reason_id")
            if reason:
                # Reason comes as [id, "Reason Name"] tuple
                reason_name = reason[1] if isinstance(reason, list) and len(reason) > 1 else str(reason)
            else:
                reason_name = "Unknown/Not Specified"

            # Count occurrences
            reasons_count[reason_name] = reasons_count.get(reason_name, 0) + 1

            # Sum values
            value = lead.get("expected_revenue", 0) or 0
            reasons_value[reason_name] = reasons_value.get(reason_name, 0) + value

        # Sort by count
        sorted_reasons = sorted(
            reasons_count.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return {
            "by_frequency": [
                {
                    "reason": reason,
                    "count": count,
                    "percentage": round((count / total_count * 100), 1) if total_count > 0 else 0,
                    "total_value": round(reasons_value.get(reason, 0), 2)
                }
                for reason, count in sorted_reasons
            ],
            "by_value": sorted(
                [
                    {
                        "reason": reason,
                        "count": reasons_count[reason],
                        "percentage": round((reasons_count[reason] / total_count * 100), 1) if total_count > 0 else 0,
                        "total_value": round(value, 2)
                    }
                    for reason, value in reasons_value.items()
                ],
                key=lambda x: x["total_value"],
                reverse=True
            )
        }

    def _analyze_by_stage(self, lost_leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze lost leads by stage."""
        stage_count = {}
        stage_value = {}
        total_count = len(lost_leads)

        for lead in lost_leads:
            stage = lead.get("stage_id")
            # Extract stage name (same logic as in _identify_reconnect_opportunities)
            if isinstance(stage, (list, tuple)) and len(stage) > 1:
                stage_name = stage[1]
            elif stage and stage != False:
                stage_name = str(stage)
            else:
                stage_name = "Unknown"

            # Count occurrences
            stage_count[stage_name] = stage_count.get(stage_name, 0) + 1

            # Sum values
            value = lead.get("expected_revenue", 0) or 0
            stage_value[stage_name] = stage_value.get(stage_name, 0) + value

        # Sort by count
        sorted_stages = sorted(
            stage_count.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            {
                "stage": stage,
                "count": count,
                "percentage": round((count / total_count * 100), 1) if total_count > 0 else 0,
                "total_value": round(stage_value.get(stage, 0), 2)
            }
            for stage, count in sorted_stages
        ]

    def _identify_reconnect_opportunities(self, lost_leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify the best opportunities to re-contact based on multiple factors.

        Scoring criteria:
        - Deal value (higher is better)
        - Recency (more recent losses are better)
        - Lost reason (some reasons are better for re-contact than others)
        - Opportunity type (opportunities usually better than leads)
        """
        reconnect_worthy_reasons = [
            "price too high",
            "timing",
            "budget",
            "not ready",
            "deferred",
            "postponed",
            "evaluating alternatives",
            "went with competitor"
        ]

        scored_leads = []
        for lead in lost_leads:
            score = 0

            # Deal value score (0-40 points)
            value = lead.get("expected_revenue", 0) or 0
            if value > 0:
                score += min(40, value / 1000)  # $1k = 1 point, capped at 40

            # Recency score (0-30 points)
            write_date = lead.get("write_date")
            if write_date:
                try:
                    date_obj = datetime.fromisoformat(write_date.replace("Z", "+00:00"))
                    days_ago = (datetime.now() - date_obj.replace(tzinfo=None)).days
                    # More recent = higher score
                    score += max(0, 30 - (days_ago / 10))  # Lose 1 point per 10 days
                except Exception:
                    pass

            # Lost reason score (0-20 points)
            reason = lead.get("lost_reason_id")
            if reason:
                reason_name = (reason[1] if isinstance(reason, list) and len(reason) > 1 else str(reason)).lower()
                if any(worthy in reason_name for worthy in reconnect_worthy_reasons):
                    score += 20

            # Type score (0-10 points)
            if lead.get("type") == "opportunity":
                score += 10

            # Extract stage name from stage_id
            # Odoo returns stage_id as [id, "Stage Name"] tuple or False if not set
            stage = lead.get("stage_id")
            if isinstance(stage, (list, tuple)) and len(stage) > 1:
                stage_name = stage[1]
            elif stage and stage != False:
                stage_name = str(stage)
            else:
                stage_name = "Unknown"

            scored_leads.append({
                "lead_id": lead.get("id"),
                "name": lead.get("name"),
                "partner_name": lead.get("partner_name"),
                "contact_name": lead.get("contact_name"),
                "email": lead.get("email_from"),
                "phone": lead.get("phone") or lead.get("mobile"),
                "expected_revenue": value,
                "lost_reason": reason[1] if isinstance(reason, list) and len(reason) > 1 else (reason or "Unknown"),
                "stage_name": stage_name,
                "type": lead.get("type"),
                "write_date": lead.get("write_date"),
                "reconnect_score": round(score, 2)
            })

        # Sort by score descending
        scored_leads.sort(key=lambda x: x["reconnect_score"], reverse=True)

        return scored_leads

