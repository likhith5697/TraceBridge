from tracebridge_mcp.normalize import (
    normalize_downstream_interaction,
    normalize_log_entry,
    normalize_recent_failure,
    normalize_service_request,
    normalize_timeline_event,
)


def test_normalize_log_entry_maps_all_known_fields():
    source = {
        "@timestamp": "2026-09-18T00:05:56.605Z",
        "service": "servicenow-consumer",
        "event": "DOWNSTREAM_RESPONSE_RECEIVED",
        "correlationId": "51d3c01d-2b02-45b3-9df4-697ecd19a796",
        "eventId": "abc",
        "targetSystem": "SERVICENOW",
        "httpStatus": 201,
        "status": "SUCCESS",
        "errorCode": None,
        "durationMs": 428,
        "message": "ServiceNow incident created: INC0010007",
        "logger_name": "should.not.leak",
        "thread_name": "should-not-leak",
    }

    result = normalize_log_entry(source)

    assert result == {
        "timestamp": "2026-09-18T00:05:56.605Z",
        "service": "servicenow-consumer",
        "event": "DOWNSTREAM_RESPONSE_RECEIVED",
        "correlationId": "51d3c01d-2b02-45b3-9df4-697ecd19a796",
        "eventId": "abc",
        "targetSystem": "SERVICENOW",
        "httpStatus": 201,
        "status": "SUCCESS",
        "errorCode": None,
        "durationMs": 428,
        "message": "ServiceNow incident created: INC0010007",
    }
    assert "logger_name" not in result
    assert "thread_name" not in result


def test_normalize_log_entry_handles_missing_fields():
    result = normalize_log_entry({"@timestamp": "t", "service": "s", "event": "e"})

    assert result["timestamp"] == "t"
    assert result["httpStatus"] is None
    assert result["errorCode"] is None


def test_normalize_timeline_event_omits_absent_optional_fields():
    result = normalize_timeline_event(
        {"@timestamp": "t", "service": "service-request-api", "event": "SERVICE_REQUEST_RECEIVED"}
    )

    assert result == {"timestamp": "t", "service": "service-request-api", "event": "SERVICE_REQUEST_RECEIVED"}
    assert "httpStatus" not in result
    assert "errorCode" not in result


def test_normalize_timeline_event_includes_present_optional_fields():
    result = normalize_timeline_event(
        {
            "@timestamp": "t",
            "service": "servicenow-consumer",
            "event": "DOWNSTREAM_REQUEST_FAILED",
            "httpStatus": 401,
            "errorCode": "UNAUTHORIZED",
        }
    )

    assert result["httpStatus"] == 401
    assert result["errorCode"] == "UNAUTHORIZED"


def test_normalize_downstream_interaction_maps_snake_case_to_camel_case():
    row = {
        "correlation_id": "06fc3488-bc83-47a4-a768-db3af8b5c161",
        "event_id": "4332df07-40d8-4238-b3a4-d39866705983",
        "target_system": "SERVICENOW",
        "operation": "CREATE_INCIDENT",
        "http_method": "POST",
        "endpoint": "/api/now/table/incident",
        "request_timestamp": None,
        "response_timestamp": None,
        "http_status": 401,
        "status": "FAILED",
        "error_code": "UNAUTHORIZED",
        "error_message": "401 Unauthorized",
        "duration_ms": 321,
        "attempt_number": 1,
        "created_at": None,
    }

    result = normalize_downstream_interaction(row)

    assert result["correlationId"] == "06fc3488-bc83-47a4-a768-db3af8b5c161"
    assert result["eventId"] == "4332df07-40d8-4238-b3a4-d39866705983"
    assert result["httpStatus"] == 401
    assert result["errorCode"] == "UNAUTHORIZED"
    assert result["attemptNumber"] == 1
    assert "request_payload" not in result
    assert "response_payload" not in result


def test_normalize_service_request_excludes_long_description():
    row = {
        "correlation_id": "51d3c01d-2b02-45b3-9df4-697ecd19a796",
        "source": "CUSTOMER_PORTAL",
        "customer_id": "CUS-92831",
        "category": "NETWORK",
        "subcategory": "CONNECTIVITY",
        "short_description": "Customer circuit unavailable",
        "description": "a very long customer-entered free text field",
        "priority": "P2",
        "status": "RECEIVED",
        "created_at": None,
        "updated_at": None,
    }

    result = normalize_service_request(row)

    assert result["shortDescription"] == "Customer circuit unavailable"
    assert "description" not in result


def test_normalize_recent_failure_is_compact():
    source = {
        "@timestamp": "t",
        "correlationId": "cid",
        "service": "servicenow-consumer",
        "event": "DOWNSTREAM_REQUEST_FAILED",
        "targetSystem": "SERVICENOW",
        "httpStatus": 401,
        "errorCode": "UNAUTHORIZED",
        "message": "should not appear",
    }

    result = normalize_recent_failure(source)

    assert "message" not in result
    assert result["httpStatus"] == 401
