from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from modules.apollo_client import ApolloClient
from modules.email_dispatcher import EmailDispatcher
from modules.followup_email import FollowUpEmailBuilder
from modules.logger import LoggingMixin
from modules.maqsam_client import MaqsamClient
from modules.odoo_client import OdooClient

logger = logging.getLogger(__name__)


@dataclass
class PostContactAction:
    """Action that should occur after the first outbound call."""

    action_type: str  # 'email' | 'note'
    contact_email: str
    odoo_lead_id: int
    subject: Optional[str] = None
    body: Optional[str] = None
    note_body: Optional[str] = None
    transcription: Optional[str] = None
    call: Dict[str, Any] = field(default_factory=dict)
    odoo_lead: Dict[str, Any] = field(default_factory=dict)

    @property
    def contact_name(self) -> str:
        return (
            self.odoo_lead.get('contact_name')
            or self.odoo_lead.get('name')
            or self.call.get('full_name')
            or self.call.get('contact_name')
            or ''
        )


class PostContactAutomationService(LoggingMixin):
    """Coordinate first-contact automations using Apollo, Maqsam, and Odoo."""

    def __init__(
        self,
        config: Optional[Config] = None,
        apollo_client: Optional[ApolloClient] = None,
        odoo_client: Optional[OdooClient] = None,
        maqsam_client: Optional[MaqsamClient] = None,
        email_builder: Optional[FollowUpEmailBuilder] = None,
        email_dispatcher: Optional[EmailDispatcher] = None,
    ) -> None:
        self.config = config or Config()
        self.apollo = apollo_client or ApolloClient(
            api_key=self.config.APOLLO_API_KEY,
            base_url=self.config.APOLLO_BASE_URL,
            send_api_key_in_body=self.config.APOLLO_API_KEY_IN_BODY,
        )
        self.odoo = odoo_client or OdooClient(self.config)
        self.email_builder = email_builder or FollowUpEmailBuilder(
            sender_name=self.config.SALESPERSON_NAME,
            value_proposition=self.config.FOLLOWUP_VALUE_PROP,
            calendar_link=self.config.FOLLOWUP_CALENDAR_LINK,
            sender_title=self.config.FOLLOWUP_SENDER_TITLE,
            sender_email=self.config.FOLLOWUP_SENDER_EMAIL,
            proposed_meeting_text=self.config.FOLLOWUP_PROPOSED_SLOT,
            openai_api_key=self.config.OPENAI_API_KEY,
            openai_model=self.config.OPENAI_MODEL,
            use_llm=True,
        )
        self.maqsam = maqsam_client or MaqsamClient(config=self.config)
        self.email_dispatcher = email_dispatcher or EmailDispatcher(self.config)
        self.no_answer_dispositions = {
            value.strip().lower() for value in self.config.APOLLO_NO_ANSWER_DISPOSITIONS
        }

    def _ensure_odoo_connection(self) -> None:
        if not hasattr(self.odoo, "uid") or self.odoo.uid is None:
            if not self.odoo.connect():
                raise RuntimeError("Failed to connect to Odoo")

    def prepare_actions(
        self,
        limit: Optional[int] = None,
        lookback_hours: Optional[int] = None,
    ) -> List[PostContactAction]:
        """Prepare follow-up actions from Apollo call activity."""

        if not self.apollo.api_key:
            logger.warning("Apollo API key missing; cannot prepare post-contact actions.")
            return []

        max_items = limit or self.config.POST_CONTACT_MAX_CALLS
        lookback_hours = lookback_hours or self.config.POST_CONTACT_LOOKBACK_HOURS
        updated_after: Optional[datetime] = None
        if lookback_hours and lookback_hours > 0:
            updated_after = datetime.utcnow() - timedelta(hours=lookback_hours)

        raw_calls = self.apollo.fetch_recent_calls(
            limit=max_items * 2,
            updated_after=updated_after,
        )
        if not raw_calls:
            logger.info("No recent Apollo calls found within the requested window.")
            return []

        summaries: List[Dict[str, Any]] = []
        for call in raw_calls:
            summary = self.apollo.call_to_contact_summary(call)
            email = (summary.get('email') or '').strip().lower()
            if not email:
                continue
            summary['raw_call'] = call
            summary['email'] = email
            summaries.append(summary)

        if not summaries:
            logger.info("Apollo returned calls without actionable contact emails.")
            return []

        self._ensure_odoo_connection()
        emails = [item['email'] for item in summaries]
        leads_by_email = self.odoo.get_leads_by_emails(
            emails,
            salesperson_name=self.config.SALESPERSON_NAME,
        )
        if not leads_by_email:
            logger.info("No matching Odoo leads found for recent Apollo calls.")
            return []

        actions: List[PostContactAction] = []
        for summary in summaries:
            email = summary['email']
            lead = leads_by_email.get(email)
            if not lead:
                continue
            lead_id = lead.get('id')
            if not lead_id:
                continue

            disposition_raw = (
                summary.get('call_disposition')
                or summary.get('disposition')
                or summary['raw_call'].get('disposition')
                or ''
            )
            disposition = disposition_raw.lower()

            if disposition in self.no_answer_dispositions:
                context: Dict[str, Any] = dict(lead)
                context.update(summary)
                context['email'] = email
                email_content = self.email_builder.build(context)
                actions.append(
                    PostContactAction(
                        action_type='email',
                        contact_email=email,
                        odoo_lead_id=lead_id,
                        subject=email_content['subject'],
                        body=email_content['body'],
                        call=summary,
                        odoo_lead=lead,
                    )
                )
            else:
                note_body, transcription = self._prepare_note(summary, lead, disposition_raw)
                if not note_body:
                    continue
                actions.append(
                    PostContactAction(
                        action_type='note',
                        contact_email=email,
                        odoo_lead_id=lead_id,
                        note_body=note_body,
                        transcription=transcription,
                        call=summary,
                        odoo_lead=lead,
                    )
                )

            if len(actions) >= max_items:
                break

        return actions

    def _prepare_note(
        self,
        summary: Dict[str, Any],
        lead: Dict[str, Any],
        disposition_label: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        call = summary['raw_call']
        call_id = self._resolve_maqsam_call_id(call)
        transcription = self.maqsam.get_transcription(call_id) if call_id else None

        details: List[str] = []
        call_dt: Optional[datetime] = summary.get('last_called_at_dt')
        if call_dt and isinstance(call_dt, datetime):
            details.append(f"Call answered on {call_dt.strftime('%Y-%m-%d %H:%M')} UTC")
        if disposition_label:
            details.append(f"Disposition: {disposition_label}")
        duration = summary.get('duration_seconds') or call.get('duration')
        if duration:
            details.append(f"Duration: {duration} seconds")
        if summary.get('notes'):
            details.append(f"Caller notes: {summary['notes']}")

        if transcription:
            details.append("Maqsam transcription:")
            details.append(transcription)
        elif summary.get('notes'):
            details.append("Transcription unavailable; storing Apollo notes above.")
        else:
            return None, None

        note_body = '\n'.join(details)
        return note_body, transcription

    def _resolve_maqsam_call_id(self, call: Dict[str, Any]) -> Optional[str]:
        for key in self.config.MAQSAM_CALL_ID_KEYS:
            value = call.get(key)
            if not value:
                continue
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (int, float)):
                return str(value)
        integrations = call.get('integrations') or {}
        if isinstance(integrations, dict):
            for key in self.config.MAQSAM_CALL_ID_KEYS:
                value = integrations.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def execute_email(self, action: PostContactAction) -> bool:
        if action.action_type != 'email':
            raise ValueError("execute_email called with non-email action")
        if not action.contact_email:
            logger.warning("Email action missing recipient address.")
            return False
        if not action.body:
            logger.warning("Email action missing body; skipping send.")
            return False
        subject = action.subject or "Follow-up"
        return self.email_dispatcher.send_email(
            to_address=action.contact_email,
            subject=subject,
            body=action.body,
        )

    def execute_note(self, action: PostContactAction) -> bool:
        if action.action_type != 'note':
            raise ValueError("execute_note called with non-note action")
        if not action.note_body:
            logger.warning("Note action has no content; skipping.")
            return False

        self._ensure_odoo_connection()
        return self.odoo.append_internal_note(
            action.odoo_lead_id,
            action.note_body,
            subject="Maqsam call transcription",
        )
