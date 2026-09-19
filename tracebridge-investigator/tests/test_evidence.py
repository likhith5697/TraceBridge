from tracebridge_investigator.evidence import EvidenceLog, extract_observed_events
from tracebridge_investigator.mcp_client import ToolCallOutcome


def test_evidence_ids_are_sequential():
    log = EvidenceLog()
    e1 = log.record("search_logs", {"correlation_id": "a"}, ToolCallOutcome(True, {"count": 0}, None))
    e2 = log.record("get_downstream_interactions", {"correlation_id": "a"}, ToolCallOutcome(True, {}, None))

    assert e1.id == "E1"
    assert e2.id == "E2"


def test_identical_repeated_call_reuses_the_same_evidence_id():
    log = EvidenceLog()
    outcome = ToolCallOutcome(True, {"count": 1}, None)

    first = log.record("search_logs", {"correlation_id": "a"}, outcome)
    second = log.record("search_logs", {"correlation_id": "a"}, outcome)

    assert first.id == second.id
    assert len(log.all()) == 1


def test_same_tool_different_arguments_gets_a_new_id():
    log = EvidenceLog()
    outcome = ToolCallOutcome(True, {"count": 1}, None)

    first = log.record("search_logs", {"correlation_id": "a"}, outcome)
    second = log.record("search_logs", {"correlation_id": "b"}, outcome)

    assert first.id != second.id


def test_valid_ids_reflects_all_recorded_evidence():
    log = EvidenceLog()
    log.record("search_logs", {}, ToolCallOutcome(True, {}, None))
    log.record("get_downstream_interactions", {}, ToolCallOutcome(True, {}, None))

    assert log.valid_ids() == {"E1", "E2"}


def test_get_returns_none_for_unknown_id():
    log = EvidenceLog()
    assert log.get("E999") is None


def test_extract_observed_events_reads_logs_and_timeline_keys():
    log = EvidenceLog()
    log.record(
        "search_logs",
        {},
        ToolCallOutcome(
            True,
            {"logs": [{"service": "service-request-api", "event": "SERVICE_REQUEST_RECEIVED"}]},
            None,
        ),
    )
    log.record(
        "get_transaction_timeline",
        {},
        ToolCallOutcome(
            True,
            {"timeline": [{"service": "servicenow-consumer", "event": "KAFKA_CONSUMED"}]},
            None,
        ),
    )

    observed = extract_observed_events(log)

    assert ("service-request-api", "SERVICE_REQUEST_RECEIVED") in observed
    assert ("servicenow-consumer", "KAFKA_CONSUMED") in observed
    assert len(observed) == 2


def test_extract_observed_events_ignores_failed_evidence():
    log = EvidenceLog()
    log.record("search_logs", {}, ToolCallOutcome(False, None, "OpenSearch unavailable"))

    assert extract_observed_events(log) == set()


def test_extract_observed_events_ignores_non_log_shaped_evidence():
    log = EvidenceLog()
    log.record(
        "get_downstream_interactions",
        {},
        ToolCallOutcome(True, {"downstreamInteractions": [{"httpStatus": 401}]}, None),
    )

    assert extract_observed_events(log) == set()
