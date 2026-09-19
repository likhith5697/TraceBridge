"""Environment-based configuration.

Local defaults match docker-compose.yml exactly. No credential has a
production-looking default - these are the same tracebridge/tracebridge
local dev values already used by service-request-api and servicenow-consumer.

This server never receives ServiceNow or Kafka credentials - it has no
need for them and is never given them. Docker access needs no credential
either: docker_base_url points at docker-socket-proxy (see
docker-compose.yml), an unauthenticated but read-only-by-configuration
gateway onto the real Docker socket.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    opensearch_url: str
    opensearch_timeout_seconds: float

    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_timeout_seconds: float

    docker_base_url: str
    docker_timeout_seconds: float
    dependency_probe_timeout_seconds: float

    @property
    def postgres_conninfo(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password}"
        )


def load_config() -> Config:
    return Config(
        opensearch_url=os.environ.get("OPENSEARCH_URL", "http://localhost:9200"),
        opensearch_timeout_seconds=float(os.environ.get("OPENSEARCH_TIMEOUT_SECONDS", "5")),
        postgres_host=os.environ.get("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.environ.get("POSTGRES_PORT", "5432")),
        postgres_db=os.environ.get("POSTGRES_DB", "tracebridge"),
        postgres_user=os.environ.get("POSTGRES_USER", "tracebridge"),
        postgres_password=os.environ.get("POSTGRES_PASSWORD", "tracebridge"),
        postgres_timeout_seconds=float(os.environ.get("POSTGRES_TIMEOUT_SECONDS", "5")),
        docker_base_url=os.environ.get("DOCKER_HOST", "tcp://docker-socket-proxy:2375"),
        docker_timeout_seconds=float(os.environ.get("DOCKER_TIMEOUT_SECONDS", "5")),
        dependency_probe_timeout_seconds=float(os.environ.get("DEPENDENCY_PROBE_TIMEOUT_SECONDS", "2")),
    )
