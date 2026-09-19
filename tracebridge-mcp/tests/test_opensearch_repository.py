from unittest.mock import MagicMock

import pytest
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError

from tracebridge_mcp.errors import EvidenceSourceUnavailableError
from tracebridge_mcp.opensearch_repository import LOG_INDEX_PATTERN, OpenSearchEvidenceRepository


def _client_returning(hits: list[dict]) -> MagicMock:
    client = MagicMock()
    client.search.return_value = {"hits": {"hits": hits}}
    return client


def test_find_logs_only_queries_the_fixed_index_pattern():
    client = _client_returning([])
    repo = OpenSearchEvidenceRepository(client)

    repo.find_logs_by_correlation_id("cid-1", None, None, 50)

    called_index = client.search.call_args.kwargs["index"]
    assert called_index == LOG_INDEX_PATTERN == "tracebridge-logs-*"


def test_find_logs_filters_by_correlation_id_as_a_term_not_a_string_query():
    client = _client_returning([])
    repo = OpenSearchEvidenceRepository(client)

    repo.find_logs_by_correlation_id("51d3c01d-2b02-45b3-9df4-697ecd19a796", None, None, 50)

    body = client.search.call_args.kwargs["body"]
    filters = body["query"]["bool"]["filter"]
    assert {"term": {"correlationId": "51d3c01d-2b02-45b3-9df4-697ecd19a796"}} in filters


def test_find_logs_adds_optional_service_and_event_filters_only_when_given():
    client = _client_returning([])
    repo = OpenSearchEvidenceRepository(client)

    repo.find_logs_by_correlation_id("cid-1", "servicenow-consumer", "KAFKA_CONSUMED", 50)

    filters = client.search.call_args.kwargs["body"]["query"]["bool"]["filter"]
    assert {"term": {"service": "servicenow-consumer"}} in filters
    assert {"term": {"event": "KAFKA_CONSUMED"}} in filters


def test_find_logs_sorts_ascending_by_timestamp():
    client = _client_returning([])
    repo = OpenSearchEvidenceRepository(client)

    repo.find_logs_by_correlation_id("cid-1", None, None, 50)

    body = client.search.call_args.kwargs["body"]
    assert body["sort"] == [{"@timestamp": "asc"}]


def test_find_logs_respects_limit_as_size():
    client = _client_returning([])
    repo = OpenSearchEvidenceRepository(client)

    repo.find_logs_by_correlation_id("cid-1", None, None, 17)

    assert client.search.call_args.kwargs["body"]["size"] == 17


def test_find_logs_returns_raw_source_documents():
    hits = [{"_source": {"event": "A"}}, {"_source": {"event": "B"}}]
    client = _client_returning(hits)
    repo = OpenSearchEvidenceRepository(client)

    result = repo.find_logs_by_correlation_id("cid-1", None, None, 50)

    assert result == [{"event": "A"}, {"event": "B"}]


def test_find_recent_failures_filters_status_failed_and_time_range():
    client = _client_returning([])
    repo = OpenSearchEvidenceRepository(client)

    repo.find_recent_failures(30, 20)

    body = client.search.call_args.kwargs["body"]
    filters = body["query"]["bool"]["filter"]
    assert {"term": {"status": "FAILED"}} in filters
    assert {"range": {"@timestamp": {"gte": "now-30m"}}} in filters
    assert body["sort"] == [{"@timestamp": "desc"}]


def test_opensearch_failure_is_translated_to_evidence_source_unavailable():
    client = MagicMock()
    client.search.side_effect = OpenSearchConnectionError("N/A", "connection refused", Exception("refused"))
    repo = OpenSearchEvidenceRepository(client)

    with pytest.raises(EvidenceSourceUnavailableError):
        repo.find_logs_by_correlation_id("cid-1", None, None, 50)


def test_no_write_methods_exist_on_the_repository():
    forbidden = {"index", "update", "delete", "bulk", "delete_by_query", "update_by_query"}
    actual_methods = {name for name in dir(OpenSearchEvidenceRepository) if not name.startswith("_")}
    assert actual_methods.isdisjoint(forbidden)
