"""Input validation for every MCP tool.

Nothing here reaches a database or search query until it passes these
checks. correlation_id is validated as a real UUID because every genuine
TraceBridge correlationId is generated with UUID.randomUUID() in
service-request-api - a non-UUID value cannot possibly match real evidence
and is rejected before it ever becomes part of a query.
"""

import uuid

from tracebridge_mcp.catalog import DEPENDENCY_CATALOG, RUNTIME_SERVICE_CONTAINERS
from tracebridge_mcp.errors import InvalidToolInputError

MAX_CORRELATION_ID_LENGTH = 100

DEFAULT_SEARCH_LOGS_LIMIT = 50
MAX_SEARCH_LOGS_LIMIT = 200

DEFAULT_RECENT_FAILURES_LIMIT = 20
MAX_RECENT_FAILURES_LIMIT = 100

DEFAULT_LOOKBACK_MINUTES = 60
MAX_LOOKBACK_MINUTES = 1440  # 24 hours - a local investigation window, not a data warehouse query

DEFAULT_CONTAINER_EVENTS_LIMIT = 10
MAX_CONTAINER_EVENTS_LIMIT = 50
CONTAINER_EVENTS_LOOKBACK_MINUTES = 1440  # fixed 24h window - a local investigation aid, not an audit log

KNOWN_SERVICES = frozenset({"service-request-api", "servicenow-consumer", "customer-db-consumer"})

KNOWN_EVENTS = frozenset(
    {
        # service-request-api
        "SERVICE_REQUEST_RECEIVED",
        "DATABASE_PERSISTED",
        "KAFKA_PUBLISH_STARTED",
        "KAFKA_PUBLISHED",
        "KAFKA_PUBLISH_FAILED",
        "REQUEST_VALIDATION_FAILED",
        # servicenow-consumer / customer-db-consumer (shared pipeline-stage names;
        # the `service` field on each log line is what tells them apart)
        "KAFKA_CONSUMED",
        "CORRELATION_VALIDATED",
        "EVENT_VALIDATED",
        "SOURCE_VALIDATED",
        "CORRELATION_MISMATCH",
        "EVENT_VALIDATION_FAILED",
        "PAYLOAD_TRANSFORMED",
        "EVENT_PROCESSING_COMPLETED",
        # idempotency guard - shared by both consumers (see each service's
        # V2__add_event_id_for_idempotency.sql): a redelivered Kafka message
        # is detected and skipped before it can repeat a downstream side effect
        "DUPLICATE_EVENT_SKIPPED",
        "DUPLICATE_EVENT_DETECTED_ON_INSERT",
        # servicenow-consumer
        "DOWNSTREAM_REQUEST_STARTED",
        "DOWNSTREAM_RESPONSE_RECEIVED",
        "DOWNSTREAM_REQUEST_FAILED",
        "DOWNSTREAM_INTERACTION_PERSISTED",
        # customer-db-consumer
        "DB_OPERATION_STARTED",
        "DB_OPERATION_SUCCEEDED",
        "DB_OPERATION_FAILED",
        "CUSTOMER_RECORD_PERSISTED",
    }
)


def validate_correlation_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidToolInputError("correlation_id is required and must not be blank")
    value = value.strip()
    if len(value) > MAX_CORRELATION_ID_LENGTH:
        raise InvalidToolInputError(f"correlation_id exceeds maximum length of {MAX_CORRELATION_ID_LENGTH}")
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise InvalidToolInputError(f"correlation_id must be a valid UUID, got: {value!r}") from exc
    return value


def validate_limit(value: int | None, default: int, maximum: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidToolInputError("limit must be an integer")
    if value <= 0:
        raise InvalidToolInputError("limit must be a positive integer")
    return min(value, maximum)


def validate_lookback_minutes(value: int | None) -> int:
    if value is None:
        return DEFAULT_LOOKBACK_MINUTES
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidToolInputError("lookback_minutes must be an integer")
    if value <= 0:
        raise InvalidToolInputError("lookback_minutes must be a positive integer")
    return min(value, MAX_LOOKBACK_MINUTES)


def validate_service(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in KNOWN_SERVICES:
        raise InvalidToolInputError(f"unknown service: {value!r}. Known services: {sorted(KNOWN_SERVICES)}")
    return value


def validate_event(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in KNOWN_EVENTS:
        raise InvalidToolInputError(f"unknown event: {value!r}. Known events: {sorted(KNOWN_EVENTS)}")
    return value


def validate_runtime_service(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidToolInputError("service is required and must not be blank")
    value = value.strip()
    if value not in RUNTIME_SERVICE_CONTAINERS:
        raise InvalidToolInputError(
            f"unknown service: {value!r}. Known services: {sorted(RUNTIME_SERVICE_CONTAINERS)}"
        )
    return value


def validate_dependency(service: str, dependency: str) -> tuple[str, str]:
    validated_service = validate_runtime_service(service)
    if not isinstance(dependency, str) or not dependency.strip():
        raise InvalidToolInputError("dependency is required and must not be blank")
    validated_dependency = dependency.strip()
    if (validated_service, validated_dependency) not in DEPENDENCY_CATALOG:
        known = sorted(dep for (svc, dep) in DEPENDENCY_CATALOG if svc == validated_service)
        raise InvalidToolInputError(
            f"{validated_dependency!r} is not a known dependency of {validated_service!r}. "
            f"Known dependencies: {known}"
        )
    return validated_service, validated_dependency


def validate_container_events_limit(value: int | None) -> int:
    return validate_limit(value, DEFAULT_CONTAINER_EVENTS_LIMIT, MAX_CONTAINER_EVENTS_LIMIT)
