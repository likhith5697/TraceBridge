from unittest.mock import MagicMock

import pytest

from tracebridge_mcp import tools
from tracebridge_mcp.errors import EvidenceSourceUnavailableError, InvalidToolInputError

CID = "51d3c01d-2b02-45b3-9df4-697ecd19a796"


def test_search_logs_rejects_invalid_correlation_id():
    with pytest.raises(InvalidToolInputError):
        tools.search_logs(MagicMock(), "not-a-uuid")


def test_search_logs_passes_validated_arguments_through_to_the_repository():
    repo = MagicMock()
    repo.find_logs_by_correlation_id.return_value = []

    tools.search_logs(repo, CID, service="servicenow-consumer", event="KAFKA_CONSUMED", limit=10)

    repo.find_logs_by_correlation_id.assert_called_once_with(CID, "servicenow-consumer", "KAFKA_CONSUMED", 10)


def test_search_logs_rejects_unknown_service_before_querying():
    repo = MagicMock()
    with pytest.raises(InvalidToolInputError):
        tools.search_logs(repo, CID, service="not-a-real-service")
    repo.find_logs_by_correlation_id.assert_not_called()


def test_search_logs_normalizes_and_counts_results():
    repo = MagicMock()
    repo.find_logs_by_correlation_id.return_value = [
        {"@timestamp": "t1", "service": "a", "event": "E1"},
        {"@timestamp": "t2", "service": "a", "event": "E2"},
    ]

    result = tools.search_logs(repo, CID)

    assert result["correlationId"] == CID
    assert result["count"] == 2
    assert [log["event"] for log in result["logs"]] == ["E1", "E2"]


def test_get_downstream_interactions_preserves_repository_order():
    repo = MagicMock()
    repo.find_downstream_interactions.return_value = [
        {"correlation_id": CID, "http_status": 500},
        {"correlation_id": CID, "http_status": 201},
    ]

    result = tools.get_downstream_interactions(repo, CID)

    assert [row["httpStatus"] for row in result["downstreamInteractions"]] == [500, 201]


def test_get_downstream_interactions_empty_is_not_an_error():
    repo = MagicMock()
    repo.find_downstream_interactions.return_value = []

    result = tools.get_downstream_interactions(repo, CID)

    assert result == {"correlationId": CID, "count": 0, "downstreamInteractions": []}


def test_get_transaction_timeline_reports_only_observed_checkpoints():
    repo = MagicMock()
    repo.find_logs_by_correlation_id.return_value = [
        {"@timestamp": "t1", "service": "service-request-api", "event": "SERVICE_REQUEST_RECEIVED"},
        {"@timestamp": "t2", "service": "servicenow-consumer", "event": "DOWNSTREAM_REQUEST_FAILED", "httpStatus": 401},
    ]

    result = tools.get_transaction_timeline(repo, CID)

    assert result["eventCount"] == 2
    events = [entry["event"] for entry in result["timeline"]]
    assert events == ["SERVICE_REQUEST_RECEIVED", "DOWNSTREAM_REQUEST_FAILED"]
    # KAFKA_CONSUMED was never in the repository response, so it must never appear -
    # this tool must not fabricate a missing checkpoint.
    assert "KAFKA_CONSUMED" not in events


def test_get_transaction_timeline_queries_without_service_or_event_filter():
    repo = MagicMock()
    repo.find_logs_by_correlation_id.return_value = []

    tools.get_transaction_timeline(repo, CID)

    args = repo.find_logs_by_correlation_id.call_args.args
    assert args[1] is None  # service filter
    assert args[2] is None  # event filter


def test_get_transaction_summary_reports_both_sources_available():
    opensearch_repo = MagicMock()
    opensearch_repo.find_logs_by_correlation_id.return_value = [
        {"@timestamp": "2026-01-01T00:00:00Z", "service": "service-request-api"},
        {"@timestamp": "2026-01-01T00:00:05Z", "service": "servicenow-consumer"},
    ]
    postgres_repo = MagicMock()
    postgres_repo.find_downstream_interactions.return_value = [{"correlation_id": CID, "http_status": 201}]

    result = tools.get_transaction_summary(opensearch_repo, postgres_repo, CID)

    assert result["openSearchAvailable"] is True
    assert result["postgresAvailable"] is True
    assert result["firstSeen"] == "2026-01-01T00:00:00Z"
    assert result["lastSeen"] == "2026-01-01T00:00:05Z"
    assert result["servicesObserved"] == ["service-request-api", "servicenow-consumer"]
    assert result["eventsObserved"] == 2
    assert len(result["downstreamInteractions"]) == 1


