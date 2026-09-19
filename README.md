# TraceBridge

TraceBridge takes one customer request and follows it across every service
it touches — then lets an AI agent explain what happened, using nothing but
the same evidence a human on-call engineer would have: logs, database rows,
and live infrastructure state.

## The problem it solves

A request comes in, gets written to a database, published to Kafka, and
picked up by two independent downstream consumers. When something breaks,
that trail is scattered across three services, two databases, and a log
pipeline. TraceBridge gives you one thing to hand over: a correlation ID.
Everything else — reconstructing the timeline, spotting the failure,
explaining it in plain language — is automated.

## Architecture

```
Client
  |
  v
service-request-api  --(Postgres)-->  request saved
  |
  v
Kafka  (one event, two independent consumers)
  |-----------------------------+
  v                             v
servicenow-consumer        customer-db-consumer
  |                             |
  v                             v
ServiceNow (external)      customer-postgres

All five services write structured JSON logs --> Fluent Bit --> OpenSearch

                    tracebridge-mcp (read-only tools)
                    reads: OpenSearch, Postgres, Docker
                              |
                              v
                    tracebridge-investigator (LLM agent)
                    given only a correlationId, decides
                    which tools to call, produces a report
                              |
                              v
                    React console (tracebridge-ui)
                    streams the investigation live
```

## Services

| Service | What it does | Port |
|---|---|---|
| `service-request-api` | Receives a request, saves it, publishes it to Kafka | `8080` |
| `servicenow-consumer` | Consumes the request, creates a ServiceNow incident | — (internal) |
| `customer-db-consumer` | Consumes the same request independently, saves a record to its own database | — (internal) |
| `postgres` / `customer-postgres` | Two separate databases — the second exists so it can be safely taken down to demo a real failure | `5432` / `5433` |
| `kafka` | Carries the one event both consumers subscribe to | `9094` |
| `opensearch` + `fluent-bit` | Every service's logs land here, searchable by correlation ID | `9200` |
| `docker-socket-proxy` | The only thing with real Docker access — read-only, GET-only | — (internal) |
| `tracebridge-mcp` | Not a container — a tool server the investigator launches on demand | — |
| `tracebridge-investigator-api` | The AI agent, exposed over HTTP/SSE | `8000` |
| `tracebridge-ui` | The web console you actually use | `3000` |

## Quick start

```bash
docker compose up -d --build
```

Open `http://localhost:3000`, submit a request through the API, then
investigate its correlation ID in the console:

```bash
curl -X POST http://localhost:8080/api/v1/service-requests \
  -H "Content-Type: application/json" \
  -d '{"source":"CUSTOMER_PORTAL","customerId":"c1","category":"billing",
       "subcategory":"invoice","shortDescription":"x","description":"x","priority":"P3"}'
```

To see the agent diagnose a real infrastructure failure, stop the second
database and submit another request:

```bash
docker compose stop customer-postgres
# submit another request, then investigate its correlationId
docker compose start customer-postgres   # restore when done
```

## The AI agent, in one paragraph

You give it a correlation ID — nothing else. It decides for itself which
questions to ask (are there logs for this? did the downstream call
succeed? is the dependency actually reachable right now? is that
container even running?) until it has enough evidence to explain what
happened. It never claims more than the evidence shows, and every claim
in its final report is tied back to a specific tool result.

## Reliability: no duplicate side effects on redelivery

Kafka only guarantees a message is delivered *at least* once, not exactly
once. Both consumers guard against this: each event carries a unique
`eventId`, and before doing any real work (calling ServiceNow, writing to
the database) they check whether that `eventId` has already been handled.
A database-level unique constraint backs this up as the real safety net.
Verified live: forcing a real Kafka redelivery produced zero duplicate
ServiceNow incidents and zero duplicate database rows. See
[`PIPELINE_MAP.md`](PIPELINE_MAP.md) for the full walkthrough.

## The tools it can call (`tracebridge-mcp`)

One MCP server, ten read-only tools — six read transaction evidence
(logs, database rows), four read live infrastructure state (Docker,
network reachability). Nothing here can write, restart, or execute
anything. Full details: [`tracebridge-mcp/README.md`](tracebridge-mcp/README.md).

## Where to look for more

| Topic | See |
|---|---|
| The MCP tool server, every tool's contract | `tracebridge-mcp/README.md` |
| The AI agent's reasoning loop, confidence rules, safety guarantees | `tracebridge-investigator/README.md` |
| ServiceNow integration details | `servicenow-consumer/` |
| The controlled-failure demo dependency | `customer-db-consumer/` |
| The web console | `tracebridge-ui/` |

## Configuration

Copy `tracebridge-investigator/.env.example` to `.env` and set an API key
(`OPENAI_API_KEY` by default, or switch `LLM_PROVIDER` to `anthropic`).
Everything else already matches `docker-compose.yml`'s defaults.
