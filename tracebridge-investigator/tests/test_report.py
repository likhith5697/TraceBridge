from tracebridge_investigator.evidence import EvidenceLog
from tracebridge_investigator.investigator import InvestigationResult
from tracebridge_investigator.mcp_client import ToolCallOutcome
from tracebridge_investigator.report import compute_confidence, render_report


def _make_result(evidence: EvidenceLog, **overrides) -> InvestigationResult:
    defaults = dict(
        investigation_id="inv-1",
        correlation_id="51d3c01d-2b02-45b3-9df4-697ecd19a796",
        outcome="SUCCESS",
        interpretation="Transaction completed.",
        limitations="None.",
        failure_boundary=None,
        recommended_investigation_area=None,
        cited_evidence_ids=[],
        evidence=evidence,
        tool_call_log=[],
        iteration_count=1,
        llm_call_count=2,
        duration_seconds=1.23,
        stopped_reason="submit_report",
    )
    defaults.update(overrides)
    return InvestigationResult(**defaults)


def test_confidence_high_when_both_sources_confirm():
    log = EvidenceLog()
    log.record("get_transaction_timeline", {}, ToolCallOutcome(True, {"timeline": [{"service": "a", "event": "X"}]}, None))
    log.record(
        "get_downstream_interactions", {}, ToolCallOutcome(True, {"downstreamInteractions": [{"httpStatus": 201}]}, None)
    )

    assert compute_confidence(_make_result(log)) == "HIGH"


def test_confidence_medium_when_only_one_source_confirms():
    log = EvidenceLog()
    log.record("search_logs", {}, ToolCallOutcome(True, {"logs": [{"event": "X"}]}, None))

    assert compute_confidence(_make_result(log)) == "MEDIUM"


def test_confidence_low_when_nothing_confirmed():
    log = EvidenceLog()
    log.record("search_logs", {}, ToolCallOutcome(True, {"logs": []}, None))

    assert compute_confidence(_make_result(log)) == "LOW"


def test_confidence_low_when_investigation_did_not_reach_a_conclusion():
    log = EvidenceLog()
    log.record("search_logs", {}, ToolCallOutcome(True, {"logs": [{"event": "X"}]}, None))

    result = _make_result(log, stopped_reason="max_iterations")

    assert compute_confidence(result) == "LOW"


def test_confidence_medium_when_only_dependency_health_confirms_alone():
    """A single live runtime probe, with nothing else corroborating it, is
    still just one source - MEDIUM, not HIGH."""
    log = EvidenceLog()
    log.record(
        "get_dependency_health",
        {},
        ToolCallOutcome(True, {"dependency": "customer-postgres", "reachable": False}, None),
    )

    assert compute_confidence(_make_result(log)) == "MEDIUM"


def test_confidence_medium_when_only_runtime_status_confirms_alone():
    log = EvidenceLog()
    log.record(
        "get_service_runtime_status",
        {},
        ToolCallOutcome(True, {"service": "customer-postgres", "running": False}, None),
    )

    assert compute_confidence(_make_result(log)) == "MEDIUM"


def test_confidence_high_when_logs_dependency_probe_and_runtime_status_all_agree():
    """The documented three-signal rule: a log-level failure plus two
    independent live runtime probes agreeing on the same dependency name."""
    log = EvidenceLog()
    log.record(
        "search_logs",
        {},
        ToolCallOutcome(True, {"logs": [{"event": "DB_OPERATION_FAILED", "errorCode": "CONNECTION_REFUSED"}]}, None),
    )
    log.record(
        "get_dependency_health",
        {},
        ToolCallOutcome(True, {"dependency": "customer-postgres", "reachable": False}, None),
    )
    log.record(
        "get_service_runtime_status",
        {},
        ToolCallOutcome(True, {"service": "customer-postgres", "running": False}, None),
    )

    assert compute_confidence(_make_result(log)) == "HIGH"


def test_confidence_stays_medium_when_runtime_probes_disagree_on_target():
    """Both runtime tools ran, but for DIFFERENT dependencies - that is not
    independent agreement, so it must not be upgraded to HIGH."""
    log = EvidenceLog()
    log.record(
        "search_logs",
        {},
        ToolCallOutcome(True, {"logs": [{"event": "DB_OPERATION_FAILED"}]}, None),
    )
    log.record(
        "get_dependency_health",
        {},
        ToolCallOutcome(True, {"dependency": "customer-postgres", "reachable": False}, None),
    )
    log.record(
        "get_service_runtime_status",
        {},
        ToolCallOutcome(True, {"service": "kafka", "running": False}, None),
    )

    assert compute_confidence(_make_result(log)) == "MEDIUM"


def test_confidence_stays_medium_when_runtime_status_contradicts_dependency_probe():
    """Dependency probe says unreachable, but the container inspection says
    it IS running for that same name - contradictory evidence must not
    become HIGH confidence."""
    log = EvidenceLog()
    log.record(
        "search_logs",
        {},
        ToolCallOutcome(True, {"logs": [{"event": "DB_OPERATION_FAILED"}]}, None),
    )
    log.record(
        "get_dependency_health",
        {},
        ToolCallOutcome(True, {"dependency": "customer-postgres", "reachable": False}, None),
    )
    log.record(
        "get_service_runtime_status",
        {},
        ToolCallOutcome(True, {"service": "customer-postgres", "running": True}, None),
    )

    assert compute_confidence(_make_result(log)) == "MEDIUM"


