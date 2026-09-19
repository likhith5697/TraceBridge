"""Test doubles for the provider-agnostic llm.py types and McpEvidenceClient
- no network, no subprocess, no API key needed for anything in
test_*_mocked.py or the other deterministic test files."""

from tracebridge_investigator.llm import AssistantTurn, ToolCall
from tracebridge_investigator.mcp_client import ToolCallOutcome, ToolSpec

REAL_TOOL_SPECS = [
    ToolSpec("search_logs", "Search structured logs", {"type": "object", "properties": {}}),
    ToolSpec(
        "get_downstream_interactions", "Get downstream interactions", {"type": "object", "properties": {}}
    ),
    ToolSpec("get_transaction_timeline", "Get transaction timeline", {"type": "object", "properties": {}}),
    ToolSpec("get_transaction_summary", "Get transaction summary", {"type": "object", "properties": {}}),
    ToolSpec("get_recent_failures", "Get recent failures", {"type": "object", "properties": {}}),
    ToolSpec("get_service_request", "Get service request", {"type": "object", "properties": {}}),
    ToolSpec("get_service_runtime_status", "Get service runtime status", {"type": "object", "properties": {}}),
    ToolSpec("get_service_config_metadata", "Get service config metadata", {"type": "object", "properties": {}}),
    ToolSpec("get_container_events", "Get container events", {"type": "object", "properties": {}}),
    ToolSpec("get_dependency_health", "Get dependency health", {"type": "object", "properties": {}}),
]


def tool_use_response(name: str, tool_input: dict, block_id: str = "call_1") -> AssistantTurn:
    return AssistantTurn(text=None, tool_calls=[ToolCall(block_id, name, tool_input)])


def text_response(text: str) -> AssistantTurn:
    return AssistantTurn(text=text, tool_calls=[])


class FakeLLMClient:
    """Returns each scripted AssistantTurn in order; raises if called more
    times than scripted, so a test's tool-call sequence is fully explicit."""

    def __init__(self, responses: list[AssistantTurn]):
        self._responses = list(responses)
        self.call_count = 0
        self.sent_tool_specs: list[list[ToolSpec]] = []

    def send(self, system, history, tool_specs):
        self.call_count += 1
        self.sent_tool_specs.append(tool_specs)
        if not self._responses:
            raise AssertionError("FakeLLMClient exhausted its scripted responses")
        return self._responses.pop(0)


class RaisingLLMClient:
    def send(self, system, history, tool_specs):
        raise RuntimeError("simulated LLM provider outage")


class FakeMcpClient:
    def __init__(self, tool_specs=None, responses: dict | None = None, list_tools_error: bool = False):
        self._tool_specs = tool_specs if tool_specs is not None else REAL_TOOL_SPECS
        self._responses = responses or {}
        self._list_tools_error = list_tools_error
        self.calls: list[tuple[str, dict]] = []

    async def list_tool_specs(self):
        if self._list_tools_error:
            raise RuntimeError("simulated MCP connection failure")
        return self._tool_specs

    async def call_tool(self, name: str, arguments: dict) -> ToolCallOutcome:
        self.calls.append((name, arguments))
        response = self._responses.get(name)
        if response is None:
            return ToolCallOutcome(success=True, content={}, error_message=None)
        if callable(response):
            return response(arguments)
        return response
