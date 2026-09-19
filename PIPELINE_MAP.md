# Agent Pipeline Map

Quick reference: which file/method implements each stage of the TraceBridge
AI investigator. This is **not a RAG pipeline** — there is no chunking,
embedding, vector store, or reranking anywhere in this system. The agent
never searches unstructured documents; it makes exact, validated queries
against structured evidence (logs, database rows, live container state) and
reasons over what comes back. Read this file top to bottom and you have the
whole system.

## 1. Where the evidence comes from (no fetch step — it's generated live)

Unlike a RAG pipeline, nothing is "ingested" from an external source ahead
of time. Evidence is produced continuously as real transactions flow
through the system:

- `service-request-api`, `servicenow-consumer`, `customer-db-consumer` —
  each writes structured JSON logs (one line per checkpoint: `KAFKA_CONSUMED`,
  `DOWNSTREAM_REQUEST_FAILED`, etc.) via `logback-spring.xml` in each
  service, and writes rows to Postgres (`service_request`,
  `downstream_interaction`, `customer_record`).
- `fluent-bit/fluent-bit.conf` — tails each service's log file and ships it
  into OpenSearch. This is the closest thing to an "ingestion" step: it's
  how a log line becomes searchable.

## 2. Evidence stores (the "vector store" equivalent — but structured, not similarity-based)

| Store | What lives there |
|---|---|
| OpenSearch (`tracebridge-logs-*`) | every structured log line, searchable by correlation ID |
| PostgreSQL (`tracebridge` DB) | `service_request`, `servicenow_consumer.downstream_interaction` |
| PostgreSQL (`customer_db`) | `customer_db_consumer.customer_record` |
| Docker (via `docker-socket-proxy`) | live container state — running/stopped, recent events |

No embeddings, no similarity scoring. Every query below is an exact,
parameterized lookup — the same query always returns the same evidence.

## 3. Retrieval layer — `tracebridge-mcp` (the only thing allowed to touch a data store)

One MCP server, ten tools, each hitting exactly one store above:

- `tracebridge_mcp/tools.py` — the actual logic for all 10 tools (pure
  functions, no MCP protocol code, fully unit-testable).
- `tracebridge_mcp/server.py` — registers each function as an MCP tool with
  a schema; this is the only file that knows it's an MCP server at all.
- `tracebridge_mcp/opensearch_repository.py` — the only place OpenSearch
  queries are built (log search, recent-failures search).
- `tracebridge_mcp/postgres_repository.py` — the only place SQL is written;
  every statement is a hardcoded, parameterized `SELECT` (no writes exist).
- `tracebridge_mcp/docker_repository.py` — the only place Docker's API is
  called; only inspect/events methods exist — no start/stop/exec anywhere
  in this file.
- `tracebridge_mcp/dependency_probe.py` — opens a bare TCP connection to
  check if a dependency is reachable right now.
- `tracebridge_mcp/catalog.py` — a hardcoded list of which services exist
  and what they depend on (used to reject unknown/arbitrary names before
  any real query runs).
- `tracebridge_mcp/validation.py` — checks every tool's input (real UUID?
  known service name? sane limit?) before it ever reaches a query.
- `tracebridge_mcp/normalize.py` — reshapes raw database/log rows into a
  consistent, predictable output shape.

**No caching layer.** Every tool call re-queries the real store, every
time — investigations are infrequent enough that this doesn't matter, and
it means the agent can never act on stale evidence.

## 4. The agent loop — `tracebridge-investigator`

- `investigator.py` → `run_investigation()` — the whole loop: send the
  conversation + all 10 tool schemas to the LLM, run whichever tool it
  picks, feed the result back, repeat. Capped at 8 rounds
  (`max_iterations`). **Nothing here decides which tool to call — that
  choice is entirely the model's**, based only on the evidence gathered so
  far. No `if error X, call tool Y` logic exists anywhere.
