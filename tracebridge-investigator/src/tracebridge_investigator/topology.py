"""The expected TraceBridge checkpoint sequence, and nothing about any
specific transaction's outcome.

This is deterministic code, not something the LLM is asked to know or
recall - the "observed path" checklist in the final report is computed
here from the actual evidence collected, so the model cannot claim a
checkpoint exists that was never observed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    service: str
    # More than one event name because a single topology "slot" can resolve
    # two ways - e.g. the downstream call either succeeds or fails, and both
    # are equally valid observed outcomes for that stage.
    events: tuple[str, ...]
    label: str
    # Which of `events`, if matched, represents a failure outcome for this
    # stage rather than a plain pass-through checkpoint - rendered as a
    # failure mark, not treated as "not reached".
    failure_events: tuple[str, ...] = ()
    # Set only on a stage whose absence means "evidence stops before reaching
    # this external system" - drives the failure-boundary description.
    external_system: str | None = None


STAGES: tuple[Stage, ...] = (
    Stage("service-request-api", ("SERVICE_REQUEST_RECEIVED",), "request received"),
    Stage("service-request-api", ("DATABASE_PERSISTED",), "database persisted"),
    # Outbox pattern: this and the DB row above commit in one transaction,
    # so this checkpoint is now the true "durably safe to lose the process"
    # point - the actual Kafka publish below happens later, on the
    # OutboxPublisher poller's own schedule, not inline with the request.
    Stage("service-request-api", ("OUTBOX_EVENT_QUEUED",), "outbox event queued"),
    Stage("service-request-api", ("KAFKA_PUBLISH_STARTED",), "Kafka publish attempted"),
    Stage("service-request-api", ("KAFKA_PUBLISHED",), "Kafka published", external_system="Kafka"),
    Stage("servicenow-consumer", ("KAFKA_CONSUMED",), "Kafka consumed"),
    Stage("servicenow-consumer", ("CORRELATION_VALIDATED",), "correlation validated"),
    Stage("servicenow-consumer", ("EVENT_VALIDATED",), "event validated"),
    Stage("servicenow-consumer", ("SOURCE_VALIDATED",), "source validated"),
    Stage("servicenow-consumer", ("PAYLOAD_TRANSFORMED",), "payload transformed"),
    Stage("servicenow-consumer", ("DOWNSTREAM_REQUEST_STARTED",), "downstream request started"),
    Stage(
        "servicenow-consumer",
        ("DOWNSTREAM_RESPONSE_RECEIVED", "DOWNSTREAM_REQUEST_FAILED"),
        "downstream request",
        failure_events=("DOWNSTREAM_REQUEST_FAILED",),
        external_system="ServiceNow",
    ),
    Stage("servicenow-consumer", ("DOWNSTREAM_INTERACTION_PERSISTED",), "downstream interaction persisted"),
    Stage("servicenow-consumer", ("EVENT_PROCESSING_COMPLETED",), "event processing completed"),
    # customer-db-consumer (Phase 8) consumes the same Kafka topic independently
    # of servicenow-consumer - both are downstream of KAFKA_PUBLISHED, not of
    # each other. Labels here are deliberately prefixed/distinct from every
    # servicenow-consumer label above: the React flow diagram keys its
    # milestone boxes by label text alone (see TransactionFlow.tsx), so a
    # collision would make one consumer's status silently overwrite the
    # other's in the UI.
    Stage("customer-db-consumer", ("KAFKA_CONSUMED",), "customer-db-consumer Kafka consumed"),
    Stage("customer-db-consumer", ("CORRELATION_VALIDATED",), "customer-db-consumer correlation validated"),
    Stage("customer-db-consumer", ("EVENT_VALIDATED",), "customer-db-consumer event validated"),
    Stage("customer-db-consumer", ("SOURCE_VALIDATED",), "customer-db-consumer source validated"),
    Stage("customer-db-consumer", ("PAYLOAD_TRANSFORMED",), "customer-db-consumer payload mapped"),
    Stage(
        "customer-db-consumer",
        ("DB_OPERATION_SUCCEEDED", "DB_OPERATION_FAILED"),
        "customer-db-consumer database operation",
        failure_events=("DB_OPERATION_FAILED",),
        external_system="customer-postgres",
    ),
    Stage("customer-db-consumer", ("CUSTOMER_RECORD_PERSISTED",), "customer-db-consumer record persisted"),
    Stage("customer-db-consumer", ("EVENT_PROCESSING_COMPLETED",), "customer-db-consumer processing completed"),
)


@dataclass(frozen=True)
class StageResult:
    stage: Stage
    observed: bool
    matched_event: str | None


def compute_observed_stages(observed_events: set[tuple[str, str]]) -> list[StageResult]:
    """observed_events is a set of (service, event) pairs actually seen in evidence."""
    results = []
    for stage in STAGES:
        matched = next((event for event in stage.events if (stage.service, event) in observed_events), None)
        results.append(StageResult(stage=stage, observed=matched is not None, matched_event=matched))
    return results


def first_gap(stage_results: list[StageResult]) -> StageResult | None:
    return next((r for r in stage_results if not r.observed), None)


def is_failure_result(result: StageResult) -> bool:
    return result.observed and result.matched_event in result.stage.failure_events


def failure_boundary_description(stage_results: list[StageResult]) -> str | None:
    """A deterministic boundary description, or None if there is nothing to
    describe (transaction fully succeeded, or nothing at all was observed)."""
    failed = next((r for r in stage_results if is_failure_result(r)), None)
    if failed is not None:
        target = failed.stage.external_system or failed.stage.service
        return f"{failed.stage.service} -> {target}"

    gap = first_gap(stage_results)
    if gap is None:
        return None

    observed_so_far = [r for r in stage_results if r.observed]
    if not observed_so_far:
        return None

    last = observed_so_far[-1]
    target = gap.stage.external_system or gap.stage.service
    if last.stage.service == target:
        return None
    return f"{last.stage.service} -> {target}"