def test_get_transaction_summary_distinguishes_opensearch_unavailable_from_no_logs():
    opensearch_repo = MagicMock()
    opensearch_repo.find_logs_by_correlation_id.side_effect = EvidenceSourceUnavailableError("down")
    postgres_repo = MagicMock()
    postgres_repo.find_downstream_interactions.return_value = []

    result = tools.get_transaction_summary(opensearch_repo, postgres_repo, CID)

    assert result["openSearchAvailable"] is False
    assert result["postgresAvailable"] is True
    assert result["eventsObserved"] == 0
    # postgres evidence must still be reported even though OpenSearch failed
    assert result["downstreamInteractions"] == []


def test_get_transaction_summary_distinguishes_postgres_unavailable_from_no_interactions():
    opensearch_repo = MagicMock()
    opensearch_repo.find_logs_by_correlation_id.return_value = [{"@timestamp": "t", "service": "service-request-api"}]
    postgres_repo = MagicMock()
    postgres_repo.find_downstream_interactions.side_effect = EvidenceSourceUnavailableError("down")

    result = tools.get_transaction_summary(opensearch_repo, postgres_repo, CID)

    assert result["postgresAvailable"] is False
    assert result["openSearchAvailable"] is True
    assert result["eventsObserved"] == 1


def test_get_recent_failures_enforces_default_and_max_bounds():
    repo = MagicMock()
    repo.find_recent_failures.return_value = []

    tools.get_recent_failures(repo)
    repo.find_recent_failures.assert_called_with(60, 20)

    tools.get_recent_failures(repo, lookback_minutes=999999, limit=999999)
    args = repo.find_recent_failures.call_args.args
    assert args[0] == 1440  # MAX_LOOKBACK_MINUTES
    assert args[1] == 100  # MAX_RECENT_FAILURES_LIMIT


def test_get_recent_failures_rejects_negative_lookback():
    repo = MagicMock()
    with pytest.raises(InvalidToolInputError):
        tools.get_recent_failures(repo, lookback_minutes=-1)


def test_get_service_request_found():
    repo = MagicMock()
    repo.find_service_request.return_value = {"correlation_id": CID, "source": "CUSTOMER_PORTAL"}

    result = tools.get_service_request(repo, CID)

    assert result["found"] is True
    assert result["serviceRequest"]["source"] == "CUSTOMER_PORTAL"


def test_get_service_request_not_found_is_not_an_error():
    repo = MagicMock()
    repo.find_service_request.return_value = None

    result = tools.get_service_request(repo, CID)

    assert result == {"correlationId": CID, "found": False, "serviceRequest": None}


def test_get_service_runtime_status_rejects_unknown_service_before_querying():
    docker_repo = MagicMock()
    with pytest.raises(InvalidToolInputError):
        tools.get_service_runtime_status(docker_repo, "not-a-real-service")
    docker_repo.get_container_status.assert_not_called()


def test_get_service_runtime_status_maps_logical_name_to_container_name():
    docker_repo = MagicMock()
    docker_repo.get_container_status.return_value = {
        "exists": True,
        "running": False,
        "state": "exited",
        "health": None,
        "startedAt": "t1",
        "finishedAt": "t2",
        "exitCode": 1,
    }

    result = tools.get_service_runtime_status(docker_repo, "customer-postgres")

    docker_repo.get_container_status.assert_called_once_with("tracebridge-customer-postgres")
    assert result["service"] == "customer-postgres"
    assert result["running"] is False
    assert result["exitCode"] == 1


def test_get_service_config_metadata_returns_only_documented_dependencies():
    result = tools.get_service_config_metadata("customer-db-consumer")

    assert result["service"] == "customer-db-consumer"
    names = {dep["name"] for dep in result["dependencies"]}
    assert names == {"kafka", "customer-postgres"}


def test_get_service_config_metadata_never_reads_a_live_repository():
    """No repository parameter exists at all for this tool - it is pure,
    static catalog data, which is what makes it impossible for a real
    credential to leak through it."""
    import inspect

    signature = inspect.signature(tools.get_service_config_metadata)
    assert list(signature.parameters) == ["service"]


def test_get_service_config_metadata_rejects_unknown_service():
    with pytest.raises(InvalidToolInputError):
        tools.get_service_config_metadata("not-a-real-service")


def test_get_container_events_enforces_default_and_max_limit():
    docker_repo = MagicMock()
    docker_repo.get_container_events.return_value = []

    tools.get_container_events(docker_repo, "customer-postgres")
    args = docker_repo.get_container_events.call_args.args
    assert args[0] == "tracebridge-customer-postgres"
    assert args[2] == 10  # DEFAULT_CONTAINER_EVENTS_LIMIT

    tools.get_container_events(docker_repo, "customer-postgres", limit=9999)
    args = docker_repo.get_container_events.call_args.args
    assert args[2] == 50  # MAX_CONTAINER_EVENTS_LIMIT


