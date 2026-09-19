"""Business logic for every MCP tool.

Deliberately plain functions, not decorated here - server.py wires each of
these to an @mcp.tool(), but every function below is callable and testable
completely on its own, with fake repositories, and with no MCP machinery
involved at all.

Every function returns OBSERVED EVIDENCE ONLY. None of them ever compute or
return a diagnosis, a root cause, or any statement about why something
happened - only what was recorded.
"""

from datetime import datetime, timezone
from typing import Any, Callable

from tracebridge_mcp.catalog import DEPENDENCY_CATALOG, RUNTIME_SERVICE_CONTAINERS, dependencies_for
from tracebridge_mcp.dependency_probe import ProbeResult
from tracebridge_mcp.docker_repository import DockerRuntimeRepository
from tracebridge_mcp.errors import EvidenceSourceUnavailableError
from tracebridge_mcp.normalize import (
    normalize_downstream_interaction,
    normalize_log_entry,
    normalize_recent_failure,
    normalize_service_request,
    normalize_timeline_event,
)
from tracebridge_mcp.opensearch_repository import OpenSearchEvidenceRepository
from tracebridge_mcp.postgres_repository import PostgresEvidenceRepository
from tracebridge_mcp.validation import (
    CONTAINER_EVENTS_LOOKBACK_MINUTES,
    DEFAULT_RECENT_FAILURES_LIMIT,
    DEFAULT_SEARCH_LOGS_LIMIT,
    MAX_RECENT_FAILURES_LIMIT,
    MAX_SEARCH_LOGS_LIMIT,
    validate_container_events_limit,
    validate_correlation_id,
    validate_dependency,
    validate_event,
    validate_limit,
    validate_lookback_minutes,
    validate_runtime_service,
    validate_service,
)

# get_transaction_timeline wants every checkpoint for a transaction, not a
# paginated slice - MAX_SEARCH_LOGS_LIMIT is already a generous per-tool cap
# (200) and a single TraceBridge transaction produces well under that today.
_TIMELINE_LIMIT = MAX_SEARCH_LOGS_LIMIT


