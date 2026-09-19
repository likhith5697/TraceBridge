"""CLI entrypoint. No frontend - a single subcommand is enough for Phase 6.

    python -m tracebridge_investigator investigate 06fc3488-bc83-47a4-a768-db3af8b5c161
    python -m tracebridge_investigator investigate "Investigate correlationId 06fc3488-..."
"""

import argparse
import asyncio
import logging
import sys

from tracebridge_investigator.config import load_config
from tracebridge_investigator.investigator import extract_correlation_id, run_investigation
from tracebridge_investigator.llm import LLMError, build_llm_client
from tracebridge_investigator.mcp_client import McpEvidenceClient
from tracebridge_investigator.report import render_report


def resolve_correlation_id(raw: str) -> str:
    """correlationId is extracted deterministically (a regex match), not by
    asking the LLM to parse the user's request."""
    extracted = extract_correlation_id(raw)
    if extracted is None:
        raise SystemExit(f"Could not find a correlationId (UUID) in: {raw!r}")
    return extracted


async def _investigate(correlation_id: str) -> int:
    config = load_config()
    try:
        llm_client = build_llm_client(config)
    except LLMError as exc:
        print(f"Cannot start investigation: {exc}", file=sys.stderr)
        return 1

    async with McpEvidenceClient(config) as mcp_client:
        result = await run_investigation(correlation_id, llm_client, mcp_client, config.max_iterations)

    print(render_report(result))
    return 0


def main() -> None:
    # The report uses plain Unicode checkmarks (see report.py); Windows' default
    # console codepage (cp1252) can't encode them, so force UTF-8 on stdout/stderr.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(prog="tracebridge-investigator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    investigate_parser = subparsers.add_parser("investigate", help="Investigate one TraceBridge transaction")
    investigate_parser.add_argument("request", help="A correlationId, or a natural-language request containing one")

    args = parser.parse_args()

    if args.command == "investigate":
        correlation_id = resolve_correlation_id(args.request)
        exit_code = asyncio.run(_investigate(correlation_id))
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
