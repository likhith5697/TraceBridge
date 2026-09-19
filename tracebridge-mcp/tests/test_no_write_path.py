"""Structural guarantees that this server cannot become a write path or a
generic query executor, independent of any single tool's behavior."""

import asyncio

from mcp import Client

from tracebridge_mcp.server import mcp

EXPECTED_TOOL_NAMES = {
    "search_logs",
    "get_downstream_interactions",
    "get_transaction_timeline",
    "get_transaction_summary",
    "get_recent_failures",
    "get_service_request",
    "get_service_runtime_status",
    "get_service_config_metadata",
    "get_container_events",
    "get_dependency_health",
}

FORBIDDEN_TOOL_NAME_FRAGMENTS = (
    "execute_sql",
    "run_sql",
    "execute_query",
    "run_shell",
    "run_command",
    "query_any_index",
    "delete",
    "update",
    "insert",
    "write",
    "exec",
    "start",
    "stop",
    "restart",
    "kill",
    "remove",
)


def test_only_the_expected_tools_are_registered():
    async def list_names():
        async with Client(mcp) as client:
            result = await client.list_tools()
            return {t.name for t in result.tools}

    assert asyncio.run(list_names()) == EXPECTED_TOOL_NAMES


def test_no_registered_tool_name_looks_like_a_generic_or_write_operation():
    async def list_names():
        async with Client(mcp) as client:
            result = await client.list_tools()
            return [t.name for t in result.tools]

    names = asyncio.run(list_names())
    for name in names:
        lowered = name.lower()
        for fragment in FORBIDDEN_TOOL_NAME_FRAGMENTS:
            assert fragment not in lowered, f"tool name {name!r} contains forbidden fragment {fragment!r}"


def test_no_tool_input_schema_accepts_arbitrary_sql_or_dsl_parameters():
    """None of our tool schemas should have a free-form 'query'/'sql'/'dsl'/'command'
    parameter - every input is a narrow, named, typed argument."""
    forbidden_param_names = {"sql", "query", "dsl", "command", "shell", "script", "raw_query", "expression"}

    async def list_schemas():
        async with Client(mcp) as client:
            result = await client.list_tools()
            return {t.name: t.input_schema for t in result.tools}

    schemas = asyncio.run(list_schemas())
    for name, schema in schemas.items():
        properties = set(schema.get("properties", {}).keys())
        assert properties.isdisjoint(forbidden_param_names), f"tool {name!r} exposes a forbidden parameter"
