from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import Config
from modules.apollo_client import ApolloClient
from modules.followup_email import FollowUpEmailBuilder
from modules.logger import LoggingMixin
from modules.odoo_client import OdooClient

logger = logging.getLogger(__name__)


class ApolloFollowUpService(LoggingMixin):
    """Coordinate Apollo call data, Odoo enrichment, and email generation."""

    def __init__(
        self,
        config: Optional[Config] = None,
        apollo_client: Optional[ApolloClient] = None,
        odoo_client: Optional[OdooClient] = None,
        email_builder: Optional[FollowUpEmailBuilder] = None,
    ) -> None:
        self.config = config or Config()
        if apollo_client is not None:
            self.apollo = apollo_client
        else:
            self.apollo = ApolloClient(
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

    def _ensure_odoo_connection(self) -> None:
        if not hasattr(self.odoo, "uid") or self.odoo.uid is None:
            if not self.odoo.connect():
                raise RuntimeError('Failed to connect to Odoo')

    def prepare_followups(
        self,
        limit: int = 10,
        lookback_hours: Optional[int] = None,
        dispositions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Prepare personalized follow-up emails for missed calls."""

        if limit <= 0:
            return []

        if not self.apollo.api_key:
            logger.warning('Apollo API key missing; cannot prepare follow-ups.')
            return []

        lookback_hours = lookback_hours or self.config.APOLLO_LOOKBACK_HOURS
        updated_after: Optional[datetime] = None
        if lookback_hours and lookback_hours > 0:
            updated_after = datetime.utcnow() - timedelta(hours=lookback_hours)

        dispositions = dispositions or self.config.APOLLO_NO_ANSWER_DISPOSITIONS
        contact_limit = max(limit * 2, limit)
        contacts = self.apollo.fetch_no_answer_contacts(
            limit=contact_limit,
            dispositions=dispositions,
            updated_after=updated_after,
        )

        if not contacts:
            logger.info('No Apollo contacts found for follow-up criteria')
            return []

        logger.info(f'Found {len(contacts)} Apollo contacts with no-answer calls')

        # Separate contacts with and without emails
        contacts_with_email = [c for c in contacts if c.get('email')]
        contacts_without_email = [c for c in contacts if not c.get('email') and c.get('full_name')]

        # Match by email first
        self._ensure_odoo_connection()
        odoo_leads_by_email = {}
        if contacts_with_email:
            emails = [c.get('email') for c in contacts_with_email]
            logger.info(f'Extracted {len(emails)} emails from Apollo contacts: {emails[:5]}')
            odoo_leads_by_email = self.odoo.get_leads_by_emails(
                emails,
                salesperson_name=None,  # Temporarily disabled: self.config.SALESPERSON_NAME,
            )
            logger.info(f'Found {len(odoo_leads_by_email)} matching Odoo leads for {len(emails)} Apollo emails')

        # Match by name for contacts without email
        odoo_leads_by_name = {}
        if contacts_without_email:
            names = [c.get('full_name') for c in contacts_without_email]
            logger.info(f'Attempting name-based matching for {len(names)} contacts without email')
            odoo_leads_by_name = self.odoo.get_leads_by_names(
                names,
                salesperson_name=None,  # Temporarily disabled: self.config.SALESPERSON_NAME,
            )
            logger.info(f'Found {len(odoo_leads_by_name)} matching Odoo leads by name')

        results: List[Dict[str, Any]] = []
        for contact in contacts:
            email = (contact.get('email') or '').strip().lower()
            full_name = (contact.get('full_name') or '').strip().lower()

            # Try to match by email first, then by name
            odoo_lead = None
            if email:
                odoo_lead = odoo_leads_by_email.get(email)
                if not odoo_lead:
                    logger.debug('No Odoo lead found for email %s', email)
            elif full_name:
                odoo_lead = odoo_leads_by_name.get(full_name)
                if not odoo_lead:
                    logger.debug('No Odoo lead found for name %s', full_name)

            if not odoo_lead:
                continue

            context: Dict[str, Any] = dict(contact)
            context.update(odoo_lead)
            context['email'] = email

            email_content = self.email_builder.build(context)
            last_called_dt = contact.get('last_called_at_dt')
            if isinstance(last_called_dt, datetime):
                last_called_iso = last_called_dt.isoformat()
            else:
                last_called_iso = contact.get('last_called_at')

            results.append(
                {
                    'email': email,
                    'subject': email_content['subject'],
                    'body': email_content['body'],
                    'call': {
                        'id': contact.get('call_id'),
                        'disposition': contact.get('call_disposition'),
                        'direction': contact.get('call_direction'),
                        'duration_seconds': contact.get('duration_seconds'),
                        'last_called_at': last_called_iso,
                        'notes': contact.get('notes'),
                    },
                    'odoo_lead': {
                        'id': odoo_lead.get('id'),
                        'name': odoo_lead.get('name'),
                        'stage_name': odoo_lead.get('stage_name'),
                        'salesperson': odoo_lead.get('salesperson_name'),
                        'phone': odoo_lead.get('phone') or odoo_lead.get('mobile'),
                        'company': odoo_lead.get('partner_name'),
                    },
                }
            )

            if len(results) >= limit:
                break

        return results

