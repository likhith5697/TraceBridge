"""tracebridge-mcp: a read-only MCP server over TraceBridge's evidence.

This module only wires MCP protocol concerns (tool registration, schemas,
transport, and translating our domain exceptions into the SDK's ToolError
so the client sees a clean anticipated-failure message instead of a raw
crash). All actual business logic lives in tools.py and is fully testable
without any of this.
"""

import functools
from typing import Any

from opensearchpy import OpenSearch
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from tracebridge_mcp import tools
from tracebridge_mcp.config import load_config
from tracebridge_mcp.dependency_probe import check_tcp_reachable
from tracebridge_mcp.docker_repository import DockerRuntimeRepository
from tracebridge_mcp.errors import EvidenceSourceUnavailableError, InvalidToolInputError
from tracebridge_mcp.opensearch_repository import OpenSearchEvidenceRepository
from tracebridge_mcp.postgres_repository import PostgresEvidenceRepository

mcp = MCPServer(
    name="tracebridge-mcp",
    instructions=(
        "Read-only investigation tools over TraceBridge's existing evidence "
        "(OpenSearch structured logs, PostgreSQL downstream_interaction / "
        "service_request tables, and read-only Docker runtime state / "
        "dependency reachability for an explicit allowlist of local "
        "services). Every tool returns observed facts only - none of them "
        "diagnose a root cause or suggest a fix."
    ),
)

_config = load_config()
_opensearch_repo = OpenSearchEvidenceRepository(
    OpenSearch(hosts=[_config.opensearch_url]),
    request_timeout_seconds=_config.opensearch_timeout_seconds,
)
_postgres_repo = PostgresEvidenceRepository(
    _config.postgres_conninfo,
    timeout_seconds=_config.postgres_timeout_seconds,
)
_docker_repo = DockerRuntimeRepository(
    _config.docker_base_url,
    timeout_seconds=_config.docker_timeout_seconds,
)
# Timeout is bound here so tools.py's function signature stays a plain
# (host, port) -> ProbeResult callable, exactly like a repository dependency.
_dependency_probe = functools.partial(
    check_tcp_reachable, timeout_seconds=_config.dependency_probe_timeout_seconds
)


