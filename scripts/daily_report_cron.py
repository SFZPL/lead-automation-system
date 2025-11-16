#!/usr/bin/env python3
"""
Daily automated report generation for Railway cron job.

This script generates a 90-day proposal follow-up report every day.
Run as: python scripts/daily_report_cron.py
"""

import os
import sys
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.proposal_followup_analyzer import ProposalFollowupAnalyzer
from api.supabase_database import SupabaseDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_daily_report():
    """Generate a 90-day automated report."""
    try:
        logger.info("Starting automated 90-day report generation...")

        # Initialize database
        db = SupabaseDatabase()

        # Get admin user (or use a specific service user)
        # For automated reports, we'll use the admin user
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@prezlab.com')

        # Fetch admin user
        from supabase import create_client
        supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )

        response = supabase.table('users').select('*').eq('email', admin_email).execute()
        if not response.data or len(response.data) == 0:
            logger.error(f"Admin user not found: {admin_email}")
            return False

        admin_user = response.data[0]
        user_id = admin_user['id']

        logger.info(f"Using user: {admin_email} (ID: {user_id})")

        # Initialize analyzer
        analyzer = ProposalFollowupAnalyzer()

        # Generate report with 90-day parameters
        report_config = {
            'report_type': '90day',
            'days_back': 90,
            'no_response_days': 3,
            'engage_email': admin_email
        }

        logger.info(f"Generating report with config: {report_config}")

        # Generate the report
        report_data = analyzer.generate_followup_report(**report_config)

        if not report_data:
            logger.error("Report generation returned no data")
            return False

        # Save to database
        report_name = f"Automated 90-Day Report - {datetime.now().strftime('%Y-%m-%d')}"

        logger.info(f"Saving report to database: {report_name}")

        db.save_followup_report(
            user_id=user_id,
            report_name=report_name,
            report_data=report_data,
            report_config=report_config
        )

        logger.info(f"✅ Successfully generated and saved report: {report_name}")
        logger.info(f"   - Total threads: {report_data.get('total_threads', 0)}")
        logger.info(f"   - Needs followup: {report_data.get('needs_followup', 0)}")
        logger.info(f"   - Engaged: {report_data.get('engaged', 0)}")

        return True

    except Exception as e:
        logger.error(f"❌ Error generating daily report: {str(e)}", exc_info=True)
        return False


if __name__ == '__main__':
    success = generate_daily_report()
    sys.exit(0 if success else 1)
