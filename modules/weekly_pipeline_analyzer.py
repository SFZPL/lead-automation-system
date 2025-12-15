"""
Weekly Pipeline Performance Analyzer

Generates comprehensive weekly pipeline reports including:
- New leads, qualified leads, proposals sent, deals closed/lost
- Pipeline breakdown by stage with ages
- Top opportunities
- At-risk leads
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from modules.odoo_client import OdooClient
from config import Config

logger = logging.getLogger(__name__)


class WeeklyPipelineAnalyzer:
    """Analyze pipeline performance for weekly reporting."""

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.odoo = OdooClient(self.config)

    def generate_weekly_report(
        self,
        week_start: Optional[str] = None,
        week_end: Optional[str] = None,
        salesperson_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive weekly pipeline report.

        Args:
            week_start: Start date (YYYY-MM-DD). Defaults to last Monday.
            week_end: End date (YYYY-MM-DD). Defaults to last Sunday.
            salesperson_filter: Filter by salesperson name (optional)

        Returns:
            Dictionary with all report sections
        """
        # Calculate week dates if not provided
        if not week_start or not week_end:
            today = datetime.now()
            # Get last Monday
            days_since_monday = (today.weekday() - 0) % 7
            last_monday = today - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)

            week_start = week_start or last_monday.strftime('%Y-%m-%d')
            week_end = week_end or last_sunday.strftime('%Y-%m-%d')

        logger.info(f"Generating weekly pipeline report for {week_start} to {week_end}")

        # Connect to Odoo
        if not self.odoo.connect():
            raise Exception("Failed to connect to Odoo")

        # Build domain filter
        domain = []
        if salesperson_filter:
            user_id = self.odoo.find_user_id(salesperson_filter)
            if user_id:
                domain.append(['user_id', '=', user_id])

        # Generate each section
        overview = self._get_week_overview(week_start, week_end, domain)
        pipeline_stages = self._get_pipeline_by_stage(domain)
        activity_metrics = self._get_activity_metrics(week_start, week_end, domain)

        return {
            "week_start": week_start,
            "week_end": week_end,
            "salesperson_filter": salesperson_filter,
            "overview": overview,
            "pipeline_stages": pipeline_stages,
            "activity_metrics": activity_metrics,
            "generated_at": datetime.now().isoformat()
        }

    def _get_week_overview(
        self,
        week_start: str,
        week_end: str,
        base_domain: List[Any]
    ) -> Dict[str, Any]:
        """Get weekly overview metrics."""
        try:
            # New leads this week
            new_leads_domain = base_domain + [
                ['create_date', '>=', f'{week_start} 00:00:00'],
                ['create_date', '<=', f'{week_end} 23:59:59']
            ]
            new_leads_data = self.odoo._call_kw(
                'crm.lead', 'search_read',
                [new_leads_domain],
                {'fields': ['id', 'name', 'partner_name', 'expected_revenue', 'user_id', 'stage_id', 'type']}
            )
            new_leads = len(new_leads_data)
            new_leads_list = [
                {
                    'id': lead.get('id'),
                    'name': lead.get('name') or lead.get('partner_name') or 'Unknown',
                    'company': lead.get('partner_name') or '',
                    'value': lead.get('expected_revenue') or 0,
                    'owner': lead.get('user_id')[1] if isinstance(lead.get('user_id'), (list, tuple)) else 'Unassigned',
                    'stage': lead.get('stage_id')[1] if isinstance(lead.get('stage_id'), (list, tuple)) else 'Unknown',
                    'type': lead.get('type', 'lead')
                }
                for lead in new_leads_data
            ]

            # Qualified leads (opportunities - type='opportunity')
            qualified_domain = base_domain + [
                ['create_date', '>=', f'{week_start} 00:00:00'],
                ['create_date', '<=', f'{week_end} 23:59:59'],
                ['type', '=', 'opportunity']
            ]
            qualified_leads_data = self.odoo._call_kw(
                'crm.lead', 'search_read',
                [qualified_domain],
                {'fields': ['id', 'name', 'partner_name', 'expected_revenue', 'user_id', 'stage_id']}
            )
            qualified_leads = len(qualified_leads_data)
            qualified_leads_list = [
                {
                    'id': lead.get('id'),
                    'name': lead.get('name') or lead.get('partner_name') or 'Unknown',
                    'company': lead.get('partner_name') or '',
                    'value': lead.get('expected_revenue') or 0,
                    'owner': lead.get('user_id')[1] if isinstance(lead.get('user_id'), (list, tuple)) else 'Unassigned',
                    'stage': lead.get('stage_id')[1] if isinstance(lead.get('stage_id'), (list, tuple)) else 'Unknown'
                }
                for lead in qualified_leads_data
            ]

            # Proposals sent - count leads that entered Proposal/Proposition stage during this week
            # We use mail.tracking.value to find all leads where stage changed TO a proposal stage
            # This captures leads even if they've since moved to another stage
            proposals_list = []
            try:
                # First, get the stage ID(s) for Proposal/Proposition stages
                proposal_stages = self.odoo._call_kw(
                    'crm.stage', 'search_read',
                    [[['name', 'ilike', 'propos']]],  # Matches "Proposal", "Proposition", etc.
                    {'fields': ['id', 'name']}
                )
                proposal_stage_ids = [s['id'] for s in proposal_stages]

                if proposal_stage_ids:
                    # Search mail.tracking.value for stage changes TO proposal stages during the week
                    tracking_domain = [
                        ['field_id.name', '=', 'stage_id'],
                        ['new_value_integer', 'in', proposal_stage_ids],
                        ['create_date', '>=', f'{week_start} 00:00:00'],
                        ['create_date', '<=', f'{week_end} 23:59:59']
                    ]
                    tracking_records = self.odoo._call_kw(
                        'mail.tracking.value', 'search_read',
                        [tracking_domain],
                        {'fields': ['mail_message_id']}
                    )

                    # Get unique lead IDs from these tracking records
                    if tracking_records:
                        message_ids = [t['mail_message_id'][0] for t in tracking_records if t.get('mail_message_id')]
                        if message_ids:
                            messages = self.odoo._call_kw(
                                'mail.message', 'search_read',
                                [[['id', 'in', message_ids], ['model', '=', 'crm.lead']]],
                                {'fields': ['res_id']}
                            )
                            unique_lead_ids = list(set(m['res_id'] for m in messages))
                            proposals_sent = len(unique_lead_ids)

                            # Fetch lead details for proposals
                            if unique_lead_ids:
                                proposals_data = self.odoo._call_kw(
                                    'crm.lead', 'search_read',
                                    [[['id', 'in', unique_lead_ids]]],
                                    {'fields': ['id', 'name', 'partner_name', 'expected_revenue', 'user_id', 'stage_id']}
                                )
                                proposals_list = [
                                    {
                                        'id': lead.get('id'),
                                        'name': lead.get('name') or lead.get('partner_name') or 'Unknown',
                                        'company': lead.get('partner_name') or '',
                                        'value': lead.get('expected_revenue') or 0,
                                        'owner': lead.get('user_id')[1] if isinstance(lead.get('user_id'), (list, tuple)) else 'Unassigned',
                                        'stage': lead.get('stage_id')[1] if isinstance(lead.get('stage_id'), (list, tuple)) else 'Unknown'
                                    }
                                    for lead in proposals_data
                                ]
                        else:
                            proposals_sent = 0
                    else:
                        proposals_sent = 0
                else:
                    proposals_sent = 0
                    logger.warning("No proposal stages found in Odoo")
            except Exception as e:
                logger.warning(f"Could not track proposal stage changes, falling back to simple count: {e}")
                # Fallback to simple count if tracking doesn't work
                proposals_domain = base_domain + [
                    ['stage_id.name', 'ilike', 'propos'],  # Matches Proposal/Proposition
                    ['date_last_stage_update', '>=', f'{week_start} 00:00:00'],
                    ['date_last_stage_update', '<=', f'{week_end} 23:59:59']
                ]
                proposals_data = self.odoo._call_kw(
                    'crm.lead', 'search_read',
                    [proposals_domain],
                    {'fields': ['id', 'name', 'partner_name', 'expected_revenue', 'user_id', 'stage_id']}
                )
                proposals_sent = len(proposals_data)
                proposals_list = [
                    {
                        'id': lead.get('id'),
                        'name': lead.get('name') or lead.get('partner_name') or 'Unknown',
                        'company': lead.get('partner_name') or '',
                        'value': lead.get('expected_revenue') or 0,
                        'owner': lead.get('user_id')[1] if isinstance(lead.get('user_id'), (list, tuple)) else 'Unassigned',
                        'stage': lead.get('stage_id')[1] if isinstance(lead.get('stage_id'), (list, tuple)) else 'Unknown'
                    }
                    for lead in proposals_data
                ]

            # Deals closed this week (using is_won boolean field)
            closed_domain = base_domain + [
                ['stage_id.is_won', '=', True],
                ['date_closed', '>=', f'{week_start} 00:00:00'],
                ['date_closed', '<=', f'{week_end} 23:59:59']
            ]
            closed_leads = self.odoo._call_kw(
                'crm.lead', 'search_read',
                [closed_domain],
                {'fields': ['id', 'name', 'partner_name', 'expected_revenue', 'user_id', 'stage_id']}
            )
            deals_closed = len(closed_leads)
            closed_value = sum((lead.get('expected_revenue') or 0) for lead in closed_leads)
            closed_leads_list = [
                {
                    'id': lead.get('id'),
                    'name': lead.get('name') or lead.get('partner_name') or 'Unknown',
                    'company': lead.get('partner_name') or '',
                    'value': lead.get('expected_revenue') or 0,
                    'owner': lead.get('user_id')[1] if isinstance(lead.get('user_id'), (list, tuple)) else 'Unassigned',
                    'stage': lead.get('stage_id')[1] if isinstance(lead.get('stage_id'), (list, tuple)) else 'Unknown'
                }
                for lead in closed_leads
            ]

            # Deals lost this week
            lost_domain = base_domain + [
                ['active', '=', False],  # Lost leads are archived
                ['probability', '=', 0],
                ['write_date', '>=', f'{week_start} 00:00:00'],
                ['write_date', '<=', f'{week_end} 23:59:59']
            ]
            lost_leads = self.odoo._call_kw(
                'crm.lead', 'search_read',
                [lost_domain],
                {'fields': ['id', 'name', 'partner_name', 'expected_revenue', 'user_id', 'stage_id', 'lost_reason_id']}
            )
            deals_lost = len(lost_leads)
            lost_leads_list = [
                {
                    'id': lead.get('id'),
                    'name': lead.get('name') or lead.get('partner_name') or 'Unknown',
                    'company': lead.get('partner_name') or '',
                    'value': lead.get('expected_revenue') or 0,
                    'owner': lead.get('user_id')[1] if isinstance(lead.get('user_id'), (list, tuple)) else 'Unassigned',
                    'stage': lead.get('stage_id')[1] if isinstance(lead.get('stage_id'), (list, tuple)) else 'Unknown',
                    'lost_reason': lead.get('lost_reason_id')[1] if isinstance(lead.get('lost_reason_id'), (list, tuple)) else 'Unknown'
                }
                for lead in lost_leads
            ]

            # Group lost reasons
            lost_reasons = {}
            for lead in lost_leads:
                reason = lead.get('lost_reason_id')
                if isinstance(reason, (list, tuple)) and len(reason) == 2:
                    reason_name = reason[1]
                else:
                    reason_name = 'Unknown'
                lost_reasons[reason_name] = lost_reasons.get(reason_name, 0) + 1

            return {
                "new_leads": new_leads,
                "new_leads_list": new_leads_list,
                "qualified_leads": qualified_leads,
                "qualified_leads_list": qualified_leads_list,
                "proposals_sent": proposals_sent,
                "proposals_list": proposals_list,
                "deals_closed": deals_closed,
                "closed_value": closed_value,
                "closed_leads_list": closed_leads_list,
                "deals_lost": deals_lost,
                "lost_leads_list": lost_leads_list,
                "lost_reasons": lost_reasons
            }

        except Exception as e:
            logger.error(f"Error getting week overview: {e}")
            return {}

    def _get_pipeline_by_stage(self, base_domain: List[Any]) -> List[Dict[str, Any]]:
        """Get pipeline breakdown by stage."""
        try:
            # Get all active leads with stage info
            domain = base_domain + [
                ['active', '=', True],
                ['probability', '<', 100],  # Exclude won deals
                ['probability', '>', 0]     # Exclude lost deals
            ]

            leads = self.odoo._call_kw(
                'crm.lead', 'search_read',
                [domain],
                {'fields': ['stage_id', 'partner_name', 'expected_revenue', 'create_date', 'date_last_stage_update']}
            )

            # Group by stage
            stages = {}
            for lead in leads:
                stage = lead.get('stage_id')
                if isinstance(stage, (list, tuple)) and len(stage) == 2:
                    stage_name = stage[1]
                else:
                    stage_name = 'Unknown'

                if stage_name not in stages:
                    stages[stage_name] = {
                        "stage_name": stage_name,
                        "count": 0,
                        "total_value": 0,
                        "leads": [],
                        "ages": []
                    }

                # Calculate age
                date_str = lead.get('date_last_stage_update') or lead.get('create_date')
                if date_str:
                    try:
                        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        age_days = (datetime.now(date_obj.tzinfo) - date_obj).days
                        stages[stage_name]["ages"].append(age_days)
                    except:
                        pass

                stages[stage_name]["count"] += 1
                stages[stage_name]["total_value"] += lead.get('expected_revenue', 0) or 0
                # Odoo returns False for empty fields, not None
                partner_name = lead.get('partner_name')
                stages[stage_name]["leads"].append({
                    "name": partner_name if partner_name else 'Unknown',
                    "value": lead.get('expected_revenue', 0) or 0
                })

            # Calculate average ages and format
            result = []
            for stage_name, data in stages.items():
                avg_age = sum(data["ages"]) / len(data["ages"]) if data["ages"] else 0

                # Get top clients in this stage
                top_clients = sorted(
                    data["leads"],
                    key=lambda x: x["value"],
                    reverse=True
                )[:5]

                result.append({
                    "stage_name": stage_name,
                    "count": data["count"],
                    "avg_age_days": round(avg_age, 1),
                    "total_value": data["total_value"],
                    "top_clients": [c["name"] for c in top_clients]
                })

            # Sort by typical stage order (you can customize this)
            stage_order = ["New", "Qualified", "Interested", "Potential", "Demo", "Proposal", "Negotiation"]
            result.sort(key=lambda x: stage_order.index(x["stage_name"]) if x["stage_name"] in stage_order else 999)

            return result

        except Exception as e:
            logger.error(f"Error getting pipeline by stage: {e}")
            return []

    def _get_activity_metrics(
        self,
        week_start: str,
        week_end: str,
        base_domain: List[Any]
    ) -> Dict[str, Any]:
        """Get activity metrics for the week: emails sent, calls, meetings, follow-ups."""
        try:
            # Get user_id from base_domain if filtering by salesperson
            user_id = None
            for condition in base_domain:
                if condition[0] == 'user_id' and condition[1] == '=':
                    user_id = condition[2]
                    break

            # Build date domain for activities
            date_start = f'{week_start} 00:00:00'
            date_end = f'{week_end} 23:59:59'

            # 1. Count emails sent (mail.message with message_type = 'email' on crm.lead)
            email_domain = [
                ['model', '=', 'crm.lead'],
                ['message_type', '=', 'email'],
                ['date', '>=', date_start],
                ['date', '<=', date_end]
            ]
            if user_id:
                email_domain.append(['author_id.user_ids', 'in', [user_id]])

            emails_sent = self.odoo._call_kw(
                'mail.message', 'search_count', [email_domain]
            )

            # 2. Count logged calls/notes (mail.message with message_type = 'comment' and subtype for notes)
            # In Odoo, logged activities often appear as comments
            notes_domain = [
                ['model', '=', 'crm.lead'],
                ['message_type', '=', 'comment'],
                ['date', '>=', date_start],
                ['date', '<=', date_end]
            ]
            if user_id:
                notes_domain.append(['author_id.user_ids', 'in', [user_id]])

            notes_logged = self.odoo._call_kw(
                'mail.message', 'search_count', [notes_domain]
            )

            # 3. Count scheduled activities completed (mail.activity - done activities)
            # We look for activities that were completed during this week
            try:
                # Get activity types first
                activity_types = self.odoo._call_kw(
                    'mail.activity.type', 'search_read',
                    [[]],
                    {'fields': ['id', 'name']}
                )
                activity_type_map = {at['id']: at['name'] for at in activity_types}

                # Get completed activities from mail.message where tracking shows activity done
                # Activities create messages when marked as done
                activity_done_domain = [
                    ['model', '=', 'crm.lead'],
                    ['subtype_id.name', '=', 'Activities'],
                    ['date', '>=', date_start],
                    ['date', '<=', date_end]
                ]
                if user_id:
                    activity_done_domain.append(['author_id.user_ids', 'in', [user_id]])

                activities_completed = self.odoo._call_kw(
                    'mail.message', 'search_count', [activity_done_domain]
                )
            except Exception as e:
                logger.warning(f"Could not fetch activity completions: {e}")
                activities_completed = 0

            # 4. Count meetings/calls scheduled (calendar.event linked to CRM leads)
            try:
                meeting_domain = [
                    ['res_model', '=', 'crm.lead'],
                    ['start', '>=', date_start],
                    ['start', '<=', date_end]
                ]
                if user_id:
                    meeting_domain.append(['user_id', '=', user_id])

                meetings_data = self.odoo._call_kw(
                    'calendar.event', 'search_read',
                    [meeting_domain],
                    {'fields': ['id', 'name', 'start', 'res_id', 'user_id']}
                )
                meetings_scheduled = len(meetings_data)
                meetings_list = [
                    {
                        'id': m.get('id'),
                        'name': m.get('name') or 'Meeting',
                        'date': m.get('start', '')[:10] if m.get('start') else '',
                        'owner': m.get('user_id')[1] if isinstance(m.get('user_id'), (list, tuple)) else 'Unknown'
                    }
                    for m in meetings_data
                ]
            except Exception as e:
                logger.warning(f"Could not fetch calendar events: {e}")
                meetings_scheduled = 0
                meetings_list = []

            # 5. Get breakdown by salesperson
            try:
                # Get all messages for the period grouped by author
                messages_domain = [
                    ['model', '=', 'crm.lead'],
                    ['message_type', 'in', ['email', 'comment']],
                    ['date', '>=', date_start],
                    ['date', '<=', date_end]
                ]

                all_messages = self.odoo._call_kw(
                    'mail.message', 'search_read',
                    [messages_domain],
                    {'fields': ['author_id', 'message_type']}
                )

                # Group by author
                by_salesperson = {}
                for msg in all_messages:
                    author = msg.get('author_id')
                    if isinstance(author, (list, tuple)) and len(author) == 2:
                        author_name = author[1]
                    else:
                        author_name = 'Unknown'

                    if author_name not in by_salesperson:
                        by_salesperson[author_name] = {'emails': 0, 'notes': 0, 'total': 0}

                    if msg.get('message_type') == 'email':
                        by_salesperson[author_name]['emails'] += 1
                    else:
                        by_salesperson[author_name]['notes'] += 1
                    by_salesperson[author_name]['total'] += 1

                # Convert to sorted list
                salesperson_breakdown = [
                    {'name': name, **counts}
                    for name, counts in sorted(by_salesperson.items(), key=lambda x: x[1]['total'], reverse=True)
                ][:10]  # Top 10
            except Exception as e:
                logger.warning(f"Could not fetch salesperson breakdown: {e}")
                salesperson_breakdown = []

            return {
                "emails_sent": emails_sent,
                "notes_logged": notes_logged,
                "activities_completed": activities_completed,
                "meetings_scheduled": meetings_scheduled,
                "meetings_list": meetings_list,
                "by_salesperson": salesperson_breakdown,
                "total_activities": emails_sent + notes_logged + activities_completed + meetings_scheduled
            }

        except Exception as e:
            logger.error(f"Error getting activity metrics: {e}")
            return {
                "emails_sent": 0,
                "notes_logged": 0,
                "activities_completed": 0,
                "meetings_scheduled": 0,
                "meetings_list": [],
                "by_salesperson": [],
                "total_activities": 0
            }