def search_logs(
    opensearch_repo: OpenSearchEvidenceRepository,
    correlation_id: str,
    service: str | None = None,
    event: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    cid = validate_correlation_id(correlation_id)
    svc = validate_service(service)
    evt = validate_event(event)
    lim = validate_limit(limit, DEFAULT_SEARCH_LOGS_LIMIT, MAX_SEARCH_LOGS_LIMIT)

    raw_hits = opensearch_repo.find_logs_by_correlation_id(cid, svc, evt, lim)
    logs = [normalize_log_entry(hit) for hit in raw_hits]

    return {"correlationId": cid, "count": len(logs), "logs": logs}


def get_downstream_interactions(
    postgres_repo: PostgresEvidenceRepository,
    correlation_id: str,
) -> dict[str, Any]:
    cid = validate_correlation_id(correlation_id)

    raw_rows = postgres_repo.find_downstream_interactions(cid)
    interactions = [normalize_downstream_interaction(row) for row in raw_rows]

    return {"correlationId": cid, "count": len(interactions), "downstreamInteractions": interactions}


def get_transaction_timeline(
    opensearch_repo: OpenSearchEvidenceRepository,
    correlation_id: str,
) -> dict[str, Any]:
    cid = validate_correlation_id(correlation_id)

    raw_hits = opensearch_repo.find_logs_by_correlation_id(cid, None, None, _TIMELINE_LIMIT)
    timeline = [normalize_timeline_event(hit) for hit in raw_hits]

    return {"correlationId": cid, "eventCount": len(timeline), "timeline": timeline}


def get_transaction_summary(
    opensearch_repo: OpenSearchEvidenceRepository,
    postgres_repo: PostgresEvidenceRepository,
    correlation_id: str,
) -> dict[str, Any]:
    cid = validate_correlation_id(correlation_id)

    # OpenSearch being down and "no logs exist" are different facts - each
    # source's availability is tracked independently rather than letting one
    # failure hide the other source's evidence.
    opensearch_available = True
    try:
        raw_logs = opensearch_repo.find_logs_by_correlation_id(cid, None, None, _TIMELINE_LIMIT)
    except EvidenceSourceUnavailableError:
        opensearch_available = False
        raw_logs = []

    postgres_available = True
    try:
        raw_interactions = postgres_repo.find_downstream_interactions(cid)
    except EvidenceSourceUnavailableError:
        postgres_available = False
        raw_interactions = []

    services_observed = sorted({entry["service"] for entry in raw_logs if entry.get("service")})
    timestamps = sorted(entry["@timestamp"] for entry in raw_logs if entry.get("@timestamp"))

    return {
        "correlationId": cid,
        "openSearchAvailable": opensearch_available,
        "postgresAvailable": postgres_available,
        "firstSeen": timestamps[0] if timestamps else None,
        "lastSeen": timestamps[-1] if timestamps else None,
        "servicesObserved": services_observed,
        "eventsObserved": len(raw_logs),
        "downstreamInteractions": [normalize_downstream_interaction(row) for row in raw_interactions],
    }


def get_recent_failures(
    opensearch_repo: OpenSearchEvidenceRepository,
    lookback_minutes: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    minutes = validate_lookback_minutes(lookback_minutes)
    lim = validate_limit(limit, DEFAULT_RECENT_FAILURES_LIMIT, MAX_RECENT_FAILURES_LIMIT)

    raw_hits = opensearch_repo.find_recent_failures(minutes, lim)
    failures = [normalize_recent_failure(hit) for hit in raw_hits]

    return {"lookbackMinutes": minutes, "count": len(failures), "failures": failures}


def get_service_request(
    postgres_repo: PostgresEvidenceRepository,
    correlation_id: str,
) -> dict[str, Any]:
    cid = validate_correlation_id(correlation_id)

    row = postgres_repo.find_service_request(cid)
    if row is None:
        return {"correlationId": cid, "found": False, "serviceRequest": None}

    return {"correlationId": cid, "found": True, "serviceRequest": normalize_service_request(row)}


# --- Phase 8: read-only runtime/dependency evidence -------------------------
#
# These four tools return facts about TraceBridge's own local runtime and
# documented topology - never about a specific transaction. They exist so an
# investigation can go deeper than "the downstream call failed" when
# application-level evidence alone cannot explain why: whether the
# underlying container is running, what it depends on, and whether that
# dependency is currently reachable. Like every other tool in this module,
# they report observed facts only - never a diagnosis.


def get_service_runtime_status(
    docker_repo: DockerRuntimeRepository,
    service: str,
) -> dict[str, Any]:
    svc = validate_runtime_service(service)
    container_name = RUNTIME_SERVICE_CONTAINERS[svc]
    status = docker_repo.get_container_status(container_name)
    return {"service": svc, **status}


def get_service_config_metadata(service: str) -> dict[str, Any]:
    svc = validate_runtime_service(service)
    return {"service": svc, "dependencies": dependencies_for(svc)}


def get_container_events(
    docker_repo: DockerRuntimeRepository,
    service: str,
    limit: int | None = None,
) -> dict[str, Any]:
    svc = validate_runtime_service(service)
    lim = validate_container_events_limit(limit)
    container_name = RUNTIME_SERVICE_CONTAINERS[svc]
    events = docker_repo.get_container_events(container_name, CONTAINER_EVENTS_LOOKBACK_MINUTES, lim)
    return {"service": svc, "count": len(events), "events": events}


def get_dependency_health(
    dependency_probe: Callable[[str, int], ProbeResult],
    service: str,
    dependency: str,
) -> dict[str, Any]:
    svc, dep = validate_dependency(service, dependency)
    info = DEPENDENCY_CATALOG[(svc, dep)]
    result = dependency_probe(info.host, info.port)
    return {
        "service": svc,
        "dependency": dep,
        "type": info.type,
        "target": f"{info.host}:{info.port}",
        "reachable": result.reachable,
        "failure": result.failure,
        "durationMs": round(result.duration_ms, 1),
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }
