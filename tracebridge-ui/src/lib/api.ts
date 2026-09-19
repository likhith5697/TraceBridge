import type { FinalResult, HistorySummary, LiveStep, StatusResponse } from "../types";

// The React app never talks to MCP, OpenSearch, PostgreSQL, or an LLM
// directly - this is the only module that makes network calls, and every
// call goes to the investigator API, nothing else.
export const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchStatus(): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE}/api/status`);
  if (!res.ok) throw new Error(`status check failed: ${res.status}`);
  return res.json();
}

export async function fetchHistory(): Promise<HistorySummary[]> {
  const res = await fetch(`${API_BASE}/api/investigations`);
  if (!res.ok) throw new Error(`history fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchInvestigationDetail(investigationId: string): Promise<FinalResult> {
  const res = await fetch(`${API_BASE}/api/investigations/${investigationId}`);
  if (!res.ok) throw new Error(`investigation fetch failed: ${res.status}`);
  return res.json();
}

interface StreamHandlers {
  onStep: (step: LiveStep) => void;
  onFinal: (result: FinalResult) => void;
  onError: (message: string, reason?: string) => void;
}

/** Opens a real SSE connection to the investigator's live stream. Every event
 * handled here is one the backend actually emitted from a real investigation
 * run - nothing here is simulated with setTimeout. */
export function streamInvestigation(correlationId: string, handlers: StreamHandlers): () => void {
  const url = `${API_BASE}/api/investigations/stream?correlation_id=${encodeURIComponent(correlationId)}`;
  const source = new EventSource(url);
  let closed = false;

  const close = () => {
    if (!closed) {
      closed = true;
      source.close();
    }
  };

  source.addEventListener("started", (event) => {
    handlers.onStep({ kind: "started", data: JSON.parse((event as MessageEvent).data) });
  });
  source.addEventListener("agent_decision", (event) => {
    handlers.onStep({ kind: "agent_decision", data: JSON.parse((event as MessageEvent).data) });
  });
  source.addEventListener("evidence", (event) => {
    handlers.onStep({ kind: "evidence", data: JSON.parse((event as MessageEvent).data) });
  });
  source.addEventListener("final", (event) => {
    handlers.onFinal(JSON.parse((event as MessageEvent).data));
    close();
  });
  source.addEventListener("error", (event) => {
    const messageEvent = event as MessageEvent;
    if (messageEvent.data) {
      try {
        const parsed = JSON.parse(messageEvent.data);
        handlers.onError(parsed.message ?? "Investigation failed", parsed.reason);
      } catch {
        handlers.onError("Investigation failed");
      }
    } else if (!closed) {
      handlers.onError("Lost connection to the investigator API");
    }
    close();
  });

  return close;
}