def _run_tool(fn, /, **kwargs) -> dict[str, Any]:
    """Translate our domain exceptions into ToolError.

    Anything else (a genuine bug) is left to crash the call as an
    UnexpectedToolError - see errors raised by tools.py for what is
    "anticipated" here: bad input and an unreachable evidence source.
    """
    try:
        return fn(**kwargs)
    except (InvalidToolInputError, EvidenceSourceUnavailableError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(structured_output=True)
def search_logs(
    correlation_id: str,
    service: str | None = None,
    event: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Search structured logs in OpenSearch for one correlationId.

    Returns normalized log lines from both TraceBridge services, sorted
    oldest first. Optional `service` / `event` filters narrow the result to
    a known service name or checkpoint name. `limit` defaults to 50 and is
    capped at 200.
    """
    return _run_tool(
        tools.search_logs,
        opensearch_repo=_opensearch_repo,
        correlation_id=correlation_id,
        service=service,
        event=event,
        limit=limit,
    )


@mcp.tool(structured_output=True)
def get_downstream_interactions(correlation_id: str) -> dict[str, Any]:
    """Get servicenow-consumer's downstream_interaction records for one correlationId.

    Returns every recorded attempt to call ServiceNow for this transaction,
    ordered chronologically. Request/response payload bodies are never
    included - only outcome metadata (http status, error code, duration).
    """
    return _run_tool(
        tools.get_downstream_interactions,
        postgres_repo=_postgres_repo,
        correlation_id=correlation_id,
    )


@mcp.tool(structured_output=True)
def get_transaction_timeline(correlation_id: str) -> dict[str, Any]:
    """Get the full chronological event timeline for one correlationId.

    Queries OpenSearch only, across both services, with no service/event
    filter. Reports only checkpoints that were actually observed - it never
    fabricates a missing checkpoint.
    """
    return _run_tool(
        tools.get_transaction_timeline,
        opensearch_repo=_opensearch_repo,
        correlation_id=correlation_id,
    )


@mcp.tool(structured_output=True)
def get_transaction_summary(correlation_id: str) -> dict[str, Any]:
    """Get a compact factual summary of one correlationId across OpenSearch and PostgreSQL.

    Combines log evidence and downstream_interaction rows into one summary.
    Still purely observational: no root cause, no diagnosis. If either
    evidence source is unreachable, that is reported explicitly rather than
    silently treated the same as "no evidence found".
    """
    return _run_tool(
        tools.get_transaction_summary,
        opensearch_repo=_opensearch_repo,
        postgres_repo=_postgres_repo,
        correlation_id=correlation_id,
    )


@mcp.tool(structured_output=True)
def get_recent_failures(lookback_minutes: int | None = None, limit: int | None = None) -> dict[str, Any]:
    """Get recent FAILED events from OpenSearch across both services.

    `lookback_minutes` defaults to 60 and is capped at 1440 (24 hours).
    `limit` defaults to 20 and is capped at 100.
    """
    return _run_tool(
        tools.get_recent_failures,
        opensearch_repo=_opensearch_repo,
        lookback_minutes=lookback_minutes,
        limit=limit,
    )


@mcp.tool(structured_output=True)
def get_service_request(correlation_id: str) -> dict[str, Any]:
    """Get the original service_request row that entered TraceBridge for one correlationId.

    Cross-service read from service-request-api's own table (public.service_request).
    Returns request metadata only - the long free-text description field is
    intentionally excluded.
    """
    return _run_tool(
        tools.get_service_request,
        postgres_repo=_postgres_repo,
        correlation_id=correlation_id,
    )


@mcp.tool(structured_output=True)
def get_service_runtime_status(service: str) -> dict[str, Any]:
    """Get the current Docker runtime state of one allowlisted TraceBridge service.

    Returns whether the container exists, is running, its lifecycle state,
    health status, start/finish timestamps, and exit code if stopped.
    `service` must be one of TraceBridge's own known services or
    infrastructure dependencies (e.g. "customer-db-consumer", "customer-postgres",
    "postgres", "kafka", "opensearch") - never returns environment variables,
    mounts, or any other container configuration, only runtime state.
    """
    return _run_tool(tools.get_service_runtime_status, docker_repo=_docker_repo, service=service)


@mcp.tool(structured_output=True)
def get_service_config_metadata(service: str) -> dict[str, Any]:
    """Get one allowlisted service's documented dependency relationships (name/type/host/port).

    This is static, curated reference data describing TraceBridge's own
    topology, never a live read of a container's real environment
    variables - no credential or secret can ever appear in this result.
    """
    return _run_tool(tools.get_service_config_metadata, service=service)


@mcp.tool(structured_output=True)
def get_container_events(service: str, limit: int | None = None) -> dict[str, Any]:
    """Get bounded recent Docker lifecycle events (start/stop/health changes) for one allowlisted service.

    `limit` defaults to 10 and is capped at 50. Looks back over a fixed
    24-hour window - this is a local investigation aid, not an audit log.
    """
    return _run_tool(tools.get_container_events, docker_repo=_docker_repo, service=service, limit=limit)


@mcp.tool(structured_output=True)
def get_dependency_health(service: str, dependency: str) -> dict[str, Any]:
    """Perform a bounded, read-only TCP reachability check from one allowlisted service to one of its known dependencies.

    Only (service, dependency) pairs in TraceBridge's own documented
    topology are accepted - this can never be used to probe an arbitrary
    host or port the caller supplies. Opens a bare TCP connection only: no
    protocol handshake, no authentication, no query, no data sent.
    """
    return _run_tool(
        tools.get_dependency_health,
        dependency_probe=_dependency_probe,
        service=service,
        dependency=dependency,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