def test_get_container_events_rejects_unknown_service():
    docker_repo = MagicMock()
    with pytest.raises(InvalidToolInputError):
        tools.get_container_events(docker_repo, "not-a-real-service")
    docker_repo.get_container_events.assert_not_called()


def test_get_dependency_health_reachable():
    from tracebridge_mcp.dependency_probe import ProbeResult

    probe = MagicMock(return_value=ProbeResult(reachable=True, failure=None, duration_ms=12.3))

    result = tools.get_dependency_health(probe, "customer-db-consumer", "customer-postgres")

    probe.assert_called_once_with("customer-postgres", 5432)
    assert result["reachable"] is True
    assert result["failure"] is None
    assert result["target"] == "customer-postgres:5432"
    assert result["type"] == "postgresql"


def test_get_dependency_health_unreachable_is_a_successful_observation_not_an_error():
    from tracebridge_mcp.dependency_probe import ProbeResult

    probe = MagicMock(return_value=ProbeResult(reachable=False, failure="CONNECTION_REFUSED", duration_ms=5.0))

    result = tools.get_dependency_health(probe, "customer-db-consumer", "customer-postgres")

    assert result["reachable"] is False
    assert result["failure"] == "CONNECTION_REFUSED"


def test_get_dependency_health_rejects_unlisted_pair_before_probing():
    probe = MagicMock()
    with pytest.raises(InvalidToolInputError):
        tools.get_dependency_health(probe, "service-request-api", "customer-postgres")
    probe.assert_not_called()


def test_get_dependency_health_rejects_arbitrary_host_before_probing():
    probe = MagicMock()
    with pytest.raises(InvalidToolInputError):
        tools.get_dependency_health(probe, "customer-db-consumer", "arbitrary-host.com")
    probe.assert_not_called()


def test_no_new_runtime_tool_ever_exposes_a_secret_shaped_field():
    docker_repo = MagicMock()
    docker_repo.get_container_status.return_value = {
        "exists": True, "running": True, "state": "running", "health": "healthy",
        "startedAt": "t", "finishedAt": None, "exitCode": None,
    }
    docker_repo.get_container_events.return_value = []

    from tracebridge_mcp.dependency_probe import ProbeResult

    probe = MagicMock(return_value=ProbeResult(reachable=False, failure="CONNECTION_REFUSED", duration_ms=1.0))

    results = [
        tools.get_service_runtime_status(docker_repo, "customer-postgres"),
        tools.get_service_config_metadata("customer-db-consumer"),
        tools.get_container_events(docker_repo, "customer-postgres"),
        tools.get_dependency_health(probe, "customer-db-consumer", "customer-postgres"),
    ]

    forbidden_substrings = ("password", "passwd", "secret", "token", "authorization", "api_key", "apikey", "credential")

    def all_strings(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield str(key)
                yield from all_strings(value)
        elif isinstance(obj, list):
            for item in obj:
                yield from all_strings(item)
        elif isinstance(obj, str):
            yield obj

    for result in results:
        blob = " ".join(all_strings(result)).lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in blob, f"secret-shaped field found in {result}"


def test_no_tool_exposes_a_root_cause_or_diagnosis_field():
    """Evidence vs reasoning boundary: scan every dict-returning tool's shape
    for anything that looks like a diagnosis rather than an observation."""
    forbidden_keys = {"rootCause", "root_cause", "diagnosis", "recommendation", "suggestedFix"}

    opensearch_repo = MagicMock()
    opensearch_repo.find_logs_by_correlation_id.return_value = [
        {"@timestamp": "t", "service": "servicenow-consumer", "event": "DOWNSTREAM_REQUEST_FAILED", "httpStatus": 401}
    ]
    opensearch_repo.find_recent_failures.return_value = []
    postgres_repo = MagicMock()
    postgres_repo.find_downstream_interactions.return_value = [
        {"correlation_id": CID, "http_status": 401, "status": "FAILED", "error_code": "UNAUTHORIZED"}
    ]
    postgres_repo.find_service_request.return_value = {"correlation_id": CID}

    results = [
        tools.search_logs(opensearch_repo, CID),
        tools.get_downstream_interactions(postgres_repo, CID),
        tools.get_transaction_timeline(opensearch_repo, CID),
        tools.get_transaction_summary(opensearch_repo, postgres_repo, CID),
        tools.get_recent_failures(opensearch_repo),
        tools.get_service_request(postgres_repo, CID),
    ]

    def all_keys(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield key
                yield from all_keys(value)
        elif isinstance(obj, list):
            for item in obj:
                yield from all_keys(item)

    for result in results:
        found_keys = set(all_keys(result))
        assert found_keys.isdisjoint(forbidden_keys), f"diagnosis-like key found in {result}"
