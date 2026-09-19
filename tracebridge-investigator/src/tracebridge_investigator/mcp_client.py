"""The only place this process talks to tracebridge-mcp.

There is no OpenSearch client, no PostgreSQL client, and no ServiceNow or
Kafka client anywhere in tracebridge-investigator - evidence only ever
arrives through this MCP connection, exactly the same way manual_client.py
in tracebridge-mcp talks to it for manual testing.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from mcp import Client, StdioServerParameters

from tracebridge_investigator.config import Config


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCallOutcome:
    success: bool
    content: Any
    error_message: str | None


class McpEvidenceClient:
    """Async context manager around one stdio connection to tracebridge-mcp."""

    def __init__(self, config: Config):
        self._config = config
        self._client: Client | None = None

    async def __aenter__(self) -> "McpEvidenceClient":
        env = os.environ.copy()
        if self._config.mcp_server_pythonpath:
            env["PYTHONPATH"] = self._config.mcp_server_pythonpath
        params = StdioServerParameters(
            command=self._config.mcp_server_command,
            args=self._config.mcp_server_args,
            cwd=str(self._config.mcp_server_cwd),
            env=env,
        )
        self._client = Client(params)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client is not None:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    async def list_tool_specs(self) -> list[ToolSpec]:
        assert self._client is not None, "McpEvidenceClient used outside its context manager"
        result = await self._client.list_tools()
        return [ToolSpec(t.name, t.description or "", t.input_schema) for t in result.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallOutcome:
        assert self._client is not None, "McpEvidenceClient used outside its context manager"
        try:
            result = await self._client.call_tool(name, arguments)
        except Exception as exc:  # the MCP connection itself failed, not the tool logic
            return ToolCallOutcome(success=False, content=None, error_message=f"MCP call failed: {exc}")

        text = _extract_text(result.content)
        if result.is_error:
            return ToolCallOutcome(success=False, content=None, error_message=text or "tool reported an error")

        parsed = _try_parse_json(text)
        return ToolCallOutcome(success=True, content=parsed if parsed is not None else text, error_message=None)


def _extract_text(content_blocks: list[Any]) -> str:
    parts = [block.text for block in content_blocks if hasattr(block, "text")]
    return "\n".join(parts)


def _try_parse_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
