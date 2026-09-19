"""The only network-facing part of tracebridge-investigator.

This module adds zero investigation logic of its own - it wraps
run_investigation() (unchanged decision-making), streams its existing
progress events over SSE, and shapes InvestigationResult into JSON using
report.py/topology.py's already-existing, already-tested pure functions.

React never talks to MCP, OpenSearch, PostgreSQL, or the LLM - only to this
API, which is the sole thing that talks to the investigator.

History is in-memory only (a capped deque), not a database. It resets
whenever this process restarts - that's a stated limitation, not an oversight.
"""

import asyncio
import json
import time
import uuid
from collections import deque
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from tracebridge_investigator.config import load_config
from tracebridge_investigator.evidence import extract_observed_events
from tracebridge_investigator.investigator import (
    InvestigationResult,
    extract_correlation_id,
    run_investigation,
)
from tracebridge_investigator.llm import LLMError, build_llm_client
from tracebridge_investigator.mcp_client import McpEvidenceClient
from tracebridge_investigator.report import compute_confidence
from tracebridge_investigator.topology import compute_observed_stages, is_failure_result

app = FastAPI(title="tracebridge-investigator API")

# Local developer tool, not a public deployment - see README for the same
# reasoning already applied to OpenSearch's disabled security in this project.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_HISTORY_LIMIT = 20
_OPENSEARCH_TOOLS = {"search_logs", "get_transaction_timeline", "get_recent_failures"}
_POSTGRES_TOOLS = {"get_downstream_interactions", "get_service_request"}
_DOCKER_RUNTIME_TOOLS = {"get_service_runtime_status", "get_container_events"}
_DEPENDENCY_PROBE_TOOLS = {"get_dependency_health"}
_CONFIG_CATALOG_TOOLS = {"get_service_config_metadata"}

_history_summaries: deque[dict[str, Any]] = deque(maxlen=_HISTORY_LIMIT)
_history_details: dict[str, dict[str, Any]] = {}


def _evidence_source(tool_name: str) -> str:
    if tool_name in _OPENSEARCH_TOOLS:
        return "OpenSearch"
    if tool_name in _POSTGRES_TOOLS:
        return "PostgreSQL"
    if tool_name == "get_transaction_summary":
        return "OpenSearch + PostgreSQL"
    if tool_name in _DOCKER_RUNTIME_TOOLS:
        return "Docker Runtime"
    if tool_name in _DEPENDENCY_PROBE_TOOLS:
        return "Dependency Probe"
    if tool_name in _CONFIG_CATALOG_TOOLS:
        return "Service Catalog"
    return "MCP"


def _evidence_summary(tool_name: str, content: Any) -> str:
    """A short, deterministic, non-LLM description of a tool result - used
    only for display. It never feeds back into the agent's own reasoning."""
    if not isinstance(content, dict):
        return "No details available."

    if tool_name == "get_transaction_summary":
        parts = [f"{content.get('eventsObserved', 0)} events observed"]
        interactions = content.get("downstreamInteractions") or []
        if interactions:
            first = interactions[0]
            parts.append(
                f"downstream {first.get('targetSystem')} → HTTP {first.get('httpStatus')} ({first.get('status')})"
            )
        return "; ".join(parts)
    if tool_name == "get_transaction_timeline":
        return f"{content.get('eventCount', 0)} checkpoints discovered"
    if tool_name == "search_logs":
        return f"{content.get('count', 0)} log entries found"
    if tool_name == "get_downstream_interactions":
        interactions = content.get("downstreamInteractions") or []
        if not interactions:
            return "No downstream interaction recorded"
        first = interactions[0]
        return (
            f"{first.get('targetSystem')} → HTTP {first.get('httpStatus')} "
            f"({first.get('status')} / {first.get('errorCode') or 'OK'})"
        )
    if tool_name == "get_recent_failures":
        return f"{content.get('count', 0)} recent failures found"
    if tool_name == "get_service_request":
        return "Request found" if content.get("found") else "No matching service request"
    if tool_name == "get_service_runtime_status":
        if not content.get("exists"):
            return f"{content.get('service')} container not found"
        state = content.get("state") or ("running" if content.get("running") else "not running")
        return f"{content.get('service')} container {state}"
    if tool_name == "get_service_config_metadata":
        deps = content.get("dependencies") or []
        names = ", ".join(d.get("name", "?") for d in deps) or "none documented"
        return f"{content.get('service')} depends on: {names}"
    if tool_name == "get_container_events":
        return f"{content.get('count', 0)} container event(s) found"
    if tool_name == "get_dependency_health":
        status = "reachable" if content.get("reachable") else f"unreachable ({content.get('failure') or 'unknown'})"
        return f"{content.get('service')} -> {content.get('dependency')}: {status}"
    return "Evidence received."


