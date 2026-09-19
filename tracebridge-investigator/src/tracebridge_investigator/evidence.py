"""Evidence bookkeeping: every MCP tool result becomes exactly one Evidence
record with a stable, sequential ID (E1, E2, ...). The final report's
citations are validated against these real IDs - the model cannot invent
E17 out of nowhere; report.py rejects any ID that was never issued here.

An identical repeated call (same tool, same arguments, same result) reuses
its existing ID instead of growing the evidence list - this keeps the
model from padding context with redundant re-fetches.
"""

import json
from dataclasses import dataclass
from typing import Any

from tracebridge_investigator.mcp_client import ToolCallOutcome


@dataclass(frozen=True)
class Evidence:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    content: Any
    success: bool
    error_message: str | None


class EvidenceLog:
    def __init__(self) -> None:
        self._items: list[Evidence] = []
        self._dedup_index: dict[str, str] = {}

    def record(self, tool_name: str, arguments: dict[str, Any], outcome: ToolCallOutcome) -> Evidence:
        dedup_key = self._dedup_key(tool_name, arguments, outcome)
        existing_id = self._dedup_index.get(dedup_key)
        if existing_id is not None:
            return self.get(existing_id)  # type: ignore[return-value]

        new_id = f"E{len(self._items) + 1}"
        item = Evidence(
            id=new_id,
            tool_name=tool_name,
            arguments=arguments,
            content=outcome.content,
            success=outcome.success,
            error_message=outcome.error_message,
        )
        self._items.append(item)
        self._dedup_index[dedup_key] = new_id
        return item

    def get(self, evidence_id: str) -> Evidence | None:
        return next((e for e in self._items if e.id == evidence_id), None)

    def all(self) -> list[Evidence]:
        return list(self._items)

    def valid_ids(self) -> set[str]:
        return {e.id for e in self._items}

    @staticmethod
    def _dedup_key(tool_name: str, arguments: dict[str, Any], outcome: ToolCallOutcome) -> str:
        return json.dumps(
            {
                "tool": tool_name,
                "args": arguments,
                "content": outcome.content,
                "success": outcome.success,
                "error": outcome.error_message,
            },
            sort_keys=True,
            default=str,
        )


def extract_observed_events(evidence_log: EvidenceLog) -> set[tuple[str, str]]:
    """Pull every (service, event) pair out of any log/timeline-shaped
    evidence collected so far - the only input topology.py needs."""
    observed: set[tuple[str, str]] = set()
    for item in evidence_log.all():
        if not item.success or not isinstance(item.content, dict):
            continue
        entries = item.content.get("logs") or item.content.get("timeline") or []
        for entry in entries:
            if isinstance(entry, dict) and entry.get("service") and entry.get("event"):
                observed.add((entry["service"], entry["event"]))
    return observed