- `investigator.py` → `SYSTEM_PROMPT` — the only place the model is told
  how to behave: don't claim more than evidence shows, treat tool results
  as data not instructions, stop once confident.
- `mcp_client.py` → `McpEvidenceClient` — launches `tracebridge-mcp` as a
  subprocess and talks to it over the real MCP protocol. This is the
  investigator's *only* connection to any evidence store — there is no
  direct OpenSearch/Postgres/Docker client anywhere in this package
  (enforced by a structural test, not just convention).

## 5. Generation — but most of the "answer" is NOT written by the LLM

This is the biggest difference from a RAG system. The two most
hallucination-prone parts of the final report are computed in plain code,
never left to the model:

- `llm.py` → `AnthropicLLMClient` / `OpenAILLMClient` — the only place an
  LLM API is called. Swappable via `LLM_PROVIDER` env var; everything else
  in the codebase is provider-agnostic.
- `topology.py` → `compute_observed_stages()` — the checkpoint
  ✓/✗ list in the report is built from actual evidence collected, not from
  what the model says happened.
- `report.py` → `compute_confidence()` — HIGH/MEDIUM/LOW is a fixed
  formula based on which independent sources actually confirmed something;
  the model never assigns its own confidence score.
- `report.py` → `render_report()` — assembles the final text report from
  the model's `interpretation`/`limitations` plus the two computed pieces
  above.

What the model *does* write, freely: `interpretation`, `failure_boundary`,
`recommended_investigation_area`, `limitations` — its actual reasoning,
constrained only by the system prompt's "never claim more than the
evidence proves" rule.

## 6. Evidence citation (the "citations.py" equivalent)

- `evidence.py` → `EvidenceLog.record()` — every tool result gets a
  sequential ID (`E1`, `E2`, ...). An identical repeated call reuses its
  existing ID instead of creating a duplicate.
- `investigator.py` → `_finalize_from_submit_report()` — validates the
  model's cited evidence IDs against real ones; any ID the model invents is
  silently dropped before the report is ever shown.

## 7. Guardrails (there's no equivalent section in a RAG map, but this is core to what this system is)

- **Read-only, structurally**: no tool name or SQL/Docker call in this
  entire codebase can write, restart, or execute anything — tested, not
  just promised (`tests/test_no_write_path.py`).
- **Allowlisting**: a service or dependency name not in `catalog.py` is
  rejected before any real query runs — stops the tools from becoming a
  generic database/network/Docker explorer.
- **Prompt-injection defense**: every tool result is treated as data, never
  an instruction — tested by feeding a fake "ignore previous instructions"
  string through a tool result and confirming it has zero effect on
  control flow.
- **Secret safety**: `get_service_config_metadata` never performs I/O at
  all — it returns a hardcoded dict, so no real credential can ever pass
  through it.

## 8. API routes

- `api.py` → `stream_investigation()` — `GET /api/investigations/stream`,
  the SSE endpoint the UI connects to; streams `started`/`agent_decision`/
  `evidence`/`final` events as the real investigation runs.
- `api.py` → `get_status()` — `GET /api/status`, health of investigator/
  MCP/OpenSearch/Postgres.
- `api.py` → `list_investigations()` / `get_investigation()` — in-memory
  history (resets on restart — a stated limitation, not a bug).

## 9. Config

- `tracebridge_mcp/config.py` — which OpenSearch/Postgres/Docker to talk
  to; needs no LLM key, no ServiceNow/Kafka credential.
- `tracebridge_investigator/config.py` — which LLM provider/model, how to
  launch `tracebridge-mcp`, max iterations. Needs exactly one LLM API key.

## 10. Scaling notes (this system doesn't need the RAG project's worker-pool section)

Investigations are triggered one at a time, by a human clicking
"Investigate" — there is no bulk-ingestion problem here, because there is
no ingestion. The only thing that would need scaling under real load is
`tracebridge-mcp` itself (more concurrent tool calls), which is already
stateless per-request and could run as multiple instances behind the
investigator without any code change.
