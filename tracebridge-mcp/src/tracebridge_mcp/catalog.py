"""Static, hand-curated catalog of TraceBridge's own local runtime services
and their documented dependency relationships.

This is never read from a live container's actual environment - it is
hardcoded reference data, the same way topology.py in tracebridge-investigator
hardcodes the expected checkpoint sequence. That is what makes it safe by
construction: there is no code path here that could ever surface a real
credential, because no credential is ever read in the first place.

This is also the single allowlist that keeps the runtime tools from becoming
a generic infrastructure explorer - a service or dependency pair not listed
here is rejected before any Docker call or network probe is attempted.
"""

from dataclasses import dataclass

# Logical service name -> its docker-compose container name. Every name here
# is one get_service_runtime_status/get_container_events may inspect -
# anything else is rejected by validation before any Docker call is made.
RUNTIME_SERVICE_CONTAINERS: dict[str, str] = {
    "service-request-api": "tracebridge-service-request-api",
    "servicenow-consumer": "tracebridge-servicenow-consumer",
    "customer-db-consumer": "tracebridge-customer-db-consumer",
    "postgres": "tracebridge-postgres",
    "kafka": "tracebridge-kafka",
    "opensearch": "tracebridge-opensearch",
    "customer-postgres": "tracebridge-customer-postgres",
}


@dataclass(frozen=True)
class DependencyInfo:
    type: str
    host: str
    port: int


# Explicit (service, dependency) allowlist consulted by both
# get_service_config_metadata and get_dependency_health. A pair not listed
# here is rejected - this is what stops get_dependency_health from becoming
# a generic network scanner against an arbitrary host the model supplies.
DEPENDENCY_CATALOG: dict[tuple[str, str], DependencyInfo] = {
    ("service-request-api", "postgres"): DependencyInfo("postgresql", "postgres", 5432),
    ("service-request-api", "kafka"): DependencyInfo("kafka", "kafka", 9092),
    ("servicenow-consumer", "postgres"): DependencyInfo("postgresql", "postgres", 5432),
    ("servicenow-consumer", "kafka"): DependencyInfo("kafka", "kafka", 9092),
    ("customer-db-consumer", "kafka"): DependencyInfo("kafka", "kafka", 9092),
    ("customer-db-consumer", "customer-postgres"): DependencyInfo("postgresql", "customer-postgres", 5432),
}


def dependencies_for(service: str) -> list[dict[str, str | int]]:
    """Safe, static config metadata for one service: name/type/host/port only.

    Never a live read of the container's real environment variables, so no
    password, token, or other secret can ever appear in the result - there
    is simply no code path that reads one.
    """
    return [
        {"name": dependency, "type": info.type, "host": info.host, "port": info.port}
        for (svc, dependency), info in DEPENDENCY_CATALOG.items()
        if svc == service
    ]
