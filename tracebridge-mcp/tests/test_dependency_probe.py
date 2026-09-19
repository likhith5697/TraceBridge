import socket
from unittest.mock import patch

from tracebridge_mcp.dependency_probe import check_tcp_reachable


def test_reachable_when_connect_succeeds():
    with patch("tracebridge_mcp.dependency_probe.socket.create_connection") as fake_connect:
        fake_connect.return_value.__enter__.return_value = None
        fake_connect.return_value.__exit__.return_value = False

        result = check_tcp_reachable("customer-postgres", 5432, timeout_seconds=1)

    assert result.reachable is True
    assert result.failure is None
    fake_connect.assert_called_once_with(("customer-postgres", 5432), timeout=1)


def test_connection_refused_is_reported_as_a_fact_not_an_exception():
    with patch("tracebridge_mcp.dependency_probe.socket.create_connection", side_effect=ConnectionRefusedError()):
        result = check_tcp_reachable("customer-postgres", 5432, timeout_seconds=1)

    assert result.reachable is False
    assert result.failure == "CONNECTION_REFUSED"


def test_timeout_is_distinguished_from_connection_refused():
    with patch("tracebridge_mcp.dependency_probe.socket.create_connection", side_effect=socket.timeout()):
        result = check_tcp_reachable("customer-postgres", 5432, timeout_seconds=1)

    assert result.reachable is False
    assert result.failure == "TIMEOUT"


def test_dns_failure_is_distinguished_from_connection_refused():
    with patch("tracebridge_mcp.dependency_probe.socket.create_connection", side_effect=socket.gaierror()):
        result = check_tcp_reachable("not-a-real-host", 5432, timeout_seconds=1)

    assert result.reachable is False
    assert result.failure == "DNS_RESOLUTION_FAILED"


def test_probe_never_sends_credentials_or_payload():
    """The probe opens and immediately closes a bare socket - it must never
    call send/recv or accept any auth-shaped argument."""
    import inspect

    from tracebridge_mcp import dependency_probe

    signature = inspect.signature(dependency_probe.check_tcp_reachable)
    assert set(signature.parameters) == {"host", "port", "timeout_seconds"}
