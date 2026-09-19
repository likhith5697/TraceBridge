from unittest.mock import MagicMock, patch

import psycopg
import pytest

from tracebridge_mcp.errors import EvidenceSourceUnavailableError
from tracebridge_mcp.postgres_repository import PostgresEvidenceRepository


def _fake_connect_returning(rows: list[dict]):
    """Build a fake psycopg.connect() replacement returning a connection whose
    cursor().fetchall() yields `rows`, supporting the same context-manager usage
    the repository relies on."""
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False

    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False

    return MagicMock(return_value=conn)


def test_find_downstream_interactions_binds_correlation_id_as_a_parameter():
    fake_connect = _fake_connect_returning([])
    repo = PostgresEvidenceRepository("conninfo")

    with patch("tracebridge_mcp.postgres_repository.psycopg.connect", fake_connect):
        repo.find_downstream_interactions("cid-1")

    conn = fake_connect.return_value
    cursor = conn.cursor.return_value
    sql, params = cursor.execute.call_args.args
    assert params == ("cid-1",)
    assert "cid-1" not in sql  # never string-concatenated into the SQL text
    assert "%s" in sql


def test_find_downstream_interactions_orders_chronologically_in_sql():
    fake_connect = _fake_connect_returning([])
    repo = PostgresEvidenceRepository("conninfo")

    with patch("tracebridge_mcp.postgres_repository.psycopg.connect", fake_connect):
        repo.find_downstream_interactions("cid-1")

    sql = fake_connect.return_value.cursor.return_value.execute.call_args.args[0]
    assert "ORDER BY request_timestamp ASC" in sql
    assert "servicenow_consumer.downstream_interaction" in sql


def test_find_downstream_interactions_never_selects_payload_columns():
    fake_connect = _fake_connect_returning([])
    repo = PostgresEvidenceRepository("conninfo")

    with patch("tracebridge_mcp.postgres_repository.psycopg.connect", fake_connect):
        repo.find_downstream_interactions("cid-1")

    sql = fake_connect.return_value.cursor.return_value.execute.call_args.args[0]
    assert "request_payload" not in sql
    assert "response_payload" not in sql


def test_find_service_request_queries_public_schema():
    fake_connect = _fake_connect_returning([{"correlation_id": "cid-1", "source": "CUSTOMER_PORTAL"}])
    repo = PostgresEvidenceRepository("conninfo")

    with patch("tracebridge_mcp.postgres_repository.psycopg.connect", fake_connect):
        result = repo.find_service_request("cid-1")

    sql = fake_connect.return_value.cursor.return_value.execute.call_args.args[0]
    assert "public.service_request" in sql
    assert "short_description" in sql
    # the long free-text `description` column must never be selected, only `short_description`
    assert sql.count("description") == sql.count("short_description")
    assert result == {"correlation_id": "cid-1", "source": "CUSTOMER_PORTAL"}


def test_find_service_request_returns_none_when_not_found():
    fake_connect = _fake_connect_returning([])
    repo = PostgresEvidenceRepository("conninfo")

    with patch("tracebridge_mcp.postgres_repository.psycopg.connect", fake_connect):
        result = repo.find_service_request("cid-does-not-exist")

    assert result is None


def test_connection_is_marked_read_only():
    fake_connect = _fake_connect_returning([])
    repo = PostgresEvidenceRepository("conninfo")

    with patch("tracebridge_mcp.postgres_repository.psycopg.connect", fake_connect):
        repo.find_downstream_interactions("cid-1")

    conn = fake_connect.return_value
    assert conn.read_only is True


def test_operational_error_is_translated_to_evidence_source_unavailable():
    repo = PostgresEvidenceRepository("conninfo")

    with patch(
        "tracebridge_mcp.postgres_repository.psycopg.connect",
        side_effect=psycopg.OperationalError("connection refused"),
    ):
        with pytest.raises(EvidenceSourceUnavailableError):
            repo.find_downstream_interactions("cid-1")


def test_no_write_methods_exist_on_the_repository():
    forbidden = {"insert", "update", "delete", "execute_write", "upsert"}
    actual_methods = {name for name in dir(PostgresEvidenceRepository) if not name.startswith("_")}
    assert actual_methods.isdisjoint(forbidden)


def test_no_sql_statement_in_this_module_is_a_write():
    import re

    from tracebridge_mcp.postgres_repository import _DOWNSTREAM_INTERACTIONS_SQL, _SERVICE_REQUEST_SQL

    forbidden_keywords = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT")
    for sql in (_DOWNSTREAM_INTERACTIONS_SQL, _SERVICE_REQUEST_SQL):
        upper_sql = sql.upper()
        words = set(re.findall(r"[A-Z_]+", upper_sql))
        for keyword in forbidden_keywords:
            assert keyword not in words, f"found forbidden SQL keyword {keyword!r} in a query constant"
        assert upper_sql.strip().startswith("SELECT")
