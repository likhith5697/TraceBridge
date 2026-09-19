"""Scriptable manual MCP client - no LLM involved.

Launches tracebridge-mcp as a real stdio subprocess (the same way Claude
Desktop or the MCP Inspector would) and calls tools against it, printing
the raw JSON result.

Usage:
    python manual_client.py demo
        Runs every tool against the two real Phase 4 correlationIds
        (one success, one 401 failure) plus a couple of edge cases.

    python manual_client.py call <tool_name> '<json-arguments>'
        Calls one tool directly, e.g.:
        python manual_client.py call search_logs '{"correlation_id": "51d3c01d-2b02-45b3-9df4-697ecd19a796"}'
"""

import asyncio
import json
import sys

from mcp import Client, StdioServerParameters

SUCCESS_CID = "51d3c01d-2b02-45b3-9df4-697ecd19a796"
FAILURE_CID = "06fc3488-bc83-47a4-a768-db3af8b5c161"

_SERVER_PARAMS = StdioServerParameters(command=sys.executable, args=["-m", "tracebridge_mcp.server"])


def dump(label: str, result) -> None:
    print(f"\n=== {label} (is_error={result.is_error}) ===")
    for block in result.content:
        if hasattr(block, "text"):
            print(block.text)


async def run_demo() -> None:
    async with Client(_SERVER_PARAMS) as client:
        tools = await client.list_tools()
        print("Registered tools:", [t.name for t in tools.tools])

        dump("search_logs (SUCCESS)", await client.call_tool("search_logs", {"correlation_id": SUCCESS_CID}))
        dump(
            "get_downstream_interactions (SUCCESS)",
            await client.call_tool("get_downstream_interactions", {"correlation_id": SUCCESS_CID}),
        )
        dump(
            "get_transaction_timeline (SUCCESS)",
            await client.call_tool("get_transaction_timeline", {"correlation_id": SUCCESS_CID}),
        )
        dump(
            "get_transaction_summary (SUCCESS)",
            await client.call_tool("get_transaction_summary", {"correlation_id": SUCCESS_CID}),
        )
        dump(
            "get_service_request (SUCCESS)",
            await client.call_tool("get_service_request", {"correlation_id": SUCCESS_CID}),
        )

        dump(
            "get_transaction_timeline (FAILURE/401)",
            await client.call_tool("get_transaction_timeline", {"correlation_id": FAILURE_CID}),
        )
        dump(
            "get_downstream_interactions (FAILURE/401)",
            await client.call_tool("get_downstream_interactions", {"correlation_id": FAILURE_CID}),
        )
        dump(
            "get_transaction_summary (FAILURE/401)",
            await client.call_tool("get_transaction_summary", {"correlation_id": FAILURE_CID}),
        )

        dump("get_recent_failures", await client.call_tool("get_recent_failures", {"lookback_minutes": 1440}))

        dump("invalid correlation_id", await client.call_tool("search_logs", {"correlation_id": "not-a-uuid"}))

        unknown_cid = "00000000-0000-0000-0000-000000000000"
        dump(
            "unknown correlation_id (no evidence)",
            await client.call_tool("search_logs", {"correlation_id": unknown_cid}),
        )


async def run_single_call(tool_name: str, arguments: dict) -> None:
    async with Client(_SERVER_PARAMS) as client:
        dump(tool_name, await client.call_tool(tool_name, arguments))


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "call":
        tool_name = sys.argv[2]
        arguments = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        asyncio.run(run_single_call(tool_name, arguments))
        return

    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
