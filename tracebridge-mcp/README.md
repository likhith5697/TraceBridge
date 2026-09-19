# tracebridge-mcp

A read-only [MCP](https://modelcontextprotocol.io) server exposing TraceBridge's
existing observability evidence (OpenSearch structured logs and PostgreSQL
`downstream_interaction` / `service_request` tables) as a fixed set of
narrow, typed tools.

**This component has no AI in it.** It receives a tool call, validates the
arguments, runs one predetermined query against one evidence source,
normalizes the result, and returns it. Nothing here reasons about *why*
something happened - that is deliberately left for a future phase.

## What MCP actually is, in this project

MCP (Model Context Protocol) is a protocol for exposing capabilities to a
*client* - which could be a human-driven test tool, or later an LLM - in a
structured, discoverable way, instead of that client having to know your
internal REST API or database schema.

This project only uses one MCP primitive:

- **Tool** - a named, schema-validated function the client can call
  (`search_logs`, `get_transaction_timeline`, etc.). This is the *only*
  primitive tracebridge-mcp uses.
- **Resource** - MCP's other primitive, for exposing readable data by URI
  (like a virtual filesystem). **Not used here** - our tools already
  return everything a caller needs, and resources would add a second way
  to reach the same evidence for no benefit.
- **Prompt** - MCP's third primitive, a reusable prompt template a client
  can ask the server for. **Not used here** - there is no LLM in this
  phase to prompt.
- **Transport** - how the client and server exchange MCP protocol
  messages. We use **stdio**: the client launches this server as a
  subprocess and talks over its stdin/stdout. See below for why.
- **MCP server** - this project, `tracebridge-mcp`.
- **MCP client** - anything that speaks the protocol to us: the scripted
  `manual_client.py` in this repo, the official MCP Inspector, or (in a
  later phase) an LLM agent.

### MCP tool vs. a REST endpoint vs. direct SQL vs. an LLM function call

| | Who defines the shape | Who can call it | What it can express |
|---|---|---|---|
| Direct SQL | nobody - any string is valid | anyone with a DB connection | *anything*, including writes |
| REST endpoint | the API author, informally (docs, maybe OpenAPI) | anyone with HTTP access | whatever the handler does |
| MCP tool | the server, as a formal JSON Schema the client can introspect *before* calling | any MCP client, human or AI | exactly what the schema allows - nothing else |
| LLM "function calling" | usually the same JSON Schema as an MCP tool | the model, inside a chat/agent loop | whatever the model decides to call, with whatever arguments it generates |

The important distinction for this phase: an MCP tool and an LLM function
call use the *same schema mechanism*, but right now nothing is generating
arguments except a human or a deterministic script. That is exactly why
Phase 5 is safe to build before Phase 6 exists - the tools are real and
callable today, with zero AI in the loop, and later an LLM can call the
*exact same* tools through the *exact same* protocol without a single line
of this server changing.

### The complete call path

```
Manual MCP client (manual_client.py, or MCP Inspector)
        |
        v   stdio (subprocess stdin/stdout)
tracebridge-mcp  (server.py registers 10 tools)
        |
        +--> OpenSearchEvidenceRepository --> OpenSearch (tracebridge-logs-*)
        |
        +--> PostgresEvidenceRepository  --> PostgreSQL (service_request, downstream_interaction)
        |
        +--> DockerRuntimeRepository     --> docker-socket-proxy --> Docker Engine (GET-only)
        |
        +--> dependency_probe            --> a bare TCP connect to a known (host, port)
        |
        v
normalize.py (shape raw evidence into bounded, predictable fields)
        |
        v
structured JSON result (both a pretty-printed text block and, for a
programmatic caller, a proper `structured_content` dict)
```

## Why Python, and why this SDK

Chosen over Java specifically because the official Python MCP SDK's
`MCPServer` (the current name - it was called `FastMCP` in SDK v1, renamed
in v2) gives decorator-based tools with JSON Schema generated straight
from Python type hints, with the smallest amount of ceremony of any
current official SDK. `opensearch-py` and `psycopg` are both minimal,
mature clients, keeping this whole server small. Using a different
language than the Spring Boot services also makes the "no shared code, no
imported Java classes" boundary physically true, not just a rule we
promise to follow.

## Why stdio, not HTTP

The MCP client launches this server as a local subprocess and talks over
its stdin/stdout. That's exactly how the MCP Inspector, Claude Desktop,
and Claude Code all expect to talk to a local tool server, and it needs no
networking, TLS, or auth setup - appropriate for a single-user local
investigation tool. Streamable HTTP would only be worth adopting if a
*remote* client needed to reach this server over a network, which is not
this project's situation.

## Read-only, by more than convention

- Every SQL statement is a hardcoded, parameterized `SELECT` -
  `correlation_id` is always a bound query parameter, never
  string-interpolated. See `postgres_repository.py`.
- Every PostgreSQL connection this server opens is explicitly marked
  `read_only`, which makes PostgreSQL itself reject a write statement at
  the session level - a real, enforced safeguard, not just a code review
  rule.
- Every OpenSearch call is a `search` - no `index`, `update`, `delete`, or
  `bulk` call exists anywhere in this codebase. `tests/test_no_write_path.py`
  asserts this structurally, and also asserts no tool exposes a
  `sql`/`query`/`dsl`/`command` style parameter that could smuggle in
  arbitrary access.
- **Production note**: local development reuses the same
  `tracebridge`/`tracebridge` role the Spring Boot services use, because
  that's what `docker-compose.yml` already provisions and this is a local
  learning project. A real deployment should give this server a dedicated
  PostgreSQL role with `SELECT`-only grants on `service_request` and
  `downstream_interaction` - a role that *cannot* write is the actual
  production control; `read_only` on the connection is a second layer on
  top of that, not a replacement for it.

## Evidence vs. reasoning

Every tool returns **observations**: `{"event": "DOWNSTREAM_REQUEST_FAILED",
"httpStatus": 401, "errorCode": "UNAUTHORIZED"}`. No tool ever returns a
statement like `{"rootCause": "ServiceNow password is wrong"}` - that
would be reasoning over the evidence, which is explicitly out of scope
until a future phase gives an LLM these same tools. `tests/test_tools.py`
includes a test that scans every tool's output shape for diagnosis-looking
keys (`rootCause`, `diagnosis`, `recommendation`, ...) and fails if one
ever appears.

## Tools

| Tool | Source(s) | Input | Notes |
|---|---|---|---|
| `search_logs` | OpenSearch | `correlation_id` (required), `service`, `event`, `limit` | default limit 50, max 200 |
| `get_downstream_interactions` | PostgreSQL | `correlation_id` | never returns `request_payload`/`response_payload` |
| `get_transaction_timeline` | OpenSearch | `correlation_id` | no service/event filter; reports only checkpoints actually observed |
| `get_transaction_summary` | OpenSearch + PostgreSQL | `correlation_id` | reports `openSearchAvailable`/`postgresAvailable` independently |
| `get_recent_failures` | OpenSearch | `lookback_minutes`, `limit` | default 60 min / 20 results, max 1440 min / 100 results |
| `get_service_request` | PostgreSQL | `correlation_id` | cross-service read (see tradeoff below); excludes the long free-text `description` field |
| `get_service_runtime_status` | Docker (via docker-socket-proxy) | `service` | allowlisted services only; only `exists`/`running`/`state`/`health`/timestamps/`exitCode` - never env vars or mounts |
| `get_service_config_metadata` | static catalog (`catalog.py`) | `service` | zero I/O - never reads a real container's environment, so no credential can ever appear |
| `get_container_events` | Docker (via docker-socket-proxy) | `service`, `limit` | default 10, max 50; fixed 24h lookback window; bounded by Docker's own event buffer (see Phase 8 notes) |
| `get_dependency_health` | bare TCP probe | `service`, `dependency` | only documented `(service, dependency)` pairs in `catalog.py` are accepted; no protocol handshake, no credential needed |

### Phase 8: read-only runtime/dependency evidence

Four more tools answer "is this piece of TraceBridge's own infrastructure
actually up?" - a question the Phase 5 tools can't answer, since they only
know about application-level evidence (logs and rows), not runtime state.
Design choices worth knowing:

- **Docker access goes through `docker-socket-proxy`** (see
  `docker-compose.yml`), never a raw `docker.sock` mount into this
  process. That proxy enables GET-only access to a small category
  allowlist (containers, events, info, ping) with POST/PUT/DELETE disabled
  globally - so even a bug in `docker_repository.py` cannot reach a
  mutating Docker endpoint, because the proxy refuses the request before
  Docker ever sees it. `docker_repository.py` itself also simply has no
  start/stop/restart/kill/remove/exec method to call.
- **Every service/dependency name is checked against a static allowlist**
  (`catalog.py`) before any Docker call or network probe - an unknown name
  is rejected by `validation.py`, the same pattern `KNOWN_SERVICES` already
  used for `search_logs`. This is what stops `get_dependency_health` from
  becoming a generic network scanner.
- **`get_service_config_metadata` never performs I/O at all** - it returns
  a hand-written Python dict. This is a deliberate, stronger guarantee than
  "read the real environment and redact secrets": there is no code path
  that could ever leak one, because none is ever read.
- **`get_dependency_health` is a bare TCP connect**, nothing more - no
  protocol handshake, no auth, no query - so it never needs a credential
  for whatever it's checking.
- **Known limitation, found during live testing**: `get_container_events`
  depends on Docker's own bounded event buffer, not a stored history. In a
  busy local stack (frequent health-check `exec` events from Postgres/Kafka/
  OpenSearch), that buffer can roll over within a few minutes - so a
  lifecycle event from more than a few minutes ago may genuinely no longer
  be retrievable, even though it happened. `get_service_runtime_status` and
  `get_dependency_health` are unaffected, since both query live current
  state rather than a historical log.

### The `get_service_request` tradeoff

`service_request` is logically owned by `service-request-api`, and reading
it from an external tool crosses that ownership boundary. This is
acceptable here because `tracebridge-mcp` isn't a peer microservice inside
that boundary - it plays the same role a tracing/observability backend
plays in real systems: an external, read-only, cross-cutting investigator
that legitimately reads out of every service's store without being *part
of* any of them. The discipline that keeps this safe is the same one
enforced everywhere else in this server: strictly read-only, and a
deliberately narrow projection of columns (no long free-text field,
nothing from any other table).

## Running it

```bash
cd tracebridge-mcp
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"       # macOS/Linux: .venv/bin/python
cp .env.example .env      # edit if your local infra differs from docker-compose.yml defaults
```

Environment variables (see `.env.example` for the full list and defaults):
`OPENSEARCH_URL`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`. This server is never given ServiceNow
or Kafka credentials - it has no need for them and never calls either.

Run the server directly (mostly for a client to launch, not for a human to
watch - stdio has nothing interesting to look at):

```bash
.venv/Scripts/python -m tracebridge_mcp.server
```

## Manually testing every tool, with zero LLM involved

**Option A - the scripted client in this repo** (`manual_client.py`), which
launches the server as a real stdio subprocess exactly like any other MCP
client would:

```bash
# Runs every tool against the two real Phase 4 correlationIds (one success,
# one 401 failure) plus a couple of edge cases, printing raw JSON results.
PYTHONPATH=src .venv/Scripts/python manual_client.py demo

# Or call one tool directly:
PYTHONPATH=src .venv/Scripts/python manual_client.py call search_logs \
  '{"correlation_id": "51d3c01d-2b02-45b3-9df4-697ecd19a796"}'
```

**Option B - the official MCP Inspector** (needs Node.js):

```bash
npx @modelcontextprotocol/inspector .venv/Scripts/python -m tracebridge_mcp.server
```

This opens a local web UI listing all ten tools, lets you fill in
arguments and fire a call, and shows the raw JSON response - the standard
way to drive any MCP server by hand.

## Running as part of docker-compose - deliberately not done

`tracebridge-mcp` is **not** added to `docker-compose.yml`. It's an
on-demand investigation tool that an MCP client launches when needed, not
a long-running service anything else depends on. Not adding it to compose
makes that independence structural: TraceBridge's business processing
(the two Spring Boot services, Kafka, the log pipeline) is completely
unaffected by whether this server is running, has ever run, or is broken.

## Tests

```bash
.venv/Scripts/python -m pytest -v
```

113 tests: input validation, OpenSearch query construction (correct index
pattern, term filters not string queries, sort order), PostgreSQL query
parameterization and read-only enforcement, result normalization,
chronological ordering, partial-evidence / source-unavailable handling,
not-found vs. error distinction, the structural no-write-path guarantees
described above, and (Phase 8) the runtime/dependency allowlist, Docker
inspect/events sanitization, the TCP dependency probe, and a dedicated
scan across all four new tools' output for secret-shaped field names.
