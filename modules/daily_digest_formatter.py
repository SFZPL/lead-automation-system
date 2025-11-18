"""
Daily Digest Formatter
Formats proposal follow-up data into a daily digest for Teams.
"""
from typing import Dict, Any, List
from datetime import datetime


class DailyDigestFormatter:
    """Formats follow-up reports into daily digest summaries."""

    @staticmethod
    def format_digest(report_data: Dict[str, Any]) -> str:
        """
        Format a complete follow-up report into a daily digest.

        Args:
            report_data: The result from a saved complete report

        Returns:
            HTML-formatted daily digest string
        """
        unanswered = report_data.get('unanswered', [])
        pending_proposals = report_data.get('pending_proposals', [])
        summary = report_data.get('summary', {})

        # Combine all threads
        all_threads = unanswered + pending_proposals

        # Categorize threads
        priority_threads = DailyDigestFormatter._get_priority_threads(all_threads)
        aging_threads = DailyDigestFormatter._get_aging_threads(all_threads)
        at_risk_threads = DailyDigestFormatter._get_at_risk_threads(all_threads)

        # Build HTML
        html = f"""
<h2>✅ DAILY FOLLOW-UP REPORT</h2>
<p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
<hr/>

<h3>📌 Executive Snapshot</h3>
<ul>
<li><strong>Total Follow-ups:</strong> {summary.get('total_count', 0)}</li>
<li><strong>Unanswered Emails:</strong> {summary.get('unanswered_count', 0)}</li>
<li><strong>Pending Proposals:</strong> {summary.get('pending_proposals_count', 0)}</li>
<li><strong>High Priority:</strong> {len(priority_threads)}</li>
<li><strong>At Risk (15+ days):</strong> {len(at_risk_threads)}</li>
</ul>

<hr/>

<h3>🔥 Priority Follow-Ups (Top 10 by urgency × value)</h3>
"""

        if priority_threads:
            html += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
            html += """
<tr style='background-color: #f0f0f0;'>
<th>Contact</th>
<th>Subject</th>
<th>Days Waiting</th>
<th>Value (AED)</th>
<th>Last From</th>
</tr>
"""
            for thread in priority_threads[:10]:
                odoo_lead = thread.get('odoo_lead') or {}
                revenue = odoo_lead.get('expected_revenue', 0)
                last_sender = thread.get('last_internal_sender', 'N/A')

                html += f"""
<tr>
<td>{thread.get('external_email', 'N/A')}</td>
<td>{thread.get('subject', 'N/A')[:50]}...</td>
<td>{thread.get('days_waiting', 0)}</td>
<td>AED {revenue:,.0f}</td>
<td>{last_sender}</td>
</tr>
"""
            html += "</table>"
        else:
            html += "<p><em>No priority follow-ups at this time.</em></p>"

        html += "<hr/>"

        # Aging Follow-Ups (5-14 days)
        html += "<h3>📌 Aging Follow-Ups (5-14 days)</h3>"
        if aging_threads:
            html += f"<p><strong>Count:</strong> {len(aging_threads)}</p>"
            html += "<ul>"
            for thread in aging_threads[:5]:  # Show top 5
                html += f"<li>{thread.get('external_email', 'N/A')} - {thread.get('subject', 'N/A')[:40]}... ({thread.get('days_waiting', 0)} days)</li>"
            html += "</ul>"
            if len(aging_threads) > 5:
                html += f"<p><em>...and {len(aging_threads) - 5} more</em></p>"
        else:
            html += "<p><em>No aging follow-ups.</em></p>"

        html += "<hr/>"

        # At-Risk Leads (15+ days)
        html += "<h3>⚠️ At-Risk Leads (15+ days)</h3>"
        if at_risk_threads:
            html += f"<p><strong>Count:</strong> {len(at_risk_threads)}</p>"
            html += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
            html += """
<tr style='background-color: #fff3cd;'>
<th>Contact</th>
<th>Subject</th>
<th>Days Waiting</th>
<th>Value (AED)</th>
</tr>
"""
            for thread in at_risk_threads[:10]:  # Show top 10 at-risk
                odoo_lead = thread.get('odoo_lead') or {}
                revenue = odoo_lead.get('expected_revenue', 0)

                html += f"""
<tr>
<td>{thread.get('external_email', 'N/A')}</td>
<td>{thread.get('subject', 'N/A')[:50]}...</td>
<td style='color: red;'><strong>{thread.get('days_waiting', 0)}</strong></td>
<td>AED {revenue:,.0f}</td>
</tr>
"""
            html += "</table>"
            if len(at_risk_threads) > 10:
                html += f"<p><em>...and {len(at_risk_threads) - 10} more at-risk leads</em></p>"
        else:
            html += "<p><em>No at-risk leads.</em></p>"

        html += """
<hr/>
<p style='text-align: center; color: gray; font-size: 12px;'>
🤖 Generated with PrezLab Lead Automation System
</p>
"""

        return html

    @staticmethod
    def _get_priority_threads(threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get priority threads sorted by urgency × value."""
        priority = []
        for thread in threads:
            days = thread.get('days_waiting', 0)
            odoo_lead = thread.get('odoo_lead') or {}
            revenue = odoo_lead.get('expected_revenue', 0)

            # Calculate priority score (days × revenue)
            priority_score = days * revenue
            thread_copy = thread.copy()
            thread_copy['priority_score'] = priority_score
            priority.append(thread_copy)

        # Sort by priority score descending
        priority.sort(key=lambda x: x['priority_score'], reverse=True)
        return priority

    @staticmethod
    def _get_aging_threads(threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get threads that are aging (5-14 days)."""
        return [
            t for t in threads
            if 5 <= t.get('days_waiting', 0) <= 14
        ]

    @staticmethod
    def _get_at_risk_threads(threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get threads that are at risk (15+ days)."""
        at_risk = [
            t for t in threads
            if t.get('days_waiting', 0) >= 15
        ]
        # Sort by days waiting descending
        at_risk.sort(key=lambda x: x.get('days_waiting', 0), reverse=True)
        return at_risk

    @staticmethod
    def format_individual_digest(report_data: Dict[str, Any], team_member_name: str) -> str:
        """
        Format a personalized digest for a specific team member showing only their follow-ups.

        Args:
            report_data: The result from a saved complete report
            team_member_name: Name of the team member (matches last_internal_sender field)

        Returns:
            HTML-formatted personal digest string
        """
        unanswered = report_data.get('unanswered', [])
        pending_proposals = report_data.get('pending_proposals', [])

        # Combine all threads
        all_threads = unanswered + pending_proposals

        # Filter to only this team member's threads
        my_threads = [
            t for t in all_threads
            if t.get('last_internal_sender') == team_member_name
        ]

        if not my_threads:
            # No threads for this person
            return None

        # Categorize threads
        priority_threads = DailyDigestFormatter._get_priority_threads(my_threads)
        aging_threads = DailyDigestFormatter._get_aging_threads(my_threads)
        at_risk_threads = DailyDigestFormatter._get_at_risk_threads(my_threads)

        # Count by category
        unanswered_count = len([t for t in my_threads if t in unanswered])
        pending_count = len([t for t in my_threads if t in pending_proposals])

        # Build HTML
        html = f"""
<h2>✅ YOUR DAILY FOLLOW-UP REPORT</h2>
<p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
<p><strong>For:</strong> {team_member_name}</p>
<hr/>

<h3>📌 Your Snapshot</h3>
<ul>
<li><strong>Total Follow-ups:</strong> {len(my_threads)}</li>
<li><strong>Unanswered Emails:</strong> {unanswered_count}</li>
<li><strong>Pending Proposals:</strong> {pending_count}</li>
<li><strong>High Priority:</strong> {len(priority_threads)}</li>
<li><strong>At Risk (15+ days):</strong> {len(at_risk_threads)}</li>
</ul>

<hr/>

<h3>🔥 Your Priority Follow-Ups (Top by urgency × value)</h3>
"""

        if priority_threads:
            html += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
            html += """
<tr style='background-color: #f0f0f0;'>
<th>Contact</th>
<th>Subject</th>
<th>Days Waiting</th>
<th>Value (AED)</th>
</tr>
"""
            for thread in priority_threads[:10]:
                odoo_lead = thread.get('odoo_lead') or {}
                revenue = odoo_lead.get('expected_revenue', 0)

                html += f"""
<tr>
<td>{thread.get('external_email', 'N/A')}</td>
<td>{thread.get('subject', 'N/A')[:50]}...</td>
<td>{thread.get('days_waiting', 0)}</td>
<td>AED {revenue:,.0f}</td>
</tr>
"""
            html += "</table>"
        else:
            html += "<p><em>No priority follow-ups.</em></p>"

        html += "<hr/>"

        # Aging Follow-Ups (5-14 days)
        html += "<h3>📌 Aging Follow-Ups (5-14 days)</h3>"
        if aging_threads:
            html += f"<p><strong>Count:</strong> {len(aging_threads)}</p>"
            html += "<ul>"
            for thread in aging_threads[:5]:
                html += f"<li>{thread.get('external_email', 'N/A')} - {thread.get('subject', 'N/A')[:40]}... ({thread.get('days_waiting', 0)} days)</li>"
            html += "</ul>"
            if len(aging_threads) > 5:
                html += f"<p><em>...and {len(aging_threads) - 5} more</em></p>"
        else:
            html += "<p><em>No aging follow-ups.</em></p>"

        html += "<hr/>"

        # At-Risk Leads (15+ days)
        html += "<h3>⚠️ At-Risk Leads (15+ days)</h3>"
        if at_risk_threads:
            html += f"<p><strong>Count:</strong> {len(at_risk_threads)}</p>"
            html += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
            html += """
<tr style='background-color: #fff3cd;'>
<th>Contact</th>
<th>Subject</th>
<th>Days Waiting</th>
<th>Value (AED)</th>
</tr>
"""
            for thread in at_risk_threads[:10]:
                odoo_lead = thread.get('odoo_lead') or {}
                revenue = odoo_lead.get('expected_revenue', 0)

                html += f"""
<tr>
<td>{thread.get('external_email', 'N/A')}</td>
<td>{thread.get('subject', 'N/A')[:50]}...</td>
<td style='color: red;'><strong>{thread.get('days_waiting', 0)}</strong></td>
<td>AED {revenue:,.0f}</td>
</tr>
"""
            html += "</table>"
            if len(at_risk_threads) > 10:
                html += f"<p><em>...and {len(at_risk_threads) - 10} more at-risk leads</em></p>"
        else:
            html += "<p><em>No at-risk leads.</em></p>"

        html += """
<hr/>
<p style='text-align: center; color: gray; font-size: 12px;'>
🤖 Generated with PrezLab Lead Automation System
</p>
"""

        return html
