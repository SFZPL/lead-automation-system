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
        top_opportunities = self._get_top_opportunities(domain, limit=5)
        at_risk_leads = self._get_at_risk_leads(domain)

        return {
            "week_start": week_start,
            "week_end": week_end,
            "salesperson_filter": salesperson_filter,
            "overview": overview,
            "pipeline_stages": pipeline_stages,
            "top_opportunities": top_opportunities,
            "at_risk_leads": at_risk_leads,
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
            new_leads = self.odoo._call_kw(
                'crm.lead', 'search_count', [new_leads_domain]
            )

            # Qualified leads (not in "New" stage)
            qualified_domain = base_domain + [
                ['create_date', '>=', f'{week_start} 00:00:00'],
                ['create_date', '<=', f'{week_end} 23:59:59'],
                ['stage_id.name', '!=', 'New']
            ]
            qualified_leads = self.odoo._call_kw(
                'crm.lead', 'search_count', [qualified_domain]
            )

            # Proposals sent (moved to "Proposal" stage during this week)
            proposals_domain = base_domain + [
                ['stage_id.name', '=', 'Proposal'],
                ['date_last_stage_update', '>=', f'{week_start} 00:00:00'],
                ['date_last_stage_update', '<=', f'{week_end} 23:59:59']
            ]
            proposals_sent = self.odoo._call_kw(
                'crm.lead', 'search_count', [proposals_domain]
            )

            # Deals closed this week (using is_won boolean field)
            closed_domain = base_domain + [
                ['stage_id.is_won', '=', True],
                ['date_closed', '>=', f'{week_start} 00:00:00'],
                ['date_closed', '<=', f'{week_end} 23:59:59']
            ]
            closed_leads = self.odoo._call_kw(
                'crm.lead', 'search_read',
                [closed_domain],
                {'fields': ['expected_revenue']}
            )
            deals_closed = len(closed_leads)
            closed_value = sum(lead.get('expected_revenue', 0) for lead in closed_leads)

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
                {'fields': ['lost_reason_id']}
            )
            deals_lost = len(lost_leads)

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
                "qualified_leads": qualified_leads,
                "proposals_sent": proposals_sent,
                "deals_closed": deals_closed,
                "closed_value": closed_value,
                "deals_lost": deals_lost,
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
                stages[stage_name]["total_value"] += lead.get('expected_revenue', 0)
                stages[stage_name]["leads"].append({
                    "name": lead.get('partner_name', 'Unknown'),
                    "value": lead.get('expected_revenue', 0)
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

    def _get_top_opportunities(self, base_domain: List[Any], limit: int = 5) -> List[Dict[str, Any]]:
        """Get top opportunities by expected revenue."""
        try:
            domain = base_domain + [
                ['active', '=', True],
                ['probability', '>', 0],
                ['probability', '<', 100],
                ['expected_revenue', '>', 0]
            ]

            opportunities = self.odoo._call_kw(
                'crm.lead', 'search_read',
                [domain],
                {
                    'fields': ['name', 'partner_name', 'stage_id', 'expected_revenue', 'user_id', 'write_date'],
                    'order': 'expected_revenue desc',
                    'limit': limit
                }
            )

            result = []
            for opp in opportunities:
                stage = opp.get('stage_id')
                stage_name = stage[1] if isinstance(stage, (list, tuple)) and len(stage) == 2 else 'Unknown'

                owner = opp.get('user_id')
                owner_name = owner[1] if isinstance(owner, (list, tuple)) and len(owner) == 2 else 'Unassigned'

                # Calculate days since last activity
                last_activity_str = opp.get('write_date')
                days_since_activity = 0
                if last_activity_str:
                    try:
                        last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
                        days_since_activity = (datetime.now(last_activity.tzinfo) - last_activity).days
                    except:
                        pass

                result.append({
                    "opportunity_name": opp.get('name') or opp.get('partner_name', 'Unknown'),
                    "company": opp.get('partner_name', ''),
                    "stage": stage_name,
                    "potential_value": opp.get('expected_revenue', 0),
                    "owner": owner_name,
                    "days_since_last_activity": days_since_activity
                })

            return result

        except Exception as e:
            logger.error(f"Error getting top opportunities: {e}")
            return []

    def _get_at_risk_leads(self, base_domain: List[Any]) -> List[Dict[str, Any]]:
        """Get leads at risk (no activity for 10+ days)."""
        try:
            # Calculate 10 days ago
            ten_days_ago = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')

            domain = base_domain + [
                ['active', '=', True],
                ['probability', '>', 0],
                ['probability', '<', 100],
                ['write_date', '<', ten_days_ago]
            ]

            at_risk = self.odoo._call_kw(
                'crm.lead', 'search_read',
                [domain],
                {'fields': ['name', 'partner_name', 'stage_id', 'user_id', 'expected_revenue', 'write_date']}
            )

            result = []
            for lead in at_risk:
                stage = lead.get('stage_id')
                stage_name = stage[1] if isinstance(stage, (list, tuple)) and len(stage) == 2 else 'Unknown'

                owner = lead.get('user_id')
                owner_name = owner[1] if isinstance(owner, (list, tuple)) and len(owner) == 2 else 'Unassigned'

                # Calculate days of inactivity
                last_activity_str = lead.get('write_date')
                days_inactive = 0
                if last_activity_str:
                    try:
                        last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
                        days_inactive = (datetime.now(last_activity.tzinfo) - last_activity).days
                    except:
                        pass

                result.append({
                    "lead_name": lead.get('name') or lead.get('partner_name', 'Unknown'),
                    "company": lead.get('partner_name', ''),
                    "stage": stage_name,
                    "owner": owner_name,
                    "value": lead.get('expected_revenue', 0),
                    "days_inactive": days_inactive
                })

            # Sort by days inactive (most at risk first)
            result.sort(key=lambda x: x["days_inactive"], reverse=True)

            return result

        except Exception as e:
            logger.error(f"Error getting at-risk leads: {e}")
            return []