def test_confidence_config_metadata_and_container_events_never_influence_confidence():
    """Static catalog data and supplementary lifecycle events are not live
    pass/fail signals about this transaction - they must never move
    confidence on their own."""
    log = EvidenceLog()
    log.record(
        "get_service_config_metadata",
        {},
        ToolCallOutcome(True, {"service": "customer-db-consumer", "dependencies": [{"name": "customer-postgres"}]}, None),
    )
    log.record(
        "get_container_events",
        {},
        ToolCallOutcome(True, {"service": "customer-postgres", "events": [{"action": "die"}]}, None),
    )

    assert compute_confidence(_make_result(log)) == "LOW"


def test_render_report_includes_correlation_id_and_outcome():
    log = EvidenceLog()
    text = render_report(_make_result(log))

    assert "51d3c01d-2b02-45b3-9df4-697ecd19a796" in text
    assert "Outcome: SUCCESS" in text


def test_render_report_shows_checkmarks_for_full_success():
    log = EvidenceLog()
    log.record(
        "get_transaction_timeline",
        {},
        ToolCallOutcome(
            True,
            {
                "timeline": [
                    {"service": "service-request-api", "event": "SERVICE_REQUEST_RECEIVED"},
                    {"service": "service-request-api", "event": "DATABASE_PERSISTED"},
                ]
            },
            None,
        ),
    )
    text = render_report(_make_result(log))

    assert "✓ request received" in text
    assert "✓ database persisted" in text


def test_render_report_shows_failure_mark_and_boundary_for_401():
    log = EvidenceLog()
    checkpoints = [
        ("service-request-api", "SERVICE_REQUEST_RECEIVED"),
        ("service-request-api", "DATABASE_PERSISTED"),
        ("service-request-api", "KAFKA_PUBLISH_STARTED"),
        ("service-request-api", "KAFKA_PUBLISHED"),
        ("servicenow-consumer", "KAFKA_CONSUMED"),
        ("servicenow-consumer", "CORRELATION_VALIDATED"),
        ("servicenow-consumer", "EVENT_VALIDATED"),
        ("servicenow-consumer", "SOURCE_VALIDATED"),
        ("servicenow-consumer", "PAYLOAD_TRANSFORMED"),
        ("servicenow-consumer", "DOWNSTREAM_REQUEST_STARTED"),
        ("servicenow-consumer", "DOWNSTREAM_REQUEST_FAILED"),
    ]
    log.record(
        "get_transaction_timeline",
        {},
        ToolCallOutcome(
            True,
            {"timeline": [{"service": service, "event": event} for service, event in checkpoints]},
            None,
        ),
    )
    result = _make_result(log, outcome="FAILURE")
    text = render_report(result)

    assert "✗ downstream request" in text
    assert "Failure boundary: servicenow-consumer -> ServiceNow" in text


def test_render_report_shows_failure_mark_and_boundary_for_customer_db_consumer():
    log = EvidenceLog()
    # The renderer walks stages in a fixed order and stops at the first gap -
    # since customer-db-consumer's stages come after servicenow-consumer's,
    # reaching them requires servicenow-consumer's own path to be complete too
    # (this mirrors the real demo: ServiceNow succeeds, customer-db-consumer
    # fails independently).
    checkpoints = [
        ("service-request-api", "SERVICE_REQUEST_RECEIVED"),
        ("service-request-api", "DATABASE_PERSISTED"),
        ("service-request-api", "KAFKA_PUBLISH_STARTED"),
        ("service-request-api", "KAFKA_PUBLISHED"),
        ("servicenow-consumer", "KAFKA_CONSUMED"),
        ("servicenow-consumer", "CORRELATION_VALIDATED"),
        ("servicenow-consumer", "EVENT_VALIDATED"),
        ("servicenow-consumer", "SOURCE_VALIDATED"),
        ("servicenow-consumer", "PAYLOAD_TRANSFORMED"),
        ("servicenow-consumer", "DOWNSTREAM_REQUEST_STARTED"),
        ("servicenow-consumer", "DOWNSTREAM_RESPONSE_RECEIVED"),
        ("servicenow-consumer", "DOWNSTREAM_INTERACTION_PERSISTED"),
        ("servicenow-consumer", "EVENT_PROCESSING_COMPLETED"),
        ("customer-db-consumer", "KAFKA_CONSUMED"),
        ("customer-db-consumer", "CORRELATION_VALIDATED"),
        ("customer-db-consumer", "EVENT_VALIDATED"),
        ("customer-db-consumer", "SOURCE_VALIDATED"),
        ("customer-db-consumer", "PAYLOAD_TRANSFORMED"),
        ("customer-db-consumer", "DB_OPERATION_FAILED"),
    ]
    log.record(
        "get_transaction_timeline",
        {},
        ToolCallOutcome(
            True,
            {"timeline": [{"service": service, "event": event} for service, event in checkpoints]},
            None,
        ),
    )
    result = _make_result(log, outcome="FAILURE")
    text = render_report(result)

    assert "✗ customer-db-consumer database operation" in text
    assert "Failure boundary: customer-db-consumer -> customer-postgres" in text


def test_render_report_only_cites_real_evidence():
    log = EvidenceLog()
    ev = log.record("get_transaction_summary", {}, ToolCallOutcome(True, {"eventsObserved": 1}, None))
    result = _make_result(log, cited_evidence_ids=[ev.id])

    text = render_report(result)

    assert f"[{ev.id}]" in text
    assert "get_transaction_summary" in text


def test_render_report_with_no_evidence_says_so_plainly():
    log = EvidenceLog()
    result = _make_result(log, outcome="INCOMPLETE", interpretation="No evidence found.")

    text = render_report(result)

    assert "no checkpoints observed" in text
    assert "(no evidence cited)" in text
