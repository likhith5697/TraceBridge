"""Pure functions that shape raw evidence into bounded, predictable shapes.

No I/O happens here. Every function takes whatever a repository handed
back and returns a plain dict containing only the fields we intentionally
expose - missing fields become None rather than being silently omitted,
so a caller can tell "field absent in evidence" from "field never existed
in the schema".
"""

from typing import Any


def normalize_log_entry(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": source.get("@timestamp"),
        "service": source.get("service"),
        "event": source.get("event"),
        "correlationId": source.get("correlationId"),
        "eventId": source.get("eventId"),
        "targetSystem": source.get("targetSystem"),
        "httpStatus": source.get("httpStatus"),
        "status": source.get("status"),
        "errorCode": source.get("errorCode"),
        "durationMs": source.get("durationMs"),
        "message": source.get("message"),
    }


def normalize_timeline_event(source: dict[str, Any]) -> dict[str, Any]:
    event: dict[str, Any] = {
        "timestamp": source.get("@timestamp"),
        "service": source.get("service"),
        "event": source.get("event"),
    }
    # Optional fields only added when present, keeping the common case (a plain
    # checkpoint like KAFKA_CONSUMED) compact instead of padded with nulls.
    for key in ("targetSystem", "httpStatus", "status", "errorCode", "durationMs"):
        if source.get(key) is not None:
            event[key] = source[key]
    return event


def normalize_downstream_interaction(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "correlationId": str(row.get("correlation_id")) if row.get("correlation_id") else None,
        "eventId": str(row.get("event_id")) if row.get("event_id") else None,
        "targetSystem": row.get("target_system"),
        "operation": row.get("operation"),
        "httpMethod": row.get("http_method"),
        "endpoint": row.get("endpoint"),
        "requestTimestamp": _isoformat(row.get("request_timestamp")),
        "responseTimestamp": _isoformat(row.get("response_timestamp")),
        "httpStatus": row.get("http_status"),
        "status": row.get("status"),
        "errorCode": row.get("error_code"),
        "errorMessage": row.get("error_message"),
        "durationMs": row.get("duration_ms"),
        "attemptNumber": row.get("attempt_number"),
        "createdAt": _isoformat(row.get("created_at")),
    }


def normalize_service_request(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "correlationId": str(row.get("correlation_id")) if row.get("correlation_id") else None,
        "source": row.get("source"),
        "customerId": row.get("customer_id"),
        "category": row.get("category"),
        "subcategory": row.get("subcategory"),
        "shortDescription": row.get("short_description"),
        "priority": row.get("priority"),
        "status": row.get("status"),
        "createdAt": _isoformat(row.get("created_at")),
        "updatedAt": _isoformat(row.get("updated_at")),
    }


def normalize_recent_failure(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": source.get("@timestamp"),
        "correlationId": source.get("correlationId"),
        "service": source.get("service"),
        "event": source.get("event"),
        "targetSystem": source.get("targetSystem"),
        "httpStatus": source.get("httpStatus"),
        "errorCode": source.get("errorCode"),
    }


def _isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
