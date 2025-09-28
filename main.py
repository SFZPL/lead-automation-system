#!/usr/bin/env python3
"""Manual Perplexity-based lead enrichment CLI."""

import argparse
import os
import sys
from pathlib import Path
from typing import Tuple

# Ensure project root is on the import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from modules.logger import setup_logging
from modules.perplexity_workflow import PerplexityWorkflow


def validate_configuration() -> bool:
    """Validate core configuration without interactive prompts."""
    result = Config.validate()

    if result["errors"]:
        print("Configuration errors detected:")
        for item in result["errors"]:
            print(f"  - {item}")
        return False

    if result["warnings"]:
        print("Configuration warnings:")
        for item in result["warnings"]:
            print(f"  - {item}")
        print("Continuing despite warnings. Adjust .env if required.")

    return True


def build_workflow() -> Tuple[PerplexityWorkflow, Config]:
    config = Config()
    logger = setup_logging(config, "INFO")
    logger.debug("Initialized Perplexity workflow")
    return PerplexityWorkflow(config), config


def command_generate(args: argparse.Namespace) -> None:
    if not validate_configuration():
        sys.exit(1)

    workflow, _ = build_workflow()

    prompt, leads = workflow.generate_enrichment_prompt()

    if not leads:
        print("No unenriched leads found in Odoo. Nothing to do.")
        return

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(prompt, encoding="utf-8")
        print(f"Prompt for {len(leads)} leads saved to {output_path.resolve()}")
    else:
        print(f"Prompt for {len(leads)} leads:\n")
        print(prompt)


def command_parse(args: argparse.Namespace) -> None:
    if not validate_configuration():
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    workflow, _ = build_workflow()

    perplexity_output = input_path.read_text(encoding="utf-8")
    _, original_leads = workflow.generate_enrichment_prompt()

    if not original_leads:
        print("No reference leads available. Ensure leads exist before parsing results.")
        sys.exit(1)

    enriched_leads = workflow.parse_perplexity_results(perplexity_output, original_leads)

    if not enriched_leads:
        print("Unable to parse any leads from the provided Perplexity output.")
        sys.exit(1)

    print(f"Parsed {len(enriched_leads)} leads from Perplexity response.")

    if args.preview:
        for index, lead in enumerate(enriched_leads, 1):
            name = lead.get("Full Name") or lead.get("name") or "Unknown"
            linkedin = lead.get("LinkedIn Link") or "(no LinkedIn URL)"
            job = lead.get("Job Role") or "(no job title)"
            print(f"  {index}. {name} | {job} | {linkedin}")

    if args.no_update:
        print("Skipping Odoo update (--no-update supplied).")
        return

    results = workflow.update_leads_in_odoo(enriched_leads)

    if not results.get("success", False):
        print("Failed to update Odoo:")
        print(f"  {results.get('error', 'Unknown error')}")
        sys.exit(1)

    print(f"Updated {results.get('updated', 0)} leads in Odoo.")
    if results.get('failed'):
        print(f"Failed to update {results['failed']} leads.")
        for error in results.get('errors', [])[:5]:
            print(f"  - {error}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Perplexity prompts and parse results back into Odoo."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate", help="Generate a Perplexity prompt for unenriched leads"
    )
    generate_parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write the generated prompt to FILE instead of stdout",
    )
    generate_parser.set_defaults(func=command_generate)

    parse_parser = subparsers.add_parser(
        "parse", help="Parse Perplexity output and update Odoo"
    )
    parse_parser.add_argument(
        "input",
        metavar="FILE",
        help="Path to the Perplexity response text file",
    )
    parse_parser.add_argument(
        "--no-update",
        action="store_true",
        help="Parse results without pushing updates back to Odoo",
    )
    parse_parser.add_argument(
        "--preview",
        action="store_true",
        help="Print a short preview of parsed leads before updating",
    )
    parse_parser.set_defaults(func=command_parse)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
