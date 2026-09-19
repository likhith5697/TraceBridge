"""The only place SQL is written for this server.

Every statement here is a hardcoded, parameterized SELECT - correlation_id
is always bound as a query parameter, never string-formatted into SQL.
Every connection this repository opens is explicitly marked read_only,
which makes PostgreSQL itself reject any write statement at the session
level - a second, independent safeguard beyond "we simply never wrote one".

Production note: local development reuses the same tracebridge/tracebridge
role the Spring Boot services use, because that is what docker-compose.yml
already provisions. A real deployment of this server should be given a
dedicated database role with SELECT-only grants on these two tables -
session-level read_only helps, but a role that physically cannot write is
the actual production control.
"""

from typing import Any

import psycopg
from psycopg.rows import dict_row

from tracebridge_mcp.errors import EvidenceSourceUnavailableError

_DOWNSTREAM_INTERACTIONS_SQL = """
    SELECT correlation_id, target_system, operation, http_method, endpoint,
           request_timestamp, response_timestamp, http_status, status,
           error_code, error_message, duration_ms, attempt_number, created_at
    FROM servicenow_consumer.downstream_interaction
    WHERE correlation_id = %s
    ORDER BY request_timestamp ASC
"""

_SERVICE_REQUEST_SQL = """
    SELECT correlation_id, source, customer_id, category, subcategory,
           short_description, priority, status, created_at, updated_at
    FROM public.service_request
    WHERE correlation_id = %s
"""


class PostgresEvidenceRepository:
    def __init__(self, conninfo: str, timeout_seconds: float = 5.0):
        self._conninfo = conninfo
        self._timeout = timeout_seconds

    def find_downstream_interactions(self, correlation_id: str) -> list[dict[str, Any]]:
        return self._query(_DOWNSTREAM_INTERACTIONS_SQL, (correlation_id,))

    def find_service_request(self, correlation_id: str) -> dict[str, Any] | None:
        rows = self._query(_SERVICE_REQUEST_SQL, (correlation_id,))
        return rows[0] if rows else None

    def _query(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
        except psycopg.OperationalError as exc:
            raise EvidenceSourceUnavailableError(f"PostgreSQL unavailable: {exc}") from exc

    def _connect(self) -> psycopg.Connection:
        conn = psycopg.connect(
            self._conninfo,
            connect_timeout=max(1, int(self._timeout)),
            row_factory=dict_row,
            autocommit=True,
        )
        conn.read_only = True
        # SET does not accept bind parameters; the value is our own config (an int
        # cast below), never user input, so building this literal is not injectable.
        timeout_ms = int(self._timeout * 1000)
        conn.execute(f"SET statement_timeout = {timeout_ms}")
        return conn
