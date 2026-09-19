from unittest.mock import MagicMock, patch

import pytest
from docker.errors import NotFound

from tracebridge_mcp.docker_repository import DockerRuntimeRepository
from tracebridge_mcp.errors import EvidenceSourceUnavailableError


def _repo_with_fake_client(fake_client):
    repo = DockerRuntimeRepository("tcp://docker-socket-proxy:2375")
    repo._client = fake_client  # bypass lazy construction for the test
    return repo


def test_running_container_reports_safe_state_fields():
    container = MagicMock()
    container.attrs = {
        "State": {
            "Status": "running",
            "Running": True,
            "StartedAt": "2026-01-01T00:00:00Z",
            "FinishedAt": "0001-01-01T00:00:00Z",
            "ExitCode": 0,
        }
    }
    client = MagicMock()
    client.containers.get.return_value = container
    repo = _repo_with_fake_client(client)

    result = repo.get_container_status("tracebridge-customer-postgres")

    assert result == {
        "exists": True,
        "running": True,
        "state": "running",
        "health": None,
        "startedAt": "2026-01-01T00:00:00Z",
        "finishedAt": "0001-01-01T00:00:00Z",
        "exitCode": 0,
    }


def test_stopped_container_reports_running_false():
    container = MagicMock()
    container.attrs = {
        "State": {
            "Status": "exited",
            "Running": False,
            "StartedAt": "2026-01-01T00:00:00Z",
            "FinishedAt": "2026-01-01T00:05:00Z",
            "ExitCode": 137,
        }
    }
    client = MagicMock()
    client.containers.get.return_value = container
    repo = _repo_with_fake_client(client)

    result = repo.get_container_status("tracebridge-customer-postgres")

    assert result["running"] is False
    assert result["state"] == "exited"
    assert result["exitCode"] == 137


def test_nonexistent_container_is_not_an_error():
    client = MagicMock()
    client.containers.get.side_effect = NotFound("no such container")
    repo = _repo_with_fake_client(client)

    result = repo.get_container_status("tracebridge-does-not-exist")

    assert result == {
        "exists": False,
        "running": False,
        "state": None,
        "health": None,
        "startedAt": None,
        "finishedAt": None,
        "exitCode": None,
    }


def test_docker_unavailable_raises_evidence_source_unavailable():
    client = MagicMock()
    client.containers.get.side_effect = ConnectionError("connection refused")
    repo = _repo_with_fake_client(client)

    with pytest.raises(EvidenceSourceUnavailableError):
        repo.get_container_status("tracebridge-customer-postgres")


def test_container_events_are_bounded_by_limit():
    client = MagicMock()
    client.containers.get.return_value = MagicMock()
    client.events.return_value = iter(
        [{"time": 1700000000 + i, "Action": "start", "Actor": {"Attributes": {}}} for i in range(20)]
    )
    repo = _repo_with_fake_client(client)

    result = repo.get_container_events("tracebridge-customer-postgres", since_minutes=1440, limit=5)

    assert len(result) == 5


def test_container_events_never_returns_actor_attributes_blob():
    client = MagicMock()
    client.containers.get.return_value = MagicMock()
    client.events.return_value = iter(
        [{"time": 1700000000, "Action": "die", "Actor": {"Attributes": {"exitCode": "1", "image": "postgres:16"}}}]
    )
    repo = _repo_with_fake_client(client)

    result = repo.get_container_events("tracebridge-customer-postgres", since_minutes=60, limit=10)

    assert result == [{"timestamp": "2023-11-14T22:13:20+00:00", "action": "die", "exitCode": "1"}]
    assert "image" not in result[0]


def test_container_events_for_nonexistent_container_is_empty_not_an_error():
    client = MagicMock()
    client.containers.get.side_effect = NotFound("no such container")
    repo = _repo_with_fake_client(client)

    result = repo.get_container_events("tracebridge-does-not-exist", since_minutes=60, limit=10)

    assert result == []


def test_repository_has_no_mutating_methods():
    forbidden = {"start", "stop", "restart", "kill", "remove", "exec_run", "create"}
    actual_methods = {name for name in dir(DockerRuntimeRepository) if not name.startswith("_")}
    assert actual_methods.isdisjoint(forbidden)
