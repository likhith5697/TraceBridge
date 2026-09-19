"""The only place the Docker Engine API is called.

Every method here is a pure read: container inspect and container events.
There is no create/start/stop/restart/kill/remove/exec method anywhere in
this class - the same "cannot become a write path" guarantee
postgres_repository.py gives for SQL, given here by simply never having a
mutating method to call in the first place.

This talks to the Docker Engine API through docker-socket-proxy (see
docker-compose.yml), never directly to the host's docker.sock. That proxy is
itself configured to allow only GET requests against a small allowlist of
API categories (containers, events, info, ping) with POST/PUT/DELETE
disabled at the proxy globally - so even a bug in this file could not reach
a mutating Docker endpoint, because the proxy would refuse the request
before Docker ever saw it.

Only specific, allowlisted fields are ever extracted from a container's
`attrs` - never the whole blob, which would include `Config.Env` and could
therefore contain real secrets. See _container_status_from_attrs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import docker
from docker.errors import NotFound

from tracebridge_mcp.errors import EvidenceSourceUnavailableError


def _container_status_from_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    state = attrs.get("State") or {}
    health = (state.get("Health") or {}).get("Status")
    return {
        "exists": True,
        "running": bool(state.get("Running")),
        "state": state.get("Status"),
        "health": health,
        "startedAt": state.get("StartedAt"),
        "finishedAt": state.get("FinishedAt"),
        "exitCode": state.get("ExitCode"),
    }


_NOT_FOUND_STATUS: dict[str, Any] = {
    "exists": False,
    "running": False,
    "state": None,
    "health": None,
    "startedAt": None,
    "finishedAt": None,
    "exitCode": None,
}


class DockerRuntimeRepository:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._client: docker.DockerClient | None = None

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.DockerClient(base_url=self._base_url, timeout=self._timeout)
        return self._client

    def get_container_status(self, container_name: str) -> dict[str, Any]:
        try:
            container = self._get_client().containers.get(container_name)
        except NotFound:
            return dict(_NOT_FOUND_STATUS)
        except Exception as exc:
            raise EvidenceSourceUnavailableError(f"Docker runtime unavailable: {exc}") from exc

        return _container_status_from_attrs(container.attrs)

    def get_container_events(self, container_name: str, since_minutes: int, limit: int) -> list[dict[str, Any]]:
        try:
            client = self._get_client()
            try:
                client.containers.get(container_name)
            except NotFound:
                return []

            since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
            until = datetime.now(timezone.utc)
            # since/until bound this generator to a fixed historical window - it
            # yields what already happened and then stops, it never blocks
            # waiting for a future event.
            raw_events = list(
                client.events(since=since, until=until, filters={"container": container_name}, decode=True)
            )
        except Exception as exc:
            raise EvidenceSourceUnavailableError(f"Docker runtime unavailable: {exc}") from exc

        sanitized = [
            {
                "timestamp": _event_timestamp(event),
                "action": event.get("Action") or event.get("status"),
                "exitCode": ((event.get("Actor") or {}).get("Attributes") or {}).get("exitCode"),
            }
            for event in raw_events
        ]
        return sanitized[-limit:]


def _event_timestamp(event: dict[str, Any]) -> str | None:
    epoch_seconds = event.get("time")
    if epoch_seconds is None:
        return None
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()
