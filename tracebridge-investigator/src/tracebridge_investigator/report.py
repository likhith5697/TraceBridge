"""Deterministic rendering of an InvestigationResult into the final report.

Two things are computed here, in code, never asked of the LLM:
  - the observed checkpoint path (from topology.py + actual evidence)
  - the confidence level (from which evidence sources actually confirmed
    something, per the rubric in the module docstring below)

This is what stops the model from claiming a checkpoint exists that was
never observed, and from picking an arbitrary-sounding confidence number.
"""

from tracebridge_investigator.evidence import extract_observed_events
from tracebridge_investigator.investigator import InvestigationResult
from tracebridge_investigator.topology import compute_observed_stages, failure_boundary_description, is_failure_result

_POSTGRES_TOOLS = {"get_downstream_interactions", "get_service_request"}
_OPENSEARCH_TOOLS = {"search_logs", "get_transaction_timeline", "get_recent_failures"}

# Phase 8: get_service_config_metadata (static catalog data) and
# get_container_events (supplementary lifecycle context) deliberately never
# influence confidence - neither one "confirms" anything about the specific
# transaction under investigation. Only two tools carry a live pass/fail
# signal about runtime reality: get_dependency_health (is the dependency
# reachable right now) and get_service_runtime_status (is its container
# running right now).


def compute_confidence(result: InvestigationResult) -> str:
    """Deterministic rubric - the LLM never assigns this itself.

    Baseline (unchanged from Phase 6): HIGH when independent evidence
    sources (OpenSearch and PostgreSQL) both confirmed something relevant
    about this transaction. MEDIUM when only one source did. LOW when
    neither did, or the investigation never reached a model conclusion.

    Phase 8 extension - runtime corroboration: a single log line saying
    "connection refused" is not, by itself, proof of *why* - so runtime
    evidence alone (just get_dependency_health, or just
    get_service_runtime_status) only ever contributes to MEDIUM, same as
    any other single source. It is upgraded to HIGH only when TWO
    independent, live runtime probes - a network reachability check and a
    container state inspection - agree the *same named dependency* is down,
    AND at least one of the baseline sources (log or DB evidence) already
    showed the failure existed. That is: three independent signals (what
    happened, is it reachable, is it running) about the same target, not
    merely three tool calls.
    """
    if result.stopped_reason != "submit_report":
        return "LOW"

    postgres_confirmed = False
    opensearch_confirmed = False
    unreachable_dependencies: set[str] = set()
    stopped_services: set[str] = set()

    for ev in result.evidence.all():
        if not ev.success or not isinstance(ev.content, dict):
            continue

        has_postgres_rows = bool(ev.content.get("downstreamInteractions") or ev.content.get("serviceRequest"))
        has_opensearch_hits = bool(ev.content.get("logs") or ev.content.get("timeline") or ev.content.get("failures"))

        if ev.tool_name in _POSTGRES_TOOLS and has_postgres_rows:
            postgres_confirmed = True
        elif ev.tool_name in _OPENSEARCH_TOOLS and has_opensearch_hits:
            opensearch_confirmed = True
        elif ev.tool_name == "get_transaction_summary":
            if ev.content.get("postgresAvailable") and ev.content.get("downstreamInteractions"):
                postgres_confirmed = True
            if ev.content.get("openSearchAvailable") and ev.content.get("eventsObserved", 0) > 0:
                opensearch_confirmed = True
        elif ev.tool_name == "get_dependency_health" and ev.content.get("reachable") is False:
            dependency = ev.content.get("dependency")
            if dependency:
                unreachable_dependencies.add(dependency)
        elif ev.tool_name == "get_service_runtime_status" and ev.content.get("running") is False:
            service = ev.content.get("service")
            if service:
                stopped_services.add(service)

    # A lone runtime probe is still just one source, same as a lone log or
    # DB hit - it counts toward MEDIUM on its own.
    runtime_probed = bool(unreachable_dependencies or stopped_services)
    # HIGH requires more: the SAME dependency name confirmed unreachable by a
    # live probe AND confirmed not-running by container inspection - two
    # independent runtime signals agreeing on one target, not just two tool
    # calls that happened to run.
    runtime_agreement = bool(unreachable_dependencies & stopped_services)

    if postgres_confirmed and opensearch_confirmed:
        return "HIGH"
    if runtime_agreement and (postgres_confirmed or opensearch_confirmed):
        return "HIGH"
    if postgres_confirmed or opensearch_confirmed or runtime_probed:
        return "MEDIUM"
    return "LOW"


def _render_observed_path(result: InvestigationResult) -> tuple[list[str], str | None]:
    observed_events = extract_observed_events(result.evidence)
    stage_results = compute_observed_stages(observed_events)

    lines: list[str] = []
    current_service: str | None = None
    next_expected: str | None = None

    for stage_result in stage_results:
        if not stage_result.observed:
            next_expected = f"{stage_result.stage.label} ({stage_result.stage.service})"
            break

        if stage_result.stage.service != current_service:
            if current_service is not None:
                lines.append("")
            lines.append(stage_result.stage.service)
            current_service = stage_result.stage.service

        mark = "✗" if is_failure_result(stage_result) else "✓"
        lines.append(f"  {mark} {stage_result.stage.label}")

        if is_failure_result(stage_result):
            break

    return lines, next_expected


def render_report(result: InvestigationResult) -> str:
    observed_events = extract_observed_events(result.evidence)
    stage_results = compute_observed_stages(observed_events)
    boundary = result.failure_boundary or failure_boundary_description(stage_results)
    confidence = compute_confidence(result)
    path_lines, next_expected = _render_observed_path(result)

    lines = [
        "Investigation",
        "-------------",
        f"Correlation ID: {result.correlation_id}",
        "",
        f"Outcome: {result.outcome}",
        "",
        "Observed path:",
    ]

    if path_lines:
        lines.extend(path_lines)
    else:
        lines.append("  (no checkpoints observed)")

    if next_expected:
        lines += ["", f"Next expected checkpoint: {next_expected}"]

    if boundary:
        lines += ["", f"Failure boundary: {boundary}"]

    lines += ["", "Interpretation:", result.interpretation or "(none provided)"]

    if result.recommended_investigation_area:
        lines += ["", "Recommended investigation area:", result.recommended_investigation_area]

    lines += ["", f"Confidence: {confidence}"]

    lines += ["", "Limitations:", result.limitations or "(none provided)"]

    lines += ["", "Evidence:"]
    if result.cited_evidence_ids:
        for evidence_id in result.cited_evidence_ids:
            evidence_item = result.evidence.get(evidence_id)
            if evidence_item is None:
                continue
            summary = evidence_item.content if evidence_item.success else f"ERROR: {evidence_item.error_message}"
            lines.append(f"  [{evidence_id}] {evidence_item.tool_name}({evidence_item.arguments}) -> {summary}")
    else:
        lines.append("  (no evidence cited)")

    lines += [
        "",
        f"Investigation stats: {result.iteration_count} iteration(s), {result.llm_call_count} LLM call(s), "
        f"{len(result.tool_call_log)} tool call(s), {result.duration_seconds:.2f}s",
    ]

    return "\n".join(lines)
