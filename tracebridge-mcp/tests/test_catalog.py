from tracebridge_mcp.catalog import DEPENDENCY_CATALOG, RUNTIME_SERVICE_CONTAINERS, dependencies_for

_FORBIDDEN_SUBSTRINGS = ("password", "passwd", "secret", "token", "authorization", "api_key", "apikey", "credential")


def test_every_runtime_service_maps_to_a_container_name():
    for service, container in RUNTIME_SERVICE_CONTAINERS.items():
        assert isinstance(container, str) and container.startswith("tracebridge-")


def test_dependency_catalog_pairs_reference_known_services():
    for service, dependency in DEPENDENCY_CATALOG:
        assert service in RUNTIME_SERVICE_CONTAINERS
        assert dependency in RUNTIME_SERVICE_CONTAINERS


def test_customer_db_consumer_depends_on_customer_postgres():
    info = DEPENDENCY_CATALOG[("customer-db-consumer", "customer-postgres")]
    assert info.type == "postgresql"
    assert info.host == "customer-postgres"
    assert info.port == 5432


def test_dependencies_for_unknown_service_is_empty_not_an_error():
    assert dependencies_for("not-a-real-service") == []


def test_dependencies_for_known_service_returns_only_safe_fields():
    deps = dependencies_for("customer-db-consumer")
    assert deps
    for dep in deps:
        assert set(dep.keys()) == {"name", "type", "host", "port"}


def test_catalog_never_contains_secret_like_values():
    """The whole point of a static catalog is that it cannot leak a real
    credential - there must be nothing secret-shaped in it to leak."""
    text = repr(RUNTIME_SERVICE_CONTAINERS) + repr(DEPENDENCY_CATALOG)
    lowered = text.lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in lowered
