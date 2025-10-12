#!/usr/bin/env python3
"""CLI to automate post-first-contact actions."""

import argparse
import sys
from textwrap import indent

from config import Config
from modules.logger import setup_logging
from modules.post_contact_automation import PostContactAction, PostContactAutomationService


def prompt_yes_no(question: str, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    try:
        answer = input(f"{question} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def render_email(action: PostContactAction) -> None:
    print("Subject:", action.subject or "(no subject)")
    print(indent(action.body or "", "  "))


def render_note(action: PostContactAction) -> None:
    print("Internal note preview:")
    print(indent(action.note_body or "", "  "))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automate post-first-contact branching workflow."
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of actions to prepare")
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=None,
        help="Only consider calls within the past N hours",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Auto-confirm all actions without interactive prompts",
    )
    args = parser.parse_args()

    config = Config()
    logger = setup_logging(config, "INFO")

    validation = Config.validate()
    if not validation["valid"]:
        for item in validation["errors"]:
            logger.error(item)
        sys.exit(1)
    for warning in validation["warnings"]:
        logger.warning(warning)

    service = PostContactAutomationService(config=config)

    try:
        actions = service.prepare_actions(limit=args.limit, lookback_hours=args.lookback_hours)
    except Exception as exc:
        logger.error("Failed to prepare post-contact actions: %s", exc)
        sys.exit(1)

    if not actions:
        print("No post-contact actions required right now.")
        return

    print(f"Prepared {len(actions)} post-contact action(s).")

    processed = 0
    for index, action in enumerate(actions, start=1):
        print("-" * 70)
        name = action.contact_name or "Unknown contact"
        disposition = action.call.get("call_disposition") or action.call.get("disposition") or "untracked"
        last_called = action.call.get("last_called_at") or action.call.get("last_called_at_dt")
        print(f"{index}. {action.action_type.upper()} for {name} <{action.contact_email}>")
        print(f"   Disposition: {disposition}")
        if last_called:
            print(f"   Last call: {last_called}")
        if action.odoo_lead_id:
            print(f"   Odoo lead ID: {action.odoo_lead_id}")

        if action.action_type == "email":
            render_email(action)
            if prompt_yes_no("Send this email now?", assume_yes=args.yes):
                success = service.execute_email(action)
                status = "SENT" if success else "FAILED"
                print(f"Email {status} for {name}.")
                processed += int(success)
            else:
                print("Skipped sending email.")
        elif action.action_type == "note":
            render_note(action)
            if prompt_yes_no("Upload this note to Odoo?", assume_yes=args.yes):
                success = service.execute_note(action)
                status = "UPLOADED" if success else "FAILED"
                print(f"Note {status} for {name}.")
                processed += int(success)
            else:
                print("Skipped uploading note.")
        else:
            print(f"Unsupported action type: {action.action_type}")

    print("-" * 70)
    print(f"Completed {processed} action(s).")


if __name__ == "__main__":
    main()

