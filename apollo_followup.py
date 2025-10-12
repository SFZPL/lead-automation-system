#!/usr/bin/env python3
"""CLI to generate follow-up emails for missed Apollo calls."""

import argparse
import json
import sys
from typing import Any

from config import Config
from modules.apollo_followup import ApolloFollowUpService
from modules.logger import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate personalized follow-up emails for missed Apollo calls",
    )
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of emails to produce')
    parser.add_argument(
        '--lookback-hours',
        type=int,
        default=None,
        help='Only include calls made within the past N hours (defaults to config)',
    )
    parser.add_argument('--json', action='store_true', help='Output results as JSON')

    args = parser.parse_args()

    config = Config()
    logger = setup_logging(config, 'INFO')

    validation = Config.validate()
    if not validation['valid']:
        for item in validation['errors']:
            logger.error(item)
        sys.exit(1)
    for warning in validation['warnings']:
        logger.warning(warning)

    service = ApolloFollowUpService(config=config)

    try:
        results = service.prepare_followups(limit=args.limit, lookback_hours=args.lookback_hours)
    except Exception as exc:  # Catch to avoid stack trace in CLI usage
        logger.error('Failed to prepare follow-up emails: %s', exc)
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        print('No follow-up emails to send right now.')
        return

    for index, item in enumerate(results, 1):
        print('-' * 60)
        print(f"{index}. {item['odoo_lead'].get('name') or item['email']}")
        print(f"   Email: {item['email']}")
        if item['odoo_lead'].get('company'):
            print(f"   Company: {item['odoo_lead']['company']}")
        if item['call'].get('last_called_at'):
            print(f"   Last Call: {item['call']['last_called_at']}")
        print('')
        print(f"Subject: {item['subject']}")
        print(item['body'])
        print('')


if __name__ == '__main__':
    main()
