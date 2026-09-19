"""Live integration tests: real tracebridge-mcp (stdio subprocess), real
OpenSearch/PostgreSQL evidence, real LLM API call (OpenAI by default, or
Anthropic - whichever LLM_PROVIDER/config.py resolves to).

Skipped automatically unless OPENAI_API_KEY or ANTHROPIC_API_KEY is set -
none of the other test files in this project need a network call or an
API key.
"""

import os

import pytest

from tracebridge_investigator.config import load_config
from tracebridge_investigator.investigator import run_investigation
from tracebridge_investigator.llm import build_llm_client
from tracebridge_investigator.mcp_client import McpEvidenceClient

SUCCESS_CID = "51d3c01d-2b02-45b3-9df4-697ecd19a796"
FAILURE_401_CID = "06fc3488-bc83-47a4-a768-db3af8b5c161"
UNKNOWN_CID = "00000000-0000-0000-0000-000000000000"

pytestmark = pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")),
    reason="no LLM API key set - skipping live LLM tests",
)


async def _investigate(correlation_id: str):
    config = load_config()
    llm_client = build_llm_client(config)
    async with McpEvidenceClient(config) as mcp_client:
        return await run_investigation(correlation_id, llm_client, mcp_client, config.max_iterations)


async def test_live_known_success_transaction():
    result = await _investigate(SUCCESS_CID)

    assert result.outcome == "SUCCESS"
    assert result.stopped_reason == "submit_report"
    assert len(result.tool_call_log) >= 1


async def test_live_known_401_failure_transaction():
    result = await _investigate(FAILURE_401_CID)

    assert result.outcome == "FAILURE"
    assert result.failure_boundary is not None
    assert "servicenow" in result.failure_boundary.lower()

    # The agent must not overclaim beyond what a bare HTTP 401 proves - it should
    # never assert a specific credential field is definitely wrong.
    overclaiming_phrases = ("password is wrong", "password was wrong", "definitely the password")
    combined_text = (result.interpretation + " " + result.limitations).lower()
    assert not any(phrase in combined_text for phrase in overclaiming_phrases)


async def test_live_unknown_correlation_id_does_not_hallucinate():
    result = await _investigate(UNKNOWN_CID)

    assert result.outcome == "INCOMPLETE"
    assert len(result.evidence.all()) >= 1
