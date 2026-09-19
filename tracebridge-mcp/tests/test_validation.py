import pytest

from tracebridge_mcp.errors import InvalidToolInputError
from tracebridge_mcp.validation import (
    MAX_CONTAINER_EVENTS_LIMIT,
    MAX_LOOKBACK_MINUTES,
    validate_container_events_limit,
    validate_correlation_id,
    validate_dependency,
    validate_event,
    validate_limit,
    validate_lookback_minutes,
    validate_runtime_service,
    validate_service,
)


def test_accepts_real_uuid():
    assert validate_correlation_id("51d3c01d-2b02-45b3-9df4-697ecd19a796") == (
        "51d3c01d-2b02-45b3-9df4-697ecd19a796"
    )


def test_strips_surrounding_whitespace():
    assert validate_correlation_id("  51d3c01d-2b02-45b3-9df4-697ecd19a796  ") == (
        "51d3c01d-2b02-45b3-9df4-697ecd19a796"
    )


@pytest.mark.parametrize("value", ["", "   ", None, "not-a-uuid", "1=1", "'; DROP TABLE x; --"])
def test_rejects_invalid_correlation_id(value):
    with pytest.raises(InvalidToolInputError):
        validate_correlation_id(value)


def test_rejects_overlong_correlation_id():
    with pytest.raises(InvalidToolInputError):
        validate_correlation_id("a" * 200)


def test_limit_defaults_when_none():
    assert validate_limit(None, default=50, maximum=200) == 50


def test_limit_capped_at_maximum():
    assert validate_limit(500, default=50, maximum=200) == 200


@pytest.mark.parametrize("value", [0, -1, 1.5, "10", True])
def test_limit_rejects_invalid_values(value):
    with pytest.raises(InvalidToolInputError):
        validate_limit(value, default=50, maximum=200)


def test_lookback_minutes_defaults_and_caps():
    assert validate_lookback_minutes(None) == 60
    assert validate_lookback_minutes(999999) == MAX_LOOKBACK_MINUTES


@pytest.mark.parametrize("value", [0, -5, "60", True])
def test_lookback_minutes_rejects_invalid_values(value):
    with pytest.raises(InvalidToolInputError):
        validate_lookback_minutes(value)


def test_service_accepts_known_value():
    assert validate_service("servicenow-consumer") == "servicenow-consumer"


def test_service_rejects_unknown_value():
    with pytest.raises(InvalidToolInputError):
        validate_service("some-other-service")


def test_event_accepts_known_value():
    assert validate_event("DOWNSTREAM_REQUEST_FAILED") == "DOWNSTREAM_REQUEST_FAILED"


def test_event_rejects_unknown_value():
    with pytest.raises(InvalidToolInputError):
        validate_event("MADE_UP_EVENT")


def test_none_filters_pass_through_as_none():
    assert validate_service(None) is None
    assert validate_event(None) is None


def test_runtime_service_accepts_known_value():
    assert validate_runtime_service("customer-db-consumer") == "customer-db-consumer"


def test_runtime_service_accepts_infrastructure_dependency_as_a_service_too():
    # customer-postgres is both a dependency (of customer-db-consumer) and its
    # own inspectable runtime service - runtime status can be checked either way.
    assert validate_runtime_service("customer-postgres") == "customer-postgres"


@pytest.mark.parametrize("value", ["", "   ", None, "arbitrary-host.com", "not-a-real-service"])
def test_runtime_service_rejects_unknown_or_blank_value(value):
    with pytest.raises(InvalidToolInputError):
        validate_runtime_service(value)


def test_dependency_accepts_known_pair():
    assert validate_dependency("customer-db-consumer", "customer-postgres") == (
        "customer-db-consumer",
        "customer-postgres",
    )


def test_dependency_rejects_unknown_service():
    with pytest.raises(InvalidToolInputError):
        validate_dependency("not-a-real-service", "customer-postgres")


def test_dependency_rejects_unlisted_pair():
    """A known service and a known runtime target that are simply not
    documented as related must still be rejected - this is what stops the
    tool from becoming a generic network scanner."""
    with pytest.raises(InvalidToolInputError):
        validate_dependency("service-request-api", "customer-postgres")


def test_dependency_rejects_arbitrary_host():
    with pytest.raises(InvalidToolInputError):
        validate_dependency("customer-db-consumer", "arbitrary-host.com")


def test_container_events_limit_defaults_and_caps():
    assert validate_container_events_limit(None) == 10
    assert validate_container_events_limit(999) == MAX_CONTAINER_EVENTS_LIMIT
