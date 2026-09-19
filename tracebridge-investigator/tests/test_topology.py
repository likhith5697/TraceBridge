from tracebridge_investigator.topology import (
    compute_observed_stages,
    failure_boundary_description,
    first_gap,
    is_failure_result,
)

_HAPPY_PATH_UP_TO_KAFKA_PUBLISHED = {
    ("service-request-api", "SERVICE_REQUEST_RECEIVED"),
    ("service-request-api", "DATABASE_PERSISTED"),
    ("service-request-api", "OUTBOX_EVENT_QUEUED"),
    ("service-request-api", "KAFKA_PUBLISH_STARTED"),
}

_FULL_SUCCESS = _HAPPY_PATH_UP_TO_KAFKA_PUBLISHED | {
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
    # Phase 8: customer-db-consumer consumes the same Kafka event independently
    # and must also complete for the transaction to be a *full* success now.
    ("customer-db-consumer", "KAFKA_CONSUMED"),
    ("customer-db-consumer", "CORRELATION_VALIDATED"),
    ("customer-db-consumer", "EVENT_VALIDATED"),
    ("customer-db-consumer", "SOURCE_VALIDATED"),
    ("customer-db-consumer", "PAYLOAD_TRANSFORMED"),
    ("customer-db-consumer", "DB_OPERATION_SUCCEEDED"),
    ("customer-db-consumer", "CUSTOMER_RECORD_PERSISTED"),
    ("customer-db-consumer", "EVENT_PROCESSING_COMPLETED"),
}

_FULL_401_FAILURE = _FULL_SUCCESS - {("servicenow-consumer", "DOWNSTREAM_RESPONSE_RECEIVED")} | {
    ("servicenow-consumer", "DOWNSTREAM_REQUEST_FAILED")
}


def test_full_success_has_no_gap_and_no_boundary():
    results = compute_observed_stages(_FULL_SUCCESS)

    assert first_gap(results) is None
    assert failure_boundary_description(results) is None
    assert not any(is_failure_result(r) for r in results)


def test_full_401_failure_marks_the_downstream_stage_as_a_failure():
    results = compute_observed_stages(_FULL_401_FAILURE)

    failed = [r for r in results if is_failure_result(r)]
    assert len(failed) == 1
    assert failed[0].matched_event == "DOWNSTREAM_REQUEST_FAILED"
    assert failure_boundary_description(results) == "servicenow-consumer -> ServiceNow"


def test_partial_evidence_reports_kafka_publish_gap():
    results = compute_observed_stages(_HAPPY_PATH_UP_TO_KAFKA_PUBLISHED)

    gap = first_gap(results)
    assert gap is not None
    assert gap.stage.label == "Kafka published"
    assert failure_boundary_description(results) == "service-request-api -> Kafka"


def test_outbox_queued_but_not_yet_published_is_a_gap_not_a_failure():
    """A perfectly normal, expected transient state under the outbox
    pattern: the row committed with the business write, but the poller
    hasn't run yet. This must show as "not yet reached", never as a
    failure - there's nothing wrong here."""
    results = compute_observed_stages(
        {
            ("service-request-api", "SERVICE_REQUEST_RECEIVED"),
            ("service-request-api", "DATABASE_PERSISTED"),
            ("service-request-api", "OUTBOX_EVENT_QUEUED"),
        }
    )

    gap = first_gap(results)
    assert gap is not None
    assert gap.stage.label == "Kafka publish attempted"
    assert not any(is_failure_result(r) for r in results)


def test_no_evidence_at_all_has_a_gap_but_no_boundary():
    results = compute_observed_stages(set())

    assert first_gap(results) is not None
    assert failure_boundary_description(results) is None


def test_unrelated_events_do_not_satisfy_stages():
    results = compute_observed_stages({("service-request-api", "REQUEST_VALIDATION_FAILED")})

    assert not any(r.observed for r in results)


_CUSTOMER_DB_CONSUMER_CONNECTION_FAILURE = _FULL_SUCCESS - {
    ("customer-db-consumer", "DB_OPERATION_SUCCEEDED"),
    ("customer-db-consumer", "CUSTOMER_RECORD_PERSISTED"),
    ("customer-db-consumer", "EVENT_PROCESSING_COMPLETED"),
} | {("customer-db-consumer", "DB_OPERATION_FAILED")}


def test_customer_db_consumer_failure_marks_its_own_stage_and_boundary():
    results = compute_observed_stages(_CUSTOMER_DB_CONSUMER_CONNECTION_FAILURE)

    failed = [r for r in results if is_failure_result(r)]
    assert len(failed) == 1
    assert failed[0].matched_event == "DB_OPERATION_FAILED"
    assert failure_boundary_description(results) == "customer-db-consumer -> customer-postgres"


def test_servicenow_and_customer_db_consumer_stage_labels_never_collide():
    """The React flow diagram keys milestone status by label text alone
    (see TransactionFlow.tsx) - if any two stages shared a label, one
    consumer's status would silently overwrite the other's in the UI."""
    from tracebridge_investigator.topology import STAGES

    labels = [stage.label for stage in STAGES]
    assert len(labels) == len(set(labels))
