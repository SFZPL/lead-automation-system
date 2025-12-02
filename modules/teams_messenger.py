"""
Microsoft Teams Group Chat Messenger

Sends formatted messages to Teams group chats via Microsoft Graph API.
"""

import requests
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class TeamsMessenger:
    """Send messages to Microsoft Teams group chats."""

    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, access_token: str):
        """
        Initialize Teams messenger.

        Args:
            access_token: Microsoft Graph API access token with Chat.ReadWrite permission
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def send_message_to_chat(self, chat_id: str, message_html: str) -> Dict[str, Any]:
        """
        Send a message to a Teams group chat.

        Args:
            chat_id: The Teams chat ID (from the chat URL)
            message_html: HTML-formatted message content

        Returns:
            Response from Microsoft Graph API
        """
        url = f"{self.GRAPH_BASE}/chats/{chat_id}/messages"

        payload = {
            "body": {
                "contentType": "html",
                "content": message_html
            }
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Successfully sent message to Teams chat {chat_id}")
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to send Teams message: {e}")
            logger.error(f"Response: {e.response.text}")
            raise

    def send_adaptive_card_to_chat(self, chat_id: str, card_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send an Adaptive Card to a Teams chat.

        Args:
            chat_id: The Teams chat ID
            card_content: The Adaptive Card JSON content

        Returns:
            Response from Microsoft Graph API
        """
        url = f"{self.GRAPH_BASE}/chats/{chat_id}/messages"

        payload = {
            "body": {
                "contentType": "html",
                "content": "<attachment id=\"1\"></attachment>"
            },
            "attachments": [
                {
                    "id": "1",
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card_content
                }
            ]
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Successfully sent Adaptive Card to Teams chat {chat_id}")
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to send Adaptive Card: {e}")
            logger.error(f"Response: {e.response.text}")
            raise

    def create_one_on_one_chat(self, user_email: str) -> Optional[str]:
        """
        Create or get a 1:1 chat with a user.

        Args:
            user_email: The email address of the user to chat with

        Returns:
            The chat ID if successful, None otherwise
        """
        try:
            # Step 1: Get the recipient's user ID from their email
            user_url = f"{self.GRAPH_BASE}/users/{user_email}"
            user_response = requests.get(user_url, headers=self.headers, timeout=30)
            user_response.raise_for_status()
            recipient_user_id = user_response.json().get("id")

            if not recipient_user_id:
                logger.error(f"Could not get user ID for {user_email}")
                return None

            logger.info(f"Got user ID {recipient_user_id} for {user_email}")

            # Step 2: Get current user ID (sender)
            me_response = requests.get(f"{self.GRAPH_BASE}/me", headers=self.headers, timeout=30)
            me_response.raise_for_status()
            my_user_id = me_response.json().get("id")

            # Step 3: Create or get existing 1:1 chat using user IDs
            chat_payload = {
                "chatType": "oneOnOne",
                "members": [
                    {
                        "@odata.type": "#microsoft.graph.aadUserConversationMember",
                        "roles": ["owner"],
                        "user@odata.bind": f"{self.GRAPH_BASE}/users/{my_user_id}"
                    },
                    {
                        "@odata.type": "#microsoft.graph.aadUserConversationMember",
                        "roles": ["owner"],
                        "user@odata.bind": f"{self.GRAPH_BASE}/users/{recipient_user_id}"
                    }
                ]
            }

            chat_response = requests.post(f"{self.GRAPH_BASE}/chats", headers=self.headers, json=chat_payload, timeout=30)
            chat_response.raise_for_status()
            chat_id = chat_response.json().get("id")

            logger.info(f"Created/retrieved 1:1 chat with {user_email}: {chat_id}")
            return chat_id

        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to create 1:1 chat with {user_email}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def send_direct_message(self, user_email: str, message_html: str = None, adaptive_card: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send a direct message to a user (creates 1:1 chat if needed).

        Args:
            user_email: The email address of the recipient
            message_html: HTML-formatted message content (optional if adaptive_card is provided)
            adaptive_card: Adaptive Card JSON content (optional)

        Returns:
            Response from Microsoft Graph API or error dict
        """
        # Create or get the 1:1 chat
        chat_id = self.create_one_on_one_chat(user_email)

        if not chat_id:
            return {"success": False, "error": f"Could not create chat with {user_email}"}

        # Send the message to the 1:1 chat
        if adaptive_card:
            return self.send_adaptive_card_to_chat(chat_id, adaptive_card)
        else:
            return self.send_message_to_chat(chat_id, message_html)

    @staticmethod
    def format_followup_report_summary(report_data: Dict[str, Any]) -> str:
        """
        Format a follow-up report into a professional Teams message.

        Args:
            report_data: The report data from ProposalFollowupAnalyzer

        Returns:
            HTML-formatted message string
        """
        # Handle both direct report data and nested summary structure
        summary = report_data.get('summary', report_data)

        # Get individual counts
        unanswered_count = summary.get('unanswered_count', 0)
        pending_proposals_count = summary.get('pending_proposals_count', 0)
        total_threads = summary.get('total_count', 0)

        # Calculate engaged (threads that don't need follow-up)
        needs_followup = unanswered_count + pending_proposals_count
        engaged = total_threads - needs_followup

        # Get threads from unanswered and pending_proposals lists
        unanswered = report_data.get('unanswered', [])
        pending_proposals = report_data.get('pending_proposals', [])
        all_threads = unanswered + pending_proposals

        # Sort by expected_revenue descending
        top_opportunities = sorted(
            all_threads,
            key=lambda x: x.get('expected_revenue', 0),
            reverse=True
        )[:5]  # Top 5

        # Build HTML message
        html = f"""
<h2>📊 Daily Proposal Follow-up Report</h2>

<p><strong>Summary:</strong></p>
<ul>
    <li><strong>{unanswered_count}</strong> unanswered emails</li>
    <li><strong>{pending_proposals_count}</strong> pending proposals (sent, no response in 3+ days)</li>
    <li><strong>{total_threads}</strong> total email threads tracked</li>
</ul>

<h3>🔥 Top Opportunities Needing Follow-up:</h3>
"""

        if top_opportunities:
            html += "<ol>"
            for opp in top_opportunities:
                # Handle nested lead data structure
                lead = opp.get('lead', {})

                # Try different field names from the report structure
                company = (
                    opp.get('partner_name') or
                    lead.get('partner_name') or
                    opp.get('company_name') or
                    lead.get('company_name') or
                    opp.get('subject') or
                    'Unknown Company'
                )

                # Try to get value from different possible fields
                value = (
                    opp.get('expected_revenue') or
                    lead.get('expected_revenue') or
                    0
                )

                stage = (
                    opp.get('stage') or
                    lead.get('stage') or
                    'Unknown'
                )

                days_since = (
                    opp.get('days_since_last_response') or
                    opp.get('days_no_response') or
                    0
                )

                html += f"""
    <li>
        <strong>{company}</strong> - AED {value:,.0f}<br/>
        <em>Stage:</em> {stage} | <em>Last contact:</em> {days_since} days ago
    </li>
"""
            html += "</ol>"
        else:
            html += "<p><em>No opportunities currently need follow-up.</em></p>"

        html += """
<hr/>
<p><em>🤖 Automated report generated by PrezLab Lead Automation System</em></p>
"""

        return html

    @staticmethod
    def format_weekly_pipeline_report(report_data: Dict[str, Any]) -> str:
        """
        Format a weekly pipeline report into a professional Teams message.

        Args:
            report_data: The report data from WeeklyPipelineAnalyzer

        Returns:
            HTML-formatted message string
        """
        week_start = report_data.get('week_start', 'N/A')
        week_end = report_data.get('week_end', 'N/A')
        overview = report_data.get('overview', {})
        pipeline_stages = report_data.get('pipeline_stages', [])
        top_opportunities = report_data.get('top_opportunities', [])
        at_risk_leads = report_data.get('at_risk_leads', [])

        # Build HTML message
        html = f"""
<h2>🟦 WEEKLY PIPELINE PERFORMANCE REPORT</h2>
<p><strong>Week:</strong> {week_start} to {week_end}</p>

<h3>📌 Week Overview</h3>
<ul>
    <li><strong>{overview.get('new_leads', 0)}</strong> new leads added</li>
    <li><strong>{overview.get('qualified_leads', 0)}</strong> leads qualified</li>
    <li><strong>{overview.get('proposals_sent', 0)}</strong> proposals sent</li>
    <li><strong>{overview.get('deals_closed', 0)}</strong> deals closed (AED {overview.get('closed_value', 0):,.0f})</li>
    <li><strong>{overview.get('deals_lost', 0)}</strong> deals lost</li>
</ul>
"""

        # Lost reasons breakdown
        lost_reasons = overview.get('lost_reasons', {})
        if lost_reasons:
            html += "<p><strong>Lost Reasons:</strong></p><ul>"
            for reason, count in sorted(lost_reasons.items(), key=lambda x: x[1], reverse=True):
                html += f"<li>{reason}: {count}</li>"
            html += "</ul>"

        # Pipeline by stage
        html += """
<h3>📊 Pipeline by Stage</h3>
<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
    <thead>
        <tr style="background-color: #f0f0f0;">
            <th>Stage</th>
            <th>Count</th>
            <th>Avg Age (days)</th>
            <th>Total Value (AED)</th>
        </tr>
    </thead>
    <tbody>
"""

        for stage in pipeline_stages:
            html += f"""
        <tr>
            <td><strong>{stage.get('stage_name', 'Unknown')}</strong></td>
            <td>{stage.get('count', 0)}</td>
            <td>{stage.get('avg_age_days', 0)}</td>
            <td>{stage.get('total_value', 0):,.0f}</td>
        </tr>
"""
            # Show top clients in this stage
            top_clients = stage.get('top_clients', [])
            if top_clients:
                html += f"""
        <tr>
            <td colspan="4" style="font-size: 0.9em; color: #666;">
                <em>Top clients:</em> {', '.join(top_clients[:3])}
            </td>
        </tr>
"""

        html += """
    </tbody>
</table>
"""

        # Top opportunities
        html += """
<h3>🔥 Top 5 Opportunities</h3>
"""

        if top_opportunities:
            html += "<ol>"
            for opp in top_opportunities:
                company = opp.get('company', 'Unknown')
                name = opp.get('opportunity_name', company)
                stage = opp.get('stage', 'Unknown')
                value = opp.get('potential_value', 0)
                owner = opp.get('owner', 'Unassigned')
                days_since = opp.get('days_since_last_activity', 0)

                html += f"""
    <li>
        <strong>{name}</strong>{' - ' + company if company and company != name else ''}<br/>
        <em>Stage:</em> {stage} | <em>Value:</em> AED {value:,.0f}<br/>
        <em>Owner:</em> {owner} | <em>Last activity:</em> {days_since} days ago
    </li>
"""
            html += "</ol>"
        else:
            html += "<p><em>No active opportunities found.</em></p>"

        # At-risk leads
        html += """
<h3>🚨 At Risk Leads (10+ Days No Activity)</h3>
"""

        if at_risk_leads:
            html += f"<p><strong>{len(at_risk_leads)}</strong> leads at risk:</p><ul>"
            for lead in at_risk_leads[:10]:  # Top 10 most at risk
                company = lead.get('company', 'Unknown')
                name = lead.get('lead_name', company)
                stage = lead.get('stage', 'Unknown')
                owner = lead.get('owner', 'Unassigned')
                days = lead.get('days_inactive', 0)
                value = lead.get('value', 0)

                html += f"""
    <li>
        <strong>{name}</strong> ({stage}) - AED {value:,.0f}<br/>
        <em>Owner:</em> {owner} | <em>Inactive:</em> {days} days
    </li>
"""
            html += "</ul>"
        else:
            html += "<p><em>✅ No leads at risk - great job staying on top of follow-ups!</em></p>"

        html += """
<hr/>
<p><em>🤖 Automated weekly report generated by PrezLab Lead Automation System</em></p>
"""

        return html

    @staticmethod
    def extract_chat_id_from_url(teams_url: str) -> Optional[str]:
        """
        Extract chat ID from a Teams chat URL.

        Example URL:
        https://teams.microsoft.com/l/chat/19:1d7fae90086342a49e12a433576697c7@thread.v2/conversations?...

        Returns:
            The chat ID (e.g., "19:1d7fae90086342a49e12a433576697c7@thread.v2")
        """
        import re

        # Pattern: /chat/{chatId}/
        match = re.search(r'/chat/([^/]+)/', teams_url)
        if match:
            return match.group(1)

        return None
