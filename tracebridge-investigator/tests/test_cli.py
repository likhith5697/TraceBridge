import pytest

from tracebridge_investigator.cli import resolve_correlation_id


def test_resolves_a_bare_correlation_id():
    assert resolve_correlation_id("51d3c01d-2b02-45b3-9df4-697ecd19a796") == "51d3c01d-2b02-45b3-9df4-697ecd19a796"


def test_resolves_a_correlation_id_inside_a_natural_language_request():
    text = "Investigate correlationId 06fc3488-bc83-47a4-a768-db3af8b5c161 please"
    assert resolve_correlation_id(text) == "06fc3488-bc83-47a4-a768-db3af8b5c161"


def test_rejects_text_with_no_correlation_id():
    with pytest.raises(SystemExit):
        resolve_correlation_id("investigate the thing that broke yesterday")
