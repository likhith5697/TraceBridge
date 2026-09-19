"""Error types.

These are deliberately distinguished so a caller can tell "the evidence
source was unreachable" apart from "the evidence source answered and there
was nothing there" - those are not the same fact.
"""


class InvalidToolInputError(ValueError):
    """Tool arguments failed validation before any query was issued."""


class EvidenceSourceUnavailableError(RuntimeError):
    """OpenSearch or PostgreSQL could not be reached or timed out."""
