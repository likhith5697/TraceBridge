# tracebridge-ui

A React console for `tracebridge-investigator`: enter a correlation ID, watch
the AI agent's investigation happen live (tool calls and evidence streamed
as they occur, not simulated), and see a structured final report.

## Architecture

```
React (this app)
        |  fetch / EventSource (SSE)
        v
tracebridge-investigator API  (FastAPI, port 8000)
        |
        v
AI Investigator  ->  MCP  ->  OpenSearch / PostgreSQL
```

This app never talks to MCP, OpenSearch, PostgreSQL, or an LLM directly -
`src/lib/api.ts` is the only module that makes network calls, and every one
of them goes to the investigator API.

## Stack

Vite + React + TypeScript + Tailwind CSS v4 + lucide-react. No router (a
single screen doesn't need one) and no state-management library (a handful
of hooks in `src/hooks/` cover it).

## Live investigation feed

Every step shown in the timeline (`Calling get_transaction_summary`,
`Evidence received`, ...) corresponds to a real Server-Sent Event the
backend emitted while the agent was actually running - see
`tracebridge-investigator/src/tracebridge_investigator/api.py`. Nothing is
faked with `setTimeout`. The frontend never sees the model's own text/
reasoning, only structured tool-call and evidence summaries, since the
backend deliberately strips that before emitting events.

## History

The "Recent investigations" panel reflects the investigator API's in-memory
history (capped, resets on API restart) - not a database. Clicking an entry
re-fetches that investigation's stored result from the API.

## Running locally

```bash
npm install
cp .env.example .env.local   # only needed if the API isn't at localhost:8000
npm run dev
```

Requires `tracebridge-investigator`'s API running (`uvicorn
tracebridge_investigator.api:app`), which in turn requires
`tracebridge-mcp` (spawned automatically as a subprocess) and the
PostgreSQL/OpenSearch/Kafka stack from the repo root's `docker-compose.yml`.

## Running via Docker

From the repo root:

```bash
docker compose up -d postgres kafka opensearch fluent-bit
docker compose up -d --build tracebridge-investigator-api tracebridge-ui
```

Then open `http://localhost:3000`. The UI container is a static build
served by nginx; `VITE_API_BASE_URL` is baked in at build time via a Docker
build arg (default `http://localhost:8000`, since it's your browser - not
another container - that calls the API).