def _observed_path_payload(
    result: InvestigationResult, supplemental_timeline: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    observed_events = extract_observed_events(result.evidence)
    # The agent may reasonably conclude from get_transaction_summary alone
    # (which has no per-checkpoint data) without ever calling
    # get_transaction_timeline itself - that's a legitimate, sufficient
    # investigation. But the flow diagram needs the granular checkpoint list
    # to render accurately, so the API layer fetches it separately purely for
    # display. This never feeds back into the agent's own reasoning.
    if supplemental_timeline:
        for entry in supplemental_timeline.get("timeline", []):
            if entry.get("service") and entry.get("event"):
                observed_events.add((entry["service"], entry["event"]))

    stage_results = compute_observed_stages(observed_events)

    path: list[dict[str, Any]] = []
    for stage_result in stage_results:
        if not stage_result.observed:
            path.append(
                {
                    "service": stage_result.stage.service,
                    "label": stage_result.stage.label,
                    "status": "pending",
                }
            )
            break
        path.append(
            {
                "service": stage_result.stage.service,
                "label": stage_result.stage.label,
                "status": "failed" if is_failure_result(stage_result) else "ok",
            }
        )
        if is_failure_result(stage_result):
            break
    return path


def _observed_error(result: InvestigationResult) -> str | None:
    """A short 'HTTP <status> <errorCode>' string derived directly from
    downstream_interaction evidence, if any failure was recorded - purely a
    display convenience so the UI never has to parse free-text summaries."""
    for e in result.evidence.all():
        if not e.success or not isinstance(e.content, dict):
            continue
        interactions = e.content.get("downstreamInteractions")
        if interactions is None and e.tool_name == "get_downstream_interactions":
            continue
        for interaction in interactions or []:
            status = interaction.get("httpStatus")
            error_code = interaction.get("errorCode")
            if status and status >= 400:
                return f"HTTP {status}" + (f" {error_code}" if error_code else "")
    return None


def _result_to_payload(
    result: InvestigationResult, supplemental_timeline: dict[str, Any] | None = None
) -> dict[str, Any]:
    all_evidence = result.evidence.all()
    ids_to_show = set(result.cited_evidence_ids) if result.cited_evidence_ids else {e.id for e in all_evidence}

    return {
        "investigationId": result.investigation_id,
        "correlationId": result.correlation_id,
        "outcome": result.outcome,
        "interpretation": result.interpretation,
        "limitations": result.limitations,
        "failureBoundary": result.failure_boundary,
        "observedError": _observed_error(result),
        "recommendedInvestigationArea": result.recommended_investigation_area,
        "confidence": compute_confidence(result),
        "observedPath": _observed_path_payload(result, supplemental_timeline),
        "evidence": [
            {
                "id": e.id,
                "source": _evidence_source(e.tool_name),
                "tool": e.tool_name,
                "success": e.success,
                "summary": _evidence_summary(e.tool_name, e.content) if e.success else (e.error_message or "Tool call failed"),
            }
            for e in all_evidence
            if e.id in ids_to_show
        ],
        "stats": {
            "iterations": result.iteration_count,
            "llmCalls": result.llm_call_count,
            "toolCalls": len(result.tool_call_log),
            "durationSeconds": round(result.duration_seconds, 2),
        },
        "stoppedReason": result.stopped_reason,
    }


def _store_result(payload: dict[str, Any]) -> None:
    _history_details[payload["investigationId"]] = payload
    _history_summaries.append(
        {
            "investigationId": payload["investigationId"],
            "correlationId": payload["correlationId"],
            "outcome": payload["outcome"],
            "confidence": payload["confidence"],
            "durationSeconds": payload["stats"]["durationSeconds"],
            "timestamp": time.time(),
        }
    )
    valid_ids = {s["investigationId"] for s in _history_summaries}
    for key in list(_history_details.keys()):
        if key not in valid_ids:
            del _history_details[key]


@app.get("/api/investigations/stream")
async def stream_investigation(correlation_id: str):
    validated = extract_correlation_id(correlation_id)

    async def event_generator():
        if validated is None:
            yield _sse(
                "error",
                {"reason": "invalid_correlation_id", "message": f"Not a valid correlationId: {correlation_id!r}"},
            )
            return

        queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

        def on_event(event_type: str, payload: dict[str, Any]) -> None:
            enriched = dict(payload)
            if event_type == "evidence":
                content = enriched.pop("content", None)
                if enriched.get("success"):
                    enriched["summary"] = _evidence_summary(enriched.get("tool", ""), content)
                    enriched["source"] = _evidence_source(enriched.get("tool", ""))
                else:
                    enriched["summary"] = enriched.get("error") or "Tool call failed"
            queue.put_nowait((event_type, enriched))

        async def run() -> None:
            config = load_config()
            try:
                llm_client = build_llm_client(config)
            except LLMError as exc:
                queue.put_nowait(("error", {"reason": "llm_unavailable", "message": str(exc)}))
                queue.put_nowait(None)
                return

            try:
                async with McpEvidenceClient(config) as mcp_client:
                    result = await run_investigation(
                        validated, llm_client, mcp_client, config.max_iterations, on_event=on_event
                    )
                    # Fetch the full timeline separately, purely for the flow-diagram
                    # visualization - see _observed_path_payload for why. This never
                    # reaches the agent and has no effect on its conclusion.
                    timeline_outcome = await mcp_client.call_tool(
                        "get_transaction_timeline", {"correlation_id": validated}
                    )
            except Exception as exc:
                queue.put_nowait(("error", {"reason": "mcp_unavailable", "message": str(exc)}))
                queue.put_nowait(None)
                return

            supplemental_timeline = timeline_outcome.content if timeline_outcome.success else None
            payload = _result_to_payload(result, supplemental_timeline)
            _store_result(payload)
            queue.put_nowait(("final", payload))
            queue.put_nowait(None)

        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event_type, payload = item
                yield _sse(event_type, payload)
        finally:
            task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event_type: str, payload: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


@app.get("/api/investigations")
async def list_investigations():
    return list(reversed(_history_summaries))


@app.get("/api/investigations/{investigation_id}")
async def get_investigation(investigation_id: str):
    result = _history_details.get(investigation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="investigation not found")
    return result


@app.get("/api/status")
async def get_status():
    status = {"investigator": "up", "mcp": "down", "opensearch": "down", "postgresql": "down"}
    config = load_config()
    try:
        async with McpEvidenceClient(config) as mcp_client:
            await mcp_client.list_tool_specs()
            status["mcp"] = "up"

            opensearch_outcome = await mcp_client.call_tool(
                "get_recent_failures", {"lookback_minutes": 1, "limit": 1}
            )
            status["opensearch"] = "up" if opensearch_outcome.success else "down"

            postgres_outcome = await mcp_client.call_tool(
                "get_service_request", {"correlation_id": str(uuid.UUID(int=0))}
            )
            status["postgresql"] = "up" if postgres_outcome.success else "down"
    except Exception:
        pass
    return status
