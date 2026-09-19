"""The only place OpenSearch query DSL is constructed.

Every method here queries exactly one fixed index pattern
(tracebridge-logs-*) and only ever issues searches - no index, update, or
delete call exists anywhere in this class. correlation_id/service/event
values are already validated by tracebridge_mcp.validation before they
reach here; they are placed into `term` filters as values, never
interpolated into a query string, so there is no query-injection surface.
"""

from typing import Any

from opensearchpy import OpenSearch
from opensearchpy.exceptions import OpenSearchException

from tracebridge_mcp.errors import EvidenceSourceUnavailableError

LOG_INDEX_PATTERN = "tracebridge-logs-*"


class OpenSearchEvidenceRepository:
    def __init__(self, client: OpenSearch, request_timeout_seconds: float = 5.0):
        self._client = client
        self._timeout = request_timeout_seconds

    def find_logs_by_correlation_id(
        self,
        correlation_id: str,
        service: str | None,
        event: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        filters: list[dict[str, Any]] = [{"term": {"correlationId": correlation_id}}]
        if service is not None:
            filters.append({"term": {"service": service}})
        if event is not None:
            filters.append({"term": {"event": event}})

        body = {
            "query": {"bool": {"filter": filters}},
            "size": limit,
            "sort": [{"@timestamp": "asc"}],
        }
        hits = self._search(body)
        return [hit["_source"] for hit in hits]

    def find_recent_failures(self, lookback_minutes: int, limit: int) -> list[dict[str, Any]]:
        body = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"status": "FAILED"}},
                        {"range": {"@timestamp": {"gte": f"now-{lookback_minutes}m"}}},
                    ]
                }
            },
            "size": limit,
            "sort": [{"@timestamp": "desc"}],
        }
        hits = self._search(body)
        return [hit["_source"] for hit in hits]

    def _search(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            response = self._client.search(
                index=LOG_INDEX_PATTERN,
                body=body,
                request_timeout=self._timeout,
            )
        except OpenSearchException as exc:
            raise EvidenceSourceUnavailableError(f"OpenSearch unavailable: {exc}") from exc
        return response["hits"]["hits"]
