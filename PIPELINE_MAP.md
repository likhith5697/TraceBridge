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

  **How a runtime tool call actually gets checked, step by step** (e.g. the
  LLM asks for `service="customer-postgres"`):
  1. `validation.py` → `validate_runtime_service()` — is `"customer-postgres"`
     one of the names `catalog.py` knows about at all? This checks the
     *plain-English service name* the LLM typed — not a real Docker
     container name, not a hostname. Unknown name → rejected immediately,
     nothing else runs.
  2. Only if it passed: `catalog.py` translates that name into the real
     Docker container name (`"tracebridge-customer-postgres"`) — this
     mapping is the only thing standing between "a name the LLM said" and
     "a real thing on the machine."
  3. *Now*, and only now, does the tool actually ask Docker about that
     container, or open a real network connection to it.

  Same two-step idea for `get_dependency_health`: `validate_dependency()`
  first checks that the exact `(service, dependency)` pair is one
  `catalog.py` explicitly lists as a real relationship (e.g.
  `customer-db-consumer` → `customer-postgres`) — a service asking about a
  dependency it doesn't actually have, or a made-up host, is rejected
  before any socket is opened. This is what stops the tool from becoming a
  generic "probe any address" function.
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
- **Idempotency**: Kafka only promises *at-least-once* delivery — a crash
  right before an offset commits, a rebalance, or a manual offset reset can
  redeliver the same message. Without a guard, that would call the real
  ServiceNow API a second time (a genuine duplicate incident) or write a
  second `customer_record` row. Both consumers now check "have I already
  processed this exact event?" (by `eventId`, a UUID generated once per
  event and never reused) *before* doing the real work — see each
  service's `V2__add_event_id_for_idempotency.sql`. A unique database
  index is the actual safety net (race-safe, enforced by Postgres itself);
  the check beforehand is what avoids the duplicate side effect in the
  normal case, not just a duplicate row. Verified live: stopped both
  consumers, rewound their Kafka offset by one, restarted them, and
  confirmed the redelivered message was logged as
  `DUPLICATE_EVENT_SKIPPED` and produced no second ServiceNow incident and
  no second database row.

  **Concretely, no new table — one new column on each existing table,**
  plus a uniqueness rule Postgres itself enforces:
  ```sql
  ALTER TABLE downstream_interaction ADD COLUMN event_id UUID;
  CREATE UNIQUE INDEX uq_downstream_interaction_event_id ON downstream_interaction (event_id);
  ```
  Real data from the live test above — one row, before and after the
  forced redelivery (not two):
  | correlation_id | event_id | http_status | status |
  |---|---|---|---|
  | `00ab2d24-...` | `05664fb2-7537-...` | 201 | SUCCESS |

  What each consumer does on every message, before touching ServiceNow or
  the database:
  ```
  1. Read the event -> eventId = 05664fb2-...
  2. Ask the table: does a row already exist with this event_id?
  3a. No  -> proceed normally (call ServiceNow / write the row)
  3b. Yes -> log DUPLICATE_EVENT_SKIPPED, stop here, touch nothing
  ```

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

## 11. Worked example — one real correlation ID, start to finish

Correlation ID `72391ab0-21fe-47d8-a7c0-cd8e55154de1` — a real transaction
run on this system while `customer-postgres` was intentionally stopped.
Every evidence value below is real output this system actually produced;
this walkthrough shows the full multi-round loop the design supports (the
LLM keeps calling tools and getting fed the results back until *it*
decides it has enough). Follow it top to bottom and you've seen every
stage in this document fire once.

```
You -> investigator: "Investigate correlationId 72391ab0-...-cd8e55154de1"
```

**Round 1**
```
investigator -> LLM:   system prompt + all 10 tool schemas + the request above
LLM -> investigator:   call get_transaction_summary(correlation_id=72391ab0-...)
investigator -> mcp:   runs it against OpenSearch + Postgres
mcp -> investigator:   eventsObserved=35, servicesObserved=[service-request-api,
                        servicenow-consumer, customer-db-consumer],
                        downstreamInteractions=[{targetSystem: SERVICENOW,
                        httpStatus: 201, status: SUCCESS}]
                        -> stored as evidence E1
```
The model now knows ServiceNow succeeded, but has no detail on what
`customer-db-consumer` actually did — just that it was "involved."

**Round 2** (evidence E1 is fed back into the conversation; LLM decides what's next)
```
LLM -> investigator:   call search_logs(correlation_id=72391ab0-...,
                        service="customer-db-consumer")
mcp -> investigator:   log lines including
                        {event: DB_OPERATION_FAILED, errorCode: DATABASE_ERROR,
                         message: "Customer record write failed: customer-postgres"}
                        -> stored as evidence E2
```
Now the model has a concrete failure, naming `customer-postgres` as the
target — but a log line alone doesn't prove the dependency is actually
down right now, or was ever really unreachable versus some other bug.

**Round 3**
```
LLM -> investigator:   call get_dependency_health(service="customer-db-consumer",
                        dependency="customer-postgres")
validation.py:         checks ("customer-db-consumer","customer-postgres") is a
                        real documented pair in catalog.py -> allowed
mcp -> investigator:   {reachable: false, failure: "DNS_RESOLUTION_FAILED"}
                        -> stored as evidence E3
```

**Round 4**
```
LLM -> investigator:   call get_service_runtime_status(service="customer-postgres")
validation.py:         checks "customer-postgres" is a known service -> allowed
catalog.py:            translates it to container name "tracebridge-customer-postgres"
mcp -> investigator:   {exists: true, running: false, state: "exited"}
                        -> stored as evidence E4
```
Three independent things now agree: the log says the write failed, a live
network probe says the dependency is unreachable, and Docker itself says
that exact container isn't running. Nothing left to check would change the
answer.

**Round 5 — the model concludes**
```
LLM -> investigator:   call submit_report(
                          outcome="FAILURE",
                          failure_boundary="customer-db-consumer -> customer-postgres",
                          interpretation="customer-postgres was unreachable and its
                            container was not running, causing the database write
                            to fail. ServiceNow processing succeeded independently.",
                          limitations="Evidence shows the dependency was unavailable,
                            not why the container stopped.",
                          cited_evidence_ids=["E1","E2","E3","E4"]
                        )
```

**What the code computes on top of that (never left to the model):**
- `topology.py` replays E1–E4 and builds the ✓/✗ checkpoint list — everything
  through `service-request-api` and `servicenow-consumer` shows ✓, then
  `customer-db-consumer` shows ✓ up to "Kafka consumed" and ✗ at "database
  operation."
- `report.py` computes confidence as **HIGH** — not because the model said
  so, but because the fixed rule was satisfied twice over here: the
  baseline rule (an OpenSearch source and a PostgreSQL source both
  confirmed something) *and* the Phase 8 rule (the live dependency probe
  and the live container check both named the same dependency,
  `customer-postgres`, as down).
- `evidence.py` confirms all four cited IDs are real (nothing invented) —
  they pass straight through unfiltered.

**What reaches the UI**, streamed live over SSE as it happens:
`started` → four `agent_decision`/`evidence` pairs (one per round above) →
`final` (the assembled report: outcome, confidence, checkpoint path,
interpretation, limitations, and the four evidence cards).

*Honesty note: this walkthrough shows the mechanism exactly as designed and
uses only real evidence values this system actually produced. A live run I
performed against this same correlation ID stopped after round 1 and
reached the wrong conclusion (SUCCESS) — a real, useful finding about when
the model settles for too little evidence, not a flaw in the flow shown
above.*
