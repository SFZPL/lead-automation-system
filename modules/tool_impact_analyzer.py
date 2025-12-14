"""
Tool Impact Analyzer - Measures the impact of the lead automation tool.

Compares metrics before and after the tool deployment date (November 23, 2025).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from config import Config
from modules.odoo_client import OdooClient
from modules.outlook_client import OutlookClient
from modules.email_token_store import EmailTokenStore

logger = logging.getLogger(__name__)

# System email identifier for engage inbox access
SYSTEM_EMAIL_IDENTIFIER = "SYSTEM_automated.response@prezlab.com"

# Tool deployment date (Nov 23, 2025)
DEPLOYMENT_DATE = datetime(2025, 11, 23)

# Stage progression order (for calculating average stage and velocity)
STAGE_ORDER = {
    "New": 1,
    "Qualified": 2,
    "Proposition": 3,
    "Proposal": 3,  # Alias
    "Won": 4,
    "Lost": 0,  # Lost is not progression
}


class ToolImpactAnalyzer:
    """Analyzes the impact of the lead automation tool on key metrics."""

    def __init__(
        self,
        config: Optional[Config] = None,
        odoo_client: Optional[OdooClient] = None,
    ) -> None:
        self.config = config or Config()
        self.odoo = odoo_client or OdooClient(self.config)
        self.token_store = EmailTokenStore()
        self._outlook_client: Optional[OutlookClient] = None
        self._engage_group_id: Optional[str] = None

    def _ensure_odoo_connection(self) -> None:
        """Ensure Odoo connection is established."""
        if not hasattr(self.odoo, "uid") or self.odoo.uid is None:
            if not self.odoo.connect():
                raise RuntimeError("Failed to connect to Odoo")

    def _get_outlook_access_token(self) -> Optional[str]:
        """Get valid access token for engage inbox."""
        tokens = self.token_store.get_tokens(SYSTEM_EMAIL_IDENTIFIER)
        if not tokens:
            logger.warning(f"No tokens found for {SYSTEM_EMAIL_IDENTIFIER}")
            return None

        outlook = OutlookClient(self.config)

        # Check if token is expired and refresh if needed
        if self.token_store.is_token_expired(SYSTEM_EMAIL_IDENTIFIER):
            logger.info(f"Access token expired for {SYSTEM_EMAIL_IDENTIFIER}, refreshing...")
            try:
                refresh_token = tokens.get("refresh_token")
                if not refresh_token:
                    logger.error(f"No refresh token available for {SYSTEM_EMAIL_IDENTIFIER}")
                    return None

                token_response = outlook.refresh_access_token(refresh_token)
                access_token = token_response.get("access_token")

                self.token_store.update_access_token(
                    SYSTEM_EMAIL_IDENTIFIER,
                    access_token,
                    token_response.get("expires_in", 3600)
                )

                tokens = self.token_store.get_tokens(SYSTEM_EMAIL_IDENTIFIER)
                logger.info(f"Successfully refreshed token for {SYSTEM_EMAIL_IDENTIFIER}")
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                return None

        return tokens.get("access_token")

    def _get_engage_group_id(self, access_token: str) -> Optional[str]:
        """Get the engage group ID."""
        if self._engage_group_id:
            return self._engage_group_id

        outlook = OutlookClient(self.config)
        groups = outlook.get_user_groups(access_token)

        for group in groups:
            display_name = (group.get("displayName") or "").lower()
            mail = (group.get("mail") or "").lower()

            if "engage" in display_name or "engage" in mail:
                self._engage_group_id = group.get("id")
                logger.info(f"Found engage group: {group.get('displayName')} (ID: {self._engage_group_id})")
                return self._engage_group_id

        logger.warning(f"Could not find engage group. Available: {[g.get('displayName') for g in groups]}")
        return None

    def _is_internal_email(self, email: str) -> bool:
        """Check if email is from prezlab domain."""
        if not email:
            return False
        return email.lower().endswith("@prezlab.com")

    def _get_stage_order(self, stage_name: str) -> int:
        """Get numeric order for a stage name."""
        # Try exact match first
        if stage_name in STAGE_ORDER:
            return STAGE_ORDER[stage_name]
        # Try case-insensitive match
        for key, value in STAGE_ORDER.items():
            if key.lower() in stage_name.lower():
                return value
        return 1  # Default to New if unknown

    def get_leads_in_period(
        self,
        start_date: datetime,
        end_date: datetime,
        source_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all leads created within a date range.

        Args:
            start_date: Start of period
            end_date: End of period
            source_filter: Optional source name to filter by

        Returns:
            List of lead dictionaries
        """
        self._ensure_odoo_connection()

        domain = [
            ["create_date", ">=", start_date.strftime("%Y-%m-%d 00:00:00")],
            ["create_date", "<=", end_date.strftime("%Y-%m-%d 23:59:59")],
            ["type", "in", ["lead", "opportunity"]],
        ]

        if source_filter:
            domain.append(["source_id", "ilike", source_filter])

        fields = [
            "id",
            "name",
            "type",
            "stage_id",
            "probability",
            "expected_revenue",
            "create_date",
            "write_date",
            "date_open",
            "date_closed",
            "date_last_stage_update",
            "user_id",
            "source_id",
            "lost_reason_id",
            "partner_name",
            "email_from",
        ]

        try:
            leads = self.odoo._call_kw(
                "crm.lead",
                "search_read",
                [domain],
                {"fields": fields, "order": "create_date asc"},
            ) or []

            # Process stage_id tuples
            for lead in leads:
                stage = lead.get("stage_id")
                if isinstance(stage, (list, tuple)) and len(stage) > 1:
                    lead["stage_name"] = stage[1]
                    lead["stage_id"] = stage[0]
                else:
                    lead["stage_name"] = "Unknown"

                # Process user_id
                user = lead.get("user_id")
                if isinstance(user, (list, tuple)) and len(user) > 1:
                    lead["salesperson_name"] = user[1]
                    lead["user_id"] = user[0]

                # Process source_id
                source = lead.get("source_id")
                if isinstance(source, (list, tuple)) and len(source) > 1:
                    lead["source_name"] = source[1]
                    lead["source_id"] = source[0]

                # Process lost_reason_id
                reason = lead.get("lost_reason_id")
                if isinstance(reason, (list, tuple)) and len(reason) > 1:
                    lead["lost_reason"] = reason[1]
                    lead["lost_reason_id"] = reason[0]

            logger.info(f"Fetched {len(leads)} leads from {start_date.date()} to {end_date.date()}")
            return leads

        except Exception as e:
            logger.error(f"Error fetching leads: {e}")
            return []

    def get_lead_messages_batch(
        self,
        lead_ids: List[int],
        batch_size: int = 50,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Fetch messages for multiple leads efficiently.

        Returns:
            Dict mapping lead_id to list of messages
        """
        self._ensure_odoo_connection()

        result = {}
        for i in range(0, len(lead_ids), batch_size):
            batch_ids = lead_ids[i:i + batch_size]

            domain = [
                ["model", "=", "crm.lead"],
                ["res_id", "in", batch_ids],
                # Include email, comment, and notification (Odoo logs most activities as notification)
                ["message_type", "in", ["email", "comment", "notification"]],
            ]

            fields = [
                "id",
                "date",
                "author_id",
                "email_from",
                "subject",
                "message_type",
                "subtype_id",
                "res_id",
            ]

            try:
                messages = self.odoo._call_kw(
                    "mail.message",
                    "search_read",
                    [domain],
                    {"fields": fields, "order": "date asc"},
                ) or []

                # Group by lead_id
                for msg in messages:
                    lead_id = msg.get("res_id")
                    if lead_id not in result:
                        result[lead_id] = []

                    # Process author
                    author = msg.get("author_id")
                    if isinstance(author, (list, tuple)) and len(author) > 1:
                        msg["author_name"] = author[1]
                        msg["author_id"] = author[0]

                    result[lead_id].append(msg)

            except Exception as e:
                logger.error(f"Error fetching messages for batch: {e}")

        return result

    def _get_engage_emails_in_period(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from engage inbox within a date range.

        Returns:
            List of email messages grouped by conversation
        """
        access_token = self._get_outlook_access_token()
        if not access_token:
            logger.warning("Cannot fetch engage emails - no valid access token")
            return []

        group_id = self._get_engage_group_id(access_token)
        if not group_id:
            logger.warning("Cannot fetch engage emails - engage group not found")
            return []

        # Calculate days back from today to start_date
        days_back = (datetime.now() - start_date).days + 1

        outlook = OutlookClient(self.config)
        try:
            emails = outlook.get_group_conversations(
                access_token=access_token,
                group_email="engage@prezlab.com",
                days_back=days_back,
                limit=5000
            )

            # Filter to only emails within our date range
            filtered_emails = []
            for email in emails:
                received_str = email.get("receivedDateTime", "")
                if not received_str:
                    continue

                try:
                    received_dt = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
                    if received_dt.tzinfo:
                        received_dt = received_dt.replace(tzinfo=None)

                    if start_date <= received_dt <= end_date:
                        filtered_emails.append(email)
                except Exception:
                    continue

            logger.info(f"Found {len(filtered_emails)} engage emails in period {start_date.date()} to {end_date.date()}")
            return filtered_emails

        except Exception as e:
            logger.error(f"Error fetching engage emails: {e}")
            return []

    def _extract_email_address(self, email_data: Dict[str, Any]) -> str:
        """Extract email address from email data structure."""
        from_data = email_data.get("from", {})
        if isinstance(from_data, dict):
            email_addr = from_data.get("emailAddress", {})
            if isinstance(email_addr, dict):
                return email_addr.get("address", "").lower()
        return ""

    def get_responses_in_period(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Fetch first contact response times from engage inbox.

        Measures time from thread creation to first internal response.

        Returns:
            List of response records with timing info
        """
        emails = self._get_engage_emails_in_period(start_date, end_date)
        if not emails:
            return []

        # Group emails by conversation ID
        conversations: Dict[str, List[Dict[str, Any]]] = {}
        for email in emails:
            conv_id = email.get("conversationId", "")
            if conv_id:
                if conv_id not in conversations:
                    conversations[conv_id] = []
                conversations[conv_id].append(email)

        first_responses = []

        for conv_id, thread in conversations.items():
            if len(thread) < 2:
                continue

            # Sort by received date
            sorted_thread = sorted(
                thread,
                key=lambda e: e.get("receivedDateTime", "")
            )

            # Find first message and first internal response
            first_msg = sorted_thread[0]
            first_msg_sender = self._extract_email_address(first_msg)

            # Skip if first message is from prezlab (we initiated)
            if self._is_internal_email(first_msg_sender):
                continue

            # Find first internal reply
            first_internal_reply = None
            for msg in sorted_thread[1:]:
                sender = self._extract_email_address(msg)
                if self._is_internal_email(sender):
                    first_internal_reply = msg
                    break

            if not first_internal_reply:
                continue

            # Check if reply is in our target period
            try:
                reply_date_str = first_internal_reply.get("receivedDateTime", "")
                reply_dt = datetime.fromisoformat(reply_date_str.replace("Z", "+00:00"))
                if reply_dt.tzinfo:
                    reply_dt = reply_dt.replace(tzinfo=None)

                if not (start_date <= reply_dt <= end_date):
                    continue

                first_msg_date_str = first_msg.get("receivedDateTime", "")
                first_msg_dt = datetime.fromisoformat(first_msg_date_str.replace("Z", "+00:00"))
                if first_msg_dt.tzinfo:
                    first_msg_dt = first_msg_dt.replace(tzinfo=None)

                hours_to_response = (reply_dt - first_msg_dt).total_seconds() / 3600

                first_responses.append({
                    "conversation_id": conv_id,
                    "subject": first_msg.get("subject", ""),
                    "external_email": first_msg_sender,
                    "first_msg_date": first_msg_date_str,
                    "response_date": reply_date_str,
                    "hours_to_response": hours_to_response if hours_to_response >= 0 else 0,
                })

            except Exception as e:
                logger.debug(f"Error processing conversation: {e}")
                continue

        logger.info(f"Found {len(first_responses)} first responses in period")
        return first_responses

    def get_email_reply_times_in_period(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[float]:
        """
        Calculate reply times for email conversations from engage inbox.

        Measures time between customer inbound email and our outbound reply.
        Only includes reply pairs where our reply was sent during the period.

        Returns:
            List of reply times in hours
        """
        emails = self._get_engage_emails_in_period(start_date, end_date)
        if not emails:
            return []

        # Group emails by conversation ID
        conversations: Dict[str, List[Dict[str, Any]]] = {}
        for email in emails:
            conv_id = email.get("conversationId", "")
            if conv_id:
                if conv_id not in conversations:
                    conversations[conv_id] = []
                conversations[conv_id].append(email)

        reply_times = []

        for conv_id, thread in conversations.items():
            if len(thread) < 2:
                continue

            # Sort by received date
            sorted_thread = sorted(
                thread,
                key=lambda e: e.get("receivedDateTime", "")
            )

            # Find inbound -> outbound pairs
            for i, msg in enumerate(sorted_thread):
                sender = self._extract_email_address(msg)

                # Is this an inbound (external) message?
                if self._is_internal_email(sender):
                    continue

                # Find next internal reply
                for next_msg in sorted_thread[i + 1:]:
                    next_sender = self._extract_email_address(next_msg)

                    if self._is_internal_email(next_sender):
                        # Check if reply is in our target period
                        try:
                            reply_date_str = next_msg.get("receivedDateTime", "")
                            reply_dt = datetime.fromisoformat(reply_date_str.replace("Z", "+00:00"))
                            if reply_dt.tzinfo:
                                reply_dt = reply_dt.replace(tzinfo=None)

                            if start_date <= reply_dt <= end_date:
                                inbound_date_str = msg.get("receivedDateTime", "")
                                inbound_dt = datetime.fromisoformat(inbound_date_str.replace("Z", "+00:00"))
                                if inbound_dt.tzinfo:
                                    inbound_dt = inbound_dt.replace(tzinfo=None)

                                hours = (reply_dt - inbound_dt).total_seconds() / 3600
                                if hours >= 0:
                                    reply_times.append(hours)
                        except Exception:
                            pass
                        break  # Found reply, move to next inbound

        logger.info(f"Found {len(reply_times)} email reply pairs in period")
        return reply_times

    def calculate_response_metrics_by_period(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """
        Calculate response metrics based on responses SENT during a period.

        This measures:
        1. First contact time: Lead creation -> First outbound email
        2. Email reply time: Customer email -> Our reply

        Returns:
            Dict with response metrics
        """
        responses = self.get_responses_in_period(start_date, end_date)
        reply_times = self.get_email_reply_times_in_period(start_date, end_date)
        period_days = max((end_date - start_date).days, 1)

        # Calculate first contact metrics
        first_contact_times = [r["hours_to_response"] for r in responses] if responses else []
        total_first_contacts = len(first_contact_times)

        avg_first_contact = None
        median_first_contact = None
        if first_contact_times:
            avg_first_contact = sum(first_contact_times) / total_first_contacts
            sorted_fc = sorted(first_contact_times)
            median_first_contact = sorted_fc[len(sorted_fc) // 2]

        within_24h = sum(1 for t in first_contact_times if t <= 24) if first_contact_times else 0
        within_48h = sum(1 for t in first_contact_times if t <= 48) if first_contact_times else 0
        within_72h = sum(1 for t in first_contact_times if t <= 72) if first_contact_times else 0

        # Calculate email reply metrics
        avg_reply_hours = None
        median_reply_hours = None
        if reply_times:
            avg_reply_hours = sum(reply_times) / len(reply_times)
            sorted_rt = sorted(reply_times)
            median_reply_hours = sorted_rt[len(sorted_rt) // 2]

        return {
            "total_responses": total_first_contacts,
            "responses_per_day": round(total_first_contacts / period_days, 1),
            "period_days": period_days,
            "avg_first_contact_hours": round(avg_first_contact, 1) if avg_first_contact is not None else None,
            "median_first_contact_hours": round(median_first_contact, 1) if median_first_contact is not None else None,
            "response_within_24h_pct": round(within_24h / total_first_contacts * 100, 1) if total_first_contacts > 0 else 0,
            "response_within_48h_pct": round(within_48h / total_first_contacts * 100, 1) if total_first_contacts > 0 else 0,
            "response_within_72h_pct": round(within_72h / total_first_contacts * 100, 1) if total_first_contacts > 0 else 0,
            "avg_reply_hours": round(avg_reply_hours, 1) if avg_reply_hours is not None else None,
            "median_reply_hours": round(median_reply_hours, 1) if median_reply_hours is not None else None,
            "total_reply_pairs": len(reply_times),
            "first_contact_times": first_contact_times,
        }

    def calculate_response_metrics(
        self,
        leads: List[Dict[str, Any]],
        messages_by_lead: Dict[int, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Calculate response time metrics for leads created in a period.

        NOTE: This is the LEGACY method that measures by lead creation date.
        For measuring responses SENT in a period, use calculate_response_metrics_by_period().

        Returns:
            Dict with response metrics including:
            - first_contact_times: List of hours to first contact
            - avg_first_contact_hours: Average time to first contact
            - response_within_24h: Percentage responded within 24h
            - response_within_48h: Percentage responded within 48h
            - response_within_72h: Percentage responded within 72h
        """
        first_contact_times = []
        subsequent_response_times = []

        for lead in leads:
            lead_id = lead.get("id")
            create_date_str = lead.get("create_date")

            if not create_date_str or lead_id not in messages_by_lead:
                continue

            try:
                create_date = datetime.fromisoformat(create_date_str.replace("Z", "+00:00"))
            except:
                continue

            messages = messages_by_lead.get(lead_id, [])
            if not messages:
                continue

            # Sort messages by date
            sorted_messages = sorted(messages, key=lambda m: m.get("date", ""))

            # Find first outbound message (from internal user, not customer)
            first_outbound = None
            for msg in sorted_messages:
                # Skip if it's from the customer (email matches lead email)
                msg_email = msg.get("email_from", "")
                lead_email = lead.get("email_from", "")

                # Consider it outbound if author_name doesn't contain lead's email domain
                # or if it's a comment type (internal note that became email)
                is_outbound = True
                if lead_email and msg_email:
                    lead_domain = lead_email.split("@")[-1] if "@" in lead_email else ""
                    msg_domain = msg_email.split("@")[-1] if "@" in msg_email else ""
                    if lead_domain and msg_domain == lead_domain:
                        is_outbound = False

                if is_outbound:
                    first_outbound = msg
                    break

            if first_outbound:
                try:
                    msg_date = datetime.fromisoformat(
                        first_outbound.get("date", "").replace("Z", "+00:00")
                    )
                    # Make create_date timezone-naive for comparison if needed
                    if create_date.tzinfo is not None:
                        create_date = create_date.replace(tzinfo=None)
                    if msg_date.tzinfo is not None:
                        msg_date = msg_date.replace(tzinfo=None)

                    hours_to_contact = (msg_date - create_date).total_seconds() / 3600
                    if hours_to_contact >= 0:  # Sanity check
                        first_contact_times.append(hours_to_contact)
                except Exception as e:
                    logger.debug(f"Error calculating first contact time: {e}")

        # Calculate metrics
        total_leads = len(leads)
        leads_with_contact = len(first_contact_times)

        response_rate = (leads_with_contact / total_leads * 100) if total_leads > 0 else 0

        within_24h = sum(1 for t in first_contact_times if t <= 24)
        within_48h = sum(1 for t in first_contact_times if t <= 48)
        within_72h = sum(1 for t in first_contact_times if t <= 72)

        avg_first_contact = (
            sum(first_contact_times) / len(first_contact_times)
            if first_contact_times else None
        )

        return {
            "total_leads": total_leads,
            "leads_with_contact": leads_with_contact,
            "response_rate_pct": round(response_rate, 1),
            "avg_first_contact_hours": round(avg_first_contact, 1) if avg_first_contact else None,
            "median_first_contact_hours": round(
                sorted(first_contact_times)[len(first_contact_times) // 2], 1
            ) if first_contact_times else None,
            "response_within_24h_pct": round(within_24h / leads_with_contact * 100, 1) if leads_with_contact > 0 else 0,
            "response_within_48h_pct": round(within_48h / leads_with_contact * 100, 1) if leads_with_contact > 0 else 0,
            "response_within_72h_pct": round(within_72h / leads_with_contact * 100, 1) if leads_with_contact > 0 else 0,
            "first_contact_times": first_contact_times,  # Raw data for distribution
        }

    def calculate_stage_metrics(
        self,
        leads: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate stage conversion and progression metrics.

        Returns:
            Dict with stage metrics including:
            - stage_distribution: Count and percentage at each stage
            - conversion_rates: Percentage reaching each stage
            - avg_stage_score: Weighted average stage progression
        """
        stage_counts = defaultdict(int)
        stage_values = defaultdict(float)
        stage_scores = []

        for lead in leads:
            stage_name = lead.get("stage_name", "Unknown")
            stage_counts[stage_name] += 1
            stage_values[stage_name] += lead.get("expected_revenue", 0) or 0
            stage_scores.append(self._get_stage_order(stage_name))

        total_leads = len(leads)

        # Stage distribution
        stage_distribution = []
        for stage, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
            stage_distribution.append({
                "stage": stage,
                "count": count,
                "percentage": round(count / total_leads * 100, 1) if total_leads > 0 else 0,
                "total_value": round(stage_values[stage], 2),
            })

        # Conversion rates (cumulative - reached this stage or beyond)
        conversion_rates = {}
        for stage_name, order in STAGE_ORDER.items():
            if order > 0:  # Exclude Lost
                reached = sum(1 for s in stage_scores if s >= order)
                conversion_rates[stage_name] = round(
                    reached / total_leads * 100, 1
                ) if total_leads > 0 else 0

        # Average stage score
        avg_stage_score = (
            sum(stage_scores) / len(stage_scores)
            if stage_scores else 0
        )

        return {
            "total_leads": total_leads,
            "stage_distribution": stage_distribution,
            "conversion_rates": conversion_rates,
            "avg_stage_score": round(avg_stage_score, 2),
        }

    def calculate_win_loss_metrics(
        self,
        leads: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate win/loss rate metrics.

        Returns:
            Dict with win/loss metrics
        """
        total = len(leads)
        won = sum(1 for l in leads if l.get("probability", 0) == 100 or
                  "won" in l.get("stage_name", "").lower())
        lost = sum(1 for l in leads if l.get("probability", 0) == 0 and
                   l.get("lost_reason_id"))
        active = total - won - lost

        # Value metrics
        total_value = sum(l.get("expected_revenue", 0) or 0 for l in leads)
        won_value = sum(
            l.get("expected_revenue", 0) or 0
            for l in leads
            if l.get("probability", 0) == 100 or "won" in l.get("stage_name", "").lower()
        )
        lost_value = sum(
            l.get("expected_revenue", 0) or 0
            for l in leads
            if l.get("probability", 0) == 0 and l.get("lost_reason_id")
        )

        # Lost reasons breakdown
        lost_reasons = defaultdict(int)
        for l in leads:
            if l.get("probability", 0) == 0 and l.get("lost_reason"):
                lost_reasons[l["lost_reason"]] += 1

        return {
            "total_leads": total,
            "won_count": won,
            "lost_count": lost,
            "active_count": active,
            "win_rate_pct": round(won / total * 100, 1) if total > 0 else 0,
            "loss_rate_pct": round(lost / total * 100, 1) if total > 0 else 0,
            "total_value": round(total_value, 2),
            "won_value": round(won_value, 2),
            "lost_value": round(lost_value, 2),
            "value_win_rate_pct": round(won_value / total_value * 100, 1) if total_value > 0 else 0,
            "lost_reasons": dict(sorted(lost_reasons.items(), key=lambda x: -x[1])),
        }

    def calculate_velocity_metrics(
        self,
        leads: List[Dict[str, Any]],
        period_days: int,
    ) -> Dict[str, Any]:
        """
        Calculate lead velocity metrics.

        Args:
            leads: List of leads
            period_days: Number of days in the period

        Returns:
            Dict with velocity metrics
        """
        weeks = max(period_days / 7, 1)

        # Leads progressing per week
        progressing = sum(
            1 for l in leads
            if self._get_stage_order(l.get("stage_name", "")) >= 2
        )

        # Calculate time to stage transitions where possible
        stage_transition_times = []
        for lead in leads:
            create_str = lead.get("create_date")
            stage_update_str = lead.get("date_last_stage_update")

            if create_str and stage_update_str:
                try:
                    create_dt = datetime.fromisoformat(create_str.replace("Z", "+00:00"))
                    update_dt = datetime.fromisoformat(stage_update_str.replace("Z", "+00:00"))

                    if create_dt.tzinfo:
                        create_dt = create_dt.replace(tzinfo=None)
                    if update_dt.tzinfo:
                        update_dt = update_dt.replace(tzinfo=None)

                    days_to_transition = (update_dt - create_dt).days
                    if days_to_transition >= 0:
                        stage_transition_times.append(days_to_transition)
                except:
                    pass

        avg_days_to_transition = (
            sum(stage_transition_times) / len(stage_transition_times)
            if stage_transition_times else None
        )

        return {
            "leads_per_week": round(len(leads) / weeks, 1),
            "progressing_per_week": round(progressing / weeks, 1),
            "progression_rate_pct": round(progressing / len(leads) * 100, 1) if leads else 0,
            "avg_days_to_stage_change": round(avg_days_to_transition, 1) if avg_days_to_transition else None,
        }

    def generate_impact_report(
        self,
        before_days: int = 90,
        after_days: Optional[int] = None,
        source_filter: Optional[str] = None,
        deployment_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive before/after impact report.

        Args:
            before_days: Number of days before deployment to analyze
            after_days: Number of days after deployment (None = until today)
            source_filter: Optional lead source filter
            deployment_date: Custom deployment date (defaults to Nov 23, 2025)

        Returns:
            Complete impact report with before/after comparisons
        """
        deploy_date = deployment_date or DEPLOYMENT_DATE
        today = datetime.now()

        # Calculate periods
        before_end = deploy_date - timedelta(days=1)
        before_start = before_end - timedelta(days=before_days)

        after_start = deploy_date
        if after_days:
            after_end = after_start + timedelta(days=after_days)
        else:
            after_end = today

        actual_after_days = (after_end - after_start).days

        logger.info(f"Analyzing impact: BEFORE {before_start.date()} to {before_end.date()}")
        logger.info(f"Analyzing impact: AFTER {after_start.date()} to {after_end.date()}")

        # Fetch leads for both periods (for stage/win-loss metrics)
        before_leads = self.get_leads_in_period(before_start, before_end, source_filter)
        after_leads = self.get_leads_in_period(after_start, after_end, source_filter)

        # Calculate response metrics based on responses SENT in each period
        # This measures "how fast were we responding during this time period"
        logger.info("Calculating response metrics by period (responses SENT)...")
        before_response = self.calculate_response_metrics_by_period(before_start, before_end)
        after_response = self.calculate_response_metrics_by_period(after_start, after_end)

        before_stages = self.calculate_stage_metrics(before_leads)
        after_stages = self.calculate_stage_metrics(after_leads)

        before_winloss = self.calculate_win_loss_metrics(before_leads)
        after_winloss = self.calculate_win_loss_metrics(after_leads)

        before_velocity = self.calculate_velocity_metrics(before_leads, before_days)
        after_velocity = self.calculate_velocity_metrics(after_leads, actual_after_days)

        # Calculate deltas (improvement)
        def calc_delta(after_val, before_val):
            if before_val is None or after_val is None:
                return None
            if before_val == 0:
                return None
            return round(((after_val - before_val) / before_val) * 100, 1)

        deltas = {
            "responses_per_day": calc_delta(
                after_response["responses_per_day"],
                before_response["responses_per_day"]
            ) if before_response["responses_per_day"] > 0 else None,
            "avg_first_contact_hours": calc_delta(
                before_response["avg_first_contact_hours"],  # Lower is better, so inverted
                after_response["avg_first_contact_hours"]
            ) if after_response["avg_first_contact_hours"] and before_response["avg_first_contact_hours"] else None,
            "response_within_24h": calc_delta(
                after_response["response_within_24h_pct"],
                before_response["response_within_24h_pct"]
            ),
            "avg_stage_score": calc_delta(
                after_stages["avg_stage_score"],
                before_stages["avg_stage_score"]
            ),
            "win_rate": calc_delta(
                after_winloss["win_rate_pct"],
                before_winloss["win_rate_pct"]
            ),
            "loss_rate": calc_delta(
                before_winloss["loss_rate_pct"],  # Lower is better, so inverted
                after_winloss["loss_rate_pct"]
            ) if after_winloss["loss_rate_pct"] else None,
            "progression_rate": calc_delta(
                after_velocity["progression_rate_pct"],
                before_velocity["progression_rate_pct"]
            ),
        }

        return {
            "generated_at": datetime.now().isoformat(),
            "deployment_date": deploy_date.isoformat(),
            "periods": {
                "before": {
                    "start": before_start.isoformat(),
                    "end": before_end.isoformat(),
                    "days": before_days,
                },
                "after": {
                    "start": after_start.isoformat(),
                    "end": after_end.isoformat(),
                    "days": actual_after_days,
                },
            },
            "source_filter": source_filter,
            "summary": {
                "before_lead_count": len(before_leads),
                "after_lead_count": len(after_leads),
                "key_improvements": deltas,
            },
            "response_metrics": {
                "before": before_response,
                "after": after_response,
            },
            "stage_metrics": {
                "before": before_stages,
                "after": after_stages,
            },
            "win_loss_metrics": {
                "before": before_winloss,
                "after": after_winloss,
            },
            "velocity_metrics": {
                "before": before_velocity,
                "after": after_velocity,
            },
        }

    def get_available_sources(self) -> List[str]:
        """Get list of available lead sources for filtering."""
        self._ensure_odoo_connection()

        try:
            sources = self.odoo._call_kw(
                "utm.source",
                "search_read",
                [[]],
                {"fields": ["name"], "order": "name"},
            ) or []

            return [s["name"] for s in sources]
        except Exception as e:
            logger.error(f"Error fetching sources: {e}")
            return []
